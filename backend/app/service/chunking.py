from llama_index.core.node_parser import SemanticSplitterNodeParser, SentenceSplitter
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.core import Document
from llama_index.core.schema import BaseNode, MetadataMode
from typing import List


MAX_CHUNK_TOKENS = 512


class Chunking_Strategy:
    def __init__(self,embed_model : AzureOpenAIEmbedding,buffer_size : int = 1 ,breakpoint_percentile_threshold : int = 95):
        self.buffer_size = buffer_size or 1
        self.breakpoint_percentile_threshold = breakpoint_percentile_threshold or 95
        self.embed_model = embed_model
        self.splitter = self.get_semantic_splitter()


    def get_semantic_splitter(self) -> SemanticSplitterNodeParser:

        semantic_splitter = SemanticSplitterNodeParser(
        buffer_size=self.buffer_size,
        breakpoint_percentile_threshold=self.breakpoint_percentile_threshold,
        embed_model=self.embed_model)

        return semantic_splitter


    STRUCTURAL_KEYS = ["file_name", "file_type", "file_size_kb", "upload_date", "uploaded_by"]


    _fallback_splitter = SentenceSplitter(chunk_size=MAX_CHUNK_TOKENS, chunk_overlap=20)

    def extract_nodes_from_docs(self, documents: List[Document]) -> List[BaseNode]:
        nodes = self.splitter.get_nodes_from_documents(documents=documents)

        safe_nodes: List[BaseNode] = []
        for node in nodes:
            if len(node.get_content()) > MAX_CHUNK_TOKENS * 4:
                oversized_doc = Document(text=node.get_content(), metadata=node.metadata)
                sub_nodes = self._fallback_splitter.get_nodes_from_documents([oversized_doc])
                safe_nodes.extend(sub_nodes)
            else:
                safe_nodes.append(node)

        for node in safe_nodes:
            node.excluded_embed_metadata_keys = self.STRUCTURAL_KEYS
            node.excluded_llm_metadata_keys = self.STRUCTURAL_KEYS

        return safe_nodes

