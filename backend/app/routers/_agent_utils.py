"""
Shared agent invocation utilities for routers.
Handles timing, MLflow 3 trace spans, experiment logging, and error wrapping.
"""

import time
import uuid
from typing import Any

import mlflow
from mlflow.entities import SpanType
import structlog

from app.agents.base_graph import log_agent_run
from app.evals.metrics import compute_inline_scores
from app.tools.chart_tools import extract_chart_from_messages

log = structlog.get_logger(__name__)


def _extract_answer_and_sql(messages: list) -> tuple[str, str | None]:
    """Extract the final AI answer and any SQL from message history."""
    from langchain_core.messages import AIMessage

    answer = ""
    sql_query = None

    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not answer:
            answer = msg.content if isinstance(msg.content, str) else str(msg.content)

    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
            for tc in (msg.tool_calls or []):
                if "sql" in tc.get("name", "").lower():
                    sql_query = tc.get("args", {}).get("sql")
                    break

    return answer, sql_query


async def invoke_agent(
    graph,
    query: str,
    session_id: str | None,
    use_case: str,
    tags: list[str] | None = None,
    extra_state: dict[str, Any] | None = None,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Invoke a LangGraph agent with full MLflow 3 observability:
    - Root AGENT span wraps the entire graph invocation
    - Child CHAIN spans per LLM step (from base_graph.call_model)
    - Child TOOL spans per tool call (from @mlflow.trace on tool functions)
    - OpenAI calls captured automatically by mlflow.openai.autolog()
    - Explicit metric run logged to the named experiment

    Returns dict matching AgentResponse schema.
    """
    _session_id = session_id or str(uuid.uuid4())
    start = time.perf_counter()

    # Build message history: prior turns + current query
    history_msgs = [
        (m["role"], m["content"])
        for m in (history or [])
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    initial_state = {
        "messages": [*history_msgs, ("user", query)],
        "session_id": _session_id,
        "user_query": query,
        **(extra_state or {}),
    }

    # mlflow.start_span() as a context manager creates a root trace when there
    # is no active parent span. Within the same async task, Python's contextvars
    # propagate through every awaited coroutine, so child spans from
    # mlflow.openai.autolog() and @mlflow.trace tool decorators nest correctly.
    # The trace is flushed to the tracking server when this `with` block exits.
    with mlflow.start_span(
        name=f"agent:{use_case}",
        span_type=SpanType.AGENT,
    ) as root_span:
        root_span.set_inputs({"query": query, "use_case": use_case, "session_id": _session_id})
        result = await graph.ainvoke(initial_state)

        latency_ms = (time.perf_counter() - start) * 1000
        messages = result.get("messages", [])
        answer, sql_query = _extract_answer_and_sql(messages)

        eval_scores = compute_inline_scores(answer, sql_query)

        root_span.set_outputs({"answer": answer[:500], "latency_ms": round(latency_ms, 1)})
        root_span.set_attribute("sql_query", sql_query or "")
        for metric_name, score in eval_scores.items():
            root_span.set_attribute(metric_name, score)
        mlflow.update_current_trace(
            request_preview=query[:200],
            response_preview=answer[:200],
        )

    # Lift any chart data the agent produced via a chart tool
    # extract_chart_from_messages scans ToolMessages for embedded JSON markers
    agent_chart_data = extract_chart_from_messages(messages)

    log_agent_run(
        use_case=use_case,
        query=query,
        answer=answer,
        latency_ms=latency_ms,
        extra_metrics=eval_scores,
    )

    log.info(
        "agent_invocation_complete",
        use_case=use_case,
        latency_ms=round(latency_ms, 1),
        session_id=_session_id,
    )

    return {
        "answer": answer,
        "sql_query": sql_query,
        "table_data": None,
        "chart_data": agent_chart_data,   # None when no chart tool was called
        "trace_id": None,
        "latency_ms": round(latency_ms, 1),
        "eval_scores": eval_scores,
    }
