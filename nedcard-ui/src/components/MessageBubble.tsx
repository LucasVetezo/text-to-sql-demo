import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, Check, ChevronDown, ChevronUp, Code2 } from 'lucide-react'
import { motion } from 'framer-motion'
import clsx from 'clsx'
import type { ChatMessage } from '../types'
import DataTable from './DataTable'
import { format } from 'date-fns'

interface Props {
  message: ChatMessage
  accent?: string
  displayContent?: string   // partial text during typewriter stream
  isStreaming?: boolean     // show blinking cursor
  userInitials?: string     // e.g. "TM" — shown on user message avatars
}

export default function MessageBubble({ message, accent = '#00C66A', displayContent, isStreaming, userInitials = 'U' }: Props) {
  const [copied,  setCopied]  = useState(false)
  const [sqlOpen, setSqlOpen] = useState(false)

  // Scroll into view as content grows during streaming
  useEffect(() => {
    if (isStreaming) {
      // lightweight — ChatWindow's scrollBottom handles the main scroll
    }
  }, [displayContent, isStreaming])

  const isUser    = message.role === 'user'
  const rendered  = isUser ? message.content : (displayContent ?? message.content)

  async function handleCopy() {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={clsx('flex gap-3 group', isUser ? 'flex-row-reverse' : 'flex-row')}
    >
      {/* AI avatar — left side */}
      {!isUser && (
        <div className="flex-shrink-0 w-11 h-11 rounded-full bg-ned-green/25 border border-ned-lite/25
                        flex items-center justify-center mt-1 overflow-hidden">
          <img src="/logo1.png" alt="AI" className="w-full h-full object-contain" />
        </div>
      )}

      {/* User avatar — right side */}
      {isUser && (
        <div className="flex-shrink-0 w-11 h-11 rounded-full
                        bg-gradient-to-br from-blue-500 to-purple-600
                        flex items-center justify-center mt-1 flex-shrink-0
                        border border-white/10 shadow-sm">
          <span className="text-white text-[13px] font-bold tracking-tight select-none">
            {userInitials}
          </span>
        </div>
      )}

      <div className={clsx('flex flex-col gap-1.5 max-w-[80%]', isUser && 'items-end')}>
        {/* Bubble */}
        <div
          className={clsx(
            'rounded-2xl px-5 py-3.5 text-sm leading-relaxed',
            isUser
              ? 'bg-ned-green/20 border border-ned-lite/20 text-white rounded-br-sm'
              : 'bg-ned-slate/50 border border-white/[0.06] text-ned-off rounded-bl-sm'
          )}
          style={isUser ? { borderColor: `${accent}33` } : undefined}
        >
          {isUser ? (
            <p>{rendered}</p>
          ) : (
            <div className="prose-ned">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {rendered}
              </ReactMarkdown>
              {isStreaming && (
                <span
                  className="inline-block w-[2px] h-[1em] ml-0.5 align-middle animate-pulse"
                  style={{ background: accent, opacity: 0.8 }}
                />
              )}
            </div>
          )}
        </div>

        {/* SQL query collapsible */}
        {message.sql_query && (
          <div className="w-full">
            <button
              onClick={() => setSqlOpen(p => !p)}
              className="flex items-center gap-2 text-[11px] text-ned-muted hover:text-ned-lite
                         transition-colors duration-150 py-1"
            >
              <Code2 className="w-3.5 h-3.5" />
              SQL query
              {sqlOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {sqlOpen && (
              <motion.pre
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="text-[11px] text-ned-lite bg-ned-dark border border-ned-lite/15
                           rounded-xl p-4 overflow-x-auto font-mono leading-relaxed"
              >
                {message.sql_query}
              </motion.pre>
            )}
          </div>
        )}

        {/* Data table */}
        {message.table_data && message.table_data.rows.length > 0 && (
          <div className="w-full">
            <DataTable data={message.table_data} />
          </div>
        )}

        {/* Meta row: timestamp + copy */}
        <div className={clsx(
          'flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200',
          isUser ? 'flex-row-reverse' : 'flex-row'
        )}>
          <span className="text-[10px] text-ned-muted">
            {format(message.timestamp, 'HH:mm')}
            {message.latency_ms && ` · ${message.latency_ms}ms`}
          </span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-[10px] text-ned-muted hover:text-white
                       transition-colors duration-150"
          >
            {copied
              ? <><Check className="w-3 h-3 text-ned-lite" /> Copied</>
              : <><Copy className="w-3 h-3" /> Copy</>}
          </button>
        </div>
      </div>
    </motion.div>
  )
}
