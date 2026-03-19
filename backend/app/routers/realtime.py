"""
OpenAI Realtime API WebSocket relay — /ws/realtime

Architecture
------------
Browser  ←──WS──→  FastAPI relay  ←──WS──→  OpenAI Realtime API (gpt-4o-realtime-preview)

The relay is a fully transparent bidirectional proxy with one interception:
  response.function_call_arguments.done
    → Execute the SQL query server-side (API key never leaves the backend)
    → Return result as conversation.item.create (function_call_output)
    → Send response.create to let the model continue speaking

All other events are forwarded as-is:
  Browser → OpenAI : input_audio_buffer.append, session overrides, etc.
  OpenAI → Browser : audio deltas, transcripts, VAD events, errors, etc.

Session is fully configured on connect (voice, VAD, tools, system prompt).
The browser never sees the API key or raw function call arguments.
"""

import asyncio
import json
import logging
import ssl

import certifi
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.tools.sql_tools import _run_sql

log = logging.getLogger(__name__)

router = APIRouter(tags=["Realtime Voice"])

_OPENAI_RT_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"

# ── Tool schemas exposed to the Realtime model ────────────────────────────────
# The model decides which tool to call based on these descriptions.
# Each tool maps to one SQLite table; _TOOL_TABLE_MAP enforces this server-side.

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "query_credit_data",
        "description": (
            "Run a SELECT query against Nedbank credit application data. "
            "Table: credit_applications. "
            "Columns: application_id, branch_name, product_type, loan_amount, income, "
            "credit_score, debt_to_income_ratio, application_status, decline_reason, application_date."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Valid SELECT statement against credit_applications only.",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "type": "function",
        "name": "query_fraud_data",
        "description": (
            "Run a SELECT query against fraud transaction data. "
            "Table: fraud_transactions. "
            "Columns: transaction_id, customer_id, amount, merchant_category, "
            "fraud_flag (0/1), risk_score (0-100), transaction_date."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Valid SELECT statement against fraud_transactions only.",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "type": "function",
        "name": "query_sentiment_data",
        "description": (
            "Run a SELECT query against social media post data. "
            "Table: social_posts. "
            "Columns: id, post_text, platform, sentiment_label (positive/neutral/negative), "
            "sentiment_score, topic, likes, post_date."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Valid SELECT statement against social_posts only.",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "type": "function",
        "name": "query_cx_data",
        "description": (
            "Run a SELECT query against call centre transcript data. "
            "Table: call_transcripts. "
            "Columns: call_id, call_date, duration_seconds, agent_name, customer_name, "
            "call_reason, transcript_text, cx_score (1-10), resolution_status (resolved/unresolved)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Valid SELECT statement against call_transcripts only.",
                },
            },
            "required": ["sql"],
        },
    },
]

# Safety: each tool is only allowed to query its own table
_TOOL_TABLE_MAP: dict[str, str] = {
    "query_credit_data":    "credit_applications",
    "query_fraud_data":     "fraud_transactions",
    "query_sentiment_data": "social_posts",
    "query_cx_data":        "call_transcripts",
}

# ── Session configuration sent to OpenAI on every new connection ──────────────
_SESSION_CONFIG = {
    "type": "session.update",
    "session": {
        "modalities": ["audio", "text"],
        "instructions": (
            "You are a senior data analyst embedded in the NedCard Intelligence dashboard at Nedbank. "
            "You have live read access to four databases and must query them for every factual answer. "
            "Never guess or invent numbers — always run the relevant query tool first. "
            "\n\n"
            "Speaking style: conversational, confident, South African professional English. "
            "You are speaking aloud — not writing a report. Keep answers short: "
            "one crisp finding, one supporting number, then offer to go deeper. "
            "Say numbers naturally in words where practical: 'three hundred and twelve', not '312'. "
            "\n\n"
            "Four data domains:\n"
            "1. Credit Intelligence — loan applications, approval/decline rates, credit scores by branch.\n"
            "2. Fraud Intelligence — flagged transactions, risk scores, merchant fraud patterns.\n"
            "3. Social Sentiment — customer posts on X/LinkedIn, brand perception, complaint topics.\n"
            "4. CX & Call Centre — call transcripts, agent CX scores, resolution rates, call reasons."
        ),
        "voice": "alloy",
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        # Transcribe user speech for display in the chat thread
        "input_audio_transcription": {"model": "whisper-1"},
        # Server-side VAD — model decides when the user has finished speaking
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 600,
        },
        "tools": _TOOL_SCHEMAS,
        "tool_choice": "auto",
        "temperature": 0.7,
        "max_response_output_tokens": 1024,
    },
}


