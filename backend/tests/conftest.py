"""
Pytest configuration and shared fixtures.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

# Use SQLite in-memory for all tests — no real DB file needed
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-not-real")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("MLFLOW_TRACKING_URI", "sqlite:///test_mlflow.db")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture
async def async_client():
    """Async HTTP test client for FastAPI endpoints."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def mock_agent_response():
    """Mock a successful agent graph invocation."""
    from langchain_core.messages import AIMessage

    return {
        "messages": [
            AIMessage(content="Here are the results of your query...")
        ],
        "session_id": "test-session-123",
        "user_query": "test query",
    }
