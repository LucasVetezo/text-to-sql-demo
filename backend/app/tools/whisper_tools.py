"""
Whisper transcription and speech analysis tools.
Uses the OpenAI Whisper API for audio → text, then GPT-4o for insights.
"""

import json
import io
import mlflow
from mlflow.entities import SpanType
from langchain_core.tools import tool
from openai import AsyncOpenAI
from sqlalchemy import text

from app.config import settings
from app.db.session import readonly_engine


_openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


@tool
@mlflow.trace(span_type=SpanType.TOOL, name="transcribe_audio")
async def transcribe_audio(audio_bytes_b64: str, filename: str = "audio.mp3") -> str:
    """
    Transcribe an audio file using OpenAI Whisper.
    
    Args:
        audio_bytes_b64: Base64-encoded audio file content.
        filename: Original filename (used to determine audio format).
    
    Returns:
        Transcribed text as a string with speaker-turn formatting.
    """
    import base64

    audio_data = base64.b64decode(audio_bytes_b64)
    audio_file = io.BytesIO(audio_data)
    audio_file.name = filename

    transcript = await _openai_client.audio.transcriptions.create(
        model=settings.openai_whisper_model,
        file=audio_file,
        response_format="text",
    )
    return str(transcript)


@tool
@mlflow.trace(span_type=SpanType.TOOL, name="get_transcript_from_db")
async def get_transcript_from_db(call_id: str) -> str:
    """
    Retrieve a stored call transcript from the database for analysis.
    Use this when no audio file is uploaded and the user wants to analyse
    an existing recorded call.
    
    Args:
        call_id: The unique call identifier (UUID string).
    
    Returns:
        JSON with call metadata and full transcript text.
    """
    sql = """
        SELECT call_id, call_date, duration_seconds, agent_name,
               customer_name, call_reason, transcript_text,
               cx_score, resolution_status
        FROM call_transcripts
        WHERE call_id = :call_id
        LIMIT 1
    """
    async with readonly_engine.connect() as conn:
        result = await conn.execute(text(sql), {"call_id": call_id})
        row = result.fetchone()
        if not row:
            return json.dumps({"error": f"No transcript found for call_id: {call_id}"})
        cols = list(result.keys())
    return json.dumps(dict(zip(cols, row)), indent=2)


@tool
@mlflow.trace(span_type=SpanType.TOOL, name="list_available_transcripts")
async def list_available_transcripts(limit: int = 20) -> str:
    """
    List available call transcripts in the database.
    Use this to show the user what recorded calls are available for analysis.
    
    Returns:
        JSON list of call summaries (id, date, reason, agent, resolution).
    """
    sql = f"""
        SELECT call_id, call_date, agent_name, customer_name,
               call_reason, duration_seconds, resolution_status, cx_score
        FROM call_transcripts
        ORDER BY call_date DESC
        LIMIT {limit}
    """
    async with readonly_engine.connect() as conn:
        result = await conn.execute(text(sql))
        rows = result.fetchall()
        cols = list(result.keys())
    calls = [dict(zip(cols, row)) for row in rows]
    return json.dumps({"calls": calls, "count": len(calls)}, indent=2)
