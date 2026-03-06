"""
Chart-aware SQL tools for credit and fraud agents.

When an agent wants to render a visual, it calls `execute_credit_sql_chart`
or `execute_fraud_sql_chart` instead of the plain text tools.  These tools:

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

    preview = rows[:6]
    lines = [f"Here's **{title}** ({len(rows)} data points):"]
    for r in preview:
        xval = r.get(x_key, "?")
        yval = r.get(y_key, "?")
        lines.append(f"- **{xval}**: {yval}")
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
        "rows":       rows,
        "color_key":  color_key,
    }, default=str)

    return f"{narrative}\n\n{_CHART_START}{payload}{_CHART_END}"


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
