/**
 * DynamicChart.tsx
 *
 * Renders any chart_data returned by the backend.  Shape discrimination:
 *   { sentiment_breakdown, … }           → SentimentInlineChart
 *   { chart_type, rows, x_key, y_key }   → bar | line | pie via Recharts
 *
 * Compact card mode: shown inline in the chat, with an expand button.
 * Fullscreen modal:  click the expand icon (or press ESC to dismiss).
 * Click-outside the modal content also closes it.
 */

import { useState, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BarChart, Bar, LineChart, Line,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, Label,
} from 'recharts'
import SentimentInlineChart from './SentimentInlineChart'
import type { ChartData } from '../types'

// ── Colour palette ────────────────────────────────────────────────────────────
const PALETTE = [
  '#00C66A', '#7EB8DF', '#E07060', '#BF9FDF',
  '#C9A84C', '#5A8070', '#60A8E0', '#E0A060',
]

// ── Shape discriminators ──────────────────────────────────────────────────────

function isSentimentChartData(d: unknown): d is ChartData {
  return (
    typeof d === 'object' && d !== null &&
    'sentiment_breakdown' in d &&
    Array.isArray((d as Record<string, unknown>).sentiment_breakdown)
  )
}

interface GenericChartPayload {
  chart_type: 'bar' | 'line' | 'pie'
  title: string
  x_key: string
  y_key: string
  y_keys?: string[]   // extra series for grouped bar / multi-line
  rows: Record<string, unknown>[]
  color_key?: string
}

function isGenericChartData(d: unknown): d is GenericChartPayload {
  if (typeof d !== 'object' || d === null) return false
  const r = d as Record<string, unknown>
  return (
    typeof r.chart_type === 'string' &&
    Array.isArray(r.rows) &&
    typeof r.x_key === 'string' &&
    typeof r.y_key === 'string'
  )
}

// ── Axis helpers ─────────────────────────────────────────────────────────────

