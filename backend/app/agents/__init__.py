"""
Agents package.
All graph singletons are compiled at import time — not per-request.
Import graphs here; the routers use these module-level singletons.
"""
from app.agents.credit_sql_agent import credit_sql_graph
from app.agents.fraud_sql_agent import fraud_sql_graph
from app.agents.sentiment_agent import sentiment_graph
from app.agents.speech_agent import speech_graph

__all__ = ["credit_sql_graph", "fraud_sql_graph", "sentiment_graph", "speech_graph"]
