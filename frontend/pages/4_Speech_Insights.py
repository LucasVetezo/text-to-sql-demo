"""
Page 4: Speech & CX Insights — Fully Voice-Oriented

Two voice layers:
  1. Voice INPUT  — record/upload audio -> Whisper transcribes -> GPT-4o analyses
  2. Voice OUTPUT — every AI response is read aloud via OpenAI TTS (audio player + auto-speak)
"""

import io
import time
import uuid

import streamlit as st

from api_client import (
    get_examples,
    list_call_transcripts,
    query_agent,
    text_to_speech,
    transcribe_to_text,
    upload_audio,
)
from components.eval_badge import render_response_footer

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "speech_history" not in st.session_state:
    st.session_state.speech_history = []
if "speech_session_id" not in st.session_state:
    st.session_state.speech_session_id = str(uuid.uuid4())
if "auto_speak" not in st.session_state:
    st.session_state.auto_speak = True
if "tts_voice" not in st.session_state:
    st.session_state.tts_voice = "nova"
if "tts_model" not in st.session_state:
    st.session_state.tts_model = "tts-1"
# Track the last processed voice recording to avoid re-submitting on reruns
if "last_voice_rec_id" not in st.session_state:
    st.session_state.last_voice_rec_id = None
# Stores the text waiting to be converted to speech.
# Set by the 🔊 button; read at the top of every render to produce audio.
if "play_text" not in st.session_state:
    st.session_state.play_text = None
if "cached_audio" not in st.session_state:
    st.session_state.cached_audio = None

# ---------------------------------------------------------------------------
# Voice helpers
# ---------------------------------------------------------------------------
# ── Persistent audio player ──────────────────────────────────────────────────
# Called ONCE at the top of every page render.
# If session state holds pending text, calls TTS and renders st.audio().
# The audio bar stays visible until the user dismisses it or asks for new audio.
def _render_audio_bar() -> None:
    if st.session_state.play_text:
        # A new TTS request was queued — call the API now
        with st.spinner("🔊 Generating audio…"):
            audio, err = text_to_speech(
                st.session_state.play_text,
                voice=st.session_state.tts_voice,
                model=st.session_state.tts_model,
            )
        st.session_state.play_text = None  # clear the request
        if audio:
            st.session_state.cached_audio = audio
        else:
            st.session_state.cached_audio = None
            st.error(
                f"❌ Voice generation failed: {err}\n\n"
                "Is the backend running on port 8000? "
                "Check the **backend** terminal for errors.",
                icon="🔇",
            )

    if st.session_state.cached_audio:
        col_player, col_x = st.columns([10, 1])
        with col_player:
            # `audio/mpeg` is the correct IANA MIME type for MP3
            # BytesIO wrapper avoids any implicit encoding issues
            st.audio(io.BytesIO(st.session_state.cached_audio), format="audio/mpeg", autoplay=True)
        with col_x:
            if st.button("✕", key="dismiss_audio", help="Dismiss audio player"):
                st.session_state.cached_audio = None
                st.rerun()


def queue_speak(text: str) -> None:
    """Queue *text* for TTS on the next render and immediately rerun."""
    st.session_state.play_text = text
    st.rerun()


def render_voice_response(answer: str, key_suffix: str = "") -> None:
    """
    Render the markdown answer + a 🔊 Listen button.
    The button queues the text for TTS and triggers a rerun so the audio bar
    at the top of the page can render st.audio() in the correct scope.
    """
    st.markdown(answer)
    col_txt, col_btn = st.columns([8, 1])
    with col_btn:
        if st.button("🔊", key=f"listen_{key_suffix}", help="Listen to this response"):
            queue_speak(answer)   # sets state + reruns — audio bar fires next render


# ---------------------------------------------------------------------------
# Page title + persistent audio bar (session state + helpers must be defined first)
# ---------------------------------------------------------------------------
st.title("🎙️ Speech & Customer Experience Insights")
st.markdown(
    "A **fully voice-oriented** CX intelligence assistant. "
    "Record your question, upload a call recording, or pick a stored call — "
    "and hear the AI analysis read back to you in real time."
)
_render_audio_bar()   # renders cached audio or processes pending TTS request

# ---------------------------------------------------------------------------
# Input mode selector
# ---------------------------------------------------------------------------
tab_upload, tab_browse, tab_chat = st.tabs([
    "🎤 Record / Upload",
    "📂 Browse Stored Calls",
    "🎤 Voice or Text",
])

