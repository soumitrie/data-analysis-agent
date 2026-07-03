# Roadmap — Ledger Lens

Investment-banking-grade transaction visualization agent.

---

## What This Agent Does

Ledger Lens turns a high-volume transaction CSV (retail bank ledgers, card/payment feeds, trading blotters, treasury wires — up to ~1M rows) into a best-in-class, investment-banking-grade chart pack. The user uploads one file in the browser and immediately gets an auto-generated, publication-quality set of charts, smart-profiled to that specific dataset. The tool auto-detects each column's role (date / amount / category / counterparty), states a best-guess interpretation as a visible assumption note (it never interrogates the user), asks the LLM to select the most insightful charts for the data, and a local deterministic pandas engine computes every figure exactly. Later phases add plain-English chart requests, the full chart arsenal, executive-summary narrative, proactive anomaly/insight detection, static publication-grade image export, and cross-session persistence.

## Who Uses It

A single analyst / banker / treasury or risk professional working locally in the browser. Their role is to make sense of a large transaction file fast and produce charts that are credible in front of an investment committee or client — the "so what" at a glance, with numbers they can defend to the cent.

## Core Problem Being Solved

Today this person either (a) hand-builds charts in Excel/Python, spending hours on aggregation and formatting to reach publication polish, or (b) pastes sensitive transaction data into a general-purpose AI tool that both leaks the raw rows and produces charts whose numbers can't be trusted. Ledger Lens replaces both: the raw rows never leave the machine, every number is computed locally and exactly, and the output is polished to an IB house style out of the box.

## Success Criteria

- [ ] Uploading the bundled sample CSV (`samples/transactions_sample.csv`) produces a 3-chart pack in the browser in under 30 seconds, with zero manual configuration.
- [ ] Every figure on every chart equals the value computed by pandas over the **full** dataset (not a sample) — asserted in the Phase-1 gate against the real data.
- [ ] Only column schema/types and aggregated numbers are ever sent to the LLM — the gate asserts no raw transaction row is present in the LLM request payload.
- [ ] The auto-detected column mapping and its assumption note are visible above the chart pack, and correctly identify date / amount / category / counterparty on the sample file.
- [ ] The three charts (time-series trend, top-N breakdown, transaction-size distribution) render as interactive Plotly charts under a consistent IB house style (palette, typography, spacing, labeling).

## What This Agent Does NOT Do (Out of Scope)

- Never sends raw transaction rows to the LLM — only schema + aggregates.
- Never lets the LLM compute or estimate a displayed figure — the local pandas engine computes every number.
- No multi-file / multi-dataset comparison in one analysis (one file at a time).
- No user accounts, auth, or multi-tenant hosting (single-user, localhost).
- No write-back to source systems, no scheduled/automated runs — it is upload-triggered and interactive only.
- No forecasting / predictive modeling — descriptive visualization only.
- Phase 1 does NOT do: NL chart requests, the full chart arsenal, executive summary, data-quality flags, anomaly/insight detection, static-image or pack export, cost/token display in the UI, or cross-session persistence. These are later phases and appear in Phase 1 only as clearly-labelled non-functional stubs.

## Key Constraints

- **Privacy (hard, from Phase 1):** raw rows never leave the machine. The LLM receives ONLY column schema/types and aggregated numbers. A local pandas engine computes every displayed figure.
- **Accuracy (hard):** every number is computed from the real data by the local engine, never estimated or produced by the LLM.
- **Scale:** files up to ~1M rows within a ~30s budget — efficient pandas aggregation; sample/aggregate only for the LLM-facing profile, never for the computed figures.
- **Publication polish (hard):** charts must look genuinely top-tier under one IB house style — not default library output.
- **Stack is fixed to the skeleton:** Python + FastAPI + LangGraph + pandas + SQLite + Next.js + Plotly, LLM = Google Gemini. See `architecture.md` → `## Stack`.
- **Run/test path:** single origin — `cd frontend && pnpm build` then `uv run python -m src`, open `http://localhost:8001/app/`. Health at `http://localhost:8001/health`.

---

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win:** upload a CSV → auto 3-chart pack. Everything else ships as clearly-labelled non-functional stubs so the user sees the vision. Later phases wire each stub into a real feature.

### Phase 1 — Upload → Auto Chart Pack

