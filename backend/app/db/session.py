"""
SQLAlchemy 2.0 async engine and session factory.
Supports SQLite (dev via aiosqlite) and PostgreSQL (prod via asyncpg).
The ORM code is identical — only DB_URL changes between environments.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# SQLite needs connect_args to allow cross-thread use in FastAPI workers.
_connect_args = {"check_same_thread": False} if "sqlite" in settings.db_url else {}

engine = create_async_engine(
    settings.db_url,
    echo=settings.is_development,      # Log SQL in dev
    future=True,
    connect_args=_connect_args,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Base class for ORM models
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Read-only engine (used by LLM-generated SQL — SELECT only)
# This prevents any accidental INSERT/UPDATE/DELETE from agent-generated SQL.
# ---------------------------------------------------------------------------
_ro_url = settings.db_url
if "sqlite" in _ro_url:
    _ro_url = _ro_url + "?mode=ro" if "?" not in _ro_url else _ro_url + "&mode=ro"

readonly_engine = create_async_engine(
    _ro_url,
    echo=False,
    future=True,
    connect_args={**_connect_args, **({"uri": True} if "sqlite" in _ro_url else {})},
)


# ---------------------------------------------------------------------------
# FastAPI dependency — yields an async session
# ---------------------------------------------------------------------------
async def get_db() -> AsyncSession:  # type: ignore[override]
    async with AsyncSessionLocal() as session:
        yield session
