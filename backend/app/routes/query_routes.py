import os
import re
import json
import asyncio
import logging
import tempfile
import datetime
from pathlib import Path
from typing import List, Optional, Dict,Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from ..service.indexing import Indexing
from ..service.agent import get_agent
from ..service.llms import build_models_from_claims, get_active_embed_model_name
from ..config.config import logger
from ..auth.security import get_current_claims
from ..core.limiter import limiter, RATE_LIMIT_QUERY
from ..service.guard import validatior_guard
from ..service.guard.validatior_guard import GuardrailsValidator, get_guardrails_validator
from llama_index.core.agent.workflow import AgentOutput, AgentStream, ToolCall, ToolCallResult
from ..langfuse.langfuse_client import get_langfuse_client
from ..service.llms import build_evaluator_from_claims
from ragas.metrics.collections import Faithfulness, AnswerRelevancy
from ..service.handoff import (
    generate_handoff_reference_id,
    evaluate_handoff_trigger,
    send_handoff_email,
)


router = APIRouter()

AGENT_RUN_TIMEOUT_SECONDS = int(os.getenv("AGENT_RUN_TIMEOUT_SECONDS", "300"))

GUARDED_TOOLS = {"clinical_reference_db", "policy_documents"}

KNOWN_TOOLS = {
    "policy_documents",
    "clinical_reference_db",
    "search_articles",
    "get_article_metadata",
    "get_full_text_article",
    "find_related_articles",
}


ANSWER_MARKER = "Answer:"

FAITHFULNESS_MIN = float(os.getenv("FAITHFULNESS_MIN", "0.3"))

_NO_RESULT_MARKERS = (
    "no articles found",
    "no results",
    "no matching",
    "0 articles",
    "no relevant",
    "not found",
    "no data",
    "no records",
    "i don't know",
    "i do not know",
)


GUARD_FLUSH_MAX_HOLD = 200
_SENTENCE_BOUNDARIES = (". ", ".\n", "! ", "!\n", "? ", "?\n", "\n")


def _split_flushable(pending: str) -> tuple:
    last = -1
    for b in _SENTENCE_BOUNDARIES:
        idx = pending.rfind(b)
        if idx != -1:
            last = max(last, idx + len(b))
    if last != -1:
        return pending[:last], pending[last:]
    if len(pending) >= GUARD_FLUSH_MAX_HOLD:
        ws = pending.rfind(" ")
        if ws > 0:
            return pending[: ws + 1], pending[ws + 1:]
        return pending, ""
    return "", pending


def _sanitize_segment(guard: "GuardrailsValidator", segment: str) -> str:
    try:
        _, clean, pii = guard.validate_output(text=segment, check_pii=True)
        if pii:
            logger.warning(f"PII redacted from live stream segment: {pii}")
        return clean
    except Exception as e:  
        logger.error(f"Live-stream PII sanitization failed, dropping segment: {e}")
        return ""


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def get_app_state():
    from ..app import app_state
    return app_state

class QueryRequest(BaseModel):
    question: str = Field(..., description="The question to ask the Reports,Policies,or any topic analytics agent", min_length=1)
    user_email: Optional[str] = Field(
        default=None,
        description="Optional user e-mail for human-handoff follow-up",
    )

    @field_validator('question')
    def validate_ques(cls,v:str):
        if len(v) < 5:
            raise ValueError('The Question asked should be of min length: 5')
        return v

    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Is our Cardiology readmission rate meeting the 2025 target?"
            }
        }


class TableAttachment(BaseModel):
    index: int
    source: Optional[str] = None
    markdown: str
    summary: Optional[str] = None


class ImageAttachment(BaseModel):
    index: int
    source: Optional[str] = None
    url: str
    caption: Optional[str] = None


