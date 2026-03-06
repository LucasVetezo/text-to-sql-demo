import type { TableData } from '../types'

interface Props {
  data: TableData
  maxRows?: number
}

export default function DataTable({ data, maxRows = 8 }: Props) {
  const { columns, rows } = data
  const visible = rows.slice(0, maxRows)
  const hasMore = rows.length > maxRows

  if (!columns.length || !rows.length) return null

  return (
    <div className="mt-3 rounded-xl overflow-hidden border border-white/[0.07] text-xs">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {columns.map(col => (
                <th
                  key={col}
                  className="px-3 py-2 text-left text-ned-lite font-semibold tracking-wide
                             bg-ned-green/15 border-b border-white/[0.06] whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, ri) => (
              <tr
                key={ri}
                className={ri % 2 === 0 ? 'bg-transparent' : 'bg-white/[0.02]'}
              >
                {columns.map(col => (
                  <td
                    key={col}
                    className="px-3 py-2 text-ned-off/80 border-b border-white/[0.04] whitespace-nowrap"
                  >
                    {String(row[col] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hasMore && (
        <div className="px-3 py-1.5 bg-white/[0.02] text-ned-muted text-[11px] border-t border-white/[0.05]">
          Showing {maxRows} of {rows.length} rows
        </div>
      )}
    </div>
  )
}
