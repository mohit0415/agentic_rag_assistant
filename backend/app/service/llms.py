
from typing import Any, Dict, Optional, Tuple

from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding

from ..config.config import load_config, logger
from .rate_limit import get_gemini_http_clients


EMBED_DIM = 3072

_OPENAI_LIKE_INSTALL_HINT = (
    "Gemini mode needs the OpenAI-compatible wrappers. Install them in the "
    "backend env:\n  uv add llama-index-llms-openai-like "
    "llama-index-embeddings-openai-like\n(or: pip install "
    "llama-index-llms-openai-like llama-index-embeddings-openai-like)"
)


def _gemini_clients(config: Dict[str, Any], gemini_api_key: str):
    return get_gemini_http_clients(
        gemini_api_key,
        llm_rpm=int(config.get('gemini_llm_rpm', 5)),
        embed_rpm=int(config.get('gemini_embed_rpm', 90)),
        max_attempts=int(config.get('gemini_retry_max_attempts', 5)),
        timeout_seconds=float(config.get('gemini_http_timeout', 120)),
        fallback_models=config.get('gemini_fallback_models', []),
    )



def initialize_llm(
    config: Optional[Dict[str, Any]] = None,*,gemini_api_key: Optional[str] = None):
    config = config or load_config()
    try:
        if config.get('use_gemini'):
            gemini_api_key = gemini_api_key or config.get('gemini_api_key')
            if not gemini_api_key:
                raise ValueError(
                    "USE_GEMINI is enabled but GEMINI_API_KEY is not set. "
                    "Add GEMINI_API_KEY=AIza... to the backend .env file."
                )
            try:
                from llama_index.llms.openai_like import OpenAILike
            except ImportError as ie:
                raise ImportError(_OPENAI_LIKE_INSTALL_HINT) from ie
  
            http_client, async_http_client = _gemini_clients(config, gemini_api_key)
            llm = OpenAILike(
                model=config.get('gemini_llm_model', 'gemini-2.5-flash'),
                api_key=gemini_api_key,
                api_base=config.get('gemini_openai_base'),
                http_client=http_client,
                async_http_client=async_http_client,
                max_retries=0,
                temperature=0.1,
                max_tokens=4000,
                is_chat_model=True,
                is_function_calling_model=True,
                context_window=1_000_000,
            )
        else:
            llm = AzureOpenAI(
                model=config.get('azure_llm_deployment'),
                deployment_name=config.get('azure_llm_deployment'),
                api_key=config.get('azure_api_key'),
                azure_endpoint=config.get('azure_endpoint'),
                api_version=config.get('api_version'),
                temperature=0.1,
                max_retries=5,
                max_completion_tokens=4000,
            )

        if llm is None:
            raise ValueError('The llm is not initialized.')
        return llm
    except ValueError as e:
        logger.error(f'Error initializing LLM: {e}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error initializing LLM: {e}')
        raise



def initialize_embeddings(
    config: Optional[Dict[str, Any]] = None,
    *,
    gemini_api_key: Optional[str] = None,
):
    config = config or load_config()
    embed_dim = int(config.get('embed_dim', EMBED_DIM))
    try:
        if config.get('use_gemini'):
            gemini_api_key = gemini_api_key or config.get('gemini_api_key')
            if not gemini_api_key:
                raise ValueError(
                    "USE_GEMINI is enabled but GEMINI_API_KEY is not set. "
                    "Add GEMINI_API_KEY=AIza... to the backend .env file."
                )
            try:
                from llama_index.embeddings.openai_like import OpenAILikeEmbedding
            except ImportError as ie:
                raise ImportError(_OPENAI_LIKE_INSTALL_HINT) from ie
            embedding_model = OpenAILikeEmbedding(
                model_name=config.get('gemini_embed_model', 'gemini-embedding-2-preview'),
                api_key=gemini_api_key,
                api_base=config.get('gemini_openai_base'),
                http_client=http_client,
                async_http_client=async_http_client,
                max_retries=0,  # 429 recovery lives in the transport
                dimensions=embed_dim,
                embed_batch_size=10,
            )
        else:
            embedding_model = AzureOpenAIEmbedding(
                model=config.get('azure_embedding_deployment'),
                deployment_name=config.get('azure_embedding_deployment'),
                api_key=config.get('azure_api_key'),
                azure_endpoint=config.get('azure_endpoint'),
                api_version=config.get('api_version'),
                dimensions=embed_dim,
            )

        if embedding_model is None:
            raise ValueError('The Embed Model is not initialized.')

        logger.info(f'Embedding model initialized ({embed_dim}-dim)')
        return embedding_model
    except ValueError as e:
        logger.error(f'Error initializing embedding model: {e}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error initializing embedding model: {e}')
        raise



