"""
Chart-aware SQL tools for all four specialist agents.

Covered domains
---------------
  execute_credit_sql_chart    — queries credit_applications
  execute_fraud_sql_chart     — queries fraud_transactions
  execute_sentiment_sql_chart — queries social_posts
  execute_sentiment_sql       — social_posts, plain JSON
  execute_speech_sql_chart    — queries call_transcripts
  execute_speech_sql          — call_transcripts, plain JSON

When an agent wants to render a visual, it calls the chart variant instead
of the plain-text SQL tool.  Those tools:

  1. Run the same validated READ-ONLY SQL.
  2. Embed structured chart metadata as a JSON marker inside the tool return
     string — which LangGraph stores in a ToolMessage in the agent's state.
  3. Return a brief human-readable narrative so the agent can describe the chart.

`invoke_agent` scans the final message list for the marker via
`extract_chart_from_messages()`, strips it from any displayed text, and lifts
it into AgentResponse.chart_data.

Why a string marker instead of a ContextVar?
  LangGraph's ToolNode wraps async tool calls in asyncio.gather(), which
  creates new Tasks. Each Task gets a COPY of the current ContextVar context;
  mutations inside those tasks do NOT propagate back to the caller. A string
  marker embedded in the tool's return value travels inside LangGraph's own
  state (the messages list) and is always visible to the caller after ainvoke()
  completes — no async context propagation issues.
"""

import json
import re
from typing import Any

from langchain_core.tools import tool

from app.tools.sql_tools import _run_sql

# ---------------------------------------------------------------------------
# Chart data marker — embedded in tool return strings
# ---------------------------------------------------------------------------

_CHART_START = "__CHART__:"
_CHART_END   = ":__ENDCHART__"
_CHART_RE    = re.compile(
    re.escape(_CHART_START) + r"(.+?)" + re.escape(_CHART_END),
    re.DOTALL,
)


def extract_chart_from_messages(messages: list) -> dict[str, Any] | None:
    """
    Scan the agent message history for an embedded chart marker.
    Returns the first chart payload found, or None.
    Called by invoke_agent after graph.ainvoke() completes.
    """
    from langchain_core.messages import ToolMessage
    for msg in messages:
        if isinstance(msg, ToolMessage) and isinstance(msg.content, str):
            m = _CHART_RE.search(msg.content)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
    return None


# Kept for API compat — no longer used but imported by _agent_utils in older code
def reset_chart_context() -> None:
    pass

def pop_chart_data() -> dict[str, Any] | None:
    return None


def _build_tool_response(
    title: str,
    chart_type: str,
    x_key: str,
    y_key: str,
    rows: list[dict[str, Any]],
    color_key: str | None = None,
) -> str:
    """
    Build the string returned by a chart tool.
    Structure: <narrative>\n\n<JSON marker>

    The narrative is what the LLM reads and incorporates into its answer.
    The JSON marker is invisible to the LLM's final response (it appears only
    in the ToolMessage, not in the AI reply) and is extracted by invoke_agent.
    """
    # Human-readable preview for the LLM to narrate
    if not rows:
        return "The query returned no data — nothing to chart."

    # Auto-detect all numeric columns so multi-series pivot queries get y_keys
    numeric_cols = [
        col for col in rows[0].keys()
        if col != x_key and isinstance(rows[0][col], (int, float))
    ]
    # y_keys: all numeric columns in result order (primary y_key first)
    y_keys_ordered = ([y_key] + [c for c in numeric_cols if c != y_key]) if numeric_cols else [y_key]

    preview = rows[:6]
    lines = [f"Here's **{title}** ({len(rows)} data points):"]
    for r in preview:
        xval = r.get(x_key, "?")
        vals = ", ".join(f"{prettykey(k)}: {r.get(k, '?')}" for k in y_keys_ordered)
        lines.append(f"- **{xval}**: {vals}")
    if len(rows) > 6:
        lines.append(f"_…and {len(rows) - 6} more — see the chart below._")
    else:
        lines.append("_Chart rendered below._")
    narrative = "\n".join(lines)

    # Machine-readable marker (lives only in the ToolMessage)
    payload = json.dumps({
        "chart_type": chart_type,
        "title":      title,
        "x_key":      x_key,
        "y_key":      y_key,
        "y_keys":     y_keys_ordered,
        "rows":       rows,
        "color_key":  color_key,
    }, default=str)

    return f"{narrative}\n\n{_CHART_START}{payload}{_CHART_END}"


