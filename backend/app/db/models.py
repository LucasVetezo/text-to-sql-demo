"""
SQLAlchemy ORM models — four tables matching the synthetic data schema.
Tables are created from these models via `db_init()` in the app lifespan.
"""

import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CreditApplication(Base):
    """Credit card / loan applications with assessor decline commentary."""

    __tablename__ = "credit_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    applicant_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(20))
    annual_income: Mapped[float] = mapped_column(Float)
    credit_score: Mapped[int] = mapped_column(Integer)
    employment_status: Mapped[str] = mapped_column(String(40))
    employer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    years_employed: Mapped[float | None] = mapped_column(Float, nullable=True)
    existing_debt: Mapped[float] = mapped_column(Float, default=0.0)
    loan_amount_requested: Mapped[float] = mapped_column(Float)
    loan_purpose: Mapped[str] = mapped_column(String(80))
    application_status: Mapped[str] = mapped_column(String(20))  # approved / rejected / pending
    decline_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assessor_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_date: Mapped[str] = mapped_column(String(20))
    branch: Mapped[str] = mapped_column(String(80))
    province: Mapped[str] = mapped_column(String(60))


class FraudCase(Base):
    """Fraud investigation cases with assessor commentary."""

    __tablename__ = "fraud_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    account_number: Mapped[str] = mapped_column(String(20), index=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    transaction_id: Mapped[str] = mapped_column(String(36), unique=True)
    transaction_amount: Mapped[float] = mapped_column(Float)
    transaction_date: Mapped[str] = mapped_column(String(20))
    merchant_name: Mapped[str] = mapped_column(String(120))
    merchant_category: Mapped[str] = mapped_column(String(60))
    location: Mapped[str] = mapped_column(String(120))
    fraud_flag: Mapped[str] = mapped_column(String(20))  # confirmed / suspected / cleared
    risk_score: Mapped[float] = mapped_column(Float)      # 0.0 – 1.0
    fraud_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    channel: Mapped[str] = mapped_column(String(40))      # online / ATM / POS / branch
    assessor_commentary: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_status: Mapped[str] = mapped_column(String(30))  # open / investigating / closed
    reported_date: Mapped[str] = mapped_column(String(20))


class SocialPost(Base):
    """Simulated social media posts mentioning Nedbank (X / LinkedIn mock)."""

    __tablename__ = "social_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(20))     # X / LinkedIn
    author_handle: Mapped[str] = mapped_column(String(80))
    post_text: Mapped[str] = mapped_column(Text)
    post_date: Mapped[str] = mapped_column(String(20))
    sentiment_label: Mapped[str] = mapped_column(String(20))  # positive / neutral / negative
    sentiment_score: Mapped[float] = mapped_column(Float)     # -1.0 to 1.0
    topic: Mapped[str] = mapped_column(String(60))            # credit / fraud / service / app / fees
    likes: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(10), default="en")


class CallTranscript(Base):
    """Simulated call centre transcripts (customer + agent turns)."""

    __tablename__ = "call_transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    call_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    call_date: Mapped[str] = mapped_column(String(20))
    duration_seconds: Mapped[int] = mapped_column(Integer)
    agent_name: Mapped[str] = mapped_column(String(80))
    customer_name: Mapped[str] = mapped_column(String(120))
    call_reason: Mapped[str] = mapped_column(String(120))
    transcript_text: Mapped[str] = mapped_column(Text)      # Full multi-turn transcript
    pain_points: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON list
    cx_score: Mapped[float | None] = mapped_column(Float, nullable=True)   # 1-10
    resolution_status: Mapped[str] = mapped_column(String(30))             # resolved / escalated / abandoned
    audio_file: Mapped[str | None] = mapped_column(String(200), nullable=True)  # Path to .mp3 if exists


# ── RAG: uploaded documents ────────────────────────────────────────────────────

class UploadedDocument(Base):
    """A user-uploaded file (PDF, TXT, CSV, Markdown) indexed for RAG retrieval."""

    __tablename__ = "uploaded_documents"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename:    Mapped[str] = mapped_column(String(255))
    file_type:   Mapped[str] = mapped_column(String(20))   # pdf / txt / csv / md
    full_text:   Mapped[str] = mapped_column(Text)          # raw extracted text
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, server_default=func.now()
    )


class DocumentChunk(Base):
    """One text chunk from an uploaded document, with its embedding vector."""

    __tablename__ = "document_chunks"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id:  Mapped[int] = mapped_column(
        Integer, ForeignKey("uploaded_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index:  Mapped[int] = mapped_column(Integer)           # position in document
    chunk_text:   Mapped[str] = mapped_column(Text)              # ~400-word text
    embedding:    Mapped[str] = mapped_column(Text)              # JSON list[float] (1536-dim)
