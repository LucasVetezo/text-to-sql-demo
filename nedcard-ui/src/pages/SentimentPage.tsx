import { useState, useCallback } from 'react'
import { BarChart3, RefreshCw, Sparkles } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import ChatWindow from '../components/ChatWindow'
import { getSentimentChartData } from '../lib/api'
import type { AgentResponse, ChartData } from '../types'

const SESSION_ID = crypto.randomUUID()

const EXAMPLES = [
  'What are customers most frustrated about on social media?',
  'Show me credit-related sentiment on X',
  'Break down LinkedIn posts by topic',
  'Which topics have the sharpest negative sentiment?',
  'Show me positive feedback — what are we doing well?',
  'Give me an executive summary of brand perception this month',
]

// ── Keyword-based filter detection ────────────────────────
type Filters = { topic?: string | null; platform?: string | null; sentiment?: string | null }

function detectFilters(query: string): Filters {
  const q = query.toLowerCase()
  const topic = (['credit', 'fraud', 'service', 'app', 'fees'] as const)
    .find(t => q.includes(t)) ?? null
  const platform =
    q.includes('linkedin') ? 'LinkedIn' :
    (q.includes(' x ') || q.includes('twitter') || q.includes('x post') || q.includes('on x')) ? 'X' : null
  const sentiment =
    (q.includes('negative') || q.includes('compla') || q.includes('frustrat')) ? 'negative' :
    (q.includes('positive') || q.includes('doing well') || q.includes('praise')) ? 'positive' :
    q.includes('neutral') ? 'neutral' : null
  return { topic, platform, sentiment }
}

// ── Colour palettes ───────────────────────────────────────
const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#00C66A', neutral: '#C9A84C', negative: '#E74C3C',
}
const TOPIC_COLORS = ['#00C66A', '#7EB8DF', '#E07060', '#BF9FDF', '#C9A84C', '#5A8070', '#F39C12', '#27AE60']

// ── Tooltips ──────────────────────────────────────────────
function PieTip({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-ned-dark2 border border-white/10 rounded-xl px-4 py-2.5 shadow-xl">
      <p className="text-white text-sm font-semibold capitalize">{payload[0].name}</p>
      <p className="text-ned-muted text-xs">{payload[0].value}% of posts</p>
    </div>
  )
}
function BarTip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-ned-dark2 border border-white/10 rounded-xl px-4 py-2.5 shadow-xl">
      <p className="text-white text-sm font-semibold capitalize">{label}</p>
      <p className="text-ned-muted text-xs">{payload[0].value} mentions</p>
    </div>
  )
}