- **Goal:** The user uploads the sample transaction CSV and, with zero configuration, sees an auto-detected column mapping (with a visible assumption note) plus a 3-chart publication-grade Plotly pack — time-series trend, top-N breakdown, transaction-size distribution — all figures computed locally over the full dataset. Deferred features appear as labelled stubs.
- **Independent slices (parallel build units):**
  - `backend-charting` (backend) — deps: none. Replaces the `transform_text` capability slot with the charting pipeline: CSV parse + in-memory dataset store; pandas profiling + column-role detection; deterministic figure computation for the 3 chart types (with the IB Plotly house-style template); the LangGraph nodes (`load_dataset → profile → detect_columns → plan_charts` (Gemini) `→ compute_figures → finalize`); the Gemini chart-planning call (schema + aggregates only); FastAPI upload + analyze endpoints; `AnalysisRun` DB model; structured token/latency logging; and the bundled `samples/transactions_sample.csv`.
  - `frontend-ui` (frontend) — deps: **API contract only** (the exact request/response shapes in `spec/api.md`; no runtime dependency — both slices build to the contract). Replaces `frontend/src/app/page.tsx`: upload dropzone, "file loaded / N rows" state, staged progress spinner, column-mapping + assumption-note panel, the 3 Plotly chart cards under the IB house style, and clearly-labelled non-functional stubs (NL chart request box, export buttons, cost/token panel, history panel). Adds the `tests/e2e/` Playwright smoke test.
