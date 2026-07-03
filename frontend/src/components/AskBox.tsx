'use client'

import { useState } from 'react'
import { askDataset, messageForError } from '@/lib/api'
import type { AskResult, ChartSpec, Dataset, Usage } from '@/lib/types'

interface AskBoxProps {
  dataset: Dataset | null
  /** Called when the ask returns a real chart to append to the pack. */
  onChart: (chart: ChartSpec) => void
  /** Called with fresh usage after every successful ask (chart OR decline). */
  onUsage: (usage: Usage | null | undefined) => void
}

export default function AskBox({ dataset, onChart, onUsage }: AskBoxProps) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [decline, setDecline] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const enabled = !!dataset && !busy
  const canSubmit = enabled && text.trim().length > 0

  async function submit() {
    if (!dataset || !text.trim() || busy) return
    setBusy(true)
    setError(null)
    setDecline(null)
    try {
      const result: AskResult = await askDataset(dataset.dataset_id, text.trim())
      onUsage(result.usage)
      if (result.declined || !result.chart) {
        // Friendly, in-scope decline — a muted note, never a red error.
        setDecline(
          result.message ??
            "That request couldn't be turned into a chart — try rephrasing.",
        )
      } else {
        onChart(result.chart)
        setText('')
      }
    } catch (err) {
      setError(messageForError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      data-testid="ask-box"
      aria-labelledby="ask-heading"
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 id="ask-heading" className="text-sm font-semibold text-navy-900">
          Ask for a chart
        </h3>
        <span className="inline-flex items-center rounded-full bg-accent-600/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent-600">
          Live
        </span>
      </div>

      <textarea
        data-testid="ask-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault()
            void submit()
          }
        }}
        rows={3}
        disabled={!enabled}
        placeholder={
          dataset
            ? 'e.g. monthly total by category'
            : 'Load a dataset to ask for a chart…'
        }
        aria-label="Describe the chart you want in plain English"
        className="w-full resize-none rounded-md border border-slate-200 bg-white p-2.5 text-sm text-navy-900 placeholder:text-slate-400 focus:border-accent-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-600/40 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
      />

      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-[11px] text-slate-400">
          {dataset ? '⌘/Ctrl + Enter to send' : 'Ask unlocks after upload'}
        </span>
        <button
          type="button"
          data-testid="ask-submit"
          onClick={() => void submit()}
          disabled={!canSubmit}
          className="inline-flex items-center gap-2 rounded-md bg-accent-600 px-4 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-accent-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-600/50 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {busy && (
            <span
              data-testid="ask-spinner"
              className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white"
              aria-hidden="true"
            />
          )}
          {busy ? 'Charting…' : 'Ask'}
        </button>
      </div>

      {decline && (
        <p
          role="status"
          data-testid="ask-decline"
          className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600"
        >
          {decline}
        </p>
      )}

      {error && (
        <p
          role="alert"
          data-testid="ask-error"
          className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700"
        >
          {error}
        </p>
      )}
    </section>
  )
}