# ---- Tab 1: Record / Upload ----
with tab_upload:
    st.markdown("### 🎤 Record or upload a call")
    st.info(
        "Record yourself asking a question **or** upload a call-centre audio file. "
        "Whisper transcribes it → GPT-4o analyses it → the answer is read back to you.\n\n"
        "**Supported:** MP3 · WAV · M4A · WebM (max 25 MB)",
        icon="🎙️",
    )

    audio_file = st.audio_input("Record or upload audio")
    if audio_file is None:
        # Fallback for environments without audio_input
        audio_file = st.file_uploader(
            "Or upload an audio file",
            type=["mp3", "wav", "m4a", "webm", "mp4"],
            label_visibility="collapsed",
        )

    analysis_prompt = st.text_area(
        "What would you like to analyse?",
        value="Identify customer pain points, score the CX experience out of 10, "
              "and provide 3 actionable process improvements for Nedbank's credit team.",
        height=80,
    )

    if st.button("🚀 Transcribe & Analyse", type="primary", use_container_width=True):
        if audio_file is None:
            st.warning("Please record or upload an audio file first.")
        else:
            with st.spinner("🎙️ Whisper is transcribing → GPT-4o is analysing..."):
                audio_bytes = audio_file.read() if hasattr(audio_file, "read") else bytes(audio_file)
                filename = getattr(audio_file, "name", "recording.mp3")
                result = upload_audio(audio_bytes, filename, analysis_prompt)

            if "error" in result:
                st.error(f"❌ {result['error']}")
            else:
                answer = result.get("answer", "No response")
                st.success("✅ Analysis complete!")
                st.caption(f"⏱ {result.get('latency_ms', '?')} ms")
                render_voice_response(
                    answer,
                    key_suffix=f"upload_{int(time.time())}",
                )

                st.session_state.speech_history.append({
                    "query": f"[Audio: {filename}] {analysis_prompt}",
                    "answer": answer,
                    "latency_ms": result.get("latency_ms"),
                })
                if st.session_state.auto_speak:
                    queue_speak(answer)

# ---- Tab 2: Browse Stored Calls ----
with tab_browse:
    st.markdown("### 📂 Analyse a stored call")
    st.caption("50 pre-generated synthetic recordings in the database.")

    with st.spinner("Loading transcripts..."):
        calls = list_call_transcripts()

    if not calls:
        st.warning("No transcripts available. Run `make seed` to generate data.")
    else:
        # Format display options
        options = {
            f"{c['call_date']} | {c['call_reason']} | {c['resolution_status'].upper()} | CX: {c.get('cx_score', '?')}/10": c['call_id']
            for c in calls
        }
        selected_label = st.selectbox("Select a call to analyse", list(options.keys()))
        selected_call_id = options[selected_label]

        custom_prompt = st.text_area(
            "Analysis instructions",
            value="Retrieve this transcript and provide a full CX analysis: "
                  "pain points, sentiment arc, agent performance, and process improvement recommendations.",
            height=80,
        )

        if st.button("🔍 Analyse & Speak", type="primary", use_container_width=True):
            query = f"Please analyse call_id: {selected_call_id}. {custom_prompt}"
            with st.spinner("🤔 Analysing..."):
                result = query_agent(
                    "/api/speech/query",
                    query,
                    session_id=st.session_state.speech_session_id,
                )

            if "error" in result:
                st.error(f"❌ {result['error']}")
            else:
                answer = result.get("answer", "No response")
                st.caption(f"⏱ {result.get('latency_ms', '?')} ms")
                render_voice_response(
                    answer,
                    key_suffix=f"browse_{int(time.time())}",
                )
                st.session_state.speech_history.append({
                    "query": f"Analyse call: {selected_call_id}",
                    "answer": answer,
                    "latency_ms": result.get("latency_ms"),
                })
                if st.session_state.auto_speak:
                    queue_speak(answer)