class QueryResult(BaseModel):
    question: str
    answer: str
    tools_used: Optional[List[str]] = None
    sources_used: Optional[str] = None
    faithfulness_score: Optional[float] = None
    relevance_score: Optional[float] = None
    tables: Optional[List[TableAttachment]] = None
    images: Optional[List[ImageAttachment]] = None
    handoff_triggered: Optional[bool] = None
    handoff_reference_id: Optional[str] = None
    handoff_reason: Optional[str] = None
    handoff_priority: Optional[str] = None


@router.post("/query")
@limiter.limit(RATE_LIMIT_QUERY)
async def query_agent(request: Request,
    response: Response,
    payload: QueryRequest,
    claims: Dict[str, Any] = Depends(get_current_claims),
):
    async def event_stream():
        try:
            yield _sse("step", {"id": "received", "label": "Query received", "status": "done"})

            _gate = get_guardrails_validator()
            _ok, _msg = _gate.validate_query_intent(payload.question)
            if not _ok:
                logger.warning(
                    f"Blocked write-intent question at input: {_msg} | "
                    f"question={payload.question!r}"
                )
                yield _sse("error", {"detail": _msg})
                yield _sse("done", {"ok": False})
                return

            llm, embed_model = build_models_from_claims(claims)
            active_embed_name = get_active_embed_model_name()
            compatible, mismatch_msg = Indexing.check_embed_model_compatibility(active_embed_name)
            if not compatible:
                logger.error(f"Embed-model mismatch, refusing query: {mismatch_msg}")
                yield _sse("step", {"id": "embed-check", "label": "Embedding model mismatch", "status": "done"})
                yield _sse("error", {"detail": mismatch_msg})
                yield _sse("done", {"ok": False})
                return
            yield _sse("step", {"id": "embed-check", "label": f"Embeddings verified ({active_embed_name})", "status": "done"})

            index_obj = Indexing(embed_model=embed_model)
            index = index_obj.load_or_create_index()
            try:
                index._embed_model = embed_model
            except Exception:
                pass
            logger.info(f'The Index Has been loaded..')
            yield _sse("step", {"id": "index", "label": "Vector index loaded", "status": "done"})

            agent = await get_agent(index=index, llm=llm, embed_model=embed_model)
            logger.info(f'The Agent has been instantiated successfully.')
            yield _sse("step", {"id": "agent", "label": "Agent instantiated", "status": "done"})

            yield _sse("step", {"id": "retrieve", "label": "Selecting tools & retrieving", "status": "active"})

            try:
                op = getattr(agent, "output_parser", None)
                if op is not None and hasattr(op, "set_forced_question"):
                    op.set_forced_question(payload.question)
            except Exception as _e:
                logger.debug(f"Could not set forced question on parser: {_e}")

            handler = agent.run(user_msg=payload.question, max_iterations=40)
            guard = get_guardrails_validator()
            guard_applies = False         
            guard_pending = ""           
            answer_started = False        
            step_buffer = ""              
            streamed_live = False         

            tool_call_results: List[ToolCallResult] = []
            try:
                async with asyncio.timeout(AGENT_RUN_TIMEOUT_SECONDS):
                    async for ev in handler.stream_events():
                        if isinstance(ev, AgentStream):
                            delta = ev.delta or ""
                            if not delta:
                                continue
                            if not answer_started:
                                step_buffer += delta
                                idx = step_buffer.find(ANSWER_MARKER)
                                if idx == -1:
                                    continue
                                answer_started = True
                                yield _sse("step", {"id": "generate", "label": "LLM generating answer", "status": "active"})
                        elif isinstance(ev, ToolCall):
                            step_buffer = ""
                            answer_started = False
                            if ev.tool_name in GUARDED_TOOLS:
                                guard_applies = True
                            logger.info(f"Agent calling tool: {ev.tool_name} | kwargs={ev.tool_kwargs}")
                            if ev.tool_name not in KNOWN_TOOLS:
                                logger.warning(f"Agent requested unknown tool {ev.tool_name!r} — hidden from pipeline UI")
                            else:
                                yield _sse("step", {"id": f"tool-{ev.tool_name}", "label": f"Calling tool: {ev.tool_name}", "status": "active"})
                        elif isinstance(ev, ToolCallResult):
                            tool_call_results.append(ev)
                            is_error = getattr(ev.tool_output, 'is_error', False)
                            logger.info(
                                f"Tool {ev.tool_name} returned (is_error={is_error}): "
                                f"{str(getattr(ev.tool_output, 'content', ''))[:300]}"
                            )
                            if ev.tool_name in KNOWN_TOOLS:
                                yield _sse("step", {"id": f"tool-{ev.tool_name}", "label": f"Tool finished: {ev.tool_name}", "status": "done"})
                        elif isinstance(ev, AgentOutput):
                            step_buffer = ""
                            answer_started = False
                            selected = [tc.tool_name for tc in (ev.tool_calls or [])]
                            logger.info(f"Agent step done. Tools selected: {selected or 'none (final answer or unparsed output)'}")
                            if not selected:
                                raw = (ev.response.content or "") if ev.response else ""
                                logger.info(f"LLM raw output head: {raw[:200]!r}")
                                logger.info(f"LLM raw output tail: {raw[-200:]!r}")

                    result = await handler 

                    if guard_pending:
                        clean = await asyncio.to_thread(_sanitize_segment, guard, guard_pending)
                        guard_pending = ""
                        if clean:
                            yield _sse("token", {"text": clean})
            except TimeoutError:
                logger.error(
                    f"Agent run exceeded {AGENT_RUN_TIMEOUT_SECONDS}s. "
                    f"Tools called so far: {[t.tool_name for t in tool_call_results]}"
                )
                try:
                    await handler.cancel_run()
                except Exception:
                    pass
                yield _sse("error", {"detail": f"Agent run timed out after {AGENT_RUN_TIMEOUT_SECONDS}s. Check backend logs for the last tool/LLM step."})
                yield _sse("done", {"ok": False})
                return

            raw_answer = result.response.content if result.response else str(result)

            guard_block_reason = _extract_sql_guard_block(tool_call_results)
            if guard_block_reason:
                logger.warning(f"SQL guardrail blocked this turn: {guard_block_reason}")
                yield _sse("step", {"id": "guard", "label": "Blocked by SQL guardrail", "status": "done"})
                yield _sse("error", {"detail": guard_block_reason})
                yield _sse("done", {"ok": False})
                return

            _, answer, pii_summaries = guard.validate_output(
                text=raw_answer,
                check_pii=True
            )
            if pii_summaries:
                logger.warning(f"PII redacted from query response: {pii_summaries}")

            retrieved_contexts: List[str] = _gather_grounding_contexts(tool_call_results)

            if not tool_call_results or not retrieved_contexts:
                logger.warning(
                    f"Ungrounded answer gated (tools={len(tool_call_results)}, "
                    f"contexts={len(retrieved_contexts)}). Head: {str(answer)[:150]!r}"
                )
                answer = (
                    "I couldn't ground an answer in your uploaded documents, the "
                    "clinical database, or the biomedical literature for this "
                    "question. I only answer from retrieved sources — try "
                    "rephrasing to reference your document content."
                )

            yield _sse("step", {"id": "generate", "label": "LLM generating answer", "status": "active"})
            if not streamed_live:
                for i in range(0, len(answer), 20):
                    yield _sse("token", {"text": answer[i:i + 20]})
                    await asyncio.sleep(0.01)

            faithfulness_score: Optional[float] = None
            relevance_score: Optional[float] = None
            yield _sse("step", {"id": "evaluate", "label": "Evaluating answer quality", "status": "active"})
            try:
                evaluator_llm, evaluator_embeddings = build_evaluator_from_claims(claims)
                if retrieved_contexts:
                    result_faith = await Faithfulness(llm=evaluator_llm).ascore(
                        user_input=payload.question,
                        response=answer,
                        retrieved_contexts=retrieved_contexts,
                    )
                    faithfulness_score = round(float(result_faith.value), 3)

                result_relevance = await AnswerRelevancy(
                    llm=evaluator_llm,
                    embeddings=evaluator_embeddings,
                ).ascore(
                    user_input=payload.question,
                    response=answer,
                )
                relevance_score = round(float(result_relevance.value), 3)

                logger.info(
                    f"Ragas scores | faithfulness={faithfulness_score} "
                    f"relevancy={relevance_score} "
                    f"(contexts={len(retrieved_contexts)})"
                )
            except Exception as ragas_err:
                logger.error(f"Ragas evaluation failed: {ragas_err}", exc_info=True)
            yield _sse("step", {"id": "evaluate", "label": "Answer quality evaluated", "status": "done"})

            list_of_tools_used: List[str] = _extract_tools_used(tool_call_results)
            sources_used: Optional[str] = _extract_sources_used(tool_call_results)
            tables_used, images_used = _extract_attachments(tool_call_results, answer=answer)

            yield _sse("step", {"id": "citations", "label": "Citations mapped", "status": "done"})

            handoff_trace_id: Optional[str] = None
            try:
                langfuse_client = get_langfuse_client()
                if langfuse_client is not None:
                    span = langfuse_client.start_span(
                        name="api_query",
                        input={"question": payload.question},
                        metadata={
                            "endpoint": "/query",
                            "source": "fastapi",
                        },
                    )
                    trace_id = span.trace_id
                    handoff_trace_id = trace_id

                    span.update(
                        output={
                            "trace_id": trace_id,
                            "answer": answer,
                        }
                    )
                    span.end()
                    langfuse_client.flush()
            except Exception as eval_err:
                logger.error(
                    f"[Eval] Error during automatic evaluation: {eval_err}",
                    exc_info=True,
                )
            answer = _ensure_citation_markers(answer, sources_used)

            handoff_triggered = False
            handoff_reference_id: Optional[str] = None
            handoff_reason: Optional[str] = None
            handoff_priority: Optional[str] = None
            try:
                decision = evaluate_handoff_trigger(
                    faithfulness=faithfulness_score,
                    relevance=relevance_score,
                    user_question=payload.question,
                    no_context=not retrieved_contexts,
                )
                if decision.get("trigger"):
                    handoff_triggered = True
                    handoff_reason = decision.get("reason")
                    handoff_priority = decision.get("priority", "normal")
                    handoff_reference_id = generate_handoff_reference_id()

                    handoff_context = {
                        "reference_id": handoff_reference_id,
                        "trace_id": handoff_trace_id,
                        "timestamp": datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat(),
                        "priority": handoff_priority,
                        "trigger_reason": handoff_reason,
                        "user_metadata": {
                            "user_email": payload.user_email,
                            "user": claims.get("sub"),
                        },
                        "query_history": [payload.question],
                        "tools_used": list_of_tools_used,
                        "generated_answer": answer,
                        "evaluation_scores": {
                            "faithfulness": faithfulness_score,
                            "relevance": relevance_score,
                        },
                        "retrieved_chunks": retrieved_contexts,
                    }
                    asyncio.create_task(
                        asyncio.to_thread(send_handoff_email, handoff_context)
                    )
                    logger.info(
                        f"Human handoff triggered (ref={handoff_reference_id}, "
                        f"priority={handoff_priority}, reason={handoff_reason})"
                    )
                    yield _sse("handoff", {
                        "reference_id": handoff_reference_id,
                        "reason": handoff_reason,
                        "priority": handoff_priority,
                        "message": (
                            "This question has been escalated to a human support "
                            f"agent. Your reference ID is {handoff_reference_id}."
                            + (f" We'll follow up at {payload.user_email}."
                               if payload.user_email else "")
                        ),
                    })
            except Exception as ho_err:
                logger.error(f"Handoff evaluation failed: {ho_err}", exc_info=True)

            queryResult = QueryResult(
                question=payload.question,
                tools_used=list_of_tools_used,
                answer=answer,
                sources_used=sources_used,
                faithfulness_score=faithfulness_score,
                relevance_score=relevance_score,
                tables=[TableAttachment(**t) for t in tables_used] or None,
                images=[ImageAttachment(**i) for i in images_used] or None,
                handoff_triggered=handoff_triggered,
                handoff_reference_id=handoff_reference_id,
                handoff_reason=handoff_reason,
                handoff_priority=handoff_priority,
            )
            yield _sse("meta", queryResult.model_dump())

            yield _sse("step", {"id": "delivered", "label": "Response delivered", "status": "done"})
            yield _sse("done", {"ok": True})

        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            yield _sse("error", {"detail": f"Error processing query: {str(e)}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  
        },
    )
    



    

