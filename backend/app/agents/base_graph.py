"""
Shared LangGraph agent utilities.
- BaseAgentState: common state TypedDict fields
- build_react_graph: factory for ReAct-pattern graphs
- MLflow logging helper
- LangSmith context manager
"""

import time
from typing import Annotated, Any
from typing_extensions import TypedDict

import mlflow
from mlflow.entities import SpanType
import structlog
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from app.config import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Configure MLflow 3 tracing at import time.
#
# mlflow.openai.autolog() in MLflow 3 does much more than v2:
#   - Captures every OpenAI call as a TRACE with nested spans (flamegraph view)
#   - Records: prompt, response, model, token counts, latency per span
#   - Visible in the new MLflow UI Traces tab — equivalent to LangSmith
#   - No external API needed — fully self-hosted
# ---------------------------------------------------------------------------
mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
mlflow.set_experiment(settings.mlflow_experiment_name)  # All runs go here
mlflow.openai.autolog(log_traces=True, silent=True)


# ---------------------------------------------------------------------------
# Shared state schema
# ---------------------------------------------------------------------------


class BaseAgentState(TypedDict):
    """Common state fields shared across all agents."""
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str          # For LangSmith grouping / correlation
    user_query: str          # Original query (stored for MLflow logging)


# ---------------------------------------------------------------------------
# ReAct graph factory
# ---------------------------------------------------------------------------


def build_react_graph(
    tools: list,
    system_prompt: str,
    state_class: type = BaseAgentState,
    model: str | None = None,
    temperature: float = 0.0,
):
    """
    Build a compiled LangGraph ReAct-style graph.

    Pattern: agent_node ↔ tool_node (loop until no more tool calls → END)

    Args:
        tools: List of @tool-decorated functions to bind to the model.
        system_prompt: System message injected at the start of every conversation.
        state_class: TypedDict state class (defaults to BaseAgentState).
        model: OpenAI model name override (defaults to settings.openai_model).
        temperature: Sampling temperature (0 = deterministic SQL generation).

    Returns:
        Compiled LangGraph graph (call `.ainvoke()` or `.astream_events()`).
    """
    _model = model or settings.openai_model
    llm = ChatOpenAI(
        model=_model,
        temperature=temperature,
        api_key=settings.openai_api_key,
    ).bind_tools(tools)

    def call_model(state: dict) -> dict:
        from langchain_core.messages import SystemMessage
        messages = state["messages"]
        # Prepend system prompt on first call only
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=system_prompt)] + messages
        # CHAIN span: captures this reasoning step (LLM call auto-captured by autolog)
        with mlflow.start_span(name="llm:agent_step", span_type=SpanType.CHAIN) as span:
            span.set_inputs({"num_messages": len(messages)})
            response = llm.invoke(messages)
            span.set_outputs({"content": str(response.content)[:300]})
        return {"messages": [response]}

    graph = StateGraph(state_class)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    graph.add_edge("agent", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# MLflow logging helper
# ---------------------------------------------------------------------------


def log_agent_run(
    use_case: str,
    query: str,
    answer: str,
    latency_ms: float,
    model: str | None = None,
    extra_metrics: dict[str, Any] | None = None,
) -> None:
    """Log explicit metrics to the active MLflow experiment run."""
    try:
        with mlflow.start_run(run_name=use_case):
            mlflow.log_param("use_case", use_case)
            mlflow.log_param("model", model or settings.openai_model)
            mlflow.log_param("query_preview", query[:200])
            mlflow.log_metric("latency_ms", latency_ms)
            mlflow.log_metric("response_length_chars", len(answer))
            if extra_metrics:
                mlflow.log_metrics(extra_metrics)
    except Exception as exc:
        log.warning("mlflow_logging_failed", error=str(exc))
