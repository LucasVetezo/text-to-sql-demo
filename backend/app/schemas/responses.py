"""Pydantic response schemas shared across routers."""

from typing import Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


# ---------------------------------------------------------------------------
# Chat / Agent
# ---------------------------------------------------------------------------


class AgentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Natural language query")
    session_id: str | None = Field(
        default=None, description="Optional session ID for trace grouping"
    )
    history: list[dict] | None = Field(
        default=None,
        description="Prior turns: [{role: 'user'|'assistant', content: str}, ...]"
    )


class AgentResponse(BaseModel):
    answer: str = Field(..., description="LLM-generated natural language answer")
    sql_query: str | None = Field(
        default=None, description="Generated SQL (for SQL use cases)"
    )
    table_data: list[dict[str, Any]] | None = Field(
        default=None, description="Raw SQL result rows (max 500)"
    )
    chart_data: dict[str, Any] | None = Field(
        default=None, description="Structured data for frontend charting"
    )
    trace_id: str | None = Field(
        default=None, description="MLflow trace ID for debugging"
    )
    latency_ms: float | None = None
    eval_scores: dict[str, float] | None = Field(
        default=None,
        description="Inline eval scores: sql_valid, sql_safe, answer_quality (0.0–1.0)",
    )
    agent_label: str | None = Field(
        default=None,
        description="Which specialist agent(s) responded. None / 'general' means no specialist was used.",
    )


# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------


class SentimentSummary(BaseModel):
    total_posts: int
    positive_pct: float
    neutral_pct: float
    negative_pct: float
    top_topics: list[str]
    overall_sentiment: str          # "positive" / "neutral" / "negative"
    gpt_summary: str                # Narrative LLM-generated summary
    sample_posts: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Speech / Whisper
# ---------------------------------------------------------------------------


class TranscriptInsight(BaseModel):
    call_id: str | None = None
    transcript: str
    pain_points: list[str]
    process_improvements: list[str]
    cx_score: float                  # 1 – 10
    sentiment: str
    gpt_summary: str
