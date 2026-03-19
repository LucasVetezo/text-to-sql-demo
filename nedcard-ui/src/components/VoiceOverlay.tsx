/**
 * VoiceOverlay — floating realtime voice agent button.
 *
 * Architecture
 * ────────────
 * Browser mic (PCM16, 24 kHz)
 *   → WebSocket /ws/realtime (FastAPI relay)
 *   → OpenAI gpt-4o-realtime-preview
 *   → audio deltas back through relay
 *   → AudioContext gapless playback
 *
 * Key behaviours:
 * - Server VAD: OpenAI decides when the user has finished speaking — no push-to-talk.
 * - Function calls (DB queries) are executed server-side; browser receives lightweight
 *   "nedcard.function_call" notification only.
 * - User and assistant transcripts are surfaced via the onMessage prop so they appear
 *   in the main chat thread alongside text-query messages.
 * - Mic audio is suppressed while the model is speaking to prevent echo.
 * - Two separate AudioContexts: one for capture (mic → WS), one for playback
 *   (WS → speakers) to avoid feedback and allow independent control.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Mic, MicOff, X } from 'lucide-react'
import clsx from 'clsx'

// ── Types ─────────────────────────────────────────────────────────────────────

type VoiceStatus = 'idle' | 'connecting' | 'listening' | 'speaking' | 'querying' | 'error'

interface VoiceOverlayProps {
  /** Called when a user or assistant transcript is ready — adds it to the chat thread. */
  onMessage: (role: 'user' | 'assistant', content: string) => void
}

// ── Config ────────────────────────────────────────────────────────────────────

const API_BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000') as string
const WS_URL   = API_BASE.replace(/^http/, 'ws') + '/ws/realtime'

// ── PCM helpers ───────────────────────────────────────────────────────────────

/** Float32 mic samples → Int16 PCM (little-endian) */
function floatToPcm16(float32: Float32Array): ArrayBuffer {
  const buf  = new ArrayBuffer(float32.length * 2)
  const view = new DataView(buf)
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]))
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
  }
  return buf
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
  const bytes  = new Uint8Array(buf)
  let   binary = ''
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i])
  return btoa(binary)
}