/** Abbreviate large tick values: 1_500_000 → 1.5M, 75_000 → 75K */
function fmtTick(v: unknown): string {
  const n = Number(v)
  if (isNaN(n)) return String(v)
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (Math.abs(n) >= 1_000)     return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}K`
  return String(n)
}

/** snake_case / camelCase → Title Case label */
function prettyKey(k: string): string {
  return k
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, c => c.toUpperCase())
}

// ── Custom tooltip ────────────────────────────────────────────────────────────

type TooltipProps = {
  active?: boolean
  payload?: { name: string; value: unknown }[]
  label?: string
}

function GenericTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-ned-dark2 border border-white/10 rounded-xl px-3 py-2 shadow-xl text-xs">
      {label && <p className="text-white font-semibold mb-0.5">{label}</p>}
      {payload.map(p => (
        <p key={p.name} className="text-ned-muted">
          {prettyKey(p.name)}:{' '}
          <span className="text-white">
            {typeof p.value === 'number'
              ? p.value.toLocaleString()
              : String(p.value)}
          </span>
        </p>
      ))}
    </div>
  )
}

// ── Chart renderers (height-aware) ────────────────────────────────────────────

function BarChartView({ data, height = 220 }: { data: GenericChartPayload; height?: number }) {
  // All series keys: primary y_key plus any extra y_keys from multi-dimension pivot
  const allSeries = data.y_keys && data.y_keys.length > 1 ? data.y_keys : [data.y_key]
  const isGrouped  = allSeries.length > 1
  const bottomMargin = isGrouped ? 40 : 56

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data.rows}
        margin={{ top: 8, right: 16, left: 16, bottom: bottomMargin }}
        barCategoryGap={isGrouped ? '20%' : '30%'}
        barGap={3}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis
          dataKey={data.x_key}
          tick={{ fill: '#6B7F72', fontSize: 11 }}
          angle={isGrouped ? 0 : -30}
          textAnchor={isGrouped ? 'middle' : 'end'}
          interval={0}
        >
          <Label
            value={prettyKey(data.x_key)}
            position="insideBottom"
            offset={isGrouped ? -28 : -44}
            style={{ fill: '#4A6055', fontSize: 10, textAnchor: 'middle' }}
          />
        </XAxis>
        <YAxis
          tick={{ fill: '#6B7F72', fontSize: 11 }}
          tickFormatter={fmtTick}
          width={64}
        >
          <Label
            value={isGrouped ? 'Count' : prettyKey(data.y_key)}
            angle={-90}
            position="insideLeft"
            offset={-4}
            style={{ fill: '#4A6055', fontSize: 10, textAnchor: 'middle' }}
          />
        </YAxis>
        <Tooltip content={<GenericTooltip />} />
        {isGrouped && (
          <Legend
            wrapperStyle={{ fontSize: 11, color: '#6B7F72', paddingTop: 8 }}
            formatter={(value) => prettyKey(value)}
          />
        )}
        {isGrouped ? (
          allSeries.map((key, idx) => (
            <Bar key={key} dataKey={key} name={key} fill={PALETTE[idx % PALETTE.length]} radius={[3, 3, 0, 0]} />
          ))
        ) : (
          <Bar dataKey={data.y_key} radius={[4, 4, 0, 0]}>
            {data.rows.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Bar>
        )}
      </BarChart>
    </ResponsiveContainer>
  )
}

function LineChartView({ data, height = 200 }: { data: GenericChartPayload; height?: number }) {
  const allSeries = data.y_keys && data.y_keys.length > 1 ? data.y_keys : [data.y_key]
  const isMulti   = allSeries.length > 1
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data.rows} margin={{ top: 8, right: 16, left: 16, bottom: isMulti ? 40 : 56 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis
          dataKey={data.x_key}
          tick={{ fill: '#6B7F72', fontSize: 11 }}
          angle={-30}
          textAnchor="end"
          interval={0}
        >
          <Label
            value={prettyKey(data.x_key)}
            position="insideBottom"
            offset={isMulti ? -28 : -44}
            style={{ fill: '#4A6055', fontSize: 10, textAnchor: 'middle' }}
          />
        </XAxis>
        <YAxis
          tick={{ fill: '#6B7F72', fontSize: 11 }}
          tickFormatter={fmtTick}
          width={64}
        >
          <Label
            value={isMulti ? 'Value' : prettyKey(data.y_key)}
            angle={-90}
            position="insideLeft"
            offset={-4}
            style={{ fill: '#4A6055', fontSize: 10, textAnchor: 'middle' }}
          />
        </YAxis>
        <Tooltip content={<GenericTooltip />} />
        {isMulti && (
          <Legend
            wrapperStyle={{ fontSize: 11, color: '#6B7F72', paddingTop: 8 }}
            formatter={(value) => prettyKey(value)}
          />
        )}
        {allSeries.map((key, idx) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            name={key}
            stroke={PALETTE[idx % PALETTE.length]}
            strokeWidth={2}
            dot={{ r: 3, fill: PALETTE[idx % PALETTE.length] }}
            activeDot={{ r: 5 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

type PieTipProps = {
  active?: boolean
  payload?: { name: string; value: number; payload: Record<string, unknown> }[]
}
function PieTip({ active, payload }: PieTipProps) {
  if (!active || !payload?.length) return null
  const p = payload[0]
  return (
    <div className="bg-ned-dark2 border border-white/10 rounded-xl px-3 py-2 shadow-xl text-xs">
      <p className="text-white font-semibold">{String(p.payload['name'] ?? p.name)}</p>
      <p className="text-ned-muted">{p.value}</p>
    </div>
  )
}

function PieChartView({
  data,
  innerRadius = 45,
  outerRadius = 70,
  height = 180,
}: {
  data: GenericChartPayload
  innerRadius?: number
  outerRadius?: number
  height?: number
}) {
  const pieData = data.rows.map(r => ({
    name:  String(r[data.x_key] ?? ''),
    value: Number(r[data.y_key] ?? 0),
  }))
  return (
    <div className="flex items-center gap-6">
      <ResponsiveContainer width="50%" height={height}>
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            dataKey="value"
            paddingAngle={2}
          >
            {pieData.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip content={<PieTip />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex flex-col gap-1.5 flex-1 overflow-y-auto max-h-48">
        {pieData.map((entry, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ background: PALETTE[i % PALETTE.length] }}
            />
            <span className="text-ned-muted truncate">{entry.name}</span>
            <span className="text-white font-medium ml-auto">{entry.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Expand / Collapse SVG icons ───────────────────────────────────────────────

function ExpandIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden>
      <path d="M1 5V1H5M9 1H13V5M13 9V13H9M5 13H1V9"
        stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}
function CollapseIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden>
      <path d="M5 1V5H1M13 5H9V1M9 13V9H13M1 9H5V13"
        stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

// ── Fullscreen modal (portal → document.body) ─────────────────────────────────

function FullscreenModal({
  data,
  onClose,
}: {
  data: GenericChartPayload
  onClose: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <motion.div
      key="backdrop"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm
                 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <motion.div
        key="panel"
        initial={{ opacity: 0, scale: 0.96, y: 12 }}
        animate={{ opacity: 1, scale: 1,    y: 0  }}
        exit={{ opacity: 0, scale: 0.96, y: 12 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
        className="relative w-full max-w-4xl bg-[#0f1a14] border border-white/[0.09]
                   rounded-2xl shadow-2xl flex flex-col overflow-hidden"
        style={{ maxHeight: '90vh' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-5 pb-4
                        border-b border-white/[0.07] flex-shrink-0">
          <div>
            <p className="text-ned-muted text-[10px] uppercase tracking-widest mb-0.5">
              {data.chart_type} chart
            </p>
            <p className="text-white text-lg font-semibold leading-snug">{data.title}</p>
          </div>
          <button
            onClick={onClose}
            className="ml-4 mt-0.5 flex items-center gap-1.5 text-ned-muted hover:text-white
                       transition-colors text-[11px] px-2.5 py-1.5 rounded-lg
                       border border-white/[0.08] hover:border-white/20
                       bg-white/[0.03] hover:bg-white/[0.07] flex-shrink-0"
          >
            <CollapseIcon />
            <span>Compact</span>
            <kbd className="opacity-40 text-[9px] font-mono ml-0.5">ESC</kbd>
          </button>
        </div>

        {/* Chart — fills remaining height */}
        <div className="flex-1 px-6 py-5 overflow-auto min-h-0" style={{ height: '62vh' }}>
          {data.chart_type === 'bar'  && <BarChartView  data={data} height={460} />}
          {data.chart_type === 'line' && <LineChartView data={data} height={460} />}
          {data.chart_type === 'pie'  && (
            <PieChartView data={data} innerRadius={90} outerRadius={155} height={420} />
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-white/[0.07] flex-shrink-0
                        flex items-center justify-between">
          <p className="text-ned-muted text-[11px]">
            {data.rows.length} data point{data.rows.length !== 1 ? 's' : ''}
          </p>
          <p className="text-ned-muted/50 text-[10px]">Click outside or press ESC to close</p>
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  )
}

// ── Compact inline card ───────────────────────────────────────────────────────

function GenericChartCard({ data }: { data: GenericChartPayload }) {
  const [expanded, setExpanded] = useState(false)
  const open  = useCallback(() => setExpanded(true),  [])
  const close = useCallback(() => setExpanded(false), [])

  return (
    <>
      <div className="space-y-3">
        {/* Header + expand button */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-ned-muted text-[10px] uppercase tracking-widest mb-0.5">
              {data.chart_type} chart
            </p>
            <p className="text-white text-sm font-semibold leading-snug">{data.title}</p>
          </div>
          <button
            onClick={open}
            title="Expand to full view"
            className="flex-shrink-0 flex items-center gap-1.5 text-ned-muted
                       hover:text-ned-green transition-colors text-[11px]
                       px-2 py-1 rounded-lg mt-0.5
                       border border-white/[0.07] hover:border-ned-green/30
                       bg-white/[0.03] hover:bg-ned-green/[0.06]"
          >
            <ExpandIcon />
            <span>Full view</span>
          </button>
        </div>

        {/* Compact chart */}
        {data.chart_type === 'bar'  && <BarChartView  data={data} height={220} />}
        {data.chart_type === 'line' && <LineChartView data={data} height={200} />}
        {data.chart_type === 'pie'  && <PieChartView  data={data} />}

        <p className="text-ned-muted text-[10px] text-right">
          {data.rows.length} data point{data.rows.length !== 1 ? 's' : ''}
        </p>
      </div>

      <AnimatePresence>
        {expanded && <FullscreenModal data={data} onClose={close} />}
      </AnimatePresence>
    </>
  )
}

// ── Public export ─────────────────────────────────────────────────────────────

interface Props {
  data: unknown
}

export default function DynamicChart({ data }: Props) {
  if (isSentimentChartData(data)) {
    return <SentimentInlineChart data={data} />
  }

  if (isGenericChartData(data)) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="rounded-2xl border border-white/[0.07] bg-ned-dark2/60 p-4"
      >
        <GenericChartCard data={data} />
      </motion.div>
    )
  }

  return null
}
