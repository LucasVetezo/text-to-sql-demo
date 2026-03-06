import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useChatHistory } from '../context/ChatHistoryContext'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, RotateCcw, Sparkles } from 'lucide-react'
import clsx from 'clsx'
import type { AgentResponse, ChatMessage } from '../types'
import { queryAgent } from '../lib/api'
import MessageBubble from './MessageBubble'

interface Props {
  endpoint: string
  sessionId: string
  placeholder?: string
  exampleQueries?: string[]
  accentColor?: string
  emptyIcon?: ReactNode
  emptyTitle?: string
  emptySubtitle?: string
  onResponse?: (query: string, response: AgentResponse) => void
}

function genId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

const THINKING_STEPS = [
  { icon: '🔍', text: 'Analysing your question…' },
  { icon: '🗄️', text: 'Querying data sources…' },
  { icon: '🤔', text: 'Interpreting results…' },
  { icon: '✨', text: 'Composing insights…' },
]

const CHARS_PER_TICK = 6   // characters revealed per frame (~60fps → ~360 chars/s)
const TICK_MS       = 16   // ~60fps

export default function ChatWindow({
  endpoint,
  sessionId,
  placeholder = 'Ask a question…',
  exampleQueries = [],
  accentColor = '#00C66A',
  emptyIcon = <img src="/logo1.png" alt="AI" style={{ width: 96, height: 96, objectFit: 'contain' }} />,
  emptyTitle = 'How can I help you today?',
  emptySubtitle = 'Ask anything in plain English and I\'ll find the answer.',
  onResponse,
}: Props) {
  const { getHistory, setHistory } = useChatHistory()

  const [messages,        setMessages]        = useState<ChatMessage[]>(() => getHistory(endpoint))
  const [input,           setInput]           = useState('')
  const [loading,         setLoading]         = useState(false)
  const [thinkingStep,    setThinkingStep]    = useState(0)
  // id → partial text being revealed
  const [streamedContent, setStreamedContent] = useState<Record<string, string>>({})
  const streamingIds = useRef<Set<string>>(new Set())
  // autocomplete
  const [activeSuggestion, setActiveSuggestion] = useState(-1)
  const [suggestionsDismissed, setSuggestionsDismissed] = useState(false)

  const bottomRef      = useRef<HTMLDivElement>(null)
  const inputRef       = useRef<HTMLTextAreaElement>(null)
  const thinkingTimer  = useRef<ReturnType<typeof setInterval> | null>(null)

  // Persist messages to context whenever they change
  useEffect(() => {
    setHistory(endpoint, messages)
  }, [messages, endpoint, setHistory])

  // filtered suggestions from exampleQueries
  const filteredSuggestions = useMemo(() => {
    const q = input.trim().toLowerCase()
    if (!q || suggestionsDismissed) return []
    return exampleQueries
      .filter(s => s.toLowerCase().includes(q))
      .slice(0, 6)
  }, [input, exampleQueries, suggestionsDismissed])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, streamedContent])

  useEffect(() => {
    const ta = inputRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }, [input])

  // Cycle through thinking steps while loading
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

  // Typewriter: reveal streamed messages char by char
  function startStreaming(id: string, fullText: string) {
    streamingIds.current.add(id)
    let pos = 0
    setStreamedContent(prev => ({ ...prev, [id]: '' }))
    const timer = setInterval(() => {
      pos = Math.min(pos + CHARS_PER_TICK, fullText.length)
      setStreamedContent(prev => ({ ...prev, [id]: fullText.slice(0, pos) }))
      if (pos >= fullText.length) {
        clearInterval(timer)
        streamingIds.current.delete(id)
      }
    }, TICK_MS)
  }

  async function submit(query: string) {
    const q = query.trim()
    if (!q || loading) return

    const userMsg: ChatMessage = {
      id: genId(), role: 'user', content: q, timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const result = await queryAgent(endpoint, q, sessionId)
      const id = genId()
      const aiMsg: ChatMessage = {
        id,
        role: 'assistant',
        content: result.answer ?? 'No response received.',
        timestamp: new Date(),
        latency_ms:  result.latency_ms,
        sql_query:   result.sql_query,
        table_data:  result.table_data ?? null,
      }
      setMessages(prev => [...prev, aiMsg])
      startStreaming(id, aiMsg.content)
      onResponse?.(q, result)
    } catch (err) {
      const errMsg: ChatMessage = {
        id: genId(), role: 'assistant',
        content: `❌ **Error:** ${err instanceof Error ? err.message : 'Could not reach the backend. Is the server running on port 8000?'}`,
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, errMsg])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (filteredSuggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveSuggestion(i => Math.min(i + 1, filteredSuggestions.length - 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveSuggestion(i => Math.max(i - 1, -1))
        return
      }
      if (e.key === 'Tab') {
        e.preventDefault()
        const idx = activeSuggestion >= 0 ? activeSuggestion : 0
        setInput(filteredSuggestions[idx])
        setActiveSuggestion(-1)
        setSuggestionsDismissed(true)
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setActiveSuggestion(-1)
        setSuggestionsDismissed(true)
        return
      }
      if (e.key === 'Enter' && !e.shiftKey && activeSuggestion >= 0) {
        e.preventDefault()
        submit(filteredSuggestions[activeSuggestion])
        setActiveSuggestion(-1)
        setSuggestionsDismissed(true)
        return
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(input) }
  }

  function clearConversation() {
    setMessages([])
    setHistory(endpoint, [])
    setInput('')
    setStreamedContent({})
    setActiveSuggestion(-1)
    setSuggestionsDismissed(false)
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-full">
      {/* ── Message list ─────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto chat-scroll px-6 py-6 space-y-5">
        {isEmpty ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center h-full text-center gap-4 py-20"
          >
            <div className="mb-2 flex items-center justify-center">{emptyIcon}</div>
            <div>
              <h3 className="text-white text-xl font-bold mb-2">{emptyTitle}</h3>
              <p className="text-ned-muted text-sm max-w-sm leading-relaxed">{emptySubtitle}</p>
            </div>
            {exampleQueries.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2 mt-4 max-w-lg">
                {exampleQueries.map(q => (
                  <button
                    key={q}
                    onClick={() => submit(q)}
                    className="px-3.5 py-2 rounded-xl text-xs font-medium
                               bg-white/[0.04] border border-white/10 text-ned-muted
                               hover:border-ned-lite/30 hover:text-white
                               transition-all duration-200 text-left"
                  >
                    <Sparkles className="inline w-3 h-3 mr-1.5 mb-0.5" style={{ color: accentColor }} />
                    {q}
                  </button>
                ))}
              </div>
            )}
          </motion.div>
        ) : (
          <AnimatePresence initial={false}>
            {messages.map(m => (
              <MessageBubble
                key={m.id}
                message={m}
                accent={accentColor}
                displayContent={m.role === 'assistant' ? (streamedContent[m.id] ?? m.content) : undefined}
                isStreaming={m.role === 'assistant' && streamingIds.current.has(m.id)}
              />
            ))}

            {/* ── Thinking steps ───────────────────────── */}
            {loading && (
              <motion.div
                key="thinking"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex gap-3"
              >
                {/* Avatar */}
                <div className="flex-shrink-0 w-11 h-11 rounded-full bg-ned-green/25 border border-ned-lite/25
                                flex items-center justify-center mt-1 overflow-hidden">
                  <img src="/logo1.png" alt="AI" className="w-full h-full object-contain" />
                </div>

                <div className="flex flex-col gap-2.5 bg-ned-slate/50 border border-white/[0.06]
                                rounded-2xl rounded-bl-sm px-5 py-4 text-sm max-w-xs">
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={thinkingStep}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.25 }}
                      className="flex items-center gap-2.5 text-ned-muted"
                    >
                      <span style={{ fontSize: 15 }}>{THINKING_STEPS[thinkingStep].icon}</span>
                      <span className="text-xs">{THINKING_STEPS[thinkingStep].text}</span>
                      <span className="flex gap-0.5 ml-1">
                        {[0,1,2].map(i => (
                          <span
                            key={i}
                            className="w-1 h-1 rounded-full bg-ned-muted animate-pulse"
                            style={{ animationDelay: `${i * 0.2}s` }}
                          />
                        ))}
                      </span>
                    </motion.div>
                  </AnimatePresence>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ────────────────────────────────────── */}
      <div className="flex-shrink-0 px-6 pb-6">
        {/* Autocomplete suggestions */}
        <AnimatePresence>
          {filteredSuggestions.length > 0 && (
            <motion.div
              key="suggestions"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.15 }}
              className="mb-2 rounded-2xl overflow-hidden border border-white/10
                         bg-ned-dark2/95 backdrop-blur-sm shadow-xl"
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
                      ? 'bg-ned-green/20 text-white'
                      : 'text-ned-muted hover:bg-white/[0.04] hover:text-white',
                    i < filteredSuggestions.length - 1 && 'border-b border-white/[0.05]'
                  )}
                >
                  <Sparkles className="flex-shrink-0 w-3 h-3" style={{ color: accentColor }} />
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
        <div className="relative flex items-end gap-2
                        bg-ned-slate/40 border border-white/10
                        rounded-2xl px-4 py-3
                        focus-within:border-ned-lite/30 focus-within:shadow-[0_0_0_1px_rgba(0,198,106,0.15)]
                        transition-all duration-200">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => { setInput(e.target.value); setActiveSuggestion(-1); setSuggestionsDismissed(false) }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            className="flex-1 resize-none bg-transparent text-white text-sm
                       placeholder-ned-muted outline-none leading-relaxed
                       min-h-[24px] max-h-[160px] py-0.5"
          />
          <div className="flex items-center gap-2 flex-shrink-0 pb-0.5">
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
              disabled={!input.trim() || loading}
              className={clsx(
                'w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-200',
                input.trim() && !loading
                  ? 'bg-ned-green text-white hover:bg-ned-mid shadow-[0_2px_12px_rgba(0,123,64,0.40)]'
                  : 'bg-white/[0.06] text-ned-muted cursor-not-allowed'
              )}
            >
              {loading ? (
                <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
                </svg>
              ) : (
                <Send className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>
        <p className="text-ned-muted text-[10px] text-center mt-2 tracking-wide">
          Press <kbd className="bg-white/10 px-1.5 py-0.5 rounded-md font-mono">Enter</kbd> to send
          · <kbd className="bg-white/10 px-1.5 py-0.5 rounded-md font-mono">Tab</kbd> to autocomplete
          · <kbd className="bg-white/10 px-1.5 py-0.5 rounded-md font-mono">Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  )
}