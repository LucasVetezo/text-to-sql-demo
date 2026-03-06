"""
API endpoint smoke tests.
Uses mocked agents so no real OpenAI calls are made in CI.
"""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "model" in data


@pytest.mark.asyncio
async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Nedbank" in response.json()["message"]


@pytest.mark.asyncio
async def test_credit_examples_endpoint(client):
    response = await client.get("/api/credit/examples")
    assert response.status_code == 200
    data = response.json()
    assert "examples" in data
    assert len(data["examples"]) > 0


@pytest.mark.asyncio
async def test_fraud_examples_endpoint(client):
    response = await client.get("/api/fraud/examples")
    assert response.status_code == 200
    assert "examples" in response.json()


@pytest.mark.asyncio
async def test_sentiment_examples_endpoint(client):
    response = await client.get("/api/sentiment/examples")
    assert response.status_code == 200
    assert "examples" in response.json()


@pytest.mark.asyncio
async def test_speech_examples_endpoint(client):
    response = await client.get("/api/speech/examples")
    assert response.status_code == 200
    assert "examples" in response.json()


@pytest.mark.asyncio
async def test_credit_query_mocked(client):
    """Test credit query endpoint with mocked agent (no real OpenAI call)."""
    from langchain_core.messages import AIMessage

    mock_result = {
        "messages": [AIMessage(content="Based on the data, the top decline reason is low credit score.")],
        "session_id": "test-123",
        "user_query": "test",
    }

    with patch("app.routers._agent_utils.invoke_agent") as mock_invoke:
        mock_invoke.return_value = {
            "answer": "Based on the data, the top decline reason is low credit score.",
            "sql_query": "SELECT decline_reason, COUNT(*) FROM credit_applications GROUP BY decline_reason",
            "table_data": None,
            "chart_data": None,
            "trace_id": None,
            "latency_ms": 1234.5,
        }

        response = await client.post(
            "/api/credit/query",
            json={"query": "What are the top decline reasons?", "session_id": "test-123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 0
    assert data["latency_ms"] == 1234.5


@pytest.mark.asyncio
async def test_credit_query_missing_body(client):
    """Empty query should return 422 validation error."""
    response = await client.post("/api/credit/query", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_fraud_query_mocked(client):
    with patch("app.routers._agent_utils.invoke_agent") as mock_invoke:
        mock_invoke.return_value = {
            "answer": "Card-not-present fraud is the most common type.",
            "sql_query": None,
            "table_data": None,
            "chart_data": None,
            "trace_id": None,
            "latency_ms": 987.0,
        }

        response = await client.post(
            "/api/fraud/query",
            json={"query": "What are the most common fraud types?"},
        )

    assert response.status_code == 200
    assert "answer" in response.json()
