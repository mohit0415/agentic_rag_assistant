import os
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional

from ..config.config import logger,load_config
from llama_index.core.settings import Settings
from llama_index.core import VectorStoreIndex
from llama_index.core.tools import QueryEngineTool, FunctionTool
from ..service.structured_data_db import get_sql_database
from ..service.guard.validatior_guard import GuardrailsValidator, get_guardrails_validator
from llama_index.core.query_engine import NLSQLTableQueryEngine, CitationQueryEngine
from llama_index.core.retrievers import VectorIndexAutoRetriever, QueryFusionRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.vector_stores.types import MetadataInfo, VectorStoreInfo
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
from ..service.mcp.mcp_tools import PubMedService



def get_app_state():
    from ..app import app_state
    return app_state


class Tools:
    def __init__(self, index: VectorStoreIndex, llm=None, embed_model=None):
        self.config = load_config()
        self.index = index
        app_state = get_app_state()
        self.llm = llm or app_state.llm
        self.embed_model = embed_model or app_state.embeddings
        self.sql_db_connection = get_sql_database()

    def get_vector_tool(self):

        logger.info("Creating vector tool...")

        Settings.embed_model = self.embed_model

        table_name = self.config.get('table_name')
        logger.info(f"Loading vector index from table: {table_name}")
        
        if self.index is None:
            error_msg = f"No policy document embeddings found in table {table_name}. Please upload and ingest documents before querying."
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        vector_store_info = VectorStoreInfo(
            content_info=(
                "A collection of uploaded documents including policies, rules, research papers, "
                "guidelines, protocols, compliance requirements, safety standards, and reports."
            ),
            metadata_info=[
                MetadataInfo(
                    name="topic",
                    type="str",
                    description="Short 1-3 word general subject of the document, e.g. 'patient safety', 'capacity management'",
                ),
                MetadataInfo(
                    name="doc_category",
                    type="str",
                    description=(
                        "Category of the document. "
                        "One of: report, manual, article, contract, research_paper, personal_notes, other"
                    ),
                ),
                MetadataInfo(
                    name="keywords",
                    type="list[str]",
                    description="3-5 specific keywords extracted from the document content",
                ),
                MetadataInfo(
                    name="file_name",
                    type="str",
                    description="Original file name of the uploaded document",
                ),
                MetadataInfo(
                    name="uploaded_by",
                    type="str",
                    description="Name of the user who uploaded the document",
                ),
                MetadataInfo(
                    name="source_type",
                    type="str",
                    description=(
                        "Origin of the content. One of: textbook, "
                        "anatomy_physiology_textbook, clinical_database, "
                        "research_paper, pubmed_article, other"
                    ),
                ),
                MetadataInfo(
                    name="content_type",
                    type="str",
                    description=(
                        "Node modality flavour. One of: text, table_summary, "
                        "image_caption"
                    ),
                ),
                MetadataInfo(
                    name="modality",
                    type="str",
                    description="Content modality. One of: text, table, diagram",
                ),
                MetadataInfo(
                    name="medical_specialty",
                    type="str",
                    description=(
                        "Medical subject. One of: anatomy, physiology, pathology, "
                        "pharmacology, neuroscience, clinical_medicine, "
                        "general_medicine, other"
                    ),
                ),
                MetadataInfo(
                    name="anatomical_system",
                    type="str",
                    description=(
                        "Body system the content covers, e.g. somatosensory_system, "
                        "nervous_system, cardiovascular_system, not_applicable"
                    ),
                ),
                MetadataInfo(
                    name="content_domain",
                    type="str",
                    description=(
                        "conceptual (explanatory prose), clinical_fact "
                        "(deterministic facts like lab ranges / drug interactions), "
                        "or mixed"
                    ),
                ),
                MetadataInfo(
                    name="intended_route",
                    type="str",
                    description="Suggested retrieval route: rag, sql, or hybrid",
                ),
            ],
        )

        top_k = int(os.getenv("RETRIEVAL_TOP_K", "15"))
        rerank_top_n = int(os.getenv("RERANK_TOP_N", "5"))

        plain_retriever = self.index.as_retriever(similarity_top_k=top_k)

        from llama_index.core.retrievers import BaseRetriever

        _use_auto = os.getenv("USE_AUTO_RETRIEVER", "false").strip().lower() in (
            "1", "true", "yes", "on"
        )
        if _use_auto:
            auto_retriever = VectorIndexAutoRetriever(
                index=self.index,
                vector_store_info=vector_store_info,
                similarity_top_k=top_k,
                llm=self.llm,
            )

            class _AutoWithFallbackRetriever(BaseRetriever):

                def _retrieve(self, query_bundle):
                    try:
                        nodes = auto_retriever.retrieve(query_bundle)
                    except Exception as e:
                        logger.warning(
                            f"Auto-retriever failed ({e}); using plain vector retrieval"
                        )
                        nodes = []
                    if not nodes:
                        logger.warning(
                            "Auto-retriever returned 0 nodes — falling back to "
                            "plain vector retrieval"
                        )
                        nodes = plain_retriever.retrieve(query_bundle)
                    return nodes

            vector_retriever = _AutoWithFallbackRetriever()
            logger.info("policy_documents: VectorIndexAutoRetriever ON (metadata inference)")
        else:
            vector_retriever = plain_retriever
            logger.info("policy_documents: plain semantic retrieval (no metadata filters)")

        retriever = vector_retriever
        try:
            available_nodes = list(self.index.docstore.docs.values())
        except Exception as e:
            logger.warning(f"Could not read nodes from docstore for BM25: {e}")
            available_nodes = []

        if available_nodes:
            bm25_top_k = min(top_k, len(available_nodes))
            bm25_retriever = BM25Retriever.from_defaults(
                nodes=available_nodes,
                similarity_top_k=bm25_top_k,
            )

            retriever = QueryFusionRetriever(
                retrievers=[vector_retriever, bm25_retriever],
                similarity_top_k=top_k,
                num_queries=1,
                mode="reciprocal_rerank",
                use_async=False,
            )
            logger.info(f"BM25 fusion enabled with {len(available_nodes)} nodes")
        else:
            logger.warning(
                "No nodes found in docstore; policy_documents tool is falling "
                "back to vector-only retrieval (BM25 skipped)."
            )

        node_postprocessors = []
        try:
            from llama_index.core.postprocessor import SentenceTransformerRerank
            reranker = SentenceTransformerRerank(
                model=os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
                top_n=rerank_top_n,
            )
            node_postprocessors.append(reranker)
            logger.info(
                f"Cross-encoder reranker enabled (retrieve {top_k} -> rerank {rerank_top_n})"
            )
        except Exception as e:
            logger.info(
                f"Reranker not active ({type(e).__name__}: {e}); using wide "
                f"retrieval only (top_k={top_k}). Install sentence-transformers "
                f"to enable relevance reranking."
            )

        query_engine = CitationQueryEngine(
            retriever=retriever,
            llm=self.llm,
            citation_chunk_size=512,
            node_postprocessors=node_postprocessors,
        )

        vector_tool = QueryEngineTool.from_defaults(
            query_engine=query_engine,
            name="policy_documents",
            description=(
                "A semantic search tool over ALL uploaded documents. "
                "Use this tool for ANY question whose answer might exist in an uploaded document — "
                "regardless of the document type. This includes recipes, diet guides, nutrition info, "
                "health articles, policies, research papers, manuals, reports, guidelines, contracts, "
                "personal notes, or any other text content. "
                "When a user asks about a topic, ingredient, procedure, rule, concept, or description "
                "of any kind, always check this tool first. "
                "Do NOT skip this tool just because the question sounds informal or non-technical."
            )
        )

        return vector_tool


    def get_sql_tool(self):

        logger.info("Creating SQL tool...")

        sql_query_engine = NLSQLTableQueryEngine(
            sql_database=self.sql_db_connection,
            llm=self.llm,
            verbose=True
        )

        guard = get_guardrails_validator()

        def guarded_sql_query(query: str) -> str:
            is_valid, error_message = guard.validate_query_intent(query)
            if not is_valid:
                logger.warning(f"Blocked clinical_reference_db tool call (regex): {error_message} | query={query!r}")
                raise ValueError(error_message)

            is_valid, error_message = guard.validate_sql_intent_with_llm(self.llm, query)
            if not is_valid:
                logger.warning(f"Blocked clinical_reference_db tool call (LLM classifier): {error_message} | query={query!r}")
                raise ValueError(error_message)

            response = sql_query_engine.query(query)
            return str(response)

        sql_query_tool = FunctionTool.from_defaults(
            fn=guarded_sql_query,
            name="clinical_reference_db",
            description=(
                "Structured clinical reference database (SQL). It contains ONLY "
                "these six fixed tables and nothing else: "
                "somatosensory_receptors (receptor types, adaptation rate, "
                "stimulus, clinical significance), receptor_density (receptor "
                "counts by body region/age), pain_signal_types (nerve fibers, "
                "conduction speed, pain quality), drug_interactions (drug pairs, "
                "severity, mechanism, management), lab_reference_ranges (normal "
                "value bands for specific laboratory assays such as hemoglobin, "
                "glucose, or creatinine, by demographic), and clinical_conditions "
                "(conditions, symptoms, diagnostics, treatment). "
                "Call this tool ONLY when the question clearly names or maps to a "
                "field in one of those six tables and needs a precise lookup, "
                "count, comparison, or filter — e.g. 'which drugs interact "
                "severely with warfarin', 'normal hemoglobin range for adult "
                "females', 'list rapidly-adapting mechanoreceptors'. "
                "This database does NOT contain general medical concepts, "
                "definitions, classifications, or indices. Do NOT use it for "
                "'what is / explain / tell me about' questions, or for concepts "
                "like BMI / body-mass classification, weight status, or diet and "
                "nutrition guidance — those are not in this database; use "
                "policy_documents instead. Never use this tool for "
                "narrative/explanatory content from uploaded documents or "
                "published literature."
            )
        )

        return sql_query_tool
    
    @staticmethod
    def _clamp_mcp_tool(tool, max_chars: int = 6000):
        from llama_index.core.tools import FunctionTool as _FunctionTool

        async def clamped(**kwargs):
            result = await tool.acall(**kwargs)
            raw = getattr(result, "raw_output", None)
            contents = getattr(raw, "content", None) if raw is not None else None
            if contents:
                text = "\n".join(
                    getattr(c, "text", "") or "" for c in contents
                )
            else:
                text = str(getattr(result, "content", result))
            if len(text) > max_chars:
                text = text[:max_chars] + f"\n... [output truncated at {max_chars} chars — narrow your query instead of re-fetching]"
            return text

        return _FunctionTool.from_defaults(
            async_fn=clamped,
            tool_metadata=tool.metadata,
        )

    async def get_mcp_tool(self):
        try:
            pubMedTool = PubMedService()
            med_tools = await pubMedTool.load_tools(
                allowed_tools=[
                    "search_articles",
                    "get_article_metadata",
                    "get_full_text_article",
                    "find_related_articles",
                ]
            )
            med_tools = [self._clamp_mcp_tool(t) for t in med_tools]
            return med_tools
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}", exc_info=True)
            raise ConnectionError(
                f"PubMed MCP tools could not be loaded: {type(e).__name__}: {e}"
            ) from e