// ── Dynamic chart panel ───────────────────────────────────
function DynamicChartPanel({ data, onRefresh }: { data: ChartData; onRefresh: () => void }) {
  const sentimentRows = data.sentiment_breakdown.map(r => ({
    name: r.sentiment_label,
    value: Number(r.pct),
    color: SENTIMENT_COLORS[r.sentiment_label] ?? '#5A8070',
  }))
  const topicRows = data.topic_distribution.map((r, i) => ({
    topic: r.topic, count: r.mentions, fill: TOPIC_COLORS[i % TOPIC_COLORS.length],
  }))
  const activeFilters = [
    data.filters.topic     && `Topic: ${data.filters.topic}`,
    data.filters.platform  && `Platform: ${data.filters.platform}`,
    data.filters.sentiment && `Sentiment: ${data.filters.sentiment}`,
  ].filter(Boolean) as string[]

  return (
    <div className="flex-shrink-0 px-6 py-5 border-b border-white/[0.05]"
         style={{ background: 'rgba(0,30,18,0.45)' }}>
      {/* Panel header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-ned-lite" />
          <p className="text-white text-xs font-semibold">
            {activeFilters.length ? 'Query-Specific View' : 'Overview — All Posts'}
          </p>
        </div>
        {activeFilters.map(f => (
          <span key={f} className="px-2.5 py-0.5 rounded-full text-[10px] font-medium
                                    bg-sky-400/10 border border-sky-400/20 text-sky-300 capitalize">
            {f}
          </span>
        ))}
        <button onClick={onRefresh}
          className="ml-auto flex items-center gap-1.5 text-ned-muted hover:text-white text-[11px] transition-colors">
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Sentiment donut */}
        <div className="glass-card p-4">
          <p className="text-white text-xs font-semibold mb-3">Sentiment Breakdown</p>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie data={sentimentRows} cx="50%" cy="50%"
                   innerRadius={42} outerRadius={68} paddingAngle={3} dataKey="value">
                {sentimentRows.map(r => <Cell key={r.name} fill={r.color} />)}
              </Pie>
              <Tooltip content={<PieTip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-3 mt-1 flex-wrap">
            {sentimentRows.map(r => (
              <div key={r.name} className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full" style={{ background: r.color }} />
                <span className="text-ned-muted text-[10px] capitalize">{r.name} {r.value}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Topic bar chart */}
        <div className="glass-card p-4">
          <p className="text-white text-xs font-semibold mb-3">Posts by Topic</p>
          <ResponsiveContainer width="100%" height={175}>
            <BarChart data={topicRows} margin={{ top: 0, right: 0, left: -24, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="topic" tick={{ fill: '#5A8070', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5A8070', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip content={<BarTip />} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {topicRows.map(r => <Cell key={r.topic} fill={r.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Platform + pain points */}
        <div className="flex flex-col gap-4">
          <div className="glass-card p-4 flex-1">
            <p className="text-white text-xs font-semibold mb-3">Platform Split</p>
            {data.platform_split.map(p => (
              <div key={p.platform}
                   className="flex items-center justify-between py-2 border-b border-white/[0.04] last:border-0">
                <span className="text-white/70 text-xs">
                  {p.platform === 'X' ? '🐦 X (Twitter)' : '💼 LinkedIn'}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-ned-lite text-xs font-bold">{Number(p.pct).toFixed(0)}%</span>
                  <span className="text-ned-muted text-[10px]">{p.count} posts</span>
                </div>
              </div>
            ))}
          </div>
          {data.trending_negatives.length > 0 && (
            <div className="glass-card p-4 flex-1">
              <p className="text-white text-xs font-semibold mb-3">🔥 Top Pain Points</p>
              <div className="flex flex-wrap gap-1.5">
                {data.trending_negatives.map(r => (
                  <span key={r.topic}
                    className="text-[10px] px-2.5 py-1 rounded-full
                               bg-red-500/10 text-red-400 border border-red-400/15 font-medium capitalize">
                    {r.topic}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────
export default function SentimentPage() {
  const [chartData,     setChartData]     = useState<ChartData | null>(null)
  const [lastFilters,   setLastFilters]   = useState<Filters>({})
  const [chartLoading,  setChartLoading]  = useState(false)
  const [chartExpanded, setChartExpanded] = useState(true)
  const [initialised,   setInitialised]   = useState(false)

  const fetchChart = useCallback(async (filters: Filters) => {
    setChartLoading(true)
    try {
      const data = await getSentimentChartData(filters)
      setChartData(data)
      setLastFilters(filters)
    } catch { /* non-fatal */ }
    finally { setChartLoading(false) }
  }, [])

  // Load overview on first render
  if (!initialised) {
    setInitialised(true)
    fetchChart({})
  }

  const handleResponse = useCallback((_query: string, _response: AgentResponse) => {
    const filters = detectFilters(_query)
    fetchChart(filters)
    setChartExpanded(true)
  }, [fetchChart])

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ─────────────────────────────────────── */}
      <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-white/[0.05]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center"
               style={{ background: 'rgba(80,120,192,0.12)', border: '1px solid rgba(126,184,223,0.18)' }}>
            <BarChart3 className="w-5 h-5" style={{ color: '#7EB8DF' }} />
          </div>
          <div>
            <h1 className="text-white text-lg font-bold leading-tight">Social Sentiment Analysis</h1>
            <p className="text-ned-muted text-xs mt-0.5">
              400 synthetic posts · X + LinkedIn · <span className="text-ned-lite">Charts update per query</span>
            </p>
          </div>
          <button
            onClick={() => setChartExpanded(p => !p)}
            className="ml-auto px-3 py-1.5 rounded-lg text-xs font-medium
                       bg-white/[0.04] border border-white/10 text-ned-muted hover:text-white
                       transition-all duration-200"
          >
            {chartExpanded ? 'Hide charts' : 'Show charts'}
          </button>
        </div>
      </div>

      {/* ── Dynamic chart panel ─────────────────────────── */}
      <AnimatePresence>
        {chartExpanded && (
          <motion.div
            key="charts"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            {chartLoading ? (
              <div className="flex items-center justify-center gap-2 py-10 text-ned-muted text-xs">
                <RefreshCw className="w-4 h-4 animate-spin" style={{ color: '#7EB8DF' }} />
                Generating chart…
              </div>
            ) : chartData ? (
              <DynamicChartPanel
                data={chartData}
                onRefresh={() => fetchChart(lastFilters)}
              />
            ) : null}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Chat ───────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden">
        <ChatWindow
          endpoint="/api/sentiment/query"
          sessionId={SESSION_ID}
          placeholder="Ask about topics, platforms, or brand sentiment — charts update automatically…"
          exampleQueries={EXAMPLES}
          accentColor="#7EB8DF"
          emptyIcon={<BarChart3 className="w-16 h-16 opacity-20" style={{ color: '#7EB8DF' }} />}
          emptyTitle="Social Sentiment Intelligence"
          emptySubtitle="Ask about topics, platforms, or sentiment — the charts above update automatically to match your question."
          onResponse={handleResponse}
        />
      </div>
    </div>
  )
}

