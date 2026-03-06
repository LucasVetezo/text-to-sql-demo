"""
Page 3: Social Media Sentiment Analysis
"""

import uuid
import time
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from api_client import get_examples, query_agent
from components.eval_badge import render_response_footer

st.title("📊 Social Sentiment — What Customers Say About Nedbank")
st.markdown(
    "Analyse social media posts mentioning Nedbank from X and LinkedIn. "
    "Ask questions or request executive summaries — the AI fetches and synthesises real-time insights."
)

st.info(
    "⚡ **Integration note:** This demo uses synthetic social data. "
    "In production, this connects to the **X API (tweepy v4)** and **LinkedIn Pages API** "
    "to fetch real mentions in real time. The agent interface is identical.",
    icon="💡",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "sentiment_history" not in st.session_state:
    st.session_state.sentiment_history = []
if "sentiment_session_id" not in st.session_state:
    st.session_state.sentiment_session_id = str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Static quick-view chart (from synthetic data breakdown)
# This provides immediate visual context before any query
# ---------------------------------------------------------------------------
with st.expander("📈 Sentiment Overview Dashboard", expanded=True):
    col1, col2 = st.columns([1, 1])

    # Donut chart — sentiment breakdown
    with col1:
        fig_donut = go.Figure(
            go.Pie(
                labels=["Negative", "Neutral", "Positive"],
                values=[50, 25, 25],
                hole=0.55,
                marker_colors=["#e74c3c", "#f39c12", "#27ae60"],
            )
        )
        fig_donut.update_layout(
            title="Sentiment Breakdown (400 posts)",
            showlegend=True,
            height=300,
            margin=dict(t=40, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # Bar chart — topic distribution
    with col2:
        topics = ["Credit", "Service", "Fraud", "App", "Fees"]
        counts = [35, 25, 20, 12, 8]
        fig_bar = px.bar(
            x=topics,
            y=counts,
            title="Posts by Topic (%)",
            color=topics,
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig_bar.update_layout(
            height=300,
            showlegend=False,
            margin=dict(t=40, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Platform split
    col3, col4, col5 = st.columns(3)
    col3.metric("🐦 X (Twitter)", "65%", help="65% of posts from X")
    col4.metric("💼 LinkedIn", "35%", help="35% from LinkedIn")
    col5.metric("😠 Most Viral Topic", "Credit Declines", help="Highest average shares")

# ---------------------------------------------------------------------------
# Example queries
# ---------------------------------------------------------------------------
examples = get_examples("/api/sentiment/examples")
if examples:
    with st.expander("💡 Example queries — click to use", expanded=False):
        cols = st.columns(2)
        for i, example in enumerate(examples):
            if cols[i % 2].button(example, key=f"sent_ex_{i}", use_container_width=True):
                st.session_state.sentiment_prefill = example

st.markdown("---")

# ---------------------------------------------------------------------------
# Chat interface
# ---------------------------------------------------------------------------
for entry in st.session_state.sentiment_history:
    with st.chat_message("user"):
        st.write(entry["query"])
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(entry["answer"])
        if entry.get("latency_ms"):
            st.caption(f"⏱ {entry['latency_ms']}ms")

prefill = st.session_state.pop("sentiment_prefill", "")
query = st.chat_input("Ask about customer sentiment...", key="sentiment_input")
if not query and prefill:
    query = prefill

if query:
    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("📡 Fetching posts and analysing sentiment..."):
                _t0 = time.time()
                result = query_agent(
                    "/api/sentiment/query",
                    query,
                    session_id=st.session_state.sentiment_session_id,
                )
                _client_ms = round((time.time() - _t0) * 1000)

        if "error" in result:
            st.error(f"❌ {result['error']}")
        else:
            st.markdown(result.get("answer", "No response"))
            render_response_footer(
                result,
                client_ms=_client_ms,
                session_id=st.session_state.sentiment_session_id,
            )
            st.session_state.sentiment_history.append({
                "query": query,
                "answer": result.get("answer", ""),
                "latency_ms": result.get("latency_ms"),
            })

with st.sidebar:
    st.markdown("### 📊 Sentiment Controls")
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.sentiment_history = []
        st.session_state.sentiment_session_id = str(uuid.uuid4())
        st.rerun()
    st.markdown("---")
    st.markdown("**Data source:** `social_posts` table")
    st.markdown("**400 synthetic posts** (X + LinkedIn)")
    st.markdown("**Platforms:** X (Twitter) · LinkedIn")
    st.markdown("**Topics:** Credit · Fraud · Service · App · Fees")
