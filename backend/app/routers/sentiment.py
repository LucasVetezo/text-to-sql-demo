"""Sentiment router — /api/sentiment endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import text

from app.agents.sentiment_agent import sentiment_graph
from app.db.session import readonly_engine
from app.routers._agent_utils import invoke_agent
from app.schemas.responses import AgentRequest, AgentResponse

router = APIRouter(prefix="/api/sentiment", tags=["Social Sentiment"])


# ---------------------------------------------------------------------------
# Chart-data helper — pure DB, no LLM, returns live filtered breakdowns
# ---------------------------------------------------------------------------

async def _sentiment_chart_data(
    topic: str | None,
    platform: str | None,
    sentiment: str | None,
) -> dict[str, Any]:
    """Return structured chart data filtered by topic / platform / sentiment."""
    conditions: list[str] = []
    if topic:
        conditions.append(f"topic = '{topic}'")
    if platform:
        conditions.append(f"platform = '{platform}'")
    if sentiment:
        conditions.append(f"sentiment_label = '{sentiment}'")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sentiment_sql = f"""
        SELECT sentiment_label,
               COUNT(*) as count,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
        FROM social_posts {where}
        GROUP BY sentiment_label ORDER BY count DESC
    """
    topic_sql = f"""
        SELECT topic, COUNT(*) as mentions
        FROM social_posts {where}
        GROUP BY topic ORDER BY mentions DESC LIMIT 8
    """
    platform_sql = f"""
        SELECT platform,
               COUNT(*) as count,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
        FROM social_posts {where}
        GROUP BY platform ORDER BY count DESC
    """
    trending_sql = f"""
        SELECT topic, sentiment_label, COUNT(*) as cnt
        FROM social_posts {where}
        WHERE sentiment_label = 'negative'
        GROUP BY topic, sentiment_label ORDER BY cnt DESC LIMIT 6
    """

    async with readonly_engine.connect() as conn:
        s_rows = (await conn.execute(text(sentiment_sql))).mappings().fetchall()
        t_rows = (await conn.execute(text(topic_sql))).mappings().fetchall()
        p_rows = (await conn.execute(text(platform_sql))).mappings().fetchall()
        tr_rows = (await conn.execute(text(trending_sql))).mappings().fetchall()

    return {
        "sentiment_breakdown": [dict(r) for r in s_rows],
        "topic_distribution":  [dict(r) for r in t_rows],
        "platform_split":      [dict(r) for r in p_rows],
        "trending_negatives":  [dict(r) for r in tr_rows],
        "filters": {"topic": topic, "platform": platform, "sentiment": sentiment},
    }


@router.get("/chart-data", summary="Live chart data — filtered by topic/platform/sentiment")
async def get_chart_data(
    topic:     str | None = Query(default=None, description="Filter by topic (credit, fraud, service, app, fees)"),
    platform:  str | None = Query(default=None, description="Filter by platform (X, LinkedIn)"),
    sentiment: str | None = Query(default=None, description="Filter by sentiment (positive, neutral, negative)"),
) -> dict[str, Any]:
    try:
        return await _sentiment_chart_data(topic=topic, platform=platform, sentiment=sentiment)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chart data error: {exc}")


@router.post("/query", response_model=AgentResponse, summary="Analyse social sentiment with NL")
async def query_sentiment(request: AgentRequest) -> AgentResponse:
    """
    Submit a natural language question about social media sentiment.
    The agent fetches posts from the synthetic database (mock for X/LinkedIn),
    analyses sentiment patterns, and generates executive-ready insights.

    **Example queries:**
    - "What are customers saying about Nedbank's credit application process?"
    - "Show me the most common negative themes on X this month"
    - "Compare sentiment between LinkedIn and X for Nedbank"
    - "Give me a 5-bullet executive summary of customer complaints"
    """
    try:
        result = await invoke_agent(
            graph=sentiment_graph,
            query=request.query,
            session_id=request.session_id,
            use_case="sentiment",
        )
        return AgentResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {exc}",
        )


@router.get("/examples", summary="Get example queries for the sentiment use case")
async def get_sentiment_examples() -> dict:
    return {
        "examples": [
            "What is the overall sentiment breakdown for Nedbank?",
            "What are customers most frustrated about?",
            "Show me positive feedback — what are we doing well?",
            "Compare credit-related sentiment vs fees-related sentiment",
            "What are the top 3 things to fix based on customer feedback?",
            "Show me the most viral negative posts about Nedbank",
            "What do LinkedIn users say vs X users?",
            "Summarise themes from the last 30 days of social posts",
        ]
    }
