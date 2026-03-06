"""Speech / Whisper router — /api/speech endpoints."""

import base64
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.speech_agent import speech_graph
from app.routers._agent_utils import invoke_agent
from app.schemas.responses import AgentRequest, AgentResponse
from app.config import settings
from openai import AsyncOpenAI

_openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


class TTSRequest(BaseModel):
    text: str
    voice: str = "alloy"        # alloy | echo | fable | onyx | nova | shimmer
    model: str = "tts-1"        # tts-1 (fast) | tts-1-hd (higher quality)

router = APIRouter(prefix="/api/speech", tags=["Speech & CX Insights"])


@router.post("/query", response_model=AgentResponse, summary="Analyse existing transcript with NL")
async def query_speech(request: AgentRequest) -> AgentResponse:
    """
    Submit a natural language question about call transcripts.
    Use this to browse and analyse stored transcripts.

    **Example queries:**
    - "List available recorded calls"
    - "Analyse call abc-123 and identify customer pain points"
    - "Which calls had the lowest CX score?"
    """
    try:
        result = await invoke_agent(
            graph=speech_graph,
            query=request.query,
            session_id=request.session_id,
            use_case="speech",
        )
        return AgentResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {exc}",
        )


@router.post(
    "/transcribe",
    response_model=AgentResponse,
    summary="Upload audio file → transcribe with Whisper → generate CX insights",
)
async def transcribe_and_analyse(
    file: UploadFile = File(..., description="Audio file (.mp3, .wav, .m4a, .webm)"),
    analysis_prompt: str = Form(
        default="Transcribe this call and identify customer pain points and process improvement opportunities.",
        description="What to analyse after transcription",
    ),
    session_id: str | None = Form(default=None),
) -> AgentResponse:
    """
    Upload an audio recording of a customer support call.
    The pipeline:
    1. Reads the audio file
    2. Calls OpenAI Whisper API to transcribe
    3. Passes transcript to GPT-4o for CX analysis
    4. Returns structured insights: pain points, recommendations, CX score

    Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm (OpenAI Whisper limits)
    Max file size: 25MB (OpenAI Whisper limit)
    """
    allowed_content_types = {
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
        "audio/m4a", "audio/x-m4a", "audio/mp4", "audio/webm",
        "video/webm",  # webm from browser recording
    }
    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio format: {file.content_type}. "
                   f"Supported: mp3, wav, m4a, webm",
        )

    audio_bytes = await file.read()
    if len(audio_bytes) > 25 * 1024 * 1024:  # 25MB
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file exceeds 25MB limit (OpenAI Whisper restriction).",
        )

    # ── Step 1: Transcribe via Whisper directly (NOT via LLM agent).
    # Passing base64 audio through GPT-4o's context window causes token explosions
    # (a 5-minute WAV ≈ 900k+ tokens). Whisper is a separate audio API — no token cost.
    from app.tools.whisper_tools import transcribe_audio as _transcribe_tool
    audio_b64 = base64.b64encode(audio_bytes).decode()
    try:
        transcript: str = await _transcribe_tool.ainvoke(
            {"audio_bytes_b64": audio_b64, "filename": file.filename or "audio.mp3"}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Whisper transcription error: {exc}",
        )

    # ── Step 2: Safety-truncate the transcript text before sending to GPT-4o.
    # ~12 000 chars ≈ 3 000 tokens — well within the 30 000 TPM limit.
    MAX_CHARS = 12_000
    if len(transcript) > MAX_CHARS:
        transcript = transcript[:MAX_CHARS] + "\n\n[Transcript truncated to fit token limits]"

    # ── Step 3: Send ONLY the text transcript to GPT-4o for CX analysis.
    query = (
        f"The following call has already been transcribed by Whisper. "
        f"Please analyse it.\n\n"
        f"---TRANSCRIPT START---\n{transcript}\n---TRANSCRIPT END---\n\n"
        f"{analysis_prompt}"
    )

    try:
        result = await invoke_agent(
            graph=speech_graph,
            query=query,
            session_id=session_id,
            use_case="speech-transcribe",
        )
        return AgentResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription/analysis error: {exc}",
        )


@router.get("/calls", summary="List available call transcripts")
async def list_calls() -> dict:
    """Return a list of available call transcripts for the demo dropdown."""
    from app.tools.whisper_tools import list_available_transcripts
    import json
    result = await list_available_transcripts.ainvoke({})
    return json.loads(result)


@router.get("/examples", summary="Get example queries for the speech use case")
async def get_speech_examples() -> dict:
    return {
        "examples": [
            "List all available recorded calls",
            "Analyse the call with the lowest CX score",
            "What are the most common customer complaints across all calls?",
            "Which agent handles credit application queries best?",
            "Show me all escalated calls and what went wrong",
            "What process improvements would reduce call abandonment?",
        ]
    }


@router.post(
    "/transcribe-text",
    summary="Transcribe audio to text via Whisper (no analysis)",
)
async def transcribe_to_text(
    file: UploadFile = File(..., description="Audio file from browser mic recorder (.wav, .webm, .mp3)"),
) -> dict:
    """
    Lightweight Whisper-only endpoint — returns the raw transcript text
    without running any GPT-4o analysis.
    Used by the frontend voice query input to convert a spoken question
    into text before sending it to the main query agent.
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio exceeds 25 MB Whisper limit.")

    from app.tools.whisper_tools import transcribe_audio as _transcribe_tool
    audio_b64 = base64.b64encode(audio_bytes).decode()
    filename = file.filename or "recording.wav"
    try:
        transcript: str = await _transcribe_tool.ainvoke(
            {"audio_bytes_b64": audio_b64, "filename": filename}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Whisper error: {exc}",
        )
    return {"transcript": transcript.strip()}


async def _stream_tts(text: str, model: str, voice: str):
    """Async generator that pipes OpenAI TTS chunks to the client as they arrive."""
    async with _openai_client.audio.speech.with_streaming_response.create(
        model=model,
        voice=voice,
        input=text,
        response_format="mp3",
    ) as response:
        async for chunk in response.iter_bytes(chunk_size=4096):
            yield chunk


@router.post("/tts", summary="Convert text to speech using OpenAI TTS")
async def text_to_speech(request: TTSRequest) -> StreamingResponse:
    """
    Convert a text response to audio using OpenAI TTS.
    Streams audio/mpeg chunks to the client as they arrive from OpenAI,
    so the browser can begin buffering/playback before synthesis completes.

    Voices: alloy (neutral), echo (male), fable (warm), onyx (deep), nova (female), shimmer (soft female)
    Models: tts-1 (fast, ~100ms), tts-1-hd (higher quality)

    The text is truncated to 4096 chars (OpenAI TTS limit).
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    # OpenAI TTS limit: 4096 characters
    if len(text) > 4096:
        text = text[:4090] + "..."

    try:
        return StreamingResponse(
            _stream_tts(text, request.model, request.voice),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=response.mp3",
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",      # disable nginx buffering if behind proxy
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS error: {exc}",
        )
