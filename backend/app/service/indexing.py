# indexing.py
from dataclasses import dataclass
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.postgres import PGVectorStore
from typing import Optional
from ..config.config import load_config
@dataclass
class DBConfig:
    user: str
    password: str
    host: str
    port: str
    name: str
    table_name: str
    embed_dim: int = 1536


_index: Optional[VectorStoreIndex] = None


def _patch_docstore_missing_node_bug(index: VectorStoreIndex) -> None:
    import types as _types

    ds = index.docstore

    def _get_nodes(self, node_ids, raise_error=True):
        nodes = []
        for nid in node_ids:
            node = self.get_node(nid, raise_error=raise_error)
            if node is not None:
                nodes.append(node)
        return nodes

    async def _aget_nodes(self, node_ids, raise_error=True):
        nodes = []
        for nid in node_ids:
            node = await self.aget_node(nid, raise_error=raise_error)
            if node is not None:
                nodes.append(node)
        return nodes

    ds.get_nodes = _types.MethodType(_get_nodes, ds)
    ds.aget_nodes = _types.MethodType(_aget_nodes, ds)


class Indexing:
    def __init__(self, embed_model):
        self.config = load_config()
        self.embed_model = embed_model

    def load_or_create_index(self) -> VectorStoreIndex:
        global _index

        if _index is not None:
            return _index

        c = self.config
        try:
            vector_store = PGVectorStore.from_params(
                database=self.config.get('db_name'),
                host=self.config.get('db_host'),
                password=self.config.get('db_password'),
                port=self.config.get('db_port'),
                user=self.config.get('db_user'),
                table_name=self.config.get('table_name', 'DOCS_MIND'),
                embed_dim=int(self.config.get('embed_dim', 3072)),
            )
        except Exception as e:
            raise ConnectionError(f"DB connection failed: {e}")

        if self._table_has_data(vector_store):
            _index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                embed_model=self.embed_model,
            )
        else:
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            _index = VectorStoreIndex(
                nodes=[],
                storage_context=storage_context,
                embed_model=self.embed_model,
            )

        _patch_docstore_missing_node_bug(_index)
        return _index

    @staticmethod
    def file_hash_exists(file_hash: str) -> bool:
        from sqlalchemy import create_engine, text
        try:
            cfg = load_config()
            engine = create_engine(cfg.get('database_url'))
            table = f"data_{cfg.get('table_name', 'DOCS_MIND')}".lower()
            with engine.connect() as conn:
                result = conn.execute(
                    text(f'SELECT 1 FROM "{table}" WHERE metadata_->>\'file_hash\' = :h LIMIT 1'),
                    {"h": file_hash},
                )
                return result.fetchone() is not None
        except Exception:
            return False

    @staticmethod
    def stored_embed_models() -> dict:
        from sqlalchemy import create_engine, text
        result = {"models": set(), "untagged": 0}
        try:
            cfg = load_config()
            engine = create_engine(cfg.get('database_url'))
            table = f"data_{cfg.get('table_name', 'DOCS_MIND')}".lower()
            with engine.connect() as conn:
                rows = conn.execute(text(
                    f'SELECT metadata_->>\'embed_model\' AS m, COUNT(*) '
                    f'FROM "{table}" GROUP BY m'
                )).fetchall()
            for model_name, count in rows:
                if model_name:
                    result["models"].add(model_name)
                else:
                    result["untagged"] = int(count)
        except Exception:
            pass
        return result

    @staticmethod
    def check_embed_model_compatibility(active_model: str) -> tuple:
        stored = Indexing.stored_embed_models()
        models, untagged = stored["models"], stored["untagged"]

        if not models and untagged == 0:
            return True, "" 
        foreign = models - {active_model}
        if not foreign and untagged == 0:
            return True, ""

        parts = []
        if foreign:
            parts.append(
                f"chunks embedded with {sorted(foreign)}"
            )
        if untagged:
            parts.append(
                f"{untagged} chunk(s) with no embed-model stamp "
                f"(indexed before this check existed, so their embedding "
                f"model is unknown)"
            )
        message = (
            f"Embedding model mismatch: the vector index contains "
            f"{' and '.join(parts)}, but the active embedding model is "
            f"'{active_model}'. Vectors from different embedding models are "
            f"not comparable, so retrieval would silently return irrelevant "
            f"chunks. Fix: clear the vector table and re-upload your "
            f"documents so everything is embedded with '{active_model}' "
            f"(or switch back to the original provider)."
        )
        return False, message

    @staticmethod
    def _table_has_data(vector_store: PGVectorStore) -> bool:
        from sqlalchemy import create_engine, text
        try:
            cfg = load_config()
            engine = create_engine(cfg.get('database_url'))
            table = f"data_{vector_store.table_name}".lower()
            with engine.connect() as conn:
                result = conn.execute(text(f'SELECT 1 FROM "{table}" LIMIT 1'))
                return result.fetchone() is not None
        except Exception:
            return False



