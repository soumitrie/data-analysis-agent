'use client'

import type { Usage } from '@/lib/types'

interface CostPanelProps {
  usage: Usage | null
}

function fmtTokens(n: number | null | undefined): string {
  return typeof n === 'number' ? n.toLocaleString('en-US') : '——'
}

function fmtCost(usd: number | null | undefined): string {
  // Never fabricate a cost: show "n/a" when rates are unset (null/undefined).
  if (typeof usd !== 'number') return 'n/a'
  return usd.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })
}

export default function CostPanel({ usage }: CostPanelProps) {
  const prompt = usage?.prompt_tokens
  const completion = usage?.completion_tokens
  const total =
    typeof prompt === 'number' && typeof completion === 'number'
      ? prompt + completion
      : undefined
  const hasData = !!usage

  return (
    <section
      data-testid="cost-panel"
      aria-labelledby="cost-heading"
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 id="cost-heading" className="text-sm font-semibold text-navy-900">
          Cost &amp; tokens
        </h3>
        <span className="inline-flex items-center rounded-full bg-accent-600/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent-600">
          Live
        </span>
      </div>

      {!hasData ? (
        <p className="text-xs text-slate-400">
          Token usage &amp; estimated cost appear here after your first analysis.
        </p>
      ) : (
        <dl className="space-y-1.5 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">Prompt tokens</dt>
            <dd
              data-testid="cost-prompt-tokens"
              className="font-mono font-medium tabular-nums text-navy-900"
            >
              {fmtTokens(prompt)}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Completion tokens</dt>
            <dd
              data-testid="cost-completion-tokens"
              className="font-mono font-medium tabular-nums text-navy-900"
            >
              {fmtTokens(completion)}
            </dd>
          </div>
          <div className="flex justify-between border-t border-slate-100 pt-1.5">
            <dt className="font-medium text-slate-600">Total tokens</dt>
            <dd
              data-testid="cost-total-tokens"
              className="font-mono font-semibold tabular-nums text-navy-900"
            >
              {fmtTokens(total)}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Estimated cost</dt>
            <dd
              data-testid="cost-estimated"
              className="font-mono font-medium tabular-nums text-accent-600"
            >
              {fmtCost(usage?.estimated_cost_usd)}
            </dd>
          </div>
        </dl>
      )}

      <p className="mt-3 border-t border-slate-100 pt-2 text-[11px] text-slate-400">
        Reflects the most recent analysis or request.
      </p>
    </section>
  )
}