def prettykey(k: str) -> str:
    """snake_case → Title Case for narrative labels."""
    return k.replace('_', ' ').title()


# ---------------------------------------------------------------------------
# Credit chart tool
# ---------------------------------------------------------------------------


@tool
async def execute_credit_sql_chart(
    sql: str,
    title: str,
    chart_type: str,
    x_col: str,
    y_col: str,
) -> str:
    """
    Execute a SELECT query against credit_applications and render the result
    as an interactive chart in the dashboard.

    Use this tool INSTEAD OF execute_credit_sql whenever the user asks for a
    graph, chart, plot, visual, or bar/line/pie breakdown of credit data.

    Args:
        sql:        Valid SELECT query.  Must return at least x_col and y_col.
                    Example: SELECT credit_score_band, COUNT(*) AS count
                             FROM credit_applications
                             WHERE application_status='rejected'
                             GROUP BY credit_score_band
                             ORDER BY credit_score_band
        title:      Human-readable chart title shown above the visual.
                    Example: "Rejected Applications by Credit Score Band"
        chart_type: Rendering hint — choose ONE of:
                    "bar"  → categorical comparison (most common for group-bys)
                    "line" → trend over time (use when x_col is a date/period)
                    "pie"  → share/proportion (good for percentages, max 8 slices)
        x_col:      Column name for the category / X-axis labels.
        y_col:      Column name for the numeric / Y-axis values.

    Returns a concise narrative; the chart is rendered automatically in the UI.
    """
    try:
        rows = await _run_sql(sql)
        if not rows:
            return "Query returned no results — nothing to chart."

        if rows and x_col not in rows[0]:
            available = list(rows[0].keys())
            return (
                f"Column '{x_col}' not found in results.  "
                f"Available columns: {available}.  Please re-run with the correct x_col."
            )
        if rows and y_col not in rows[0]:
            available = list(rows[0].keys())
            return (
                f"Column '{y_col}' not found in results.  "
                f"Available columns: {available}.  Please re-run with the correct y_col."
            )

        return _build_tool_response(title, chart_type, x_col, y_col, rows)

    except ValueError as exc:
        return f"⛔ Security error: {exc}"
    except Exception as exc:
        return f"❌ SQL error: {exc}"


# ---------------------------------------------------------------------------
# Fraud chart tool
# ---------------------------------------------------------------------------


@tool
async def execute_fraud_sql_chart(
    sql: str,
    title: str,
    chart_type: str,
    x_col: str,
    y_col: str,
) -> str:
    """
    Execute a SELECT query against fraud_cases and render the result
    as an interactive chart in the dashboard.

    Use this tool INSTEAD OF execute_fraud_sql whenever the user asks for a
    graph, chart, plot, visual, or bar/line/pie breakdown of fraud data.

    Args:
        sql:        Valid SELECT query.  Must return at least x_col and y_col.
                    Example: SELECT fraud_type, COUNT(*) AS count
                             FROM fraud_cases
                             GROUP BY fraud_type ORDER BY count DESC
        title:      Human-readable chart title.
                    Example: "Fraud Cases by Type"
        chart_type: "bar" | "line" | "pie"  (same rules as credit chart tool)
        x_col:      Column name for X-axis / category labels.
        y_col:      Column name for numeric values.

    Returns a concise narrative; the chart is rendered automatically in the UI.
    """
    try:
        rows = await _run_sql(sql)
        if not rows:
            return "Query returned no results — nothing to chart."

        if rows and x_col not in rows[0]:
            available = list(rows[0].keys())
            return (
                f"Column '{x_col}' not found.  Available: {available}.  "
                "Please re-run with the correct x_col."
            )
        if rows and y_col not in rows[0]:
            available = list(rows[0].keys())
            return (
                f"Column '{y_col}' not found.  Available: {available}.  "
                "Please re-run with the correct y_col."
            )

        return _build_tool_response(title, chart_type, x_col, y_col, rows)

    except ValueError as exc:
        return f"⛔ Security error: {exc}"
    except Exception as exc:
        return f"❌ SQL error: {exc}"


