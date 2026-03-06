import { useState } from 'react'
import { motion } from 'framer-motion'
import { ShieldAlert, Info } from 'lucide-react'
import ChatWindow from '../components/ChatWindow'

const SESSION_ID = crypto.randomUUID()

const EXAMPLES = [
  'Show me the top 20 flagged transactions this week',
  'Which merchants have the highest fraud rate?',
  'Identify card-not-present fraud patterns in Johannesburg',
  'How many accounts were compromised in Q1 2026?',
  'Compare fraud volume between debit and credit card transactions',
  'Show me rapid consecutive transactions flagged as suspicious',
]

const STATS = [
  { label: 'Transactions analysed', value: '486K',  accent: '#E07060' },
  { label: 'Fraud rate',            value: '0.34%', accent: '#C9A84C' },
  { label: 'Cases this month',      value: '1,641', accent: '#E07060' },
  { label: 'Avg fraud value',       value: 'R4,280', accent: '#7EB8DF' },
]

const ALERTS = [
  { severity: 'HIGH',   msg: 'Unusual after-hours ATM activity detected — East Rand cluster',   time: '14 min ago' },
  { severity: 'MEDIUM', msg: 'Multiple failed PIN attempts on 37 accounts from same IP range',   time: '1 hr ago' },
  { severity: 'LOW',    msg: 'Card-not-present spike on international merchant category 7995',    time: '3 hr ago' },
]

const SEVERITY_STYLE: Record<string, string> = {
  HIGH:   'bg-red-500/15 text-red-400 border-red-400/20',
  MEDIUM: 'bg-yellow-500/15 text-yellow-400 border-yellow-400/20',
  LOW:    'bg-blue-500/15 text-blue-400 border-blue-400/20',
}

export default function FraudPage() {
  const [infoOpen, setInfoOpen] = useState(false)

  return (
    <div className="flex flex-col h-full">
      {/* ── Header strip ─────────────────────────────────── */}
      <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-white/[0.05]">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                 style={{ background: 'rgba(192,80,60,0.15)', border: '1px solid rgba(224,112,96,0.2)' }}>
              <ShieldAlert className="w-5 h-5" style={{ color: '#E07060' }} />
            </div>
            <div>
              <h1 className="text-white text-lg font-bold leading-tight">Fraud Detection</h1>
              <p className="text-ned-muted text-xs mt-0.5">
                Surface suspicious patterns, flag anomalies, and drill into high-risk accounts
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

        {/* Live alerts bar */}
        <div className="mt-4 space-y-2">
          {ALERTS.map((a, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-xl bg-white/[0.02] border border-white/[0.05]">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${SEVERITY_STYLE[a.severity]}`}>
                {a.severity}
              </span>
              <span className="text-white/70 text-xs flex-1 truncate">{a.msg}</span>
              <span className="text-ned-muted text-[10px] flex-shrink-0">{a.time}</span>
            </div>
          ))}
        </div>

        {/* Info panel */}
        {infoOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mt-4 p-4 rounded-xl text-xs text-ned-muted leading-relaxed"
            style={{ background: 'rgba(192,80,60,0.08)', border: '1px solid rgba(224,112,96,0.15)' }}
          >
            <strong className="block mb-1" style={{ color: '#E07060' }}>Data source</strong>
            Connected to <code style={{ color: '#E07060' }}>fraud_transactions</code> and{' '}
            <code style={{ color: '#E07060' }}>flagged_accounts</code> tables via LangGraph + GPT-4o.
            Read-only access. In production, integrates with Nedbank's real-time transaction
            monitoring system and AML compliance pipeline.
          </motion.div>
        )}
      </div>

      {/* ── Chat ─────────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden">
        <ChatWindow
          endpoint="/api/fraud/query"
          sessionId={SESSION_ID}
          placeholder="Ask about flagged transactions, fraud patterns, at-risk accounts…"
          exampleQueries={EXAMPLES}
          accentColor="#E07060"
          emptyIcon="🛡️"
          emptyTitle="Fraud Detection Intelligence"
          emptySubtitle="Ask about suspicious transactions, fraud patterns, affected accounts, or risk concentrations — in plain English."
        />
      </div>
    </div>
  )
}
