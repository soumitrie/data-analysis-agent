import type { ColumnMapping } from '@/lib/types'

interface MappingPanelProps {
  mapping: ColumnMapping
}

const ROLES: { key: keyof ColumnMapping; label: string }[] = [
  { key: 'date', label: 'Date' },
  { key: 'amount', label: 'Amount' },
  { key: 'category', label: 'Category' },
  { key: 'counterparty', label: 'Counterparty' },
]

export default function MappingPanel({ mapping }: MappingPanelProps) {
  return (
    <section
      data-testid="mapping-panel"
      aria-labelledby="mapping-heading"
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 id="mapping-heading" className="text-sm font-semibold uppercase tracking-wide text-slate-500">
        Detected column roles
      </h2>

      <dl className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {ROLES.map(({ key, label }) => {
          const column = mapping[key] as string | null
          return (
            <div
              key={key}
              data-testid={`role-${key}`}
              className="flex flex-col gap-1 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3"
            >
              <dt className="text-xs font-semibold uppercase tracking-wide text-accent-600">
                {label}
              </dt>
              <dd className="truncate font-mono text-sm font-medium text-navy-900" title={column ?? undefined}>
                {column ?? '— not detected'}
              </dd>
            </div>
          )
        })}
      </dl>

      {mapping.assumption_note && (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Best-guess interpretation — no configuration needed
          </p>
          <p className="mt-1 text-sm text-slate-600">{mapping.assumption_note}</p>
        </div>
      )}
    </section>
  )
}
