
import os
import re
import logging
import sys
from typing import Dict, Any
from dotenv import load_dotenv


_APP_LOG_NAME = os.getenv("APP_LOG_NAME", "agentic-rag")


def _system_log_dir() -> "os.PathLike | str":
    from pathlib import Path

    override = os.getenv("LOG_DIR")
    if override:
        return Path(override)
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Logs" / _APP_LOG_NAME
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", home / "AppData" / "Local"))
        return base / _APP_LOG_NAME / "Logs"
    xdg_state = Path(os.getenv("XDG_STATE_HOME", home / ".local" / "state"))
    return xdg_state / _APP_LOG_NAME / "log"


def setup_logging(level: int = logging.INFO):
    handlers = [logging.StreamHandler(sys.stdout)]

    _true = {"1", "true", "yes", "on", "y", "t"}
    if os.getenv("LOG_TO_FILE", "true").strip().lower() in _true:
        try:
            from logging.handlers import RotatingFileHandler
            from pathlib import Path

            log_dir = Path(_system_log_dir())
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_dir / "backend.log",
                maxBytes=int(float(os.getenv("LOG_FILE_MAX_MB", "5")) * 1024 * 1024),
                backupCount=int(os.getenv("LOG_FILE_BACKUPS", "3")),
                encoding="utf-8",
            )
            handlers.append(file_handler)
        except Exception as e:  
            print(f"[logging] file handler disabled ({e}); using stdout only", file=sys.stderr)

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True
    )

    _file_targets = [getattr(h, 'baseFilename', None) for h in handlers if isinstance(h, logging.FileHandler)]
    if _file_targets:
        logging.getLogger(__name__).info(f"File logging active: {_file_targets[0]}")
    
    
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)



setup_logging()
logger = logging.getLogger(__name__)



_TRUE = {"1", "true", "yes", "on", "y", "t"}


def use_gemini() -> bool:
    return os.getenv("USE_GEMINI", "false").strip().lower() in _TRUE