# ── Function call execution ───────────────────────────────────────────────────

async def _handle_function_call(event: dict, openai_ws) -> None:
    """
    Execute the SQL query the model requested and return the result to OpenAI.

    Flow:
      1. Parse tool name + SQL from the event
      2. Run _run_sql (same security-validated executor used by all other agents)
      3. Send conversation.item.create (function_call_output) back to OpenAI
      4. Send response.create so the model continues speaking with the data
    """
    name      = event.get("name", "")
    call_id   = event.get("call_id", "")
    arguments = event.get("arguments", "{}")

    try:
        args = json.loads(arguments)
        sql  = args.get("sql", "").strip()

        if not _TOOL_TABLE_MAP.get(name):
            output = json.dumps({"error": f"Unknown tool: {name}"})
        elif not sql:
            output = json.dumps({"error": "No SQL provided in arguments."})
        else:
            rows   = await _run_sql(sql, limit=50)   # cap at 50 rows — voice answers must be concise
            output = json.dumps({"rows": rows, "row_count": len(rows)}, default=str)

    except ValueError as exc:
        # Security: write-op rejected by _validate_sql
        output = json.dumps({"error": f"Query rejected: {exc}"})
    except Exception as exc:
        log.warning("realtime_tool_error name=%s error=%s", name, exc)
        output = json.dumps({"error": f"Query failed: {exc}"})

    # Step 1: return the function output to the model's conversation
    await openai_ws.send(json.dumps({
        "type": "conversation.item.create",
        "item": {
            "type":    "function_call_output",
            "call_id": call_id,
            "output":  output,
        },
    }))

    # Step 2: ask the model to continue its response (speak the answer)
    await openai_ws.send(json.dumps({"type": "response.create"}))


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/realtime")
async def realtime_relay(client_ws: WebSocket) -> None:
    """
    Bidirectional WebSocket relay between browser and OpenAI Realtime API.

    The browser sends standard OpenAI Realtime API client events
    (input_audio_buffer.append, etc.) and receives server events
    (response.audio.delta, conversation.item.created, etc.).

    Function calls are intercepted and executed here — the browser only
    receives a lightweight `nedcard.function_call` notification for UX purposes.
    """
    await client_ws.accept()

    openai_headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())

        async with websockets.connect(
            _OPENAI_RT_URL,
            additional_headers=openai_headers,
            ssl=ssl_ctx,
            ping_interval=20,
            ping_timeout=10,
        ) as openai_ws:

            # Configure session immediately — no round-trip needed from browser
            await openai_ws.send(json.dumps(_SESSION_CONFIG))
            log.info("realtime_session_opened")

            async def browser_to_openai() -> None:
                """Forward all browser messages directly to OpenAI."""
                try:
                    while True:
                        data = await client_ws.receive_text()
                        await openai_ws.send(data)
                except (WebSocketDisconnect, RuntimeError):
                    pass
                except Exception as exc:
                    log.debug("browser_to_openai_exit: %s", exc)

            async def openai_to_browser() -> None:
                """
                Forward OpenAI events to the browser.
                Intercept function_call_arguments.done and execute SQL instead.
                """
                try:
                    async for raw in openai_ws:
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            await client_ws.send_text(raw)
                            continue

                        etype = event.get("type", "")

                        if etype == "response.function_call_arguments.done":
                            # Execute server-side — never forward raw function call to browser
                            asyncio.create_task(_handle_function_call(event, openai_ws))
                            # Lightweight UX notification so the browser can show "Querying data…"
                            await client_ws.send_text(json.dumps({
                                "type": "nedcard.function_call",
                                "name": event.get("name", ""),
                            }))

                        else:
                            # All other events pass through transparently
                            await client_ws.send_text(json.dumps(event))

                except Exception as exc:
                    log.debug("openai_to_browser_exit: %s", exc)

            # Run both directions concurrently; either task ending closes the session
            await asyncio.gather(browser_to_openai(), openai_to_browser())

    except websockets.exceptions.WebSocketException as exc:
        log.warning("openai_ws_connect_failed: %s", exc)
        try:
            await client_ws.send_text(json.dumps({
                "type": "error",
                "error": {"message": f"Could not connect to OpenAI Realtime API: {exc}"},
            }))
        except Exception:
            pass
    except Exception as exc:
        log.warning("realtime_relay_error: %s", exc)
    finally:
        log.info("realtime_session_closed")
        try:
            await client_ws.close()
        except Exception:
            pass
