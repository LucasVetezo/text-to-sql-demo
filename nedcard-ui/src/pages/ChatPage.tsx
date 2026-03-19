import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, RotateCcw, LogOut, Mic, Paperclip, X } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../context/AuthContext'
import { useChatHistory } from '../context/ChatHistoryContext'
import { queryAgent, queryDocument, uploadDocument } from '../lib/api'
import MessageBubble from '../components/MessageBubble'
import DynamicChart from '../components/DynamicChart'
import VoiceOverlay from '../components/VoiceOverlay'
import type { ChatMessage } from '../types'

// ── Display-only domain metadata (backend /api/unified/query handles routing) ──
// These signals are ONLY used to pick a badge label and thinking-step text.
// They do NOT determine which agent is called — that is the backend's job.
interface DisplayMeta { label: string; color: string; thinkLabel: string }

interface OverviewData {
  card_apps:  { total: number }
  fraud:      { confirmed: number; non_fraud: number }
  sentiment:  { positive: number; negative: number; neutral: number }
  cx:         { good: number; bad: number }
}

const DISPLAY_SIGNALS: Array<{ test: RegExp } & DisplayMeta> = [
  {
    test: /fraud|transact|suspicious|flagg|risk.?score|merchant|dispute|stolen|phish/i,
    label: 'Fraud Intelligence', color: '#E07060', thinkLabel: 'Scanning fraud records…',
  },
  {
    // Genuine social/sentiment domain signals only — visual intent words excluded
    test: /sentiment|social|twitter|x\.com|linkedin|post|review|feedback|brand|complaint|public opinion/i,
    label: 'Social Sentiment', color: '#7EB8DF', thinkLabel: 'Analysing social data…',
  },
  {
    test: /call.?cent|speech|transcript|cx|customer.?experience|voice|recording|agent.?(score|rating)/i,
    label: 'CX & Speech', color: '#BF9FDF', thinkLabel: 'Retrieving call transcripts…',
  },
]

const fmt = (n: number | undefined) => n == null ? '—' : n.toLocaleString()

