"""Text processing module using SemanticSplitterNodeParser."""

from typing import List
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.core.schema import TextNode, BaseNode
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from ...service.chunking import Chunking_Strategy


class TextProcessor:
    
    def __init__(self, embed_model: AzureOpenAIEmbedding):
        self.embed_model = embed_model
    
    def process(self, text: str, metadata: dict = None) -> List[TextNode]:

        if not text or not text.strip():
            return []
        
        from llama_index.core.schema import Document
        doc = Document(text=text, metadata=metadata or {})
        
      
        chunk_obj = Chunking_Strategy(embed_model=self.embed_model)
        nodes = chunk_obj.extract_nodes_from_docs(documents=[doc])
        
        for node in nodes:
            node.metadata = node.metadata or {}
            node.metadata["content_type"] = "text"
            if metadata:
                node.metadata.update(metadata)
            node.metadata.setdefault("modality", "text")
            node.metadata.setdefault("level", "node")

        return nodes

