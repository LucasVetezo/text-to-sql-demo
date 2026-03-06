// ── Auth ──────────────────────────────────────────────────
export interface User {
  name: string
  email: string
  role: 'analyst' | 'executive' | 'agent' | 'admin'
  avatar?: string
}

// ── Chat ──────────────────────────────────────────────────
export type MessageRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: Date
  latency_ms?: number
  sql_query?: string
  table_data?: TableData | null
  chart_data?: ChartData | null
  evaluation?: EvalData | null
  isStreaming?: boolean
}

export interface TableData {
  columns: string[]
  rows: Record<string, unknown>[]
}

export interface EvalData {
  tier: string
  score: number
  label: string
  color: string
}

// ── Agent ─────────────────────────────────────────────────
export interface ChartData {
  sentiment_breakdown: { sentiment_label: string; count: number; pct: number }[]
  topic_distribution:  { topic: string; mentions: number }[]
  platform_split:      { platform: string; count: number; pct: number }[]
  trending_negatives:  { topic: string; cnt: number }[]
  filters: { topic: string | null; platform: string | null; sentiment: string | null }
}

export interface AgentResponse {
  answer: string
  sql_query?: string
  table_data?: TableData | null
  chart_data?: ChartData | null
  latency_ms?: number
  evaluation?: EvalData | null
  error?: string
  /** Which specialist(s) responded. Absent/null means conversational — no badge shown. */
  agent_label?: string | null
}

// ── RAG / Document upload ─────────────────────────────────
export interface DocumentUploadResponse extends AgentResponse {
  doc_id:      number
  filename:    string
  chunk_count: number
  word_count:  number
  summary:     string
}

export interface UploadedDocument {
  id:          number
  filename:    string
  file_type:   string
  chunk_count: number
  uploaded_at: string
}

// ── Sentiment ─────────────────────────────────────────────
export interface SentimentBreakdown {
  positive: number
  neutral: number
  negative: number
}

export interface TopicCount {
  topic: string
  count: number
}

// ── Navigation module ─────────────────────────────────────
export interface NavModule {
  id: string
  label: string
  icon: string
  path: string
  accent: string
  description: string
}
