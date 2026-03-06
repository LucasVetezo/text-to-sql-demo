"""
Page 1: Credit Application Text-to-SQL
"""

import uuid
import time
import pandas as pd
import streamlit as st

from api_client import get_examples, query_agent
from components.eval_badge import render_response_footer

st.title("💳 Credit Application Intelligence")
st.markdown(
    "Ask questions about Nedbank's credit application data in plain English. "
    "The AI agent generates SQL, executes it, and explains the results."
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "credit_history" not in st.session_state:
    st.session_state.credit_history = []
if "credit_session_id" not in st.session_state:
    st.session_state.credit_session_id = str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Example queries
# ---------------------------------------------------------------------------
examples = get_examples("/api/credit/examples")
if examples:
    with st.expander("💡 Example queries — click to use", expanded=True):
        cols = st.columns(2)
        for i, example in enumerate(examples):
            if cols[i % 2].button(example, key=f"credit_ex_{i}", use_container_width=True):
                st.session_state.credit_prefill = example

st.markdown("---")

# ---------------------------------------------------------------------------
# Chat interface
# ---------------------------------------------------------------------------
# Display history
for entry in st.session_state.credit_history:
    with st.chat_message("user"):
        st.write(entry["query"])
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(entry["answer"])
        if entry.get("sql_query"):
            with st.expander("🔍 View generated SQL", expanded=False):
                st.code(entry["sql_query"], language="sql", line_numbers=True)
        if entry.get("table_data"):
            st.dataframe(pd.DataFrame(entry["table_data"]), use_container_width=True)
        if entry.get("latency_ms"):
            st.caption(f"⏱ {entry['latency_ms']}ms · Session: {st.session_state.credit_session_id[:8]}")

# Input box
prefill = st.session_state.pop("credit_prefill", "")
query = st.chat_input("Ask about credit applications...", key="credit_input")
if not query and prefill:
    query = prefill

if query:
    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("🤔 Agent is thinking..."):
                _t0 = time.time()
                result = query_agent(
                    "/api/credit/query",
                    query,
                    session_id=st.session_state.credit_session_id,
                )
                _client_ms = round((time.time() - _t0) * 1000)

        if "error" in result:
            st.error(f"❌ {result['error']}")
        else:
            st.markdown(result.get("answer", "No response"))

            sql = result.get("sql_query")
            if sql:
                with st.expander("🔍 View generated SQL", expanded=False):
                    st.code(sql, language="sql", line_numbers=True)

            table_data = result.get("table_data")
            if table_data:
                st.dataframe(pd.DataFrame(table_data), use_container_width=True)

            latency = result.get("latency_ms")
            if latency:
                render_response_footer(
                    result,
                    client_ms=_client_ms,
                    session_id=st.session_state.credit_session_id,
                )

            # Store in history
            st.session_state.credit_history.append({
                "query": query,
                "answer": result.get("answer", ""),
                "sql_query": sql,
                "table_data": table_data,
                "latency_ms": latency,
            })

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 💳 Credit Controls")
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.credit_history = []
        st.session_state.credit_session_id = str(uuid.uuid4())
        st.rerun()

    st.markdown("---")
    st.markdown("**Data source:** `credit_applications` table")
    st.markdown("**500 synthetic records** with assessor comments")
    st.markdown("**Model:** GPT-4o via LangGraph ReAct agent")
