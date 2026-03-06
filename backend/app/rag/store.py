"""SQLite-backed vector store for RAG.

Embeddings are stored as JSON blobs (list[float]) in the document_chunks table.
Retrieval uses numpy cosine similarity — no external vector DB required.
"""

import json

import numpy as np
from sqlalchemy import delete, select

from app.db.models import DocumentChunk, UploadedDocument
from app.db.session import AsyncSessionLocal


# ── Write helpers ─────────────────────────────────────────────────────────────

async def save_document(
    filename: str,
    file_type: str,
    full_text: str,
    chunk_count: int,
) -> int:
    """Insert an UploadedDocument row and return its auto-generated id."""
    async with AsyncSessionLocal() as session:
        doc = UploadedDocument(
            filename=filename,
            file_type=file_type,
            full_text=full_text,
            chunk_count=chunk_count,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        return doc.id


async def save_chunks(
    doc_id: int,
    chunks: list[tuple[int, str, list[float]]],
) -> None:
    """Bulk-insert (chunk_index, chunk_text, embedding) tuples."""
    async with AsyncSessionLocal() as session:
        rows = [
            DocumentChunk(
                document_id=doc_id,
                chunk_index=idx,
                chunk_text=text,
                embedding=json.dumps(embedding),
            )
            for idx, text, embedding in chunks
        ]
        session.add_all(rows)
        await session.commit()


# ── Read helpers ──────────────────────────────────────────────────────────────

async def list_documents() -> list[dict]:
    """Return all uploaded documents ordered newest first."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UploadedDocument).order_by(UploadedDocument.uploaded_at.desc())
        )
        docs = result.scalars().all()
        return [
            {
                "id":          d.id,
                "filename":    d.filename,
                "file_type":   d.file_type,
                "chunk_count": d.chunk_count,
                "uploaded_at": str(d.uploaded_at),
            }
            for d in docs
        ]


async def delete_document(doc_id: int) -> bool:
    """Delete a document and all its chunks. Returns False if not found."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UploadedDocument).where(UploadedDocument.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return False
        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )
        await session.delete(doc)
        await session.commit()
        return True


# ── Retrieval ─────────────────────────────────────────────────────────────────

async def retrieve_chunks(
    doc_id: int,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """Return the top-k chunks from a document ranked by cosine similarity.

    Returns: list of dicts with keys: text, score (0–1), index.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )
        chunks = result.scalars().all()

    if not chunks:
        return []

    query_vec = np.array(query_embedding, dtype=np.float32)
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)

    scored: list[dict] = []
    for chunk in chunks:
        emb = np.array(json.loads(chunk.embedding), dtype=np.float32)
        emb_norm = emb / (np.linalg.norm(emb) + 1e-10)
        score = float(np.dot(query_norm, emb_norm))
        scored.append({
            "text":  chunk.chunk_text,
            "score": score,
            "index": chunk.chunk_index,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
