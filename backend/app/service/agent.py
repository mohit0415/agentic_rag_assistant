import os
from dotenv import load_dotenv
from llama_index.agent.openai import OpenAIAgent
from llama_index.core import Settings
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from ..service.tools import Tools
from ..config.config import load_config,logger
from llama_index.core import VectorStoreIndex

from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.agent.react.output_parser import ReActOutputParser
from llama_index.core.agent.react.types import (
    ActionReasoningStep,
    ResponseReasoningStep,
)


class LenientReActOutputParser(ReActOutputParser):

    MAX_IMPLICIT_REJECTIONS = 2

    def __init__(self, *args, valid_tools=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._implicit_rejections = 0
        self._tool_used_this_turn = False
        self._forced_question = None
        self._valid_tools = set(valid_tools or ())

    def set_forced_question(self, question):
        """Give the parser the raw user question so the forced-retrieval
        fallback can search on the real query instead of the model's draft."""
        self._forced_question = (question or "").strip() or None

    def set_valid_tools(self, names):
        """Register the real tool names so invented ones can be corrected."""
        self._valid_tools = set(names or ())

    def _forced_query_text(self, step=None):
        """Best retrieval query: the real user question, else the model's
        own action input, else a generic fallback."""
        forced = self._forced_question
        if not forced and step is not None:
            ai = step.action_input if isinstance(getattr(step, "action_input", None), dict) else {}
            forced = str(ai.get("input") or ai.get("query") or "").strip()
        return (forced or "the user's question")[:500]

    def parse(self, output: str, is_streaming: bool = False):
        try:
            step = super().parse(output, is_streaming=is_streaming)
        except ValueError:
            step = None  

        if isinstance(step, ActionReasoningStep):
            action = (step.action or "").strip()
            if not self._valid_tools or action in self._valid_tools:
                self._tool_used_this_turn = True
                self._implicit_rejections = 0
                return step
            logger.warning(
                f"Agent picked unknown tool {action!r}; rewriting to a "
                f"policy_documents retrieval to stay grounded."
            )
            self._tool_used_this_turn = True
            self._implicit_rejections = 0
            return ActionReasoningStep(
                thought=(step.thought or "").strip()
                or "(Corrected) Using policy_documents to retrieve grounded context.",
                action="policy_documents",
                action_input={"input": self._forced_query_text(step)},
            )
        if (
            not self._tool_used_this_turn
            and self._implicit_rejections < self.MAX_IMPLICIT_REJECTIONS
        ):
            self._implicit_rejections += 1
            raise ValueError(
                "You wrote an answer without taking any Action. That is "
                "not allowed — you MUST first retrieve information with "
                "a tool. Respond in EXACTLY this format:\n"
                "Thought: I need to search the uploaded documents.\n"
                "Action: policy_documents\n"
                'Action Input: {"input": "<the user\'s question>"}\n'
                "Never answer from your own knowledge."
            )

        if self._tool_used_this_turn:
            self._implicit_rejections = 0
            self._tool_used_this_turn = False
            if step is not None:
                return step
            text = output.split("Thought:", 1)[-1].strip() if "Thought:" in output else output.strip()
            return ResponseReasoningStep(
                thought="(Implicit) Model gave a final answer without the Answer: marker.",
                response=text,
                is_streaming=is_streaming,
            )
        self._implicit_rejections = 0
        self._tool_used_this_turn = True
        recovered = (
            step.response if isinstance(step, ResponseReasoningStep)
            else (output.split("Thought:", 1)[-1] if "Thought:" in output else output)
        ).strip()
        if recovered.lower().startswith("answer:"):
            recovered = recovered[len("answer:"):].strip()
        query_text = (self._forced_question or recovered)[:500] or "the user's question"
        return ActionReasoningStep(
            thought=(
                "(Forced) No tool was used after repeated attempts; retrieving "
                "from policy_documents before answering to stay grounded."
            ),
            action="policy_documents",
            action_input={"input": query_text},
        )


def get_app_state():
    from ..app import app_state
    return app_state


_agent_tools = None


async def get_agent(index: VectorStoreIndex, llm=None, embed_model=None) -> ReActAgent:

    global _agent_tools

    config = load_config()
    app_state = get_app_state()

    llm = llm or app_state.llm
    embed_model = embed_model or app_state.embeddings

    if llm is None:
        raise ValueError('LLM model is not instantiated')
    if embed_model is None:
        raise ValueError('embed model is not instantiated')

    Settings.llm = llm
    Settings.embed_model = embed_model

    use_gemini = bool(config.get('use_gemini'))

    if not use_gemini and _agent_tools is not None:
        agent_tools = _agent_tools
    else:
        tools = Tools(index=index, llm=llm, embed_model=embed_model)
        sql_tool = tools.get_sql_tool()
        vector_tool = tools.get_vector_tool()
        mcp_tools = await tools.get_mcp_tool()
        agent_tools = [vector_tool, sql_tool, *mcp_tools]
        if not use_gemini:
            _agent_tools = agent_tools

    valid_tool_names = {
        getattr(getattr(t, "metadata", None), "name", None) for t in agent_tools
    }
    valid_tool_names.discard(None)
    logger.info(f"Registered tool names for parser: {sorted(valid_tool_names)}")

    agent = ReActAgent(
        tools=agent_tools,
        verbose=True,
        llm=llm,
        output_parser=LenientReActOutputParser(valid_tools=valid_tool_names),
        system_prompt="""
        You are an intelligent Documents analytics assistant with access to a SQL database, a vector store of documents, and a PubMed/NCBI biomedical literature tool.

        TOOL NAMING (mandatory):
        - When you take an Action, the action name MUST be EXACTLY one of these registered tool names:
          policy_documents, clinical_reference_db, search_articles, get_article_metadata, get_full_text_article, find_related_articles.
        - NEVER write the literal word "tool" (or "tool name", "vector_tool", "sql_tool", "med_mcp_tool") as an Action — those are not real tools and the call will fail.

        TOOL SELECTION (decide which tool(s) to call before answering):
        - DEFAULT ROUTING: Definitions, classifications, indices, explanations, and any "what is / explain / tell me about" question go to policy_documents FIRST. Only reach for clinical_reference_db when the question explicitly targets one of its six tables (below). When unsure between the two, use policy_documents.
        - clinical_reference_db (SQL): Call this tool ONLY when the question clearly names or maps to a field in one of its SIX fixed tables — somatosensory_receptors (types, adaptation rate, stimulus, clinical significance), receptor_density (counts by body region/age), pain_signal_types (nerve fibers, conduction speed, pain quality), drug_interactions (drug pairs, severity, mechanism, management), lab_reference_ranges (normal value bands for specific laboratory assays such as hemoglobin, glucose, or creatinine, by demographic), and clinical_conditions (symptoms, diagnostics, treatment) — AND needs a precise value, count, comparison, filter, or lookup over those fields (e.g. "which drugs interact severely with warfarin", "normal hemoglobin range for adult females", "list rapidly-adapting mechanoreceptors"). This database does NOT contain general medical concepts, definitions, classifications, or indices. Do NOT call it for definitional / "what is" / "explain" / "tell me about" questions, and do NOT call it for concepts like BMI / body-mass classification, weight status, or diet and nutrition topics — those belong to policy_documents. Do NOT call it for external published research (use the PubMed/NCBI tools). If the question does not clearly name one of the six tables above, do not call this tool.
        - policy_documents (vector store): Use for ANY question whose answer could exist in an uploaded document — this includes definitions, classifications, indices (e.g. BMI/body-mass categories), recipes, diet advice, nutrition info, ingredients, health articles, procedures, descriptions, policies, guidelines, protocols, compliance requirements, safety standards, reports, manuals, research papers, contracts, or personal notes. If in doubt, always call this tool.
        - PubMed/NCBI literature tools (search_articles, get_article_metadata, get_full_text_article, find_related_articles, lookup_article_by_citation, ...): these are individual tools, there is NO single tool named "med_mcp_tool" — always call one of the tool names listed above (typically search_articles first). Use them ONLY for questions that require external, peer-reviewed biomedical or scientific literature — clinical studies, drug/treatment evidence, disease mechanisms, published guidelines, or any claim that should be verified against published research rather than the uploaded documents or clinical_reference_db. Do not use these tools for questions already answerable from policy_documents or clinical_reference_db.
        - If a question spans more than one domain (e.g. comparing structured values from clinical_reference_db to targets in the documents, or grounding a document's claim in published literature), call ALL the relevant tools and synthesize the answer using only what they return.
        - Always explain your reasoning when choosing a tool.

        LITERATURE TOOL LIMITS (mandatory — keeps responses within output limits):
        - When calling search_articles, ALWAYS set max_results to 5 or fewer.
        - When calling get_article_metadata, pass AT MOST 5 PMIDs.
        - Call get_full_text_article for AT MOST 1 article per question, and only when the abstract/metadata is not enough — it returns an entire paper.
        - Keep your Thought lines short (1-2 sentences). Summarize literature findings concisely — titles, key finding, PMID — never article-by-article essays.
        - When calling find_related_articles, ALWAYS set max_results to AT MOST 3.

        GROUNDING RULE (highest priority — no hallucination):
        - You MUST NEVER answer a question without calling at least one tool first. Your FIRST step for EVERY question MUST be an Action (normally policy_documents). Writing a final answer in your very first Thought — with zero Actions taken this turn — is FORBIDDEN and will be rejected, even if you are certain you know the answer from general knowledge.
        - This applies especially to questions that sound like general knowledge (e.g. "what are the components of a RAG architecture"). The user is asking about THEIR uploaded documents, not about the world — retrieve first, then answer only from what came back.
        - You MUST answer ONLY using information returned by the tools in THIS conversation turn. Every claim in your answer must be traceable to a tool result.
        - NEVER use your own training knowledge, general knowledge, or assumptions to fill gaps — not even partially. If a tool returns partial information, answer only the part it covers and say the rest is not available.
        - Retrieved chunks are only "relevant" if they actually address the user's question. If policy_documents returns chunks about unrelated topics, treat that as NO relevant information — do not force an answer out of them.
        - If policy_documents returns no relevant information, respond with:
          "I don't know — the uploaded documents don't contain information about [topic]."
        - If clinical_reference_db returns no rows or raises an error, relay its exact error/message — do not invent a result.
        - If the PubMed/NCBI literature tools return no relevant results, respond with:
          "I don't know — I couldn't find published literature on [topic]."
        - If a PubMed/NCBI literature tool raises an error (e.g. connection failure), relay the exact error message, the same way you do for clinical_reference_db.
        - If none of the tools return usable information, respond with:
          "I don't know — I couldn't find this in the uploaded documents, the clinical database, or the literature."
        - Saying "I don't know" is ALWAYS the correct behavior when tools come back empty. A wrong or guessed answer is a failure; an honest "I don't know" is not.

        Guidelines:
        - Be concise but comprehensive in your responses.

        Citation Instructions (MANDATORY and NON-NEGOTIABLE when using policy_documents):
        - The policy_documents tool returns its answer with inline citation markers such as [1], [2], [3] attached to the sentences they support.
        - When you write your final Answer, you MUST carry those [n] markers through verbatim — keep each marker right after the claim it supports. Do NOT rephrase them, renumber them, move them to the end, or drop them.
        - Every sentence in your final answer that came from a policy_documents chunk MUST end with its [n] marker. An answer built from policy_documents that contains ZERO [n] markers is INVALID — recheck the tool output and re-attach the markers before answering.
        - Example — tool observation: "Breakfast should be light [1]. Dinner is roti and dal [2]." Your final Answer MUST read: "Breakfast should be light [1]. Dinner is roti and dal [2]." (markers preserved), never "Breakfast should be light. Dinner is roti and dal." (markers dropped — not allowed).
        - These markers are how the UI links each claim to its source, so preserving them is as important as the answer text itself.

        Important Instructions:
        - Compare metrics only when both values come from the tools.
        - Protect patient privacy.
        - Provide actionable insights only when grounded in tool output.
        """
    )

    return agent




