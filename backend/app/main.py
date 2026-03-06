"""
FastAPI application factory.
Startup: initialise DB tables, configure LangSmith env vars.
"""

import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import engine, Base
from app.routers import credit_router, documents_router, fraud_router, sentiment_router, speech_router, unified_router

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Propagate secrets into os.environ so OpenAI SDK and LangChain can read them.
# pydantic-settings loads from .env but third-party libs read os.environ directly.
# ---------------------------------------------------------------------------
if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
os.environ["OPENAI_MODEL"] = settings.openai_model
# LangSmith disabled — using MLflow for tracing and observability
os.environ["LANGSMITH_TRACING"] = "false"


# ---------------------------------------------------------------------------
# Lifespan — runs at startup and shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup:
    1. Create DB tables if they don't exist (idempotent — run seed_db.py for data)
    2. Pre-import agents so their graphs compile at startup (not first request)
    """
    log.info("startup", environment=settings.environment, db_url=settings.db_url)

    # Create tables (does not drop existing data)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Warm up agent graphs (compile LangGraph graphs at startup)
    log.info("compiling_agent_graphs")
    from app.agents import credit_sql_graph, fraud_sql_graph, sentiment_graph, speech_graph  # noqa: F401
    log.info("agent_graphs_ready")

    yield  # Application runs here

    # Graceful shutdown
    log.info("shutdown")
    await engine.dispose()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title="Nedbank AI Demo — Text-to-SQL & Agent Platform",
        description=(
            "Multi-agent LLM platform showcasing Text-to-SQL on credit & fraud data, "
            "social sentiment analysis, and speech-to-text CX insights. "
            "Powered by GPT-4o + LangGraph."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — allow Streamlit frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(credit_router)
    app.include_router(documents_router)
    app.include_router(fraud_router)
    app.include_router(sentiment_router)
    app.include_router(speech_router)
    app.include_router(unified_router)

    # Health check
    @app.get("/health", tags=["System"])
    async def health():
        return {
            "status": "ok",
            "environment": settings.environment,
            "model": settings.openai_model,
            "version": "0.1.0",
        }

    @app.get("/", tags=["System"])
    async def root():
        return {"message": "Nedbank AI Demo API", "docs": "/docs"}

    return app


app = create_app()
