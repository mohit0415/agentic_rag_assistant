from fastapi import FastAPI
from .routes import query_routes, ingestion_routes, auth_routes
import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .core.limiter import limiter
from .config.config import setup_logging,logger,load_config


from .service.indexing import Indexing,DBConfig
from .service.llms import initialize_llm,initialize_embeddings
from .langfuse.langfuse_client import init_langfuse, shutdown_langfuse
from .service.guard.validatior_guard import get_guardrails_validator


class AppState:
    config: Optional[Dict[str, Any]] = None
    embeddings: Optional[Any] = None
    llm: Optional[Any] = None
    vectorstore: Optional[Any] = None
    rag_chain: Optional[Any] = None
    retriever: Optional[Any] = None
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_chunks_retrieved: int = 0
    start_time: datetime = datetime.now()



app_state = AppState()

indexing: Indexing = None

class ErrorResponse(BaseModel):
    error: str = Field(description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    timestamp: str = Field(description="Error timestamp")

setup_logging()


async def initialize_components():
    logger.info("="*80)
    logger.info("Starting RAG API component initialization")
    logger.info("="*80)
    try:
        global indexing
        logger.info("Step 0: Initializing Guardrails validator (fail fast)")
        get_guardrails_validator()
        logger.info("Guardrails validator ready (DetectPII / Presidio loaded)")

        logger.info("Step 1: Loading configuration")
        app_state.config = load_config()

        logger.info("Step 1a: Running one-time SQL schema bootstrap")
        from .service.sql_bootstrap import run_sql_bootstrap
        run_sql_bootstrap()

        logger.info("Step 1b: Initializing Langfuse tracing")
        init_langfuse()

        if app_state.config.get('use_gemini'):
            logger.info(
                "USE_GEMINI is enabled — LLM, embeddings and index are built "
                "per-request using GEMINI_API_KEY from the environment."
            )
            logger.info("=" * 80)
            logger.info("Startup complete (Gemini per-request mode)")
            logger.info("=" * 80)
            return

        logger.info(f"Configuration loaded: {app_state.config['azure_llm_deployment']}")

        logger.info("Step 2: Initializing embedding model")
        app_state.embeddings = initialize_embeddings(app_state.config)

        logger.info("Step 3: Initializing LLM")
        app_state.llm = initialize_llm(app_state.config)

        logger.info("Step 4: Setting up vectorstore")
        indexing = Indexing(embed_model=app_state.embeddings)
        index = indexing.load_or_create_index()
        logger.info("="*80)
        logger.info("All components initialized successfully")
        logger.info("="*80)
   
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}", exc_info=True)
        raise

async def shutdown_components():
    logger.info("="*80)
    logger.info("Shutting down RAG pipeline...")
    logger.info("="*80)
    shutdown_langfuse() 


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting AutoMind RAG API...")
    await initialize_components()
    app_state.start_time = datetime.now()
    
    yield
    await shutdown_components()

app = FastAPI(
    title="Documents Analytics Platform API",
    description="An intelligent agentic RAG system that combines hospital operational database queries with policy document search",
    version="1.0.0",
    lifespan=lifespan
)
cors_origins_env = os.getenv('CORS_ORIGINS', '*')
if cors_origins_env == '*':
    cors_origins = ['*']
else:
    cors_origins = [origin.strip().rstrip('/') for origin in cors_origins_env.split(',') if origin.strip()]

logger.info(f"CORS allowed origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "Retry-After",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    ],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=f"{type(exc).__name__}: {str(exc)}",
            timestamp=datetime.now().isoformat()
        ).model_dump()
    )




@app.get("/health")
def health():
    try:
        from guardrails.hub import DetectPII  
        get_guardrails_validator()
        return {"status": "ok", "guardrails": "ready"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "detail": f"guardrails: {e}"},
        )


@app.get("/")
def root():
    return {
        "message": "Documents Analytics Platform API",
        "docs": "/docs",
        "endpoints": {
            "login": "/api/login",
            "query": "/api/query",
            "upload_documents": "/api/upload",
        }
    }




app.include_router(auth_routes.router, prefix="/api", tags=["Auth"])
app.include_router(query_routes.router, prefix="/api", tags=["Query_Pipeline"])
app.include_router(ingestion_routes.router, prefix="/api", tags=["Ingestion_Pipeline"])