def _extract_sql_guard_block(tool_call_results: List["ToolCallResult"]) -> Optional[str]:
    if not tool_call_results:
        return None

    for tcr in tool_call_results:
        tool_name = getattr(tcr, 'tool_name', None)
        tool_output = getattr(tcr, 'tool_output', None)
        is_error = getattr(tool_output, 'is_error', False)
        if tool_name == 'clinical_reference_db' and is_error:
            content = getattr(tool_output, 'content', None) or ""
            if "Query blocked" in content:
                return content

    return None


IMAGES_STORAGE_DIR = Path(os.getenv("IMAGES_STORAGE_DIR", "stored_images")).resolve()


def _node_image_path(node_obj, metadata: dict) -> Optional[str]:
    path = metadata.get('image_path')
    if not path:
        path = getattr(node_obj, 'image_path', None)
    if not path and metadata.get('content_type') == 'image_caption':
        path = metadata.get('file_path') or metadata.get('path')
    return path or None


def _cited_indices(answer: Optional[str]) -> set:
    if not answer:
        return set()
    return {int(m) for m in _CITATION_MARKER_RE.findall(answer)}


ATTACHMENT_SCORE_RATIO = float(os.getenv("ATTACHMENT_SCORE_RATIO", "0.6"))


def _is_relevant_attachment(
    idx: int, node, cited: set, max_score: float
) -> bool:
    node_obj = getattr(node, 'node', node)
    meta = getattr(node_obj, 'metadata', {}) or {}
    is_image = bool(_node_image_path(node_obj, meta))

    if cited and not is_image:
        return idx in cited
    score = getattr(node, 'score', None)
    if score is None or max_score <= 0 or ATTACHMENT_SCORE_RATIO <= 0:
        return True  # can't judge → don't hide
    return score >= ATTACHMENT_SCORE_RATIO * max_score


