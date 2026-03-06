"""Document RAG router.

Endpoints:
  POST /api/documents/upload          – parse → chunk → embed → store → summarise
  GET  /api/documents/                – list all uploaded documents
  DELETE /api/documents/{doc_id}      – delete document + chunks
  POST /api/documents/{doc_id}/query  – RAG question-answering over a document
"""

import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.rag import store
from app.rag.embedder import embed_batch, embed_text
from app.rag.parser import AUDIO_EXTENSIONS, chunk_text, extract_audio, extract_text

router = APIRouter(prefix="/api/documents", tags=["Documents"])

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI()
    return _client


# ── System prompts ─────────────────────────────────────────────────────────────

_SUMMARY_SYSTEM = """
You are a senior financial analyst AI assistant.
You have been given the text content of an uploaded document (e.g. bank statement, assessment report, CSV data).

Your task:
1. Identify what the document is (type, time period, account holder/entity if visible).
2. Surface the 3–5 most important financial facts, figures or patterns.
3. Flag any risks, anomalies or items requiring attention.
4. Close with one sentence inviting follow-up questions about the document.

Format in clean markdown. Be precise about numbers. Never fabricate data not in the document.
""".strip()

_RAG_SYSTEM = """
You are a senior financial analyst AI.
Answer questions about an uploaded document using ONLY the retrieved context passages provided below.
Rules:
- If the answer is not in the context, say so explicitly — do not guess.
- Be precise about amounts, dates and account names.
- If multiple passages address the question, synthesise them into one coherent answer.
- Keep responses concise but complete.
""".strip()


_CALL_ANALYSIS_SYSTEM = """
You are an expert call centre quality assessor AI.
You have been given the full transcript of a recorded call between a customer care agent and a client.

Your task:
1. **Call overview**: Identify the purpose of the call, the client’s primary concern and the outcome.
2. **Client sentiment**: Describe the client’s emotional tone throughout the call (e.g. frustrated → relieved). Quote key phrases to evidence your assessment.
3. **Agent performance**: Evaluate the agent’s communication, empathy, product knowledge and adherence to call-handling standards. Note any commendable moments and areas for improvement.
4. **Compliance & risk flags**: Highlight any statements, promises or omissions that may carry compliance, reputational or operational risk.
5. **Client needs & recommended actions**: Summarise any unresolved client needs and suggest concrete follow-up actions for the assessor.

Format in clean markdown with clear section headings. Be precise and quote from the transcript to support key findings. Do not name the organisation — refer to it simply as ‘the bank’ only where context makes it necessary. Never fabricate content not in the transcript.
""".strip()


_CALL_RAG_SYSTEM = """
You are an expert call centre quality assessor AI.
Answer questions about the call recording transcript using ONLY the retrieved context passages provided below.
Rules:
- If the answer is not in the transcript context, say so explicitly — do not guess.
- Refer to speakers as 'the client' and 'the agent' unless names are stated in the transcript.
- Do not name the organisation in your response — it can be assumed from context.
- Support sentiment and quality assessments with direct quotes from the transcript.
- Keep responses clear and actionable for an assessor making a quality decision.
""".strip()


# ── Request/Response schemas ───────────────────────────────────────────────────

class DocumentQueryBody(BaseModel):
    query:      str
    session_id: str | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/upload", summary="Upload and index a document or audio file for RAG Q&A")
