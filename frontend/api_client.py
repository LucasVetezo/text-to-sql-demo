"""
Backend API client for Streamlit pages.

Uses sync httpx (NOT async) — Streamlit has its own event loop.
All API calls go through this module — Streamlit pages never import
FastAPI code or agent code directly.
"""

import os
from typing import Any

import httpx

# Backend URL from environment (set by Docker Compose or .env)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEOUT = httpx.Timeout(120.0, connect=10.0)  # LLM calls can take time


def _client() -> httpx.Client:
    return httpx.Client(base_url=BACKEND_URL, timeout=TIMEOUT)


def check_health() -> dict[str, Any]:
    """Ping the backend health endpoint. Returns status dict or error."""
    try:
        with _client() as client:
            r = client.get("/health")
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def query_agent(endpoint: str, query: str, session_id: str | None = None) -> dict[str, Any]:
    """
    Send a natural language query to one of the agent endpoints.

    Args:
        endpoint: Path like "/api/credit/query" or "/api/fraud/query"
        query: The user's natural language question
        session_id: Optional session ID for LangSmith trace grouping

    Returns:
        AgentResponse dict with keys: answer, sql_query, table_data, latency_ms
    """
    payload = {"query": query, "session_id": session_id}
    try:
        with _client() as client:
            r = client.post(endpoint, json=payload)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.json().get("detail", str(exc)) if exc.response else str(exc)
        return {"error": detail}
    except Exception as exc:
        return {"error": str(exc)}


def get_examples(endpoint: str) -> list[str]:
    """Fetch example queries for a given use case endpoint."""
    try:
        with _client() as client:
            r = client.get(endpoint)
            r.raise_for_status()
            return r.json().get("examples", [])
    except Exception:
        return []


def list_call_transcripts() -> list[dict]:
    """Fetch available call transcripts from the backend."""
    try:
        with _client() as client:
            r = client.get("/api/speech/calls")
            r.raise_for_status()
            return r.json().get("calls", [])
    except Exception:
        return []


def upload_audio(audio_bytes: bytes, filename: str, analysis_prompt: str) -> dict[str, Any]:
    """Upload an audio file to the Whisper transcription endpoint."""
    try:
        with _client() as client:
            files = {"file": (filename, audio_bytes, "audio/mpeg")}
            data = {"analysis_prompt": analysis_prompt}
            r = client.post("/api/speech/transcribe", files=files, data=data)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.json().get("detail", str(exc)) if exc.response else str(exc)
        return {"error": detail}
    except Exception as exc:
        return {"error": str(exc)}


def transcribe_to_text(audio_bytes: bytes, filename: str = "recording.wav") -> tuple[str | None, str | None]:
    """
    Send raw audio bytes to the Whisper transcription-only endpoint.
    Returns (transcript_text, None) on success or (None, error_message) on failure.
    """
    try:
        with _client() as client:
            r = client.post(
                "/api/speech/transcribe-text",
                files={"file": (filename, audio_bytes, "audio/wav")},
            )
            if r.status_code != 200:
                try:
                    detail = r.json().get("detail", r.text)
                except Exception:
                    detail = r.text or f"HTTP {r.status_code}"
                return None, detail
            return r.json().get("transcript", ""), None
    except Exception as exc:
        return None, str(exc)


def text_to_speech(text: str, voice: str = "nova", model: str = "tts-1") -> tuple[bytes | None, str | None]:
    """
    Convert text to speech using the OpenAI TTS backend endpoint.

    Returns (mp3_bytes, None) on success, or (None, error_message) on failure.
    Voice options: alloy, echo, fable, onyx, nova, shimmer
    """
    try:
        with _client() as client:
            r = client.post(
                "/api/speech/tts",
                json={"text": text, "voice": voice, "model": model},
            )
            if r.status_code != 200:
                # Surface the real error detail from the backend JSON
                try:
                    detail = r.json().get("detail", r.text)
                except Exception:
                    detail = r.text or f"HTTP {r.status_code}"
                return None, detail
            content = r.content
            if not content:
                return None, "Backend returned empty audio response"
            return content, None
    except Exception as exc:
        return None, str(exc)