# ---------------------------------------------------------------------------
# Sentiment chart tool
# ---------------------------------------------------------------------------


@tool
async def execute_sentiment_sql_chart(
    sql: str,
    title: str,
    chart_type: str,
    x_col: str,
    y_col: str,
) -> str:
    """
    Execute a SELECT query against social_posts and render the result
    as an interactive chart in the dashboard.

    Use this tool INSTEAD OF get_sentiment_breakdown whenever the user asks for
    a specific graph, chart, plot, visual, or a breakdown by a particular
    dimension (e.g. by platform, by topic, by sentiment, over time).

    The social_posts table has columns:
        id, post_text, platform, sentiment_label, sentiment_score, topic, likes, post_date

    Args:
        sql:        Valid SELECT query against social_posts only.
                    Example (bar chart of post count by platform):
                      SELECT platform, COUNT(*) AS post_count
                      FROM social_posts
                      GROUP BY platform ORDER BY post_count DESC
                    Example (sentiment split by platform):
                      SELECT platform,
                             SUM(CASE WHEN sentiment_label='positive' THEN 1 ELSE 0 END) AS positive,
                             SUM(CASE WHEN sentiment_label='negative' THEN 1 ELSE 0 END) AS negative
                      FROM social_posts GROUP BY platform
        title:      Human-readable chart title shown above the visual.
                    Example: "Sentiment by Platform"
        chart_type: "bar" | "line" | "pie"
                    bar  → categorical comparison (most queries)
                    line → trend over time (when x_col is a date/period)
                    pie  → share/proportion breakdown
        x_col:      Column name for category / X-axis labels (e.g. "platform", "topic").
        y_col:      Column name for the primary numeric / Y-axis value (e.g. "post_count").

    Returns a concise narrative; the chart is rendered automatically in the UI.
    """
    try:
        rows = await _run_sql(sql)
        if not rows:
            return "Query returned no results — nothing to chart."

        if rows and x_col not in rows[0]:
            available = list(rows[0].keys())
            return (
                f"Column '{x_col}' not found in results.  "
                f"Available columns: {available}.  Please re-run with the correct x_col."
            )
        if rows and y_col not in rows[0]:
            available = list(rows[0].keys())
            return (
                f"Column '{y_col}' not found in results.  "
                f"Available columns: {available}.  Please re-run with the correct y_col."
            )

        return _build_tool_response(title, chart_type, x_col, y_col, rows)

    except ValueError as exc:
        return f"⛔ Security error: {exc}"
    except Exception as exc:
        return f"❌ SQL error: {exc}"


@tool
async def execute_sentiment_sql(sql: str) -> str:
    """
    Execute a read-only SELECT query against social_posts and return
    the results as plain JSON text (no chart rendered).

    Use this to answer analytical questions about social sentiment as plain text —
    NOT when the user explicitly asks for a chart or graph.

    The social_posts table has columns:
        id, post_text, platform, sentiment_label, sentiment_score, topic, likes, post_date

    Args:
        sql: Valid SELECT query against social_posts only.
             Example: SELECT platform, AVG(sentiment_score) AS avg_score
                      FROM social_posts GROUP BY platform ORDER BY avg_score DESC

    Returns a JSON string of the result rows.
    """
    try:
        rows = await _run_sql(sql)
        if not rows:
            return "Query returned no results."
        return json.dumps(rows, default=str, indent=2)
    except ValueError as exc:
        return f"⛔ Security error: {exc}"
    except Exception as exc:
        return f"❌ SQL error: {exc}"


