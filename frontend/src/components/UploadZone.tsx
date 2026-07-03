'use client'

import { useRef, useState } from 'react'
import type { Dataset } from '@/lib/types'

interface UploadZoneProps {
  dataset: Dataset | null
  busy: boolean
  onFile: (file: File) => void
}

function isCsv(file: File): boolean {
  return (
    file.type === 'text/csv' ||
    file.type === 'application/vnd.ms-excel' ||
    file.name.toLowerCase().endsWith('.csv')
  )
}

export default function UploadZone({ dataset, busy, onFile }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  function handleFiles(files: FileList | null) {
    setLocalError(null)
    const file = files?.[0]
    if (!file) {
      setLocalError('Please choose a .csv file.')
      return
    }
    if (!isCsv(file)) {
      setLocalError('Please choose a .csv file.')
      return
    }
    onFile(file)
  }

  return (
    <section aria-labelledby="upload-heading">
      <h2 id="upload-heading" className="sr-only">
        Upload a transaction CSV
      </h2>

      <button
        type="button"
        onClick={() => !busy && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          if (!busy) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!busy) handleFiles(e.dataTransfer.files)
        }}
        disabled={busy}
        data-testid="upload-zone"
        className={`flex w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
          dragging
            ? 'border-accent-600 bg-accent-600/5'
            : 'border-slate-300 bg-white hover:border-accent-500 hover:bg-slate-50'
        } focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-600 disabled:cursor-not-allowed disabled:opacity-60`}
      >
        <svg
          className="h-10 w-10 text-accent-600"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16.5V6m0 0L8.25 9.75M12 6l3.75 3.75M3 16.5v1.875A2.625 2.625 0 005.625 21h12.75A2.625 2.625 0 0021 18.375V16.5"
          />
        </svg>
        <span className="text-base font-semibold text-navy-900">
          Drag &amp; drop a transaction CSV
        </span>
        <span className="text-sm text-slate-500">or click to choose a .csv file</span>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
        aria-label="Choose a CSV file"
      />

      {localError && (
        <p role="alert" className="mt-3 text-sm font-medium text-red-600">
          {localError}
        </p>
      )}

      {dataset && (
        <div
          data-testid="dataset-loaded"
          className="mt-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
        >
          <p className="text-sm font-semibold text-navy-900">
            Loaded {dataset.filename} · {dataset.row_count.toLocaleString()} rows ·{' '}
            {dataset.column_count.toLocaleString()} columns
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {dataset.columns.map((col) => (
              <span
                key={col.name}
                title={`${col.dtype}${
                  col.sample_values?.length ? ` · e.g. ${col.sample_values.join(', ')}` : ''
                }`}
                className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600"
              >
                {col.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