/** Base64 audio delta → Int16 PCM array */
function base64ToInt16(b64: string): Int16Array {
  const binary = atob(b64)
  const raw    = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) raw[i] = binary.charCodeAt(i)
  return new Int16Array(raw.buffer)
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function VoiceOverlay({ onMessage }: VoiceOverlayProps) {
  const [status,       setStatus]       = useState<VoiceStatus>('idle')
  const [errorMsg,     setErrorMsg]     = useState<string>('')
  const [queryingTool, setQueryingTool] = useState<string>('')
  const [barHeights,   setBarHeights]   = useState<number[]>([30, 60, 90, 60, 30])

  // Audio infrastructure
  const wsRef               = useRef<WebSocket | null>(null)
  const captureCtxRef       = useRef<AudioContext | null>(null)
  const playbackCtxRef      = useRef<AudioContext | null>(null)
  const streamRef           = useRef<MediaStream | null>(null)
  const processorRef        = useRef<ScriptProcessorNode | null>(null)
  const captureAnalyserRef  = useRef<AnalyserNode | null>(null)
  const playbackAnalyserRef = useRef<AnalyserNode | null>(null)
  const nextPlayTimeRef     = useRef<number>(0)

  // Animation
  const rafRef    = useRef<number>(0)
  const statusRef = useRef<VoiceStatus>('idle')  // readable inside audio callbacks

  useEffect(() => { statusRef.current = status }, [status])

  // ── Waveform animation ───────────────────────────────────────────────────────

  useEffect(() => {
    if (status === 'idle' || status === 'connecting' || status === 'error') {
      cancelAnimationFrame(rafRef.current)
      setBarHeights([30, 60, 90, 60, 30])
      return
    }

    const tick = () => {
      const analyser = status === 'speaking'
        ? playbackAnalyserRef.current
        : captureAnalyserRef.current

      if (analyser) {
        const data = new Uint8Array(analyser.frequencyBinCount)
        analyser.getByteFrequencyData(data)
        const step = Math.max(1, Math.floor(data.length / 5))
        setBarHeights([
          Math.max(12, (data[step * 0] / 255) * 100),
          Math.max(12, (data[step * 1] / 255) * 100),
          Math.max(12, (data[step * 2] / 255) * 100),
          Math.max(12, (data[step * 3] / 255) * 100),
          Math.max(12, (data[step * 4] / 255) * 100),
        ])
      }
      rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [status])

  // ── Audio playback ───────────────────────────────────────────────────────────

  const scheduleAudioChunk = useCallback((b64: string) => {
    const ctx = playbackCtxRef.current
    if (!ctx || ctx.state === 'closed') return

    // Decode PCM16 → Float32
    const int16  = base64ToInt16(b64)
    const float32 = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768

    const buf = ctx.createBuffer(1, float32.length, 24000)
    buf.copyToChannel(float32, 0)

    const src = ctx.createBufferSource()
    src.buffer = buf

    // Route through analyser for waveform visualisation
    const analyser = playbackAnalyserRef.current
    if (analyser) {
      src.connect(analyser)
      analyser.connect(ctx.destination)
    } else {
      src.connect(ctx.destination)
    }

    // Gapless scheduling: each chunk plays exactly where the previous one ends
    const startTime = Math.max(ctx.currentTime + 0.01, nextPlayTimeRef.current)
    src.start(startTime)
    nextPlayTimeRef.current = startTime + buf.duration
  }, [])

  // ── Cleanup ──────────────────────────────────────────────────────────────────

  const disconnect = useCallback(() => {
    cancelAnimationFrame(rafRef.current)

    processorRef.current?.disconnect()
    processorRef.current = null

    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null

    captureCtxRef.current?.close().catch(() => {})
    captureCtxRef.current = null

    playbackCtxRef.current?.close().catch(() => {})
    playbackCtxRef.current = null

    captureAnalyserRef.current  = null
    playbackAnalyserRef.current = null
    nextPlayTimeRef.current     = 0

    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
      wsRef.current.close()
    }
    wsRef.current = null

    setStatus('idle')
    setErrorMsg('')
    setQueryingTool('')
  }, [])

  // Disconnect cleanly on unmount
  useEffect(() => () => { disconnect() }, [disconnect])

  // ── Server event handler ─────────────────────────────────────────────────────

  const handleServerEvent = useCallback((event: Record<string, unknown>) => {
    const type = event.type as string

    switch (type) {

      // ── Transcripts ────────────────────────────────────────────────────────
      case 'conversation.item.input_audio_transcription.completed': {
        const text = (event.transcript as string | undefined)?.trim()
        if (text) onMessage('user', `🎙️ ${text}`)
        break
      }

      case 'response.audio_transcript.done': {
        const text = (event.transcript as string | undefined)?.trim()
        if (text) onMessage('assistant', text)
        break
      }

      // ── Audio playback ─────────────────────────────────────────────────────
      case 'response.audio.delta': {
        setStatus('speaking')
        scheduleAudioChunk(event.delta as string)
        break
      }

      // ── Turn lifecycle ─────────────────────────────────────────────────────
      case 'input_audio_buffer.speech_started': {
        // User started speaking — if model was mid-sentence, its audio will be cut
        // (OpenAI handles interruption automatically)
        if (statusRef.current !== 'speaking') setStatus('listening')
        break
      }

      case 'response.done': {
        nextPlayTimeRef.current = 0
        setStatus('listening')
        break
      }

      // ── Function call (SQL query in progress, server-side) ─────────────────
      case 'nedcard.function_call': {
        // Relay intercepted a function call — display "Querying…" indicator
        const raw = (event.name as string ?? '').replace('query_', '').replace('_data', '')
        setQueryingTool(raw.replace(/_/g, ' '))
        setStatus('querying')
        break
      }

      // ── Session / config ───────────────────────────────────────────────────
      case 'session.created':
      case 'session.updated':
        // Session is configured server-side; nothing for browser to do
        break

      // ── Errors ─────────────────────────────────────────────────────────────
      case 'error': {
        const errObj = event.error as Record<string, unknown> | undefined
        const msg = (errObj?.message as string | undefined) ?? 'Unknown error from OpenAI.'
        setErrorMsg(msg)
        setStatus('error')
        break
      }

      default:
        break
    }
  }, [onMessage, scheduleAudioChunk])

  // ── Connect ──────────────────────────────────────────────────────────────────

  const connect = useCallback(async () => {
    setStatus('connecting')
    setErrorMsg('')

    try {
      // 1. Microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 24000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      streamRef.current = stream

      // 2. Capture context — 24 kHz matches Realtime API PCM16 input format
      const captureCtx = new AudioContext({ sampleRate: 24000 })
      captureCtxRef.current = captureCtx
      if (captureCtx.state === 'suspended') await captureCtx.resume()

      const micSource = captureCtx.createMediaStreamSource(stream)

      // AnalyserNode for live waveform visualisation during listening
      const captureAnalyser = captureCtx.createAnalyser()
      captureAnalyser.fftSize = 64
      captureAnalyserRef.current = captureAnalyser
      micSource.connect(captureAnalyser)

      // ScriptProcessorNode reads PCM chunks every ~85 ms and sends to WebSocket.
      // Note: deprecated but universally supported on localhost.
      const processor = captureCtx.createScriptProcessor(2048, 1, 1)
      processorRef.current = processor
      micSource.connect(processor)
      // Must connect to destination for events to fire; outputBuffer remains silent
      // (no data is copied to outputBuffer → no mic echo through speakers)
      processor.connect(captureCtx.destination)

      // 3. Playback context — 24 kHz matches Realtime API PCM16 output format
      const playbackCtx = new AudioContext({ sampleRate: 24000 })
      playbackCtxRef.current = playbackCtx
      if (playbackCtx.state === 'suspended') await playbackCtx.resume()

      const playbackAnalyser = playbackCtx.createAnalyser()
      playbackAnalyser.fftSize = 64
      playbackAnalyserRef.current = playbackAnalyser

      // 4. WebSocket to FastAPI relay
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('listening')
        // Attach audio processor now that WS is open
        processor.onaudioprocess = (e) => {
          if (ws.readyState !== WebSocket.OPEN) return
          // Don't send mic input while model is speaking — prevents echo feedback
          if (statusRef.current === 'speaking') return

          const float32 = e.inputBuffer.getChannelData(0)
          const pcm16   = floatToPcm16(float32)
          const b64     = arrayBufferToBase64(pcm16)
          ws.send(JSON.stringify({ type: 'input_audio_buffer.append', audio: b64 }))
        }
      }

      ws.onmessage = (evt) => {
        try {
          const event = JSON.parse(evt.data as string) as Record<string, unknown>
          handleServerEvent(event)
        } catch { /* ignore malformed events */ }
      }

      ws.onerror = () => {
        setErrorMsg('WebSocket connection failed. Is the backend running on port 8000?')
        setStatus('error')
        disconnect()
      }

      ws.onclose = () => {
        if (statusRef.current !== 'idle') disconnect()
      }

    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.toLowerCase().includes('permission') || msg.toLowerCase().includes('denied')) {
        setErrorMsg('Microphone access denied. Please allow mic access and try again.')
      } else {
        setErrorMsg(msg)
      }
      setStatus('error')
      disconnect()
    }
  }, [disconnect, handleServerEvent])

  // ── Toggle: start or stop ─────────────────────────────────────────────────

  const toggle = () => {
    if (status === 'idle' || status === 'error') connect()
    else disconnect()
  }

  // ── Status display ────────────────────────────────────────────────────────

  const statusLabel: Record<VoiceStatus, string> = {
    idle:       '',
    connecting: 'Connecting…',
    listening:  'Listening',
    speaking:   'Speaking',
    querying:   `Querying ${queryingTool}…`,
    error:      errorMsg || 'Connection error',
  }

  const isActive = status !== 'idle'

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="fixed bottom-36 right-6 z-50 flex flex-col items-end gap-2 select-none pointer-events-none">

      {/* ── Status pill (visible when session is active) ─────────────────── */}
      {isActive && status !== 'connecting' && (
        <div
          className={clsx(
            'flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-medium',
            'backdrop-blur-sm border shadow-lg transition-all duration-200 pointer-events-auto',
            status === 'error'
              ? 'bg-red-950/90 border-red-700/50 text-red-300'
              : 'bg-[#0D1117]/90 border-white/10 text-white',
          )}
        >
          {/* Live waveform bars */}
          {(status === 'listening' || status === 'speaking') && (
            <div className="flex items-center gap-[2px] h-3.5">
              {barHeights.map((h, i) => (
                <div
                  key={i}
                  className="w-[3px] rounded-full bg-ned-green transition-all duration-75"
                  style={{ height: `${h}%` }}
                />
              ))}
            </div>
          )}

          {/* Query spinner */}
          {status === 'querying' && (
            <svg className="w-3 h-3 animate-spin text-ned-green flex-shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
          )}

          <span className="capitalize leading-none">{statusLabel[status]}</span>

          {/* Dismiss on error */}
          {status === 'error' && (
            <button onClick={disconnect} className="ml-1 opacity-60 hover:opacity-100 pointer-events-auto">
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      )}

      {/* ── Mic button ──────────────────────────────────────────────────────── */}
      <div className="relative pointer-events-auto">
        {/* Pulsing ring — visible while listening */}
        {status === 'listening' && (
          <span className="absolute inset-0 rounded-full bg-ned-green opacity-25 animate-ping" />
        )}

        <button
          onClick={toggle}
          aria-label={isActive ? 'End voice session' : 'Start voice session (gpt-4o Realtime)'}
          title={isActive ? 'End voice session' : 'Start voice session'}
          className={clsx(
            'relative w-14 h-14 rounded-full flex items-center justify-center',
            'shadow-xl transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-ned-green/50',
            {
              // Idle — subtle, unobtrusive
              'bg-[#161B22] border border-white/10 text-ned-muted hover:text-white hover:border-ned-green/40 hover:shadow-ned-green/10':
                status === 'idle',
              // Active (listening / speaking / querying) — vivid green
              'bg-ned-green text-white shadow-[0_4px_24px_rgba(0,123,64,0.5)]':
                isActive && status !== 'error',
              // Error — red
              'bg-red-700 hover:bg-red-600 text-white':
                status === 'error',
            }
          )}
        >
          {status === 'connecting' ? (
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
          ) : isActive ? (
            <MicOff className="w-5 h-5" />
          ) : (
            <Mic className="w-5 h-5" />
          )}
        </button>
      </div>
    </div>
  )
}