def _extract_attachments(
    tool_call_results: List["ToolCallResult"],
    answer: Optional[str] = None,
) -> tuple:
    tables: List[dict] = []
    images: List[dict] = []
    seen_tables: set = set()
    seen_images: set = set()

    cited = _cited_indices(answer)

    for tcr in (tool_call_results or []):
        tool_output = getattr(tcr, 'tool_output', None)
        raw_output = getattr(tool_output, 'raw_output', None)
        source_nodes = getattr(raw_output, 'source_nodes', None)
        if not source_nodes:
            continue
        try:
            max_score = max(
                (getattr(n, 'score', None) or 0.0) for n in source_nodes
            )
        except ValueError:
            max_score = 0.0
        try:
            summary_dbg = [
                (
                    type(getattr(n, 'node', n)).__name__,
                    (getattr(getattr(n, 'node', n), 'metadata', {}) or {}).get('content_type'),
                )
                for n in source_nodes
            ]
            logger.info(
                f"[attachments] tool={getattr(tcr, 'tool_name', '?')} "
                f"nodes={len(source_nodes)} types/content_types={summary_dbg}"
            )
        except Exception:
            pass

        for idx, node in enumerate(source_nodes, start=1):
            node_obj = getattr(node, 'node', node)
            metadata = getattr(node_obj, 'metadata', {}) or {}
            content_type = metadata.get('content_type')
            source_name = (
                metadata.get('original_file_name')
                or metadata.get('source')
                or metadata.get('file_name')
            )

            if not _is_relevant_attachment(idx, node, cited, max_score):
                continue

            original_table = metadata.get('original_table')
            is_table = content_type == 'table_summary' or bool(original_table)
            image_path = _node_image_path(node_obj, metadata)

            if is_table and original_table:
                key = original_table.strip()
                if key in seen_tables:
                    continue
                seen_tables.add(key)
                try:
                    summary = node_obj.get_content()
                except Exception:
                    summary = None
                tables.append({
                    "index": idx,
                    "source": source_name,
                    "markdown": original_table,
                    "summary": summary,
                })

            elif image_path:
                filename = os.path.basename(image_path)
                if filename in seen_images:
                    continue
                seen_images.add(filename)
                try:
                    caption = node_obj.get_content()
                except Exception:
                    caption = None
                images.append({
                    "index": idx,
                    "source": source_name,
                    "url": f"/api/images/{filename}",
                    "caption": caption,
                })

    return tables, images


