"""
Sentiment analysis tools for social media posts.

In DEVELOPMENT: Returns synthetic data from the local database.
In PRODUCTION: Replace `_fetch_posts_from_db` with real API client calls:
  - X (Twitter): tweepy v4 — client.search_recent_tweets(query="Nedbank", ...)
  - LinkedIn: Use the LinkedIn API (requires company page admin access)
The interface is identical — real data just replaces the mock rows.
"""

import json
from typing import Any
import mlflow
from mlflow.entities import SpanType
from langchain_core.tools import tool
from sqlalchemy import text

from app.db.session import readonly_engine


async def _fetch_posts_from_db(
    platform: str | None = None,
    sentiment: str | None = None,
    topic: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Fetch social posts from the local DB (dev mock layer)."""
    conditions = []
    if platform:
        conditions.append(f"platform = '{platform}'")
    if sentiment:
        conditions.append(f"sentiment_label = '{sentiment}'")
    if topic:
        conditions.append(f"topic = '{topic}'")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM social_posts {where} ORDER BY post_date DESC LIMIT {limit}"

    async with readonly_engine.connect() as conn:
        result = await conn.execute(text(sql))
        rows = result.fetchall()
        cols = list(result.keys())
    return [dict(zip(cols, row)) for row in rows]


@tool
@mlflow.trace(span_type=SpanType.TOOL, name="fetch_social_posts")
async def fetch_social_posts(
    platform: str = "all",
    sentiment_filter: str = "all",
    topic_filter: str = "all",
    limit: int = 100,
) -> str:
    """
    Fetch social media posts mentioning Nedbank from the database.
    
    ⚡ Real integration note: In production this calls the X (Twitter) API via
    tweepy or the LinkedIn API. The mock layer returns identical data shape.
    
    Args:
        platform: Filter by platform — "X", "LinkedIn", or "all"
        sentiment_filter: Filter by sentiment — "positive", "neutral", "negative", or "all"
        topic_filter: Filter by topic — "credit", "fraud", "service", "app", "fees", or "all"
        limit: Max number of posts to return (default 100)
    
    Returns:
        JSON string with list of post objects including text, sentiment, topic, date.
    """
    p = None if platform == "all" else platform
    s = None if sentiment_filter == "all" else sentiment_filter
    t = None if topic_filter == "all" else topic_filter

    posts = await _fetch_posts_from_db(platform=p, sentiment=s, topic=t, limit=limit)
    if not posts:
        return json.dumps({"posts": [], "count": 0})

    # Return only text-relevant fields to save tokens
    simplified = [
        {
            "platform": post["platform"],
            "date": post["post_date"],
            "text": post["post_text"],
            "sentiment": post["sentiment_label"],
            "score": post["sentiment_score"],
            "topic": post["topic"],
            "likes": post["likes"],
        }
        for post in posts
    ]
    return json.dumps({"posts": simplified, "count": len(simplified)})


@tool
@mlflow.trace(span_type=SpanType.TOOL, name="get_sentiment_breakdown")
async def get_sentiment_breakdown() -> str:
    """
    Get aggregate sentiment statistics across all social posts.
    Returns percentage breakdown by sentiment label and top topics.
    Use this to understand the overall customer perception of Nedbank.
    """
    sql = """
        SELECT
            sentiment_label,
            COUNT(*) as count,
            AVG(sentiment_score) as avg_score,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
        FROM social_posts
        GROUP BY sentiment_label
        ORDER BY count DESC
    """
    topic_sql = """
        SELECT topic, COUNT(*) as mentions
        FROM social_posts
        GROUP BY topic
        ORDER BY mentions DESC
        LIMIT 5
    """
    async with readonly_engine.connect() as conn:
        result = await conn.execute(text(sql))
        sentiments = [dict(zip(result.keys(), r)) for r in result.fetchall()]
        result2 = await conn.execute(text(topic_sql))
        topics = [dict(zip(result2.keys(), r)) for r in result2.fetchall()]

    return json.dumps({"sentiment_breakdown": sentiments, "top_topics": topics}, indent=2)
