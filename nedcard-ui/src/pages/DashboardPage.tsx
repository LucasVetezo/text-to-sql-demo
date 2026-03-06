import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { CreditCard, ShieldAlert, BarChart3, Mic, TrendingUp, TrendingDown, Minus, ArrowRight } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const MODULES = [
  {
    path: '/credit',
    icon: CreditCard,
    label: 'Credit Risk Intelligence',
    description: 'Interrogate credit application data to identify high-risk segments, approval rates, and risk score distributions across demographics.',
    accent: '#00C66A',
    bg: 'rgba(0,123,64,0.12)',
    border: 'rgba(0,198,106,0.15)',
    tag: 'SQL · Risk · Lending',
  },
  {
    path: '/fraud',
    icon: ShieldAlert,
    label: 'Fraud Detection',
    description: 'Surface suspicious transaction patterns, flag anomalies across channels, and drill into specific accounts or timeframes in plain English.',
    accent: '#E07060',
    bg: 'rgba(192,80,60,0.10)',
    border: 'rgba(224,112,96,0.15)',
    tag: 'Anomaly · AML · Transactions',
  },
  {
    path: '/sentiment',
    icon: BarChart3,
    label: 'Social Sentiment Analysis',
    description: 'Monitor what customers say on X and LinkedIn. Identify trending pain points, monitor brand health, and benchmark against competitors.',
    accent: '#7EB8DF',
    bg: 'rgba(80,120,192,0.10)',
    border: 'rgba(126,184,223,0.15)',
    tag: 'X · LinkedIn · NLP',
  },
  {
    path: '/speech',
    icon: Mic,
    label: 'CX & Speech Insights',
    description: 'Upload call-centre recordings, ask questions in voice, and receive AI-synthesised CX analysis with actionable improvement recommendations.',
    accent: '#BF9FDF',
    bg: 'rgba(160,100,192,0.10)',
    border: 'rgba(191,159,223,0.15)',
    tag: 'Whisper · TTS · Call Analytics',
  },
]

const KPI_CARDS = [
  { label: 'Queries today',     value: '142',    delta: '+18%',  trend: 'up',   icon: '📊' },
  { label: 'Active sessions',   value: '7',      delta: 'live',  trend: 'flat', icon: '👥' },
  { label: 'Avg response time', value: '1.8s',   delta: '-12%',  trend: 'up',   icon: '⚡' },
  { label: 'CSAT score',        value: '8.4/10', delta: '+0.3',  trend: 'up',   icon: '🌟' },
]

const ACTIVITY = [
  { time: 'Just now', user: 'Analyst', action: 'queried credit applications for Q1 2026', module: 'Credit' },
  { time: '3 min ago', user: 'Agent', action: 'analysed call transcript for case #4872', module: 'CX' },
  { time: '12 min ago', user: 'Exec', action: 'reviewed sentiment trends for March 2026', module: 'Sentiment' },
  { time: '28 min ago', user: 'Analyst', action: 'flagged 14 suspicious transactions in Gauteng', module: 'Fraud' },
]

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'up')   return <TrendingUp className="w-3.5 h-3.5 text-ned-lite" />
  if (trend === 'down') return <TrendingDown className="w-3.5 h-3.5 text-red-400" />
  return <Minus className="w-3.5 h-3.5 text-ned-muted" />
}

function fadeItem(delay: number) {
  return {
    initial: { opacity: 0, y: 16 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.45, delay },
  }
}

export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="min-h-full px-6 py-8 max-w-6xl mx-auto">
      {/* ── Greeting ─────────────────────────────────────── */}
      <motion.div {...fadeItem(0)} className="mb-8">
        <div className="badge-green w-fit mb-5">
          <span className="w-1.5 h-1.5 rounded-full bg-ned-lite inline-block" />
          Live Platform
        </div>
        <h1 className="text-white text-3xl font-extrabold leading-tight tracking-tight mb-2">
          Welcome back, <span className="text-ned-lite">{user?.name ?? 'there'}</span>
        </h1>
        <p className="text-ned-muted text-sm leading-relaxed max-w-xl">
          Your AI-powered analytics command centre. Select a module below to begin,
          or type a question directly in any workspace.
        </p>
      </motion.div>

      {/* ── KPI cards ────────────────────────────────────── */}
      <motion.div {...fadeItem(0.08)} className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {KPI_CARDS.map(k => (
          <div key={k.label} className="metric-card">
            <div className="flex items-center justify-between mb-2">
              <span className="text-lg">{k.icon}</span>
              <div className="flex items-center gap-1">
                <TrendIcon trend={k.trend} />
                <span className={`text-[11px] font-semibold ${
                  k.trend === 'up' ? 'text-ned-lite' :
                  k.trend === 'down' ? 'text-red-400' : 'text-ned-muted'
                }`}>{k.delta}</span>
              </div>
            </div>
            <p className="text-white text-2xl font-bold">{k.value}</p>
            <p className="text-ned-muted text-xs mt-0.5">{k.label}</p>
          </div>
        ))}
      </motion.div>

      {/* ── Module cards ─────────────────────────────────── */}
      <motion.div {...fadeItem(0.14)}>
        <h2 className="text-white text-sm font-semibold tracking-wide uppercase mb-4">
          Intelligence Modules
        </h2>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-8">
          {MODULES.map((m, i) => {
            const Icon = m.icon
            return (
              <motion.button
                key={m.path}
                {...fadeItem(0.14 + i * 0.07)}
                onClick={() => navigate(m.path)}
                className="glass-card p-6 text-left group cursor-pointer w-full
                           hover:border-white/15 transition-all duration-250"
                style={{ borderColor: m.border }}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
              >
                <div className="flex items-start justify-between mb-4">
                  <div
                    className="w-11 h-11 rounded-xl flex items-center justify-center"
                    style={{ background: m.bg }}
                  >
                    <Icon className="w-5 h-5" style={{ color: m.accent }} />
                  </div>
                  <ArrowRight
                    className="w-4 h-4 text-ned-muted group-hover:text-white
                               group-hover:translate-x-1 transition-all duration-200"
                  />
                </div>
                <h3 className="text-white text-base font-bold mb-1.5" style={{ color: m.accent }}>
                  {m.label}
                </h3>
                <p className="text-ned-muted text-sm leading-relaxed mb-4">
                  {m.description}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {m.tag.split(' · ').map(t => (
                    <span
                      key={t}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-full border"
                      style={{
                        background: m.bg,
                        color: m.accent,
                        borderColor: m.border,
                      }}
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </motion.button>
            )
          })}
        </div>
      </motion.div>

      {/* ── Recent activity ──────────────────────────────── */}
      <motion.div {...fadeItem(0.4)}>
        <h2 className="text-white text-sm font-semibold tracking-wide uppercase mb-4">
          Recent Activity
        </h2>
        <div className="glass-card divide-y divide-white/[0.04]">
          {ACTIVITY.map((a, i) => (
            <div key={i} className="flex items-center gap-4 px-5 py-3.5">
              <div className="w-1.5 h-1.5 rounded-full bg-ned-lite flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-white/80 text-xs truncate">
                  <span className="font-semibold text-white">{a.user}</span>{' '}
                  {a.action}
                </p>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-ned-green/15 text-ned-lite
                               border border-ned-lite/15 flex-shrink-0">
                {a.module}
              </span>
              <span className="text-ned-muted text-[10px] flex-shrink-0">{a.time}</span>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