@router.get("/images/{filename}")
async def get_image(filename: str):
    from fastapi.responses import FileResponse

    safe_name = os.path.basename(filename)
    file_path = (IMAGES_STORAGE_DIR / safe_name).resolve()

    if os.path.commonpath([str(IMAGES_STORAGE_DIR), str(file_path)]) != str(IMAGES_STORAGE_DIR):
        raise HTTPException(status_code=400, detail="Invalid image path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(str(file_path))


def _gather_grounding_contexts(tool_call_results: List["ToolCallResult"]) -> List[str]:
    contexts: List[str] = []
    for tcr in (tool_call_results or []):
        tool_output = getattr(tcr, 'tool_output', None)
        if tool_output is None or getattr(tool_output, 'is_error', False):
            continue
        raw_output = getattr(tool_output, 'raw_output', None)
        source_nodes = getattr(raw_output, 'source_nodes', None)
        if source_nodes:
            for node in source_nodes:
                node_obj = getattr(node, 'node', node)
                contexts.append(node_obj.get_content())
            continue
        content = getattr(tool_output, 'content', None)
        if not content:
            continue
        text = str(content).strip()
        if len(text) < 40:
            continue
        low = text.lower()
        if any(marker in low for marker in _NO_RESULT_MARKERS):
            continue
        contexts.append(text)
    return contexts


def _extract_tools_used(tool_call_results: List["ToolCallResult"]) -> List[str]:

    list_of_tools = []

    for tcr in (tool_call_results or []):
        tool_name = getattr(tcr, 'tool_name', None)
        if tool_name in KNOWN_TOOLS and tool_name not in list_of_tools:
            list_of_tools.append(tool_name)

    return list_of_tools



_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


def _ensure_citation_markers(answer: Optional[str], sources_used: Optional[str]) -> Optional[str]:
    if answer and sources_used and not _CITATION_MARKER_RE.search(answer):
        logger.warning(
            "Document-grounded answer has no inline [n] citation markers — the "
            "agent dropped the per-chunk markers CitationQueryEngine produced. "
            "Source chips still show; inline citations do not."
        )
    return answer


def _extract_sources_used(tool_call_results: List["ToolCallResult"]) -> Optional[str]:
    citation_lines = []

    for tcr in (tool_call_results or []):
        tool_output = getattr(tcr, 'tool_output', None)
        raw_output = getattr(tool_output, 'raw_output', None)
        source_nodes = getattr(raw_output, 'source_nodes', None)
        if source_nodes:
            for idx, node in enumerate(source_nodes, start=1):
                node_obj = getattr(node, 'node', node)
                metadata = getattr(node_obj, 'metadata', {}) or {}
                original_file_name = metadata.get('original_file_name')
                if original_file_name:
                    citation_lines.append(f"[{idx}] {original_file_name}")

    return '\n'.join(citation_lines) if citation_lines else None


