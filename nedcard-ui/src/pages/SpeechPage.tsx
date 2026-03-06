import { useState, useRef, useCallback, useMemo, useEffect } from 'react'
import { useChatHistory } from '../context/ChatHistoryContext'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, Send, Volume2, VolumeX, SquareIcon, Loader2, Info, Sparkles } from 'lucide-react'
import clsx from 'clsx'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { queryAgent, transcribeToText, textToSpeech } from '../lib/api'
import type { ChatMessage } from '../types'
import TypingIndicator from '../components/TypingIndicator'

const SESSION_ID = crypto.randomUUID()

const EXAMPLES = [
  'List all available recorded calls',
  'Analyse the call with the lowest CX score',
  'What are the most common customer complaints?',
  'Which agent handles credit queries best?',
  'Show me all escalated calls and what went wrong',
  'What process improvements would reduce call time?',
]

const VOICES = ['nova', 'shimmer', 'alloy', 'echo', 'fable', 'onyx']

function genId() { return Math.random().toString(36).slice(2) + Date.now().toString(36) }

type RecordState = 'idle' | 'recording' | 'transcribing'

const SPEECH_HISTORY_KEY = '/api/speech/query'

export default function SpeechPage() {
  const { getHistory, setHistory } = useChatHistory()

  const [messages,     setMessages]     = useState<ChatMessage[]>(() => getHistory(SPEECH_HISTORY_KEY))
  const [input,        setInput]        = useState('')
  const [loading,      setLoading]      = useState(false)
  const [recordState,  setRecordState]  = useState<RecordState>('idle')
  const [voice,        setVoice]        = useState('nova')
  const [autoSpeak,    setAutoSpeak]    = useState(true)
  const [audioBlob,    setAudioBlob]    = useState<Blob | null>(null)
  const [audioPlaying, setAudioPlaying] = useState(false)
  const [infoOpen,     setInfoOpen]     = useState(false)

  const bottomRef    = useRef<HTMLDivElement>(null)
  const mediaRef     = useRef<MediaRecorder | null>(null)
  const chunksRef    = useRef<Blob[]>([])
  const audioRef     = useRef<HTMLAudioElement | null>(null)
  const inputRef     = useRef<HTMLTextAreaElement>(null)

  // Persist messages to context whenever they change
  useEffect(() => {
    setHistory(SPEECH_HISTORY_KEY, messages)
  }, [messages, setHistory])

  // autocomplete
  const [activeSuggestion,    setActiveSuggestion]    = useState(-1)
  const [suggestionsDismissed, setSuggestionsDismissed] = useState(false)

  const filteredSuggestions = useMemo(() => {
    const q = input.trim().toLowerCase()
    if (!q || suggestionsDismissed) return []
    return EXAMPLES.filter(s => s.toLowerCase().includes(q)).slice(0, 6)
  }, [input, suggestionsDismissed])

  function scrollBottom() {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 80)
  }

  const submitQuery = useCallback(async (query: string) => {
    const q = query.trim()
    if (!q || loading) return
    setInput('')

    const userMsg: ChatMessage = {
      id: genId(), role: 'user', content: q, timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)
    scrollBottom()

    try {
      const result = await queryAgent('/api/speech/query', q, SESSION_ID)
      const answer = result.answer ?? 'No response.'
      const aiMsg: ChatMessage = {
        id: genId(), role: 'assistant', content: answer,
        timestamp: new Date(), latency_ms: result.latency_ms,
      }
      setMessages(prev => [...prev, aiMsg])
      scrollBottom()

      if (autoSpeak) {
        speakText(answer)
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: genId(), role: 'assistant',
        content: `❌ **Error:** ${err instanceof Error ? err.message : 'Backend unreachable'}`,
        timestamp: new Date(),
      }])
    } finally {
      setLoading(false)
    }
  }, [loading, autoSpeak, voice])

  async function speakText(text: string) {
    try {
      const blob = await textToSpeech(text.slice(0, 4096), voice)
      const url  = URL.createObjectURL(blob)
      if (audioRef.current) { audioRef.current.pause(); URL.revokeObjectURL(audioRef.current.src) }
      const audio = new Audio(url)
      audioRef.current = audio
      setAudioBlob(blob)
      setAudioPlaying(true)
      audio.onended = () => setAudioPlaying(false)
      audio.play()
    } catch { /* silent — TTS is optional */ }
  }

  function stopAudio() {
    audioRef.current?.pause()
    setAudioPlaying(false)
  }

  // ── Mic recording ────────────────────────────────────────
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setRecordState('transcribing')
        try {
          const transcript = await transcribeToText(blob, 'question.webm')
          if (transcript.trim()) {
            setInput(transcript)
            submitQuery(transcript)
          }
        } catch {
          // fallback: just put transcript in input box
        } finally {
          setRecordState('idle')
        }
      }
      mediaRef.current = mr
      mr.start()
      setRecordState('recording')
    } catch {
      alert('Microphone access denied. Please allow microphone access in your browser.')
    }
  }

  function stopRecording() {
    mediaRef.current?.stop()
  }

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ───────────────────────────────────────── */}
      <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-white/[0.05]">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                 style={{ background: 'rgba(160,100,192,0.12)', border: '1px solid rgba(191,159,223,0.2)' }}>
              <Mic className="w-5 h-5" style={{ color: '#BF9FDF' }} />
            </div>
            <div>
              <h1 className="text-white text-lg font-bold">Speech & CX Insights</h1>
              <p className="text-ned-muted text-xs mt-0.5">
                Voice-first CX intelligence · Ask by mic or text · AI reads answers aloud
              </p>
            </div>
          </div>
          <button
            onClick={() => setInfoOpen(p => !p)}
            className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/10
                       flex items-center justify-center text-ned-muted hover:text-white transition-all"
          >
            <Info className="w-4 h-4" />
          </button>
        </div>

        {/* Controls row */}
        <div className="flex flex-wrap items-center gap-3 mt-4">
          {/* Voice selector */}
          <div className="flex items-center gap-2">
            <span className="text-ned-muted text-xs">Voice:</span>
            <div className="flex gap-1">
              {VOICES.map(v => (
                <button
                  key={v}
                  onClick={() => setVoice(v)}
                  className={clsx(
                    'px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-all duration-150 capitalize',
                    voice === v
                      ? 'border-purple-400/40 bg-purple-400/15 text-purple-300'
                      : 'border-white/10 bg-white/[0.03] text-ned-muted hover:text-white'
                  )}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>

          {/* Auto-speak toggle */}
          <button
            onClick={() => setAutoSpeak(p => !p)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all',
              autoSpeak
                ? 'border-purple-400/30 bg-purple-400/10 text-purple-300'
                : 'border-white/10 bg-white/[0.03] text-ned-muted'
            )}
          >
            {autoSpeak ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
            {autoSpeak ? 'Auto-speak on' : 'Auto-speak off'}
          </button>

          {/* Audio player indicator */}
          <AnimatePresence>
            {audioPlaying && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg
                           bg-purple-400/10 border border-purple-400/20 text-purple-300 text-xs"
              >
                <div className="flex gap-0.5 items-end h-3">
                  {[0,1,2,3].map(i => (
                    <div
                      key={i}
                      className="w-1 bg-purple-300 rounded-full animate-pulse"
                      style={{
                        height: `${[8,12,6,10][i]}px`,
                        animationDelay: `${i * 0.15}s`,
                      }}
                    />
                  ))}
                </div>
                Speaking…
                <button onClick={stopAudio}>
                  <SquareIcon className="w-3 h-3 hover:text-white" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {infoOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mt-4 p-4 rounded-xl text-xs text-ned-muted leading-relaxed"
            style={{ background: 'rgba(160,100,192,0.08)', border: '1px solid rgba(191,159,223,0.15)' }}
          >
            <strong style={{ color: '#BF9FDF' }} className="block mb-1">How it works</strong>
            1. <strong>Voice question:</strong> your mic → OpenAI Whisper → text → GPT-4o agent<br/>
            2. <strong>Text question:</strong> typed query → GPT-4o agent<br/>
            3. <strong>Voice answer:</strong> agent response → OpenAI TTS → plays in browser<br/>
            Powered by Whisper, GPT-4o, TTS-1, and a LangGraph ReAct agent with real call transcript data.
          </motion.div>
        )}
      </div>

      {/* ── Messages ─────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto chat-scroll px-6 py-6 space-y-5">
        {messages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center h-full text-center gap-5 py-16"
          >
            <div className="text-6xl">🎙️</div>
            <div>
              <h3 className="text-white text-xl font-bold mb-2">Speech & CX Intelligence</h3>
              <p className="text-ned-muted text-sm max-w-sm leading-relaxed">
                Press the microphone to ask a question by voice, or type below.
                I'll analyse calls and respond — in voice, too.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 max-w-lg">
              {EXAMPLES.map(q => (
                <button
                  key={q}
                  onClick={() => submitQuery(q)}
                  className="px-3.5 py-2 rounded-xl text-xs bg-white/[0.04] border border-white/10
                             text-ned-muted hover:border-purple-400/30 hover:text-white
                             transition-all duration-200 text-left"
                >
                  🎙️ {q}
                </button>
              ))}
            </div>
          </motion.div>
        ) : (
          <>
            {messages.map(m => (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={clsx('flex gap-3', m.role === 'user' ? 'flex-row-reverse' : 'flex-row')}
              >
                {m.role === 'assistant' && (
                  <div className="flex-shrink-0 w-11 h-11 rounded-full flex items-center justify-center
                                  bg-purple-400/20 border border-purple-400/25 mt-1 overflow-hidden">
                    <img src="/logo1.png" alt="AI" className="w-full h-full object-contain" />
                  </div>
                )}
                <div className={clsx('max-w-[80%]', m.role === 'user' && 'items-end flex flex-col')}>
                  <div className={clsx(
                    'rounded-2xl px-5 py-3.5 text-sm leading-relaxed',
                    m.role === 'user'
                      ? 'bg-purple-400/15 border border-purple-400/20 text-white rounded-br-sm'
                      : 'bg-ned-slate/50 border border-white/[0.06] text-ned-off rounded-bl-sm'
                  )}>
                    {m.role === 'user' ? (
                      <p>{m.content}</p>
                    ) : (
                      <div className="prose-ned">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                      </div>
                    )}
                  </div>
                  {m.role === 'assistant' && (
                    <button
                      onClick={() => speakText(m.content)}
                      className="mt-1.5 flex items-center gap-1.5 text-[11px] text-ned-muted
                                 hover:text-purple-300 transition-colors"
                    >
                      <Volume2 className="w-3.5 h-3.5" /> Listen
                      {m.latency_ms && <span>· {m.latency_ms}ms</span>}
                    </button>
                  )}
                </div>
              </motion.div>
            ))}
            {loading && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <TypingIndicator />
              </motion.div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ────────────────────────────────────── */}
      <div className="flex-shrink-0 px-6 pb-6">
        <div className="flex items-end gap-3">
          {/* Mic button */}
          <button
            onClick={recordState === 'recording' ? stopRecording : startRecording}
            disabled={recordState === 'transcribing' || loading}
            className={clsx(
              'flex-shrink-0 w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-200',
              recordState === 'recording'
                ? 'bg-red-500 shadow-[0_0_20px_rgba(239,68,68,0.5)] animate-pulse'
                : recordState === 'transcribing'
                ? 'bg-purple-500/30 border border-purple-400/30'
                : 'bg-purple-400/20 border border-purple-400/25 hover:bg-purple-400/35'
            )}
          >
            {recordState === 'transcribing' ? (
              <Loader2 className="w-5 h-5 text-purple-300 animate-spin" />
            ) : recordState === 'recording' ? (
              <MicOff className="w-5 h-5 text-white" />
            ) : (
              <Mic className="w-5 h-5 text-purple-300" />
            )}
          </button>

          {/* Text input */}
          <div className="flex-1 relative">
            {/* Autocomplete suggestions */}
            <AnimatePresence>
              {filteredSuggestions.length > 0 && (
                <motion.div
                  key="speech-suggestions"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 4 }}
                  transition={{ duration: 0.15 }}
                  className="absolute bottom-full mb-2 left-0 right-0 rounded-2xl overflow-hidden
                             border border-white/10 bg-ned-dark2/95 backdrop-blur-sm shadow-xl z-10"
                >
                  {filteredSuggestions.map((s, i) => (
                    <button
                      key={s}
                      onMouseDown={e => {
                        e.preventDefault()
                        setInput(s)
                        setActiveSuggestion(-1)
                        setSuggestionsDismissed(true)
                        inputRef.current?.focus()
                      }}
                      className={clsx(
                        'w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-left transition-colors duration-100',
                        i === activeSuggestion
                          ? 'bg-purple-400/20 text-white'
                          : 'text-ned-muted hover:bg-white/[0.04] hover:text-white',
                        i < filteredSuggestions.length - 1 && 'border-b border-white/[0.05]'
                      )}
                    >
                      <Sparkles className="flex-shrink-0 w-3 h-3 text-purple-400" />
                      <span className="flex-1">{s}</span>
                      {i === activeSuggestion && (
                        <kbd className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded font-mono text-ned-muted">Enter</kbd>
                      )}
                      {i === 0 && activeSuggestion < 0 && (
                        <kbd className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded font-mono text-ned-muted">Tab</kbd>
                      )}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
            <div className="flex items-end gap-2 bg-ned-slate/40 border border-white/10
                            rounded-2xl px-4 py-3 focus-within:border-purple-400/30 transition-all">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => { setInput(e.target.value); setActiveSuggestion(-1); setSuggestionsDismissed(false) }}
              onKeyDown={e => {
                if (filteredSuggestions.length > 0) {
                  if (e.key === 'ArrowDown') { e.preventDefault(); setActiveSuggestion(i => Math.min(i + 1, filteredSuggestions.length - 1)); return }
                  if (e.key === 'ArrowUp') { e.preventDefault(); setActiveSuggestion(i => Math.max(i - 1, -1)); return }
                  if (e.key === 'Tab') { e.preventDefault(); const idx = activeSuggestion >= 0 ? activeSuggestion : 0; setInput(filteredSuggestions[idx]); setActiveSuggestion(-1); setSuggestionsDismissed(true); return }
                  if (e.key === 'Escape') { e.preventDefault(); setActiveSuggestion(-1); setSuggestionsDismissed(true); return }
                  if (e.key === 'Enter' && !e.shiftKey && activeSuggestion >= 0) { e.preventDefault(); submitQuery(filteredSuggestions[activeSuggestion]); setActiveSuggestion(-1); setSuggestionsDismissed(true); return }
                }
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitQuery(input) }
              }}
              placeholder={
                recordState === 'recording' ? '🔴 Recording…' :
                recordState === 'transcribing' ? '⏳ Transcribing…' :
                'Type or use mic to ask about CX and call transcripts…'
              }
              rows={1}
              disabled={recordState !== 'idle'}
              className="flex-1 resize-none bg-transparent text-white text-sm
                         placeholder-ned-muted outline-none leading-relaxed min-h-[24px] max-h-[120px] py-0.5"
            />
            <button
              onClick={() => submitQuery(input)}
              disabled={!input.trim() || loading || recordState !== 'idle'}
              className={clsx(
                'flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all',
                input.trim() && !loading
                  ? 'bg-purple-500 text-white hover:bg-purple-400'
                  : 'bg-white/[0.06] text-ned-muted cursor-not-allowed'
              )}
            >
              {loading
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <Send className="w-3.5 h-3.5" />}
            </button>
          </div>
          </div>
        </div>
        <p className="text-ned-muted text-[10px] text-center mt-2">
          🎤 Click mic to record · <kbd className="bg-white/10 px-1 py-0.5 rounded font-mono">Tab</kbd> to autocomplete · Enter to send · Responses spoken aloud automatically
        </p>
      </div>
    </div>
  )
}