@tool
async def execute_speech_sql(sql: str) -> str:
    """
    Execute a read-only SELECT query against call_transcripts and return
    the results as plain JSON text (no chart rendered).

    Use this to answer analytical questions about call data as plain text—
    NOT when the user explicitly asks for a chart or graph.

    The call_transcripts table has columns:
        call_id, call_date, duration_seconds, agent_name, customer_name,
        call_reason, transcript_text, cx_score, resolution_status

    Args:
        sql: Valid SELECT query against call_transcripts only.
             Example: SELECT agent_name, AVG(cx_score) AS avg_score
                      FROM call_transcripts GROUP BY agent_name ORDER BY avg_score DESC

    Returns a JSON string of the result rows.
    """
    try:
        rows = await _run_sql(sql)
        if not rows:
            return "Query returned no results."
        return json.dumps(rows, default=str, indent=2)
    except ValueError as exc:
        return f"⛔ Security error: {exc}"
    except Exception as exc:
        return f"❌ SQL error: {exc}"


@tool
async def execute_speech_sql_chart(
    sql: str,
    title: str,
    chart_type: str,
    x_col: str,
    y_col: str,
) -> str:
    """
    Execute a SELECT query against call_transcripts and render the result
    as an interactive chart in the dashboard.

    Use this INSTEAD OF execute_speech_sql whenever the user asks for a
    graph, chart, plot, visual, or visual breakdown of call centre data.

    The call_transcripts table has columns:
        call_id, call_date, duration_seconds, agent_name, customer_name,
        call_reason, transcript_text, cx_score, resolution_status

    Args:
        sql:        Valid SELECT query against call_transcripts only.
                    Example (avg CX score by agent):
                      SELECT agent_name, ROUND(AVG(cx_score),1) AS avg_cx_score
                      FROM call_transcripts GROUP BY agent_name ORDER BY avg_cx_score DESC
                    Example (call volume by reason):
                      SELECT call_reason, COUNT(*) AS call_count
                      FROM call_transcripts GROUP BY call_reason ORDER BY call_count DESC
        title:      Human-readable chart title.
                    Example: "Average CX Score by Agent"
        chart_type: "bar" | "line" | "pie"
        x_col:      Column name for category / X-axis labels.
        y_col:      Column name for numeric / Y-axis values.

    Returns a concise narrative; the chart is rendered automatically in the UI.
    """
    try:
        rows = await _run_sql(sql)
        if not rows:
            return "Query returned no results — nothing to chart."
        if rows and x_col not in rows[0]:
            return f"Column '{x_col}' not found. Available: {list(rows[0].keys())}."
        if rows and y_col not in rows[0]:
            return f"Column '{y_col}' not found. Available: {list(rows[0].keys())}."
        return _build_tool_response(title, chart_type, x_col, y_col, rows)
    except ValueError as exc:
        return f"⛔ Security error: {exc}"
    except Exception as exc:
        return f"❌ SQL error: {exc}"
    """
    Execute a read-only SELECT query against social_posts and return
    the results as plain JSON text (no chart rendered).

    Use this when the user wants numbers, counts, or stats as plain text —
    NOT when they explicitly ask for a graph, chart, or visual.

    The social_posts table has columns:
        id, post_text, platform, sentiment_label, sentiment_score, topic, likes, post_date

    Args:
        sql: Valid SELECT query against social_posts only.
             Example: SELECT platform, COUNT(*) AS total FROM social_posts GROUP BY platform

    Returns a JSON string of the result rows.
    """
    try:
        rows = await _run_sql(sql)
        if not rows:
            return "Query returned no results."
        return json.dumps(rows, default=str, indent=2)
    except ValueError as exc:
        return f"⛔ Security error: {exc}"
    except Exception as exc:
        return f"❌ SQL error: {exc}"