def load_config() -> Dict[str, Any]:
    logger.debug("Loading configuration from environment variables")
    load_dotenv()
    logger.debug(".env loaded (if present)")

    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    
    if not all([db_user, db_password, db_host, db_port, db_name]):
        missing = [k for k, v in {
            'DB_USER': db_user,
            'DB_PASSWORD': db_password,
            'DB_HOST': db_host,
            'DB_PORT': db_port,
            'DB_NAME': db_name
        }.items() if not v]
        logger.error(f"Missing required database configuration: {', '.join(missing)}")
        raise ValueError(f"Missing required database configuration: {', '.join(missing)}")
    
    database_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    config = {
        'db_user':db_user,
        'db_password':db_password,
        'embed_dim':os.getenv('EMBED_DIM','3072'),
        'db_host':db_host,
        'db_port':db_port,
        'db_name':db_name,
        'database_url': database_url,
        'azure_endpoint': os.getenv('AZURE_OPENAI_ENDPOINT'),
        'azure_api_key': os.getenv('AZURE_OPENAI_API_KEY'),
        'azure_embedding_deployment': os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT'),
        'azure_llm_deployment': os.getenv('AZURE_OPENAI_LLM_DEPLOYMENT'),
        'azure_llm_model': os.getenv('AZURE_OPENAI_LLM_MODEL', 'gpt-4o'),
        'azure_embedding_model': os.getenv('AZURE_OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large'),
        'api_version': os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-01'),
        'table_name': os.getenv('TABLE_NAME', 'smart_auto_advisor'),
        'top_k': int(os.getenv('TOP_K', '5')),
        'chunk_size': int(os.getenv('CHUNK_SIZE', '1000')),
        'chunk_overlap': int(os.getenv('CHUNK_OVERLAP', '200')),
        'cors_origins': os.getenv('CORS_ORIGINS', '*').split(',') if os.getenv('CORS_ORIGINS') else ['*'],

        'use_gemini': use_gemini(),
        'gemini_api_key': os.getenv('GEMINI_API_KEY'),
        'gemini_llm_model': os.getenv('GEMINI_LLM_MODEL', 'gemini-2.5-flash'),
        'gemini_embed_model': os.getenv('GEMINI_EMBED_MODEL', 'gemini-embedding-2-preview'),
        'gemini_openai_base': os.getenv(
            'GEMINI_OPENAI_BASE',
            'https://generativelanguage.googleapis.com/v1beta/openai/',
        ),
        'gemini_fallback_models': [
            m.strip() for m in os.getenv(
                'GEMINI_FALLBACK_MODELS',
                'gemini-2.5-flash-lite,gemini-2.5-flash,'
                'gemini-2.0-flash,gemini-2.0-flash-lite',
            ).split(',') if m.strip()
        ],
        'gemini_llm_rpm': int(os.getenv('GEMINI_LLM_RPM', '5')),
        'gemini_embed_rpm': int(os.getenv('GEMINI_EMBED_RPM', '90')),
        'gemini_retry_max_attempts': int(os.getenv('GEMINI_RETRY_MAX_ATTEMPTS', '5')),
        'gemini_http_timeout': float(os.getenv('GEMINI_HTTP_TIMEOUT', '120')),
    }

  
    try:
        config['embed_dim'] = int(config['embed_dim'])
    except (TypeError, ValueError):
        config['embed_dim'] = 3072

    active_embed = (
        config['gemini_embed_model'] if config['use_gemini']
        else (config['azure_embedding_deployment'] or 'azure_embedding')
    )
    _suffix = re.sub(r'[^a-z0-9]+', '_', str(active_embed).lower()).strip('_')
    config['base_table_name'] = config['table_name']
    config['table_name'] = f"{config['table_name']}_{_suffix}"


    if config['use_gemini']:
        if not config['gemini_api_key']:
            logger.error("Missing GEMINI_API_KEY")
            raise ValueError(
                "USE_GEMINI is enabled but GEMINI_API_KEY was not found in the "
                "environment (.env). Create a key at https://aistudio.google.com/apikey "
                "and add: GEMINI_API_KEY=AIza..."
            )

    if not config['use_gemini']:
        if not config['azure_api_key']:
            logger.error("Missing AZURE_OPENAI_API_KEY")
            raise ValueError("AZURE_OPENAI_API_KEY not found in environment variables")
        if not config['azure_endpoint']:
            logger.error("Missing AZURE_OPENAI_ENDPOINT")
            raise ValueError("AZURE_OPENAI_ENDPOINT not found in environment variables")
        if not config['azure_llm_deployment']:
            logger.error("Missing AZURE_OPENAI_LLM_DEPLOYMENT")
            raise ValueError("AZURE_OPENAI_LLM_DEPLOYMENT not found in environment variables")
        if not config['azure_embedding_deployment']:
            logger.error("Missing AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
            raise ValueError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT not found in environment variables")

    if config['top_k'] < 1 or config['top_k'] > 50:
        logger.warning(f"top_k={config['top_k']} is outside recommended range (1-50), using default")
        config['top_k'] = 5
    if config['chunk_size'] < 100:
        logger.warning(f"chunk_size={config['chunk_size']} is too small, using minimum 100")
        config['chunk_size'] = 100
    
    logger.info("Configuration loaded")
    logger.info(f"Provider: {'GEMINI (OpenAI-compatible)' if config['use_gemini'] else 'AZURE OPENAI'}")
    logger.debug(f"Embedding dim: {config['embed_dim']}")
    logger.debug(f"Embedding deployment: {config['azure_embedding_deployment']}")
    logger.debug(f"LLM deployment: {config['azure_llm_deployment']}")
    logger.debug(f"Endpoint: {config['azure_endpoint']}")
    logger.debug(f"Collection: {config['table_name']}")
    logger.debug(f"Top-K: {config['top_k']}")
    logger.debug(f"Chunking: size={config['chunk_size']}, overlap={config['chunk_overlap']}")
    
    return config


