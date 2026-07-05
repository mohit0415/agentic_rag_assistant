from llama_index.core.schema import BaseNode
from llama_index.core import VectorStoreIndex
from typing import List
from ..config.config import logger



class NodeInsertionError(Exception):
    pass

class VectorDB:
    def __init__(self,nodes : List[BaseNode],current_index : VectorStoreIndex):
        self.nodes = nodes
        self.index = current_index

    def insert_nodes_index(self) -> dict:
        indexing = self.index

        try:
            indexing.insert_nodes(self.nodes)
            inserted_count = len(self.nodes)
        except NodeInsertionError:
            raise
        except Exception as e:
            short_msg = f"Node insertion failed: {type(e).__name__}: {str(e)[:200]}"
            raise NodeInsertionError(short_msg) from e

        logger.info("Successfully inserted %d/%d nodes into index", inserted_count, len(self.nodes))
        return {"message": f"Successfully indexed to the number of nodes: {len(self.nodes)}"}




