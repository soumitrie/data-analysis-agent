export default function Header() {
  return (
    <header className="border-b border-slate-200 bg-navy-900 text-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-1 px-6 py-6">
        <div className="flex items-center gap-3">
          <span
            className="flex h-9 w-9 items-center justify-center rounded-md bg-accent-600 text-lg font-bold tracking-tight"
            aria-hidden="true"
          >
            LL
          </span>
          <h1 className="text-2xl font-bold tracking-tight">Ledger Lens</h1>
        </div>
        <p className="text-sm text-slate-300">
          Investment-grade charts from your transaction data — computed locally, never sampled.
        </p>
      </div>
    </header>
  )
}
