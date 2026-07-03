'use client'

import { useEffect, useState } from 'react'
import { fetchChartTable, messageForError } from '@/lib/api'
import type { ChartTable } from '@/lib/types'

interface DataTableDrawerProps {
  datasetId: string
  chartId: string
  open: boolean
}

function fmtCell(value: string | number): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }
  return String(value)
}

function isNumeric(value: string | number): boolean {
  return typeof value === 'number' && Number.isFinite(value)
}

export default function DataTableDrawer({
  datasetId,
  chartId,
  open,
}: DataTableDrawerProps) {
  const [table, setTable] = useState<ChartTable | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Lazy-fetch on first expand; cache the result so re-expanding is instant.
    if (!open || table || loading) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchChartTable(datasetId, chartId)
      .then((data) => {
        if (!cancelled) setTable(data)
      })
      .catch((err) => {
        if (!cancelled) {
          const msg =
            err && typeof err === 'object' && 'status' in err && err.status === 404
              ? 'This chart’s data is no longer available — re-run the analysis.'
              : messageForError(err)
          setError(msg)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // `table`/`loading` are intentionally excluded: including them re-runs the
    // effect on setLoading(true), firing the first run's cleanup (cancelled=true)
    // which discards the in-flight fetch and hangs the spinner forever.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, datasetId, chartId])

  if (!open) return null

  return (
    <div
      data-testid="data-table-drawer"
      className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60"
    >
      {loading && (
        <div
          data-testid="data-table-loading"
          className="flex items-center gap-2 px-4 py-3 text-sm text-slate-500"
        >
          <span
            className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-accent-600"
            aria-hidden="true"
          />
          Loading data…
        </div>
      )}

      {error && (
        <p
          role="alert"
          data-testid="data-table-error"
          className="px-4 py-3 text-sm font-medium text-red-700"
        >
          {error}
        </p>
      )}

      {table && !loading && !error && (
        <div className="max-h-72 overflow-auto rounded-lg">
          <table
            data-testid="data-table"
            className="w-full border-collapse text-sm"
          >
            <thead className="sticky top-0 bg-white">
              <tr className="border-b border-slate-200">
                {table.columns.map((col, i) => (
                  <th
                    key={`${col}-${i}`}
                    scope="col"
                    className={`px-4 py-2 font-semibold uppercase tracking-wide text-[11px] text-slate-500 ${
                      i === 0 ? 'text-left' : 'text-right'
                    }`}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, r) => (
                <tr
                  key={r}
                  className="border-b border-slate-100 last:border-0 even:bg-white/60"
                >
                  {row.map((cell, c) => (
                    <td
                      key={c}
                      className={`px-4 py-1.5 text-navy-900 ${
                        isNumeric(cell)
                          ? 'text-right font-mono tabular-nums'
                          : 'text-left'
                      }`}
                    >
                      {fmtCell(cell)}
                    </td>
                  ))}
                </tr>
              ))}
              {table.rows.length === 0 && (
                <tr>
                  <td
                    colSpan={table.columns.length || 1}
                    className="px-4 py-3 text-center text-sm text-slate-400"
                  >
                    No aggregated rows for this chart.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {table && !loading && !error && (
        <p className="border-t border-slate-100 px-4 py-2 text-[11px] text-slate-400">
          Aggregated figures · exact, computed locally
        </p>
      )}
    </div>
  )
}