function getDisplayMeta(q: string): DisplayMeta {
  const match = DISPLAY_SIGNALS.find(s => s.test.test(q))
  return match ?? { label: 'Credit Intelligence', color: '#00C66A', thinkLabel: 'Querying credit data…' }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function genId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

const BASE_CHAR_MS   = 18   // ~55 chars/sec — smooth reading pace
const SENTENCE_PAUSE = 210  // pause after  . ! ?
const CLAUSE_PAUSE   = 90   // pause after  , ; :
const LINE_PAUSE     = 130  // pause after  \n
const HISTORY_KEY = '/api/unified/query'

// Thinking step labels; index 1 is overridden with the detected domain message
const THINKING_STEPS = [
  { text: 'Routing your question…' },
  { text: 'Querying data…' },          // replaced dynamically
  { text: 'Interpreting results…' },
  { text: 'Composing your answer…' },
]

// ── Component ──────────────────────────────────────────────────────────────────
export default function ChatPage() {
  const { user, logout } = useAuth()
  const navigate          = useNavigate()
  const { getHistory, setHistory } = useChatHistory()

  const [messages,        setMessages]        = useState<ChatMessage[]>(() => getHistory(HISTORY_KEY))
  const [input,           setInput]           = useState('')
  const [loading,         setLoading]         = useState(false)
  const [thinkingMeta,    setThinkingMeta]    = useState<DisplayMeta | null>(null)
  const [thinkingStep,    setThinkingStep]    = useState(0)
  const [streamedContent, setStreamedContent] = useState<Record<string, string>>({})
  const [domainMeta,      setDomainMeta]      = useState<Record<string, DisplayMeta>>({})
  const [chartData,       setChartData]       = useState<Record<string, unknown>>({})
  const [recording,       setRecording]       = useState(false)
  const [recordingMs,     setRecordingMs]     = useState(0)
  const [attachedFile,    setAttachedFile]    = useState<File | null>(null)
  const [activeDocId,     setActiveDocId]     = useState<number | null>(null)
  const [activeDocName,   setActiveDocName]   = useState<string | null>(null)
  const [speakingId,      setSpeakingId]      = useState<string | null>(null)
  const [overview,        setOverview]        = useState<OverviewData | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef   = useRef<Blob[]>([])
  const fileInputRef     = useRef<HTMLInputElement>(null)

  const streamingIds   = useRef<Set<string>>(new Set())
  const thinkingTimer  = useRef<ReturnType<typeof setInterval> | null>(null)
  const activeSpeaker  = useRef<HTMLAudioElement | null>(null)
  const bottomRef      = useRef<HTMLDivElement>(null)
  const inputRef       = useRef<HTMLTextAreaElement>(null)
  const sessionId      = useRef(genId())

  // ── Persist messages
  useEffect(() => { setHistory(HISTORY_KEY, messages) }, [messages, setHistory])

  // ── Scroll to latest
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, streamedContent, chartData])

  // ── Fetch At-a-Glance overview metrics
  useEffect(() => {
    fetch('/api/overview')
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setOverview(d))
      .catch(() => {})
  }, [])

  // ── Auto-resize textarea
  useEffect(() => {
    const ta = inputRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }, [input])

  // ── Speak a message aloud via TTS (Nova voice)
  // Uses streaming MediaSource so playback starts as soon as the first audio
  // chunks arrive from OpenAI — eliminates the ~8-10s "full-synthesis" wait.
  const handleSpeak = async (msgId: string, text: string) => {
    // Stop any currently playing audio
    if (activeSpeaker.current) {
      activeSpeaker.current.pause()
      activeSpeaker.current = null
      if (speakingId === msgId) { setSpeakingId(null); return }
    }
    setSpeakingId(msgId)

    const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

    try {
      const resp = await fetch(`${API_BASE}/api/speech/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice: 'nova', model: 'tts-1' }),
      })

      if (!resp.ok || !resp.body) throw new Error('TTS request failed')

      // ── Streaming path (Chrome / Firefox / Edge) ─────────────────────────
      if (typeof MediaSource !== 'undefined' && MediaSource.isTypeSupported('audio/mpeg')) {
        const mediaSource = new MediaSource()
        const audioUrl    = URL.createObjectURL(mediaSource)
        const audio       = new Audio(audioUrl)
        activeSpeaker.current = audio

        const cleanup = () => {
          URL.revokeObjectURL(audioUrl)
          setSpeakingId(null)
          activeSpeaker.current = null
        }
        audio.onended = cleanup
        audio.onerror = cleanup

        mediaSource.addEventListener('sourceopen', async () => {
          const sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg')
          const reader       = resp.body!.getReader()

          // Start playing immediately — browser buffers as chunks arrive
          audio.play().catch(() => setSpeakingId(null))

          const waitForUpdate = () =>
            new Promise<void>(r =>
              sourceBuffer.addEventListener('updateend', () => r(), { once: true })
            )

          try {
            while (true) {
              const { done, value } = await reader.read()
              if (done) {
                if (mediaSource.readyState === 'open') mediaSource.endOfStream()
                break
              }
              if (sourceBuffer.updating) await waitForUpdate()
              sourceBuffer.appendBuffer(value)
              await waitForUpdate()
            }
          } catch {
            // Stream was interrupted (user pressed stop, navigated away, etc.)
          }
        }, { once: true })

      } else {
        // ── Fallback: collect full Blob then play (Safari) ─────────────────
        const arrayBuffer = await resp.arrayBuffer()
        const blob  = new Blob([arrayBuffer], { type: 'audio/mpeg' })
        const url   = URL.createObjectURL(blob)
        const audio = new Audio(url)
        activeSpeaker.current = audio
        audio.onended = () => { URL.revokeObjectURL(url); setSpeakingId(null); activeSpeaker.current = null }
        audio.onerror = () => { setSpeakingId(null); activeSpeaker.current = null }
        await audio.play()
      }
    } catch {
      setSpeakingId(null)
    }
  }

  // ── Cycle thinking steps while waiting
  useEffect(() => {
    if (loading) {
      setThinkingStep(0)
      thinkingTimer.current = setInterval(() => {
        setThinkingStep(s => (s + 1) % THINKING_STEPS.length)
      }, 1400)
    } else {
      if (thinkingTimer.current) clearInterval(thinkingTimer.current)
    }
    return () => { if (thinkingTimer.current) clearInterval(thinkingTimer.current) }
  }, [loading])

  // ── Typewriter reveal — punctuation-aware, fluid pacing
  function startStreaming(id: string, fullText: string) {
    streamingIds.current.add(id)
    let pos = 0
    setStreamedContent(prev => ({ ...prev, [id]: '' }))

    function tick() {
      pos += 1
      const slice = fullText.slice(0, pos)
      setStreamedContent(prev => ({ ...prev, [id]: slice }))

      if (pos >= fullText.length) {
        streamingIds.current.delete(id)
        return
      }

      // Vary delay based on the character we just revealed
      const ch = fullText[pos - 1]
      const delay =
        (ch === '.' || ch === '!' || ch === '?') ? SENTENCE_PAUSE
        : (ch === ',' || ch === ';' || ch === ':') ? CLAUSE_PAUSE
        : ch === '\n'                              ? LINE_PAUSE
        : BASE_CHAR_MS

      setTimeout(tick, delay)
    }

    setTimeout(tick, BASE_CHAR_MS)
  }

  // ── Recording duration timer
  useEffect(() => {
    if (!recording) { setRecordingMs(0); return }
    const t = setInterval(() => setRecordingMs(ms => ms + 1), 1000)
    return () => clearInterval(t)
  }, [recording])

  // ── Voice recording ──────────────────────────────────────────────────────
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioChunksRef.current = []
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mr.ondataavailable = e => { if (e.data.size > 0) audioChunksRef.current.push(e.data) }
      mr.onstop = () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        const file = new File([blob], `voice-recording-${Date.now()}.webm`, { type: 'audio/webm' })
        setAttachedFile(file)
        inputRef.current?.focus()
      }
      mr.start()
      mediaRecorderRef.current = mr
      setRecording(true)
    } catch {
      // microphone permission denied or unavailable
    }
  }, [])

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current = null
    setRecording(false)
  }, [])

  const toggleRecording = useCallback(() => {
    if (recording) stopRecording()
    else startRecording()
  }, [recording, startRecording, stopRecording])

  // ── File attach ──────────────────────────────────────────────────────────
  const handleFileChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null
    setAttachedFile(file)
    e.target.value = '' // allow re-selecting same file
  }, [])

  // ── Internal helper: RAG Q&A against an already-uploaded document ────────────
  async function submitDocQuery(docId: number, question: string) {
    const docMeta: DisplayMeta = { label: 'Document Analysis', color: '#C9A84C', thinkLabel: 'Searching document…' }
    setThinkingMeta(docMeta)
    try {
      const result = await queryDocument(docId, question, sessionId.current)
      const id = genId()
      const aiMsg: ChatMessage = {
        id,
        role: 'assistant',
        content: result.answer ?? 'No answer found in document.',
        timestamp: new Date(),
        latency_ms: result.latency_ms,
      }
      setMessages(prev => [...prev, aiMsg])
      setDomainMeta(prev => ({ ...prev, [id]: docMeta }))
      startStreaming(id, aiMsg.content)
    } catch (err) {
      setMessages(prev => [...prev, {
        id: genId(), role: 'assistant',
        content: `❌ **Document query failed:** ${err instanceof Error ? err.message : 'Unknown error'}`,
        timestamp: new Date(),
      }])
    }
  }

  // ── Submit — three paths: file upload → active-doc RAG → normal unified ─────
  async function submit(query: string) {
    // PATH A — file is attached: upload → index → auto-summary (+ optional question)
    if (attachedFile) {
      if (loading) return
      const file = attachedFile
      setAttachedFile(null)
      setLoading(true)

      const userLabel = query.trim()
        ? `📎 ${file.name}\n${query.trim()}`
        : `📎 ${file.name}`
      setMessages(prev => [...prev, {
        id: genId(), role: 'user', content: userLabel, timestamp: new Date(),
      }])
      setInput('')
      setThinkingMeta({ label: 'Document Analysis', color: '#C9A84C', thinkLabel: 'Parsing & indexing document…' })

      try {
        const result = await uploadDocument(file)
        setActiveDocId(result.doc_id)
        setActiveDocName(result.filename)

        if (query.trim()) {
          // User asked a specific question — skip the auto-summary and answer directly via RAG.
          // The full call-analysis report is available on demand; don't duplicate responses.
          await submitDocQuery(result.doc_id, query.trim())
        } else {
          // No question typed — show the auto-summary (full call analysis / document overview).
          const id = genId()
          const aiMsg: ChatMessage = {
            id,
            role: 'assistant',
            content: result.summary,
            timestamp: new Date(),
            latency_ms: result.latency_ms,
          }
          setMessages(prev => [...prev, aiMsg])
          setDomainMeta(prev => ({
            ...prev,
            [id]: { label: 'Document Analysis', color: '#C9A84C', thinkLabel: '' },
          }))
          startStreaming(id, result.summary)
        }
      } catch (err) {
        setMessages(prev => [...prev, {
          id: genId(), role: 'assistant',
          content: `❌ **Upload failed:** ${err instanceof Error ? err.message : 'Could not upload document.'}`,
          timestamp: new Date(),
        }])
      } finally {
        setLoading(false)
      }
      return
    }

    // PATH B — active document: route question through RAG
    if (activeDocId !== null && query.trim()) {
      if (loading) return
      setLoading(true)
      setMessages(prev => [...prev, {
        id: genId(), role: 'user', content: query.trim(), timestamp: new Date(),
      }])
      setInput('')
      try {
        await submitDocQuery(activeDocId, query.trim())
      } finally {
        setLoading(false)
      }
      return
    }

    // PATH C — normal unified agent query
    const q = query.trim()
    if (!q || loading) return

    const meta = getDisplayMeta(q)
    setThinkingMeta(meta)
    setMessages(prev => [...prev, {
      id: genId(), role: 'user', content: q, timestamp: new Date(),
    }])
    setInput('')
    setLoading(true)

    try {
      // Send last 10 messages (5 turns) as context so agents can follow up
      const historySnapshot = messages.slice(-10).map(m => ({
        role: m.role as 'user' | 'assistant',
        content: (m.role === 'assistant'
          ? (streamedContent[m.id] ?? m.content)
          : m.content) as string,
      }))
      const result = await queryAgent('/api/unified/query', q, sessionId.current, historySnapshot)
      const id = genId()
      const aiMsg: ChatMessage = {
        id,
        role: 'assistant',
        content: result.answer ?? 'No response received.',
        timestamp: new Date(),
        latency_ms: result.latency_ms,
        sql_query:  result.sql_query,
        table_data: result.table_data ?? null,
      }
      setMessages(prev => [...prev, aiMsg])
      if (result.agent_label) setDomainMeta(prev => ({ ...prev, [id]: meta }))
      if (result.chart_data)  setChartData(prev => ({ ...prev, [id]: result.chart_data }))
      startStreaming(id, aiMsg.content)
    } catch (err) {
      setMessages(prev => [...prev, {
        id: genId(), role: 'assistant',
        content: `❌ **Error:** ${err instanceof Error ? err.message : 'Could not reach the backend. Is the server running on port 8000?'}`,
        timestamp: new Date(),
      }])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (attachedFile || input.trim()) submit(input)
    }
  }

  function handleLogout() { logout(); navigate('/login') }

  function clearConversation() {
    stopRecording()
    setAttachedFile(null)
    setActiveDocId(null)
    setActiveDocName(null)
    setMessages([])
    setHistory(HISTORY_KEY, [])
    setInput('')
    setStreamedContent({})
    setDomainMeta({})
    setChartData({})
  }

  /** Add a voice-agent transcript message to the chat thread. */
  const handleVoiceMessage = useCallback(
    (role: 'user' | 'assistant', content: string) => {
      const msg: ChatMessage = {
        id:        crypto.randomUUID(),
        role,
        content,
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, msg])
    },
    [],
  )

  // Build thinking step text (override index 1 with domain-specific label)
  function currentThinkStep() {
    const step = { ...THINKING_STEPS[thinkingStep] }
    if (thinkingStep === 1 && thinkingMeta) step.text = thinkingMeta.thinkLabel
    return step
  }

  const isEmpty = messages.length === 0

  // User initials for avatar
  const initials = (user?.name ?? 'U')
    .split(' ')
    .map(n => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className="h-screen flex flex-col bg-ned-dark overflow-hidden">

      {/* ── Top bar ─────────────────────────────────────────────── */}
      <header className="flex-shrink-0 h-16 flex items-center justify-between px-6
                         bg-ned-dark2 border-b border-white/[0.06] z-10">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-ned-green flex items-center justify-center">
            <span className="text-white font-black text-sm leading-none">N</span>
          </div>
          <div>
            <p className="text-white font-bold text-sm leading-none tracking-tight">NedCard</p>
            <p className="text-ned-muted text-[9px] tracking-widest uppercase leading-none mt-0.5">
              Intelligence
            </p>
          </div>
        </div>

        {/* Live status */}
        <div className="hidden sm:flex items-center gap-1.5 text-ned-muted text-[11px]">
          <span className="w-1.5 h-1.5 rounded-full bg-ned-green" style={{ boxShadow: '0 0 5px #00C66A' }} />
          All systems operational
        </div>

        {/* User + logout */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:block text-right">
            <p className="text-white text-xs font-semibold leading-none">{user?.name}</p>
            <p className="text-ned-muted text-[10px] leading-none mt-0.5 capitalize">{user?.role}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600
                          flex items-center justify-center text-white text-[11px] font-bold
                          flex-shrink-0">
            {initials}
          </div>
          <button
            onClick={handleLogout}
            className="w-8 h-8 rounded-xl flex items-center justify-center
                       text-ned-muted hover:text-white hover:bg-white/10
                       transition-all duration-200 flex-shrink-0"
            title="Log out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* ── Message list ────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto chat-scroll">

          {isEmpty ? (
            /* ── Empty state: At-a-Glance + hero ──────────── */
            <div className="max-w-4xl mx-auto px-4 py-8">

              {/* At a Glance cards */}
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.45 }}
                className="mb-8"
              >
                <p className="text-ned-muted text-[11px] font-semibold tracking-widest uppercase mb-3">
                  At a Glance
                </p>
                <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">

                  {/* Card Applications */}
                  <div className="rounded-2xl border border-white/[0.08] bg-ned-slate/40 p-4">
                    <p className="text-ned-muted text-[11px] font-medium uppercase tracking-wide mb-1">Card Applications</p>
                    <p className="text-white text-3xl font-bold">{fmt(overview?.card_apps.total)}</p>
                    <p className="text-ned-muted text-xs mt-1">Total volume</p>
                  </div>

                  {/* Fraud */}
                  <div className="rounded-2xl border border-white/[0.08] bg-ned-slate/40 p-4">
                    <p className="text-ned-muted text-[11px] font-medium uppercase tracking-wide mb-2">Application Fraud</p>
                    <div className="flex items-center gap-3">
                      <div>
                        <p className="text-red-400 text-xl font-bold">{fmt(overview?.fraud.confirmed)}</p>
                        <p className="text-ned-muted text-[10px] mt-0.5">Confirmed</p>
                      </div>
                      <div className="w-px h-8 bg-white/10" />
                      <div>
                        <p className="text-ned-lite text-xl font-bold">{fmt(overview?.fraud.non_fraud)}</p>
                        <p className="text-ned-muted text-[10px] mt-0.5">Non-Fraud</p>
                      </div>
                    </div>
                  </div>

                  {/* Sentiment */}
                  <div className="rounded-2xl border border-white/[0.08] bg-ned-slate/40 p-4">
                    <p className="text-ned-muted text-[11px] font-medium uppercase tracking-wide mb-2">Social Sentiment</p>
                    <div className="flex items-center gap-2 flex-wrap">
                      <div>
                        <p className="text-ned-lite text-lg font-bold">{fmt(overview?.sentiment.positive)}</p>
                        <p className="text-ned-muted text-[10px] mt-0.5">Positive</p>
                      </div>
                      <div className="w-px h-6 bg-white/10" />
                      <div>
                        <p className="text-red-400 text-lg font-bold">{fmt(overview?.sentiment.negative)}</p>
                        <p className="text-ned-muted text-[10px] mt-0.5">Negative</p>
                      </div>
                      <div className="w-px h-6 bg-white/10" />
                      <div>
                        <p className="text-white/60 text-lg font-bold">{fmt(overview?.sentiment.neutral)}</p>
                        <p className="text-ned-muted text-[10px] mt-0.5">Neutral</p>
                      </div>
                    </div>
                  </div>

                  {/* Customer Experience */}
                  <div className="rounded-2xl border border-white/[0.08] bg-ned-slate/40 p-4">
                    <p className="text-ned-muted text-[11px] font-medium uppercase tracking-wide mb-2">Customer Experience</p>
                    <div className="flex items-center gap-3">
                      <div>
                        <p className="text-ned-lite text-xl font-bold">{fmt(overview?.cx.good)}</p>
                        <p className="text-ned-muted text-[10px] mt-0.5">Good</p>
                      </div>
                      <div className="w-px h-8 bg-white/10" />
                      <div>
                        <p className="text-red-400 text-xl font-bold">{fmt(overview?.cx.bad)}</p>
                        <p className="text-ned-muted text-[10px] mt-0.5">Bad</p>
                      </div>
                    </div>
                  </div>

                </div>
              </motion.div>

              {/* Hero */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: 'easeOut', delay: 0.15 }}
                className="flex flex-col items-center justify-center text-center gap-5 py-6"
              >
                {/* Icon with pulsing glow */}
                <div className="relative flex items-center justify-center">
                  <motion.span
                    animate={{ opacity: [0.15, 0.45, 0.15], scale: [1, 1.18, 1] }}
                    transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                    className="absolute w-36 h-36 rounded-full bg-ned-green/30 pointer-events-none"
                  />
                  <motion.div
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.01, duration: 0.4 }}
                    className="relative w-36 h-36 rounded-full bg-ned-green/10 border border-ned-green/30
                               flex items-center justify-center overflow-hidden"
                    style={{ boxShadow: '0 0 40px rgba(0,198,106,0.5), 0 0 12px rgba(0,198,106,0.25)' }}
                  >
                    <img
                      src="/logo1.png"
                      alt="NedCard AI"
                      className="w-40 h-40 object-contain"
                      onError={e => {
                        const t = e.currentTarget
                        t.style.display = 'none'
                        t.parentElement!.innerHTML = '<span style="font-size:28px">✦</span>'
                      }}
                    />
                  </motion.div>
                </div>
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
                  <h2 className="text-white text-[22px] font-bold mb-2 tracking-tight">
                    What do you need to know?
                  </h2>
                </motion.div>
              </motion.div>

            </div>

          ) : (
            /* ── Messages ──────────────── */
            <div className="max-w-2xl mx-auto px-4 py-8 space-y-5">
            <AnimatePresence initial={false}>
              {messages.map(m => (
                <div key={m.id}>
                  {/* Chart renders ABOVE the text bubble so "the chart above" is accurate */}
                  {m.role === 'assistant' && chartData[m.id] !== undefined && (
                    <div className="ml-14 mb-2">
                      <DynamicChart data={chartData[m.id]} />
                    </div>
                  )}

                  <MessageBubble
                    message={m}
                    accent={domainMeta[m.id]?.color ?? '#00C66A'}
                    displayContent={
                      m.role === 'assistant'
                        ? (streamedContent[m.id] ?? m.content)
                        : undefined
                    }
                    isStreaming={m.role === 'assistant' && streamingIds.current.has(m.id)}
                    userInitials={initials}
                  />

                  {/* Speaker button — only on completed assistant messages */}
                  {m.role === 'assistant' && !streamingIds.current.has(m.id) && (
                    <div className="ml-14 mt-1">
                      <button
                        onClick={() => handleSpeak(m.id, streamedContent[m.id] ?? m.content)}
                        disabled={speakingId !== null && speakingId !== m.id}
                        title={speakingId === m.id ? 'Stop' : 'Listen'}
                        className={clsx(
                          'flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] transition-all',
                          speakingId === m.id
                            ? 'text-ned-green bg-ned-green/10 border border-ned-green/30'
                            : 'text-ned-muted hover:text-white hover:bg-white/5 border border-transparent',
                          speakingId !== null && speakingId !== m.id && 'opacity-30 cursor-not-allowed'
                        )}
                      >
                        {speakingId === m.id ? (
                          <>
                            <svg className="w-3 h-3 animate-pulse" viewBox="0 0 24 24" fill="currentColor">
                              <rect x="6" y="4" width="4" height="16" rx="1"/>
                              <rect x="14" y="4" width="4" height="16" rx="1"/>
                            </svg>
                            <span>Stop</span>
                          </>
                        ) : (
                          <>
                            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                              <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
                              <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
                            </svg>
                            <span>Listen</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              ))}

              {/* Thinking indicator — staged chain-of-thought */}
              {loading && (() => {
                const step = currentThinkStep()
                const accent = thinkingMeta?.color ?? '#00C66A'
                return (
                  <motion.div
                    key="thinking"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex gap-3"
                  >
                    <div className="flex-shrink-0 w-11 h-11 rounded-full bg-ned-green/20
                                    border border-ned-lite/20 flex items-center justify-center
                                    overflow-hidden mt-1">
                      <img
                        src="/logo1.png"
                        alt="AI"
                        className="w-8 h-8 object-contain"
                        onError={e => { e.currentTarget.style.display = 'none' }}
                      />
                    </div>
                    <div className="bg-ned-slate/40 border border-white/[0.06]
                                    rounded-2xl rounded-bl-sm px-5 py-4 min-w-[200px]">
                      {/* Step progress dots */}
                      <div className="flex items-center gap-1 mb-2.5">
                        {THINKING_STEPS.map((_, i) => (
                          <span
                            key={i}
                            className="h-0.5 rounded-full transition-all duration-500"
                            style={{
                              width: i === thinkingStep ? '20px' : '6px',
                              background: i <= thinkingStep ? accent : 'rgba(255,255,255,0.12)'
                            }}
                          />
                        ))}
                      </div>
                      {/* Animated step label */}
                      <AnimatePresence mode="wait">
                        <motion.div
                          key={thinkingStep}
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -4 }}
                          transition={{ duration: 0.2 }}
                          className="flex items-center gap-2"
                        >
                          {/* Spinner */}
                          <svg
                            className="w-3.5 h-3.5 animate-spin flex-shrink-0"
                            xmlns="http://www.w3.org/2000/svg"
                            fill="none"
                            viewBox="0 0 24 24"
                          >
                            <circle className="opacity-20" cx="12" cy="12" r="10"
                              stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-80" fill="currentColor"
                              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                          <span className="text-xs font-medium" style={{ color: accent }}>
                            {step.text}
                          </span>
                          {/* Trailing pulse dots */}
                          <span className="flex gap-0.5 ml-0.5">
                            {[0, 1, 2].map(i => (
                              <motion.span
                                key={i}
                                className="w-1 h-1 rounded-full"
                                style={{ background: accent }}
                                animate={{ opacity: [0.2, 1, 0.2] }}
                                transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                              />
                            ))}
                          </span>
                        </motion.div>
                      </AnimatePresence>
                    </div>
                  </motion.div>
                )
              })()}
            </AnimatePresence>
              <div ref={bottomRef} />
            </div>
          )}
      </div>

      {/* ── Input bar ───────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-white/[0.06] bg-ned-dark px-4 pt-4 pb-6">
        <div className="max-w-2xl mx-auto">

          {/* Active document banner (persists between questions) */}
          {activeDocId !== null && (
            <div className="flex items-center justify-between gap-2 mb-1.5 px-1">
              <div className="flex items-center gap-1.5 text-xs
                              bg-amber-500/10 border border-amber-500/25
                              text-amber-400 rounded-lg px-2.5 py-1">
                <span>📄</span>
                <span className="truncate max-w-[220px] font-medium">{activeDocName}</span>
                <span className="text-amber-500/50 ml-0.5">· active document</span>
              </div>
              <button
                onClick={() => { setActiveDocId(null); setActiveDocName(null) }}
                className="text-amber-500/50 hover:text-amber-400 transition-colors flex-shrink-0"
                title="Close document"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          )}

          {/* Pending file attachment badge (before upload) */}
          {attachedFile && (
            <div className="flex items-center gap-2 mb-2 px-1">
              <div className="flex items-center gap-1.5 text-xs bg-ned-green/10 border
                              border-ned-green/25 text-ned-green rounded-lg px-2.5 py-1">
                <Paperclip className="w-3 h-3 flex-shrink-0" />
                <span className="truncate max-w-[240px]">{attachedFile.name}</span>
                <button
                  onClick={() => setAttachedFile(null)}
                  className="ml-1 text-ned-green/60 hover:text-ned-green transition-colors"
                  title="Remove attachment"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
              <span className="text-ned-muted text-[10px]">Press Send to upload &amp; analyse</span>
            </div>
          )}

          <div
            className={clsx(
              'flex items-end gap-2 bg-ned-slate/40 border rounded-2xl px-3 py-3',
              'transition-all duration-200',
              recording
                ? 'border-red-500/40 shadow-[0_0_0_1px_rgba(239,68,68,0.15)]'
                : 'border-white/10 focus-within:border-ned-lite/30 focus-within:shadow-[0_0_0_1px_rgba(0,198,106,0.10)]'
            )}
          >
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.txt,.csv,.md,.mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm,.ogg,.flac"
              onChange={handleFileChange}
            />

            {/* Left: Attach + Mic + duration */}
            <div className="flex items-center gap-1 flex-shrink-0 pb-0.5">
              {/* Attach file */}
              <button
                onClick={() => fileInputRef.current?.click()}
                title="Attach a file"
                className="w-8 h-8 rounded-xl flex items-center justify-center
                           text-ned-muted hover:text-ned-green hover:bg-ned-green/10
                           transition-all duration-200"
              >
                <Paperclip className="w-3.5 h-3.5" />
              </button>

              {/* Mic / recording toggle */}
              <button
                onClick={toggleRecording}
                title={recording ? 'Stop recording' : 'Record a voice question'}
                disabled={loading}
                className={clsx(
                  'relative w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-200',
                  recording
                    ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                    : 'text-ned-muted hover:text-ned-green hover:bg-ned-green/10'
                )}
              >
                <Mic className="w-3.5 h-3.5" />
                {/* Red pulsing dot when recording */}
                {recording && (
                  <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full
                                   bg-red-500 animate-pulse" />
                )}
              </button>

              {/* Live duration counter — only visible while recording */}
              {recording && (
                <span className={clsx(
                  'text-[11px] font-mono tabular-nums leading-none px-1.5 py-0.5 rounded-md',
                  recording
                    ? 'text-red-400 bg-red-500/10'
                    : 'text-ned-muted'
                )}>
                  {`${Math.floor(recordingMs / 60)}:${String(recordingMs % 60).padStart(2, '0')}`}
                </span>
              )}
            </div>

            {/* Centre: textarea */}
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                recording     ? 'Recording… click mic to stop & attach' :
                attachedFile  ? 'Add a question (optional) then press Send…' :
                activeDocId   ? `Ask about ${activeDocName ?? 'document'}…` :
                                'Ask anything…'
              }
              rows={1}
              className="flex-1 resize-none bg-transparent text-white text-sm
                         placeholder-ned-muted outline-none leading-relaxed
                         min-h-[24px] max-h-[160px] py-0.5"
            />

            {/* Right: Clear + Send */}
            <div className="flex items-center gap-1.5 flex-shrink-0 pb-0.5">
              {messages.length > 0 && (
                <button
                  onClick={clearConversation}
                  className="w-8 h-8 rounded-xl flex items-center justify-center
                             text-ned-muted hover:text-white hover:bg-white/10
                             transition-all duration-200"
                  title="Clear conversation"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              )}

              <button
                onClick={() => submit(input)}
                disabled={(!input.trim() && !attachedFile) || loading}
                className={clsx(
                  'w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-200',
                  (input.trim() || attachedFile) && !loading
                    ? 'bg-ned-green text-white shadow-[0_2px_12px_rgba(0,123,64,0.40)] hover:opacity-90'
                    : 'bg-white/[0.06] text-ned-muted cursor-not-allowed'
                )}
              >
                {loading ? (
                  <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10"
                            stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor"
                          d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          </div>

          <p className="text-ned-muted text-[10px] text-center mt-2 tracking-wide">
            <kbd className="bg-white/10 px-1.5 py-0.5 rounded font-mono">Enter</kbd> to send ·{' '}
            <kbd className="bg-white/10 px-1.5 py-0.5 rounded font-mono">Shift + Enter</kbd> for new line
          </p>
        </div>
      </div>

      {/* ── Realtime voice agent — floats above the input bar ────────────── */}
      <VoiceOverlay onMessage={handleVoiceMessage} />

    </div>
  )
}
