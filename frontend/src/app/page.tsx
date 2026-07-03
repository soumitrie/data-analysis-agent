'use client'

import { useCallback, useState } from 'react'
import { analyzeDataset, messageForError, uploadDataset } from '@/lib/api'
import type { AnalysisResult, ChartSpec, Dataset, Usage } from '@/lib/types'
import Header from '@/components/Header'
import UploadZone from '@/components/UploadZone'
import ProgressSpinner from '@/components/ProgressSpinner'
import MappingPanel from '@/components/MappingPanel'
import ChartCard from '@/components/ChartCard'
import ChartSkeleton from '@/components/ChartSkeleton'
import ErrorCallout from '@/components/ErrorCallout'
import Sidebar from '@/components/Sidebar'
import AskBox from '@/components/AskBox'
import CostPanel from '@/components/CostPanel'

type Phase = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error'

export default function Home() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [askedCharts, setAskedCharts] = useState<ChartSpec[]>([])
  const [usage, setUsage] = useState<Usage | null>(null)
  const [error, setError] = useState<string | null>(null)

  const runAnalyze = useCallback(async (datasetId: string) => {
    setPhase('analyzing')
    setError(null)
    setResult(null)
    setAskedCharts([])
    try {
      const analysis = await analyzeDataset(datasetId)
      setResult(analysis)
      setUsage(analysis.usage ?? null)
      setPhase('done')
    } catch (err) {
      setError(messageForError(err))
      setPhase('error')
    }
  }, [])

  const handleFile = useCallback(
    async (file: File) => {
      setPhase('uploading')
      setError(null)
      setResult(null)
      setDataset(null)
      setAskedCharts([])
      setUsage(null)
      try {
        const uploaded = await uploadDataset(file)
        setDataset(uploaded)
        // Auto-fire the analysis as soon as the upload lands.
        await runAnalyze(uploaded.dataset_id)
      } catch (err) {
        setError(messageForError(err))
        setPhase('error')
      }
    },
    [runAnalyze],
  )

  // Append a chart returned by the Ask box to the pack (below the auto-pack).
  const handleAskedChart = useCallback((chart: ChartSpec) => {
    setAskedCharts((prev) => [...prev, chart])
  }, [])

  const handleUsage = useCallback((next: Usage | null | undefined) => {
    if (next) setUsage(next)
  }, [])

  const busy = phase === 'uploading' || phase === 'analyzing'
  const showSkeletons = phase === 'analyzing' || phase === 'uploading'
  const autoCharts = result?.charts ?? []
  const datasetId = dataset?.dataset_id ?? ''
  // The Ask box is only live once the auto-pack analysis has completed.
  const askReady = phase === 'done' ? dataset : null

  return (
    <div className="min-h-screen bg-slate-100">
      <Header />

      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
          {/* Main column */}
          <div className="flex min-w-0 flex-col gap-6">
            <UploadZone dataset={dataset} busy={busy} onFile={handleFile} />

            {phase === 'error' && error && (
              <ErrorCallout
                message={error}
                onRetry={
                  dataset ? () => void runAnalyze(dataset.dataset_id) : undefined
                }
              />
            )}

            {busy && <ProgressSpinner />}

            {result?.column_mapping && phase === 'done' && (
              <MappingPanel mapping={result.column_mapping} />
            )}

            {/* Chart pack */}
            {showSkeletons && (
              <div className="flex flex-col gap-6" aria-hidden="true">
                <ChartSkeleton />
                <ChartSkeleton />
                <ChartSkeleton />
              </div>
            )}

            {phase === 'done' && (autoCharts.length > 0 || askedCharts.length > 0) && (
              <section aria-label="Chart pack" className="flex flex-col gap-6">
                {autoCharts.map((chart) => (
                  <ChartCard key={chart.id} chart={chart} datasetId={datasetId} />
                ))}
                {askedCharts.map((chart) => (
                  <ChartCard key={chart.id} chart={chart} datasetId={datasetId} />
                ))}
              </section>
            )}

            {/* Empty / idle state */}
            {phase === 'idle' && (
              <div className="rounded-xl border border-slate-200 bg-white p-10 text-center shadow-sm">
                <p className="text-base font-semibold text-navy-900">
                  Upload a transaction CSV to begin
                </p>
                <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
                  Ledger Lens auto-detects your columns and builds a publication-grade,
                  investment-banking-style chart pack — every figure computed locally over the
                  full dataset, nothing sampled.
                </p>
              </div>
            )}

            {phase === 'done' && autoCharts.length === 0 && askedCharts.length === 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
                <p className="text-sm text-slate-500">
                  No charts were returned for this dataset.
                </p>
              </div>
            )}
          </div>

          {/* Right sidebar: real Ask + Cost controls, then labelled stubs. */}
          <div className="flex flex-col gap-4">
            <AskBox
              dataset={askReady}
              onChart={handleAskedChart}
              onUsage={handleUsage}
            />
            <CostPanel usage={usage} />
            <Sidebar />
          </div>
        </div>
      </main>
    </div>
  )
}
