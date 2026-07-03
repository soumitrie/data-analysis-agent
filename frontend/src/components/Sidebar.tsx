function PhaseBadge({ phase }: { phase: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
      Coming soon · {phase}
    </span>
  )
}

function StubPanel({
  title,
  phase,
  children,
}: {
  title: string
  phase: string
  children: React.ReactNode
}) {
  return (
    <section
      data-testid="stub-panel"
      aria-disabled="true"
      className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-500">{title}</h3>
        <PhaseBadge phase={phase} />
      </div>
      <div className="opacity-70">{children}</div>
    </section>
  )
}

export default function Sidebar() {
  return (
    <aside
      aria-label="Upcoming features"
      className="flex flex-col gap-4"
      data-testid="sidebar-stubs"
    >
      {/* Ask for a chart — Phase 2 */}
      <StubPanel title="Ask for a chart" phase="Phase 2">
        <div className="flex flex-col gap-2">
          <textarea
            disabled
            rows={2}
            placeholder="Ask in plain English… — Phase 2"
            className="w-full cursor-not-allowed resize-none rounded-md border border-slate-200 bg-white/60 p-2 text-sm text-slate-400"
          />
          <button
            type="button"
            disabled
            className="cursor-not-allowed rounded-md bg-slate-300 px-3 py-1.5 text-sm font-medium text-white"
          >
            Ask
          </button>
        </div>
      </StubPanel>

      {/* Cost & tokens — Phase 2 */}
      <StubPanel title="Cost &amp; tokens" phase="Phase 2">
        <dl className="space-y-1.5 text-sm text-slate-400">
          <div className="flex justify-between">
            <dt>Prompt tokens</dt>
            <dd>——</dd>
          </div>
          <div className="flex justify-between">
            <dt>Completion tokens</dt>
            <dd>——</dd>
          </div>
          <div className="flex justify-between">
            <dt>Estimated cost</dt>
            <dd>——</dd>
          </div>
        </dl>
        <p className="mt-2 text-xs text-slate-400">Token usage &amp; cost — Phase 2</p>
      </StubPanel>

      {/* Export — Phase 4 */}
      <StubPanel title="Export" phase="Phase 4">
        <div className="flex flex-col gap-2">
          <button
            type="button"
            disabled
            className="cursor-not-allowed rounded-md border border-slate-200 bg-white/60 px-3 py-1.5 text-sm font-medium text-slate-400"
          >
            Download PNG / SVG
          </button>
          <button
            type="button"
            disabled
            className="cursor-not-allowed rounded-md border border-slate-200 bg-white/60 px-3 py-1.5 text-sm font-medium text-slate-400"
          >
            Export pack
          </button>
        </div>
      </StubPanel>

      {/* History — Phase 4 */}
      <StubPanel title="History" phase="Phase 4">
        <ul className="space-y-2 text-sm text-slate-400">
          <li className="rounded-md border border-slate-200 bg-white/60 px-3 py-2">
            Past analyses — Phase 4
          </li>
          <li className="rounded-md border border-slate-200 bg-white/60 px-3 py-2">
            &nbsp;
          </li>
        </ul>
      </StubPanel>
    </aside>
  )
}
