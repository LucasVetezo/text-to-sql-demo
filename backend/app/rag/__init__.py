"""RAG (Retrieval-Augmented Generation) module.

Provides document ingestion, embedding, vector retrieval, and answer generation
for uploaded files (PDF, TXT, CSV, Markdown).

Pipeline:
  upload → extract_text → chunk_text → embed_batch → save_chunks
  query  → embed_text   → retrieve_chunks (cosine) → GPT-4o answer
"""
