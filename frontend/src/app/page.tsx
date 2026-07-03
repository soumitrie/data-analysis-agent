'use client'

import { useCallback, useState } from 'react'
import { analyzeDataset, messageForError, uploadDataset } from '@/lib/api'
import type { AnalysisResult, Dataset } from '@/lib/types'
import Header from '@/components/Header'
import UploadZone from '@/components/UploadZone'
import ProgressSpinner from '@/components/ProgressSpinner'
import MappingPanel from '@/components/MappingPanel'
import ChartCard from '@/components/ChartCard'
import ChartSkeleton from '@/components/ChartSkeleton'
import ErrorCallout from '@/components/ErrorCallout'
import Sidebar from '@/components/Sidebar'

type Phase = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error'

export default function Home() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const runAnalyze = useCallback(async (datasetId: string) => {
    setPhase('analyzing')
    setError(null)
    setResult(null)
    try {
      const analysis = await analyzeDataset(datasetId)
      setResult(analysis)
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

  const busy = phase === 'uploading' || phase === 'analyzing'
  const showSkeletons = phase === 'analyzing' || phase === 'uploading'
  const charts = result?.charts ?? []

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

            {phase === 'done' && charts.length > 0 && (
              <section aria-label="Chart pack" className="flex flex-col gap-6">
                {charts.map((chart) => (
                  <ChartCard key={chart.id} chart={chart} />
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

            {phase === 'done' && charts.length === 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
                <p className="text-sm text-slate-500">
                  No charts were returned for this dataset.
                </p>
              </div>
            )}
          </div>

          {/* Right sidebar (labelled stubs) */}
          <Sidebar />
        </div>
      </main>
    </div>
  )
}
