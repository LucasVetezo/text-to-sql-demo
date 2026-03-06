"""
Shared UI components for the Nedbank AI Demo.
Import from pages via: from components.eval_badge import render_response_footer
"""

import streamlit as st


def _score_dot(score: float | None) -> str:
    """Return a coloured dot based on a 0.0–1.0 eval score."""
    if score is None:
        return "⚪"
    if score >= 0.9:
        return "🟢"
    if score >= 0.4:
        return "🟡"
    return "🔴"


def render_response_footer(
    result: dict,
    client_ms: float | None = None,
    session_id: str | None = None,
) -> None:
    """
    Render the response footer below every agent answer. Shows:
    - Backend latency (from the server's timer)
    - Client-side round-trip latency (browser → backend → browser)
    - Inline eval score badges (sql_valid, sql_safe, answer_quality)
    - Link to MLflow trace
    - Session ID prefix

    Args:
        result:     AgentResponse dict returned by api_client.query_agent()
        client_ms:  Total time in ms measured on the client side (incl. network)
        session_id: Current session UUID for display
    """
    backend_ms = result.get("latency_ms")
    eval_scores = result.get("eval_scores") or {}

    # --- Latency row ---
    latency_parts = []
    if backend_ms is not None:
        latency_parts.append(f"⏱ Backend **{backend_ms:,.0f}ms**")
    if client_ms is not None and backend_ms is not None:
        overhead = client_ms - backend_ms
        latency_parts.append(f"Network **+{overhead:,.0f}ms**")
    elif client_ms is not None:
        latency_parts.append(f"⏱ **{client_ms:,.0f}ms** round-trip")

    # --- Eval badges ---
    badge_parts = []
    if eval_scores:
        for label, key in [
            ("SQL valid", "eval/sql_valid"),
            ("SQL safe", "eval/sql_safe"),
            ("Answer quality", "eval/answer_quality"),
        ]:
            score = eval_scores.get(key)
            badge_parts.append(f"{_score_dot(score)} {label}")

    # --- Assemble caption ---
    footer_items = latency_parts + badge_parts
    if session_id:
        footer_items.append(f"Session `{session_id[:8]}`")
    footer_items.append("[Trace in MLflow ↗](http://localhost:5000)")

    st.caption("  ·  ".join(footer_items))

    # Show detail expander if any eval score is below ideal
    problem_scores = {k: v for k, v in eval_scores.items() if v < 0.9}
    if problem_scores:
        with st.expander("⚠️ Eval warnings — expand for details", expanded=False):
            for key, score in problem_scores.items():
                metric_name = key.split("/")[-1].replace("_", " ").title()
                colour = "orange" if score >= 0.4 else "red"
                st.markdown(
                    f":{colour}[**{metric_name}**: {score:.2f}] — "
                    + _get_advice(key, score)
                )


def _get_advice(metric_key: str, score: float) -> str:
    """Return a short human-readable explanation for a low eval score."""
    advice = {
        "eval/sql_valid": "The generated SQL may contain a syntax error. Check the SQL expander above.",
        "eval/sql_safe": "The generated SQL contains a DML/DDL keyword (DROP, DELETE, INSERT, etc.). This should not happen.",
        "eval/answer_quality": "The answer was very short or began with an error/refusal. Consider rephrasing your question.",
    }
    return advice.get(metric_key, "Score below threshold.")
