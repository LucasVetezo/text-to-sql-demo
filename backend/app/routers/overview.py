"""Overview router — /api/overview

Returns live dataset volume metrics for the Dashboard "At a Glance" cards.
All queries are read-only SELECTs against the configured SQLite database.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(prefix="/api/overview", tags=["Overview"])


@router.get("", summary="Live dataset volume metrics for the dashboard")
async def get_overview(db: AsyncSession = Depends(get_db)):
    """
    Returns volume metrics across all four intelligence domains:

    - **card_apps**: Total credit application volume
    - **fraud**: Confirmed fraud cases vs non-fraud (cleared + suspected)
    - **sentiment**: Positive / Negative / Neutral social post counts
    - **cx**: Good (cx_score ≥ 7) vs Bad (cx_score < 7) call transcripts
    """

    # ── 1. Card Applications — total volume ────────────────────────────────
    result = await db.execute(text("SELECT COUNT(*) FROM credit_applications"))
    card_apps_total = result.scalar() or 0

    # ── 2. Application Fraud — confirmed vs non-fraud ──────────────────────
    result = await db.execute(
        text("""
            SELECT fraud_flag, COUNT(*) AS cnt
            FROM fraud_cases
            GROUP BY fraud_flag
        """)
    )
    fraud_rows = {row[0]: row[1] for row in result.fetchall()}
    fraud_confirmed = fraud_rows.get("confirmed", 0)
    fraud_non_fraud = fraud_rows.get("cleared", 0) + fraud_rows.get("suspected", 0)

    # ── 3. Social Sentiment — positive / negative / neutral ────────────────
    result = await db.execute(
        text("""
            SELECT sentiment_label, COUNT(*) AS cnt
            FROM social_posts
            GROUP BY sentiment_label
        """)
    )
    sentiment_rows = {row[0]: row[1] for row in result.fetchall()}
    sentiment_positive = sentiment_rows.get("positive", 0)
    sentiment_negative = sentiment_rows.get("negative", 0)
    sentiment_neutral  = sentiment_rows.get("neutral", 0)

    # ── 4. Customer Experience — good (≥ 7) vs bad (< 7) ──────────────────
    result = await db.execute(
        text("""
            SELECT
                SUM(CASE WHEN cx_score >= 7 THEN 1 ELSE 0 END) AS good,
                SUM(CASE WHEN cx_score <  7 THEN 1 ELSE 0 END) AS bad
            FROM call_transcripts
        """)
    )
    cx_row = result.fetchone()
    cx_good = cx_row[0] or 0
    cx_bad  = cx_row[1] or 0

    return {
        "card_apps": {
            "total": card_apps_total,
        },
        "fraud": {
            "confirmed": fraud_confirmed,
            "non_fraud": fraud_non_fraud,
        },
        "sentiment": {
            "positive": sentiment_positive,
            "negative": sentiment_negative,
            "neutral":  sentiment_neutral,
        },
        "cx": {
            "good": cx_good,
            "bad":  cx_bad,
        },
    }
