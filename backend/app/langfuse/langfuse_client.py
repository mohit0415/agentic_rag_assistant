import os
from typing import Optional

from dotenv import load_dotenv
from langfuse import Langfuse
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

from ..config.config import logger

_client: Optional[Langfuse] = None


def init_langfuse() -> Optional[Langfuse]:

    global _client
    if _client is not None:
        return _client


    load_dotenv()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    host = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    if not secret_key or not public_key:
        logger.warning("Langfuse credentials not found - tracing disabled")
        logger.warning("Set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY to enable")
        return None

    _client = Langfuse(
        secret_key=secret_key,
        public_key=public_key,
        host=host,
    )
    logger.info(f"Langfuse client initialized (host={host})")

    LlamaIndexInstrumentor().instrument()
    logger.info("✓ OpenInference LlamaIndex instrumentation enabled - all "
                "LlamaIndex/agent operations will be traced in Langfuse")
    return _client


def get_langfuse_client() -> Optional[Langfuse]:
    return _client


def shutdown_langfuse() -> None:
    if _client is not None:
        _client.flush()
