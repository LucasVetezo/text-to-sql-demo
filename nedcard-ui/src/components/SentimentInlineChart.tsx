import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { motion } from 'framer-motion'
import type { ChartData } from '../types'

const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#00C66A',
  neutral:  '#C9A84C',
  negative: '#E07060',
}
const TOPIC_COLORS = ['#00C66A', '#7EB8DF', '#E07060', '#BF9FDF', '#C9A84C', '#5A8070']

function PieTip({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-ned-dark2 border border-white/10 rounded-xl px-3 py-2 shadow-xl text-xs">
      <p className="text-white font-semibold capitalize">{payload[0].name}</p>
      <p className="text-ned-muted">{payload[0].value}%</p>
    </div>
  )
}

function BarTip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-ned-dark2 border border-white/10 rounded-xl px-3 py-2 shadow-xl text-xs">
      <p className="text-white font-semibold capitalize">{label}</p>
      <p className="text-ned-muted">{payload[0].value} mentions</p>
    </div>
  )
}

interface Props {
  data: ChartData
}

export default function SentimentInlineChart({ data }: Props) {
  const pieData = data.sentiment_breakdown.map(r => ({
    name:  r.sentiment_label,
    value: Number(r.pct),
    color: SENTIMENT_COLORS[r.sentiment_label] ?? '#5A8070',
  }))

  const barData = data.topic_distribution.map((r, i) => ({
    topic: r.topic,
    count: r.mentions,
    fill:  TOPIC_COLORS[i % TOPIC_COLORS.length],
  }))

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="mt-3 rounded-2xl border border-white/[0.07] bg-ned-dark2/60 p-4 space-y-5"
    >
      {/* ── Sentiment donut + legend ── */}
      <div>
        <p className="text-ned-muted text-[10px] uppercase tracking-widest font-semibold mb-3">
          Sentiment breakdown
        </p>
        <div className="flex items-center gap-6">
          <div style={{ width: 120, height: 120, flexShrink: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%" cy="50%"
                  innerRadius={32} outerRadius={52}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<PieTip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="flex flex-col gap-2">
            {pieData.map(row => (
              <div key={row.name} className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ background: row.color }}
                />
                <span className="text-ned-muted text-xs capitalize">{row.name}</span>
                <span className="text-white text-xs font-semibold ml-1">{row.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Topic bar chart ── */}
      {barData.length > 0 && (
        <div>
          <p className="text-ned-muted text-[10px] uppercase tracking-widest font-semibold mb-3">
            Mentions by topic
          </p>
          <div style={{ height: 140 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} barSize={16} margin={{ top: 0, right: 0, left: -28, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                <XAxis
                  dataKey="topic"
                  tick={{ fontSize: 10, fill: '#6B7A8E' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: '#6B7A8E' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<BarTip />} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {barData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </motion.div>
  )
}
