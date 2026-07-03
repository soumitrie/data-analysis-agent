export default function ChartSkeleton() {
  return (
    <div
      data-testid="chart-skeleton"
      aria-hidden="true"
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="h-4 w-2/3 animate-pulse rounded bg-slate-200" />
      <div className="mt-2 h-3 w-1/3 animate-pulse rounded bg-slate-100" />
      <div className="mt-4 h-[300px] animate-pulse rounded-lg bg-slate-100" />
    </div>
  )
}
