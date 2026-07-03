import type { ChartSpec } from '@/lib/types'
import PlotlyChart from './PlotlyChart'

interface ChartCardProps {
  chart: ChartSpec
}

export default function ChartCard({ chart }: ChartCardProps) {
  return (
    <article
      data-testid="chart-card"
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-navy-900" title={chart.title}>
            {chart.title}
          </h3>
          {chart.subtitle && (
            <p className="mt-0.5 text-sm text-slate-500">{chart.subtitle}</p>
          )}
        </div>
        {/* Stubbed export icon — Phase 4. Disabled, labelled, never a bug. */}
        <button
          type="button"
          disabled
          aria-label="Export chart (coming in Phase 4)"
          title="Export — coming in Phase 4"
          className="shrink-0 cursor-not-allowed rounded-md border border-slate-200 p-1.5 text-slate-300"
        >
          <svg
            className="h-4 w-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"
            />
          </svg>
        </button>
      </div>

      <div className="mt-3">
        <PlotlyChart figure={chart.figure} title={chart.title} />
      </div>

      <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-400">
        Computed locally · figures exact
      </p>
    </article>
  )
}