# ---- Tab 3: Voice or Text input ----
with tab_chat:
    st.markdown("### 🎤 Ask by voice or type your question")
    st.caption(
        "Record a question with your microphone **or** type it below. "
        "Responses are read aloud in the voice selected in the sidebar."
    )

    examples = get_examples("/api/speech/examples")
    if examples:
        with st.expander("💡 Example queries", expanded=True):
            cols = st.columns(2)
            for i, ex in enumerate(examples):
                if cols[i % 2].button(ex, key=f"speech_ex_{i}", use_container_width=True):
                    st.session_state.speech_prefill = ex

    # ── Voice input ──────────────────────────────────────────────────────────
    st.markdown("##### 🎤 Speak your question")
    voice_recording = st.audio_input(
        "Click the microphone to record, then click stop when done",
        key="chat_mic",
    )

    # Process a new recording exactly once (deduplicate across Streamlit reruns)
    if voice_recording is not None:
        rec_id = voice_recording.file_id
        if rec_id != st.session_state.last_voice_rec_id:
            st.session_state.last_voice_rec_id = rec_id
            with st.spinner("🎤 Transcribing your question…"):
                transcript, err = transcribe_to_text(
                    voice_recording.read(),
                    filename="question.wav",
                )
            if err:
                st.error(f"❌ Transcription failed: {err}")
            elif transcript:
                st.session_state.speech_prefill = transcript
                st.rerun()   # let the prefill flow into the query pipeline below

    st.markdown("##### ⌨️ Or type your question")
    st.markdown("---")

    for idx, entry in enumerate(st.session_state.speech_history):
        with st.chat_message("user"):
            st.write(entry["query"])
        with st.chat_message("assistant", avatar="🎙️"):
            render_voice_response(entry["answer"], key_suffix=f"hist_{idx}")
            if entry.get("latency_ms"):
                st.caption(f"⏱ {entry['latency_ms']} ms")

    prefill = st.session_state.pop("speech_prefill", "")
    query = st.chat_input("Ask about call transcripts...", key="speech_input")
    if not query and prefill:
        query = prefill

    if query:
        with st.chat_message("user"):
            st.write(query)

        with st.chat_message("assistant", avatar="🎙️"):
            with st.spinner("🎙️ Thinking..."):
                _t0 = time.time()
                result = query_agent(
                    "/api/speech/query",
                    query,
                    session_id=st.session_state.speech_session_id,
                )
                _client_ms = round((time.time() - _t0) * 1000)

            if "error" in result:
                st.error(f"❌ {result['error']}")
            else:
                answer = result.get("answer", "No response")
                render_voice_response(
                    answer,
                    key_suffix=f"chat_{_client_ms}",
                )
                render_response_footer(
                    result,
                    client_ms=_client_ms,
                    session_id=st.session_state.speech_session_id,
                )
                st.session_state.speech_history.append({
                    "query": query,
                    "answer": answer,
                    "latency_ms": result.get("latency_ms"),
                })
                # Auto-speak: queue AFTER history is saved, so the item
                # persists across the rerun that st.rerun() triggers.
                if st.session_state.auto_speak:
                    queue_speak(answer)

# ---------------------------------------------------------------------------
# Sidebar — voice settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔊 Voice Settings")

    st.session_state.auto_speak = st.toggle(
        "Auto-speak responses",
        value=st.session_state.auto_speak,
        help="Automatically read every AI response aloud after it is generated.",
    )

    VOICES = {
        "nova (female · warm)":       "nova",
        "shimmer (female · soft)":    "shimmer",
        "alloy (neutral)":            "alloy",
        "echo (male · balanced)":     "echo",
        "fable (warm · storyteller)": "fable",
        "onyx (male · deep)":         "onyx",
    }
    voice_label = st.selectbox(
        "AI voice",
        list(VOICES.keys()),
        index=list(VOICES.values()).index(st.session_state.tts_voice),
    )
    st.session_state.tts_voice = VOICES[voice_label]

    st.session_state.tts_model = st.radio(
        "Voice quality",
        ["tts-1", "tts-1-hd"],
        index=["tts-1", "tts-1-hd"].index(st.session_state.tts_model),
        horizontal=True,
        help="tts-1 is faster; tts-1-hd is higher fidelity.",
    )

    st.markdown("---")
    st.markdown("### 🎙️ Session")
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.speech_history = []
        st.session_state.speech_session_id = str(uuid.uuid4())
        st.rerun()

    st.markdown("---")
    st.markdown("**Transcription:** OpenAI Whisper")
    st.markdown("**Analysis:** GPT-4o")
    st.markdown("**Voice output:** OpenAI TTS")
    st.markdown("**50 synthetic** call transcripts in DB")
