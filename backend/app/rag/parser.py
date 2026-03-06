"""Document text extractor and chunker.

Supported file types:
  Documents : PDF (.pdf), plain text (.txt, .md, .csv)
  Audio     : MP3, MP4, MPEG, MPGA, M4A, WAV, WEBM, OGG, FLAC (transcribed via Whisper)

Chunks use word-based sliding windows with configurable size and overlap.
"""

import io
import re
from dataclasses import dataclass

# All formats accepted by OpenAI Whisper
AUDIO_EXTENSIONS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg", "flac"}

# ── Chunk tuning ──────────────────────────────────────────────────────────────
CHUNK_SIZE    = 400   # target words per chunk
CHUNK_OVERLAP = 50    # words shared between consecutive chunks


@dataclass
class TextChunk:
    index:      int
    text:       str
    word_count: int


# ── Parsers ───────────────────────────────────────────────────────────────────

def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n\n".join(pages)


def _extract_plain(content: bytes) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


# ── Public API ────────────────────────────────────────────────────────────────

def extract_text(filename: str, content: bytes) -> str:
    """Route to the right parser based on file extension (documents only)."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    if ext == "pdf":
        return _extract_pdf(content)
    return _extract_plain(content)   # txt, md, csv, unknown


async def extract_audio(filename: str, content: bytes) -> str:
    """Transcribe an audio file via OpenAI Whisper and return the transcript text.

    Supports all Whisper-accepted formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg, flac.
    The returned string is treated as the document text for chunking and RAG.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI()

    # BytesIO with a .name attribute so the SDK can detect the correct MIME type
    audio_io = io.BytesIO(content)
    audio_io.name = filename  # type: ignore[attr-defined]

    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_io,
        response_format="text",
    )
    # response_format="text" returns a plain string
    return transcript if isinstance(transcript, str) else str(transcript)


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Split text into overlapping word-based chunks.

    Normalises excessive whitespace and returns a list of TextChunk objects.
    """
    # Collapse 3+ blank lines → 2
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    words = text.split()

    if not words:
        return []

    chunks: list[TextChunk] = []
    start = 0
    idx = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunks.append(TextChunk(
            index=idx,
            text=" ".join(chunk_words),
            word_count=len(chunk_words),
        ))
        if end == len(words):
            break
        start = end - overlap
        idx += 1

    return chunks