def build_models_from_claims(
    claims: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, Any]:
    config = config or load_config()
    claims = claims or {}
    if config.get('use_gemini'):
        llm = initialize_llm(config)
        embed = initialize_embeddings(config)
        return llm, embed

    try:
        from ..app import app_state
        if app_state.llm is not None and app_state.embeddings is not None:
            return app_state.llm, app_state.embeddings
    except Exception:
        pass
    return initialize_llm(config), initialize_embeddings(config)

_azure_evaluator_cache: Optional[Tuple[Any, Any]] = None
_gemini_evaluator_cache: Dict[str, Tuple[Any, Any]] = {}


def build_evaluator_from_claims(
    claims: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, Any]:
    global _azure_evaluator_cache
    config = config or load_config()
    claims = claims or {}

    from openai import AsyncOpenAI, AsyncAzureOpenAI
    from ragas.llms import llm_factory
    from ragas.embeddings.base import embedding_factory

    if config.get('use_gemini'):
        gemini_api_key = config.get('gemini_api_key')
        if not gemini_api_key:
            raise ValueError(
                "USE_GEMINI is enabled but GEMINI_API_KEY is not set in the "
                "environment — cannot build the ragas evaluator."
            )
        cached = _gemini_evaluator_cache.get(gemini_api_key)
        if cached is not None:
            return cached
        _sync_client, async_http_client = _gemini_clients(config, gemini_api_key)
        client = AsyncOpenAI(
            api_key=gemini_api_key,
            base_url=config.get('gemini_openai_base'),
            http_client=async_http_client,
            max_retries=0,  
        )
        evaluator_llm = llm_factory(
            config.get('gemini_eval_llm_model', 'gemini-2.5-flash-lite'),
            client=client,
        )
        evaluator_embeddings = embedding_factory(
            "openai",
            model=config.get('gemini_embed_model', 'gemini-embedding-2-preview'),
            client=client,
        )
        if len(_gemini_evaluator_cache) > 32:
            _gemini_evaluator_cache.clear()
        _gemini_evaluator_cache[gemini_api_key] = (evaluator_llm, evaluator_embeddings)
        logger.info("Ragas evaluator initialized (gemini)")
        return evaluator_llm, evaluator_embeddings

    if _azure_evaluator_cache is not None:
        return _azure_evaluator_cache

    client = AsyncAzureOpenAI(
        api_key=config.get('azure_api_key'),
        azure_endpoint=config.get('azure_endpoint'),
        api_version=config.get('api_version'),
    )
    evaluator_llm = llm_factory(
        config.get('azure_llm_deployment'),
        client=client,
    )
    evaluator_embeddings = embedding_factory(
        "openai",
        model=config.get('azure_embedding_deployment'),
        client=client,
    )
    _azure_evaluator_cache = (evaluator_llm, evaluator_embeddings)
    logger.info("Ragas evaluator initialized (azure)")
    return evaluator_llm, evaluator_embeddings


def get_active_embed_model_name(config: Optional[Dict[str, Any]] = None) -> str:
    config = config or load_config()
    if config.get('use_gemini'):
        return config.get('gemini_embed_model', 'gemini-embedding-2-preview')
    return config.get('azure_embedding_deployment') or 'azure-embedding'


def get_active_model_names(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or load_config()
    if config.get('use_gemini'):
        return {
            "provider": "gemini",
            "llm_model": config.get('gemini_llm_model', 'gemini-2.5-flash'),
            "embed_model": config.get('gemini_embed_model', 'gemini-embedding-2-preview'),
            "embed_dim": int(config.get('embed_dim', EMBED_DIM)),
        }
    return {
        "provider": "azure",
        "llm_model": config.get('azure_llm_deployment'),
        "embed_model": config.get('azure_embedding_deployment'),
        "embed_dim": int(config.get('embed_dim', EMBED_DIM)),
    }
