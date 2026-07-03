'use client'

import dynamic from 'next/dynamic'
import type { PlotlyFigure } from '@/lib/types'

// Dynamic import with ssr:false so the static export never tries to render
// Plotly on the server (it needs `window`/`document`).
const Plot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => (
    <div
      className="flex h-[340px] w-full items-center justify-center text-sm text-slate-400"
      aria-hidden="true"
    >
      Rendering chart…
    </div>
  ),
})

interface PlotlyChartProps {
  figure: PlotlyFigure
  title: string
}

export default function PlotlyChart({ figure, title }: PlotlyChartProps) {
  return (
    <div className="w-full" data-testid="plotly-chart" role="img" aria-label={title}>
      <Plot
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        data={(figure?.data ?? []) as any}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        layout={
          {
            autosize: true,
            margin: { l: 64, r: 24, t: 12, b: 56 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            ...(figure?.layout ?? {}),
          } as any
        }
        config={{
          responsive: true,
          displaylogo: false,
          // The card owns the title/subtitle; keep Plotly's mode bar for
          // real interactivity (zoom/pan/hover) per spec.
          modeBarButtonsToRemove: ['lasso2d', 'select2d'],
          toImageButtonOptions: { format: 'png', filename: title },
        }}
        useResizeHandler
        style={{ width: '100%', height: '340px' }}
      />
    </div>
  )
}
