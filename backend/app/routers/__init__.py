"""Routers package."""
from app.routers.credit_sql import router as credit_router
from app.routers.documents import router as documents_router
from app.routers.fraud_sql import router as fraud_router
from app.routers.sentiment import router as sentiment_router
from app.routers.speech import router as speech_router
from app.routers.unified import router as unified_router

__all__ = [
    "credit_router",
    "documents_router",
    "fraud_router",
    "sentiment_router",
    "speech_router",
    "unified_router",
]
