"""
Nedbank AI Demo — Streamlit Multi-Page Application
====================================================
Entrypoint: streamlit run app.py

Uses st.navigation() (Streamlit 1.42+ modern API) for multi-page navigation
with persistent st.session_state across page switches.
"""

import streamlit as st
from api_client import check_health

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Nedbank AI Demo",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — clean, Nedbank-adjacent green palette
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Nedbank green accent */
    :root { --nedbank-green: #009A44; }
    .stButton > button {
        background-color: #009A44;
        color: white;
        border-radius: 6px;
        border: none;
        font-weight: 600;
    }
    .stButton > button:hover { background-color: #007a35; }
    .metric-card {
        background: #f8f9fa;
        border-left: 4px solid #009A44;
        padding: 12px 16px;
        border-radius: 4px;
        margin-bottom: 8px;
    }
    .sql-block { font-size: 0.85em; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — shared across all pages
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Nedbank_Logo.svg/320px-Nedbank_Logo.svg.png",
        use_container_width=True,
    )
    st.markdown("---")
    st.markdown("### 🤖 AI Agent Platform")
    st.caption("Powered by GPT-4o + LangGraph")

    # Backend health indicator
    health = check_health()
    if health.get("status") == "ok":
        st.success(f"✅ Backend connected — {health.get('model', 'GPT-4o')}")
    else:
        st.error(f"❌ Backend offline — {health.get('detail', 'Check that `make dev` is running')}")

    st.markdown("---")

    with st.expander("ℹ️ About this demo", expanded=False):
        st.markdown(
            """
            This demo showcases 4 AI use cases built for Nedbank:

            1. **💳 Credit SQL** — Query credit application data in plain English
            2. **🔍 Fraud SQL** — Investigate fraud patterns with natural language
            3. **📊 Sentiment** — Analyse social media mentions of Nedbank
            4. **🎙️ Speech Insights** — Transform call recordings into CX insights

            **Stack:** GPT-4o · LangGraph · FastAPI · Streamlit · MLflow 3

            **Data:** All data is synthetic (Faker-generated) — no real customer
            information is used in this demo.
            """
        )

    with st.expander("🔧 Tech stack", expanded=False):
        st.markdown(
            """
            | Layer | Technology |
            |---|---|
            | LLM | OpenAI GPT-4o |
            | Agents | LangGraph (ReAct) |
            | Backend | FastAPI |
            | Frontend | Streamlit |
            | Tracing | MLflow 3 Traces |
            | Experiments | MLflow |
            | Database | SQLite → PostgreSQL |
            | Deploy | Docker → AKS |
            """
        )

    st.markdown("---")
    st.caption("🔒 Synthetic data only — no real PII")

# ---------------------------------------------------------------------------
# Navigation — modern st.navigation() API
# ---------------------------------------------------------------------------
pages = [
    st.Page("pages/1_Credit_SQL.py",         title="Credit Applications",   icon="💳"),
    st.Page("pages/2_Fraud_SQL.py",           title="Fraud Cases",           icon="🔍"),
    st.Page("pages/3_Sentiment_Analysis.py",  title="Social Sentiment",      icon="📊"),
    st.Page("pages/4_Speech_Insights.py",     title="Speech & CX Insights",  icon="🎙️"),
]

pg = st.navigation(pages)
pg.run()