async def upload_document(
    file: UploadFile = File(..., description="PDF, TXT, CSV, MD or audio (MP3, WAV, M4A, OGG, WEBM, FLAC — max 25 MB)"),
):
    """
    Full ingestion pipeline:
      1. Read bytes from uploaded file
      2. Extract text — pypdf for PDFs; UTF-8 decode for text formats;
         OpenAI Whisper transcription for audio (mp3/wav/m4a/ogg/webm/flac/…)
      3. Split into ~400-word overlapping chunks
      4. Embed all chunks with text-embedding-3-small (one batched API call)
      5. Persist document + chunks in SQLite
      6. Generate a structured auto-summary with GPT-4o
      7. Return doc_id, chunk_count, word_count, summary, latency_ms
    """
    t0 = time.perf_counter()

    content = await file.read()
    filename  = file.filename or "upload"
    file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    is_audio  = file_type in AUDIO_EXTENSIONS

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Whisper hard limit is 25 MB; documents stay at 50 MB
    max_bytes = 25 * 1024 * 1024 if is_audio else 50 * 1024 * 1024
    max_label = "25 MB" if is_audio else "50 MB"
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum is {max_label} for {'audio' if is_audio else 'documents'}.",
        )

    # 1. Extract text
    try:
        if is_audio:
            full_text = await extract_audio(filename, content)
        else:
            full_text = extract_text(filename, content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {exc}")

    if not full_text.strip():
        raise HTTPException(
            status_code=422, detail="No text could be extracted from this file."
        )

    # 2. Chunk
    chunks = chunk_text(full_text)
    if not chunks:
        raise HTTPException(status_code=422, detail="Document produced no text chunks.")

    # 3. Embed (one batched call — cheaper and faster than N individual calls)
    chunk_texts_list = [c.text for c in chunks]
    embeddings = await embed_batch(chunk_texts_list)

    # 4. Persist document record
    doc_id = await store.save_document(
        filename=filename,
        file_type=file_type,
        full_text=full_text,
        chunk_count=len(chunks),
    )

    # 5. Persist chunks with their embeddings
    chunk_tuples = [(c.index, c.text, emb) for c, emb in zip(chunks, embeddings)]
    await store.save_chunks(doc_id, chunk_tuples)

    # 6. Generate auto-summary using first ~3 000 words (keeps context window manageable)
    summary_text   = " ".join(full_text.split()[:3_000])
    system_prompt  = _CALL_ANALYSIS_SYSTEM if is_audio else _SUMMARY_SYSTEM
    client = _get_client()
    summary_resp = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"Document content:\n\n{summary_text}"},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    summary = summary_resp.choices[0].message.content or "Document uploaded and indexed."

    latency_ms = round((time.perf_counter() - t0) * 1_000, 1)

    return {
        "doc_id":      doc_id,
        "filename":    filename,
        "chunk_count": len(chunks),
        "word_count":  len(full_text.split()),
        "summary":     summary,
        "latency_ms":  latency_ms,
        # AgentResponse-compatible fields so frontend can reuse the same type
        "answer":      summary,
        "agent_label": "Document Analysis",
        "sql_query":   None,
        "table_data":  None,
        "chart_data":  None,
    }


@router.get("/", summary="List uploaded documents")
async def list_documents():
    return {"documents": await store.list_documents()}


@router.delete("/{doc_id}", summary="Delete a document and all its chunks")
async def delete_document(doc_id: int):
    deleted = await store.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": True, "doc_id": doc_id}


@router.post("/{doc_id}/query", summary="Ask a question about an uploaded document")
async def query_document(doc_id: int, body: DocumentQueryBody):
    """
    RAG pipeline:
      1. Embed the user's question
      2. Cosine-similarity retrieval of top-5 chunks from the document
      3. Pass retrieved context + question to GPT-4o
      4. Return answer, latency, number of chunks used, top similarity score
    """
    t0 = time.perf_counter()
    question = body.query.strip()

    if not question:
        raise HTTPException(status_code=400, detail="query must not be empty.")

    # 1. Embed question
    query_embedding = await embed_text(question)

    # 2. Retrieve most relevant chunks
    chunks = await store.retrieve_chunks(doc_id, query_embedding, top_k=5)
    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="Document not found or contains no indexed content.",
        )

    # Determine if this document is a call recording (audio-sourced)
    docs = await store.list_documents()
    doc  = next((d for d in docs if d["id"] == doc_id), None)
    is_call = doc is not None and doc.get("file_type", "") in AUDIO_EXTENSIONS
    rag_system = _CALL_RAG_SYSTEM if is_call else _RAG_SYSTEM

    # 3. Build context string
    context = "\n\n---\n\n".join(
        f"[Passage {i + 1}]\n{c['text']}" for i, c in enumerate(chunks)
    )

    # 4. GPT-4o answer
    client = _get_client()
    resp = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": rag_system},
            {
                "role": "user",
                "content": (
                    f"Context retrieved from document:\n\n{context}"
                    f"\n\n---\n\nQuestion: {question}"
                ),
            },
        ],
        temperature=0.1,
        max_tokens=600,
    )
    answer = resp.choices[0].message.content or "No answer could be generated."

    latency_ms = round((time.perf_counter() - t0) * 1_000, 1)

    return {
        "answer":      answer,
        "latency_ms":  latency_ms,
        "chunks_used": len(chunks),
        "top_score":   round(chunks[0]["score"], 3) if chunks else None,
        "agent_label": "Document Analysis",
        "sql_query":   None,
        "table_data":  None,
        "chart_data":  None,
    }