- **Key surfaces / files:**
  - backend: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/analysis/` (new: `profiling.py`, `columns.py`, `figures.py`, `housestyle.py`, `store.py`), `src/prompts/plan_charts.md`, `src/api/datasets.py`, `src/api/__init__.py` (register router), `src/db/models.py` (`AnalysisRun`), `src/domain/analysis.py`, `samples/transactions_sample.csv`, `tests/integration/test_chart_pack.py`, `tests/unit/analysis/*`.
  - frontend: `frontend/src/app/page.tsx`, `frontend/src/components/*`, `frontend/package.json` (add `plotly.js-dist-min`, `react-plotly.js`, `@playwright/test`), `frontend/tests/e2e/chart_pack.spec.ts`.
- **Gate command:** `uv run pytest tests/integration/test_chart_pack.py tests/unit -q` (runs against real Gemini via `AGENT_GEMINI_API_KEY` in `.env`, SQLite production driver). Full Phase-1 gate also requires: (1) app boots via `uv run python -m src` with no import error; (2) `init_db()` creates the schema (skeleton uses `Base.metadata.create_all`, no Alembic — see `data.md`); (3) after `cd frontend && pnpm build`, `http://localhost:8001/app/` is styled (built CSS has real utility selectors); (4) `cd frontend && npx playwright test tests/e2e/ --reporter=line` passes against the live app.
- **How the user tests it (handoff seed):** Run `cd frontend && pnpm build` then `uv run python -m src`. Open `http://localhost:8001/app/`. Click the upload area and choose `samples/transactions_sample.csv`. Watch the staged spinner (Profiling → Detecting columns → Building charts). Within ~30s you see: a mapping panel at the top ("Interpreted `txn_date` as date, `amount` as amount, `category` as category, `counterparty` as counterparty" + assumption note), then three interactive charts (trend line, top-counterparties bar, transaction-size histogram) in the IB house style — hover to see exact values. The greyed-out "Ask for a chart", "Export", "Cost & tokens", and "History" panels are **labelled stubs** ("Coming soon") — not bugs.

### Phase 2 — Ask + Observe (NL chart requests + observability)

- **Goal:** With a dataset loaded, the user types a plain-English request ("show me daily volume for the top 3 counterparties") and gets a new chart added to the pack; they can expand any chart to see the exact aggregated data table behind it and the per-analysis token count + estimated cost. Conversation history (prior requests in the session) gives follow-ups context.
- **Capabilities:** `nl_chart_requests`, `aggregated_data_table`, `cost_token_display` (≥3).
- **Independent slices (parallel build units):**
  - `backend-nl` (backend) — deps: none. Adds a `route_request` / `plan_from_nl` graph path, per-session chart+message history in the dataset store, an aggregated-data-table serializer, and the tokens/cost surfaced in the analyze/ask responses.
  - `frontend-ask` (frontend) — deps: API contract. Wires the NL request box (real), the expandable data-table drawer per chart, and the cost/token panel — replacing those Phase-1 stubs.
- **Key surfaces / files:** backend: `src/graph/nodes.py` (`route_request`, `plan_from_nl`), `src/api/datasets.py` (`POST /api/datasets/{id}/ask`), `src/analysis/tables.py`, `src/domain/analysis.py`; frontend: `frontend/src/components/AskBox.tsx`, `DataTableDrawer.tsx`, `CostPanel.tsx`.
- **Gate command:** `uv run pytest tests/integration/test_ask.py -q` (real Gemini, SQLite). Plus `npx playwright test tests/e2e/ask.spec.ts`.
- **How the user tests it (handoff seed):** Load the sample, then type "monthly total by category" in the now-active Ask box → a new chart appears. Click a chart's "Show data" to see the exact aggregated table; the cost/token panel shows real numbers for the last analysis.

### Phase 3 — Full Arsenal + Narrative (composition/flow/concentration/outlier + exec summary + data-quality flags)

- **Goal:** The auto-pack and NL requests can now produce the full chart arsenal (composition/waterfall/treemap, flow/Sankey, concentration/heatmap, box/outlier), the auto-pack is topped with a written executive-summary "key findings", and a data-quality panel flags issues (nulls, duplicates, mixed types, out-of-range dates).
- **Capabilities:** `full_chart_arsenal`, `executive_summary`, `data_quality_flags` (≥3).
- **Independent slices (parallel build units):**
  - `backend-arsenal` (backend) — deps: none. Extends `figures.py` with the new chart types + house-style variants, adds a `write_summary` node (Gemini, aggregates only), and a `data_quality` profiling pass.
  - `frontend-arsenal` (frontend) — deps: API contract. Renders the new chart types, the exec-summary block above the pack, and the data-quality flag panel.
- **Key surfaces / files:** backend: `src/analysis/figures.py`, `src/analysis/quality.py`, `src/graph/nodes.py` (`write_summary`, `data_quality`), `src/prompts/exec_summary.md`; frontend: `frontend/src/components/ExecSummary.tsx`, `QualityPanel.tsx`, arsenal chart renderers.
- **Gate command:** `uv run pytest tests/integration/test_arsenal.py -q` (real Gemini, SQLite). Plus `npx playwright test tests/e2e/arsenal.spec.ts`.
- **How the user tests it (handoff seed):** Load the sample → the pack now leads with a written "Key findings" summary, includes composition/flow/concentration charts, and shows a data-quality panel flagging any nulls/dupes in the sample.

### Phase 4 — Proactive + Export + Persistence (anomalies/insights/follow-ups + static export + saved analyses)

- **Goal:** The tool proactively flags anomalies/outliers, surfaces "so what" insights, and suggests 2–3 sharp follow-ups; the user can download individual charts (high-res PNG/SVG) and export the full pack as a slide-ready bundle; analyses are persisted server-side and reopenable across sessions.
- **Capabilities:** `proactive_insights`, `static_publication_export`, `session_persistence` (≥3).
- **Independent slices (parallel build units):**
  - `backend-proactive` (backend) — deps: none. Adds an `anomaly_scan` + `suggest_followups` node (local detection feeding aggregates to Gemini for phrasing), static Kaleido PNG/SVG rendering with slide-ready sizing, a bundle exporter, and persistence of `AnalysisRun` + chart specs for reopen.
  - `frontend-proactive` (frontend) — deps: API contract. Wires the insights/anomaly banners, follow-up suggestion chips, per-chart download + full-pack export (replacing the Phase-1 export stub), and a real History panel to reopen past analyses.
- **Key surfaces / files:** backend: `src/analysis/anomalies.py`, `src/analysis/export.py`, `src/graph/nodes.py` (`anomaly_scan`, `suggest_followups`), `src/api/datasets.py` (export + history endpoints); frontend: `frontend/src/components/Insights.tsx`, `ExportBar.tsx`, `HistoryPanel.tsx`.
- **Gate command:** `uv run pytest tests/integration/test_proactive_export.py -q` (real Gemini, SQLite). Plus `npx playwright test tests/e2e/export.spec.ts`.
- **How the user tests it (handoff seed):** Load the sample → see anomaly flags + 2–3 follow-up chips; click a follow-up to generate that chart; download a chart as PNG and export the full pack; reload the page and reopen the past analysis from the History panel.
