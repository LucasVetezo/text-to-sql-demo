"""
Page 2: Fraud Cases Text-to-SQL
"""

import uuid
import time
import pandas as pd
import streamlit as st

from api_client import get_examples, query_agent
from components.eval_badge import render_response_footer

st.title("🔍 Fraud Intelligence Dashboard")
st.markdown(
    "Investigate fraud patterns using natural language. "
    "The agent queries fraud case data and surfaces risk insights."
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "fraud_history" not in st.session_state:
    st.session_state.fraud_history = []
if "fraud_session_id" not in st.session_state:
    st.session_state.fraud_session_id = str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Quick metrics overview
# ---------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("📁 Total Cases", "300", help="Synthetic fraud cases in database")
col2.metric("🔴 Confirmed Fraud", "~42%", help="Fraud flag = confirmed")
col3.metric("🟡 Suspected", "~38%", help="Fraud flag = suspected")
col4.metric("🟢 Cleared", "~20%", help="Fraud flag = cleared")
st.markdown("---")

# ---------------------------------------------------------------------------
# Example queries
# ---------------------------------------------------------------------------
examples = get_examples("/api/fraud/examples")
if examples:
    with st.expander("💡 Example queries — click to use", expanded=True):
        cols = st.columns(2)
        for i, example in enumerate(examples):
            if cols[i % 2].button(example, key=f"fraud_ex_{i}", use_container_width=True):
                st.session_state.fraud_prefill = example

st.markdown("---")

# ---------------------------------------------------------------------------
# Chat interface
# ---------------------------------------------------------------------------
for entry in st.session_state.fraud_history:
    with st.chat_message("user"):
        st.write(entry["query"])
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(entry["answer"])
        if entry.get("sql_query"):
            with st.expander("🔍 View generated SQL"):
                st.code(entry["sql_query"], language="sql")
        if entry.get("table_data"):
            df = pd.DataFrame(entry["table_data"])
            # Colour-code risk_score if present
            if "risk_score" in df.columns:
                st.dataframe(
                    df.style.background_gradient(subset=["risk_score"], cmap="RdYlGn_r"),
                    use_container_width=True,
                )
            else:
                st.dataframe(df, use_container_width=True)
        if entry.get("latency_ms"):
            st.caption(f"⏱ {entry['latency_ms']}ms")

prefill = st.session_state.pop("fraud_prefill", "")
query = st.chat_input("Ask about fraud cases...", key="fraud_input")
if not query and prefill:
    query = prefill

if query:
    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("🔎 Investigating..."):
                _t0 = time.time()
                result = query_agent(
                    "/api/fraud/query",
                    query,
                    session_id=st.session_state.fraud_session_id,
                )
                _client_ms = round((time.time() - _t0) * 1000)

        if "error" in result:
            st.error(f"❌ {result['error']}")
        else:
            st.markdown(result.get("answer", "No response"))

            sql = result.get("sql_query")
            if sql:
                with st.expander("🔍 View generated SQL"):
                    st.code(sql, language="sql")

            table_data = result.get("table_data")
            if table_data:
                df = pd.DataFrame(table_data)
                if "risk_score" in df.columns:
                    st.dataframe(
                        df.style.background_gradient(subset=["risk_score"], cmap="RdYlGn_r"),
                        use_container_width=True,
                    )
                else:
                    st.dataframe(df, use_container_width=True)

            render_response_footer(
                result,
                client_ms=_client_ms,
                session_id=st.session_state.fraud_session_id,
            )

            st.session_state.fraud_history.append({
                "query": query,
                "answer": result.get("answer", ""),
                "sql_query": sql,
                "table_data": table_data,
                "latency_ms": result.get("latency_ms"),
            })

with st.sidebar:
    st.markdown("### 🔍 Fraud Controls")
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.fraud_history = []
        st.session_state.fraud_session_id = str(uuid.uuid4())
        st.rerun()
    st.markdown("---")
    st.markdown("**Data source:** `fraud_cases` table")
    st.markdown("**300 synthetic records** with investigator commentary")
    st.markdown("**Risk scores:** 0.0 (low) → 1.0 (critical)")
