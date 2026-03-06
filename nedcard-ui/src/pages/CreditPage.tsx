import { useState } from 'react'
import { motion } from 'framer-motion'
import { CreditCard, Info } from 'lucide-react'
import ChatWindow from '../components/ChatWindow'

const SESSION_ID = crypto.randomUUID()

const EXAMPLES = [
  'What is the approval rate for applicants in Gauteng?',
  'Show me the top 10 highest-risk credit applications this month',
  'Which age group has the highest default probability?',
  'Average credit score by income bracket',
  'How many applications were declined in Q1 2026?',
  'List applicants with a risk score above 80 from Cape Town',
]

const STATS = [
  { label: 'Applications reviewed', value: '12,840', accent: '#00C66A' },
  { label: 'Avg approval rate',     value: '64.2%',  accent: '#C9A84C' },
  { label: 'High-risk flagged',     value: '1,203',  accent: '#E07060' },
  { label: 'Avg credit score',      value: '618',    accent: '#7EB8DF' },
]

export default function CreditPage() {
  const [infoOpen, setInfoOpen] = useState(false)

  return (
    <div className="flex flex-col h-full">
      {/* ── Header strip ─────────────────────────────────── */}
      <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-white/[0.05]">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-ned-green/20 border border-ned-lite/20
                            flex items-center justify-center">
              <CreditCard className="w-5 h-5 text-ned-lite" />
            </div>
            <div>
              <h1 className="text-white text-lg font-bold leading-tight">Credit Risk Intelligence</h1>
              <p className="text-ned-muted text-xs mt-0.5">
                Interrogate credit application data — approval rates, risk scores, demographics
              </p>
            </div>
          </div>
          <button
            onClick={() => setInfoOpen(p => !p)}
            className="flex-shrink-0 w-8 h-8 rounded-lg bg-white/[0.04] border border-white/10
                       flex items-center justify-center text-ned-muted hover:text-white transition-all"
          >
            <Info className="w-4 h-4" />
          </button>
        </div>

        {/* Stat pills */}
        <div className="flex flex-wrap gap-3 mt-4">
          {STATS.map(s => (
            <div key={s.label} className="flex items-center gap-2 px-3 py-1.5 rounded-lg
                                         bg-white/[0.04] border border-white/[0.07]">
              <span className="text-sm font-bold" style={{ color: s.accent }}>{s.value}</span>
              <span className="text-ned-muted text-xs">{s.label}</span>
            </div>
          ))}
        </div>

        {/* Info panel */}
        {infoOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mt-4 p-4 rounded-xl bg-ned-green/10 border border-ned-lite/15 text-xs text-ned-muted leading-relaxed"
          >
            <strong className="text-ned-lite block mb-1">Data source</strong>
            Connected to the <code className="text-ned-lite">credit_applications</code> SQLite table via a
            LangGraph ReAct agent with GPT-4o. The agent constructs SQL queries, executes them, and
            synthesises natural-language answers. In production, this connects to Nedbank's
            core lending system via a read-only analytical replica.
          </motion.div>
        )}
      </div>

      {/* ── Chat ─────────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden">
        <ChatWindow
          endpoint="/api/credit/query"
          sessionId={SESSION_ID}
          placeholder="Ask about credit applications, risk scores, approval rates…"
          exampleQueries={EXAMPLES}
          accentColor="#00C66A"
          emptyIcon="💳"
          emptyTitle="Credit Risk Intelligence"
          emptySubtitle="Ask about approval rates, risk profiles, regional breakdowns, or individual applications — in plain English."
        />
      </div>
    </div>
  )
}
