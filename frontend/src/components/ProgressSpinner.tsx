'use client'

import { useEffect, useState } from 'react'

const STAGES = ['Profiling data…', 'Detecting columns…', 'Building charts…']

export default function ProgressSpinner() {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    // Client-side timed / indicative staging — advances but holds on the last
    // caption until the real result arrives. Labelled below so it is never read
    // as precise per-node telemetry.
    const id = setInterval(() => {
      setStage((s) => (s < STAGES.length - 1 ? s + 1 : s))
    }, 2200)
    return () => clearInterval(id)
  }, [])

  return (
    <div
      data-testid="progress-spinner"
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center gap-4 rounded-xl border border-slate-200 bg-white px-6 py-12 shadow-sm"
    >
      <span
        className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-accent-600"
        aria-hidden="true"
      />
      <p className="text-base font-semibold text-navy-900">{STAGES[stage]}</p>
      <div className="flex gap-1.5" aria-hidden="true">
        {STAGES.map((label, i) => (
          <span
            key={label}
            className={`h-1.5 w-8 rounded-full ${
              i <= stage ? 'bg-accent-600' : 'bg-slate-200'
            }`}
          />
        ))}
      </div>
      <p className="text-xs text-slate-400">Estimated progress · computed locally over the full dataset</p>
    </div>
  )
}
