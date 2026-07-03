# UI — Ledger Lens

---

## UI Type

Single-page web app (Next.js 15 static export, served at `http://localhost:8001/app/`). One screen: upload → mapping panel → chart pack, with a persistent sidebar of labelled stubs for deferred features. Interactive charts via `react-plotly.js`.

## IB House Style (the visual contract — a HARD requirement)

The pack must read as investment-banking-grade, not default Plotly. The house style is defined **once, server-side**, as a Plotly template applied to every figure in `compute_figures`; the frontend applies matching chrome around it.

- **Palette:** restrained, institutional. `Assumed:` deep navy/charcoal primary (`#1B2A41`), a single muted accent (`#2E6E8E` teal-blue) for primary series, a low-saturation categorical ramp for breakdowns, neutral greys for gridlines/axes. No default bright Plotly colors.
- **Typography:** a clean sans (Inter, falling back to Helvetica/Arial). Chart title bold, subtitle in muted grey; axis labels small-caps-feel, tick labels light. Consistent sizes across all charts.
- **Spacing/layout:** generous margins, thin horizontal gridlines only (no vertical clutter), white plot background, no chart borders. Numbers formatted with thousands separators and currency where relevant.
- **Labeling:** every chart has a clear title + subtitle (unit/aggregation), axis titles, and a subtle source/footnote line ("Computed locally · figures exact"). Hover tooltips show exact values.
- Frontend chrome: each chart sits in a clean white card with subtle shadow, title row, and (stubbed) export icon; the page uses the same navy/neutral palette and Inter font so cards and charts feel unified.

## Views / Screens

### Screen: Analyzer (the single page)

**Purpose:** upload one transaction CSV and see the auto chart pack.

**Layout (top → bottom, main column) + right sidebar:**

**Main column:**
- **Header** — "Ledger Lens" wordmark + one-line tagline ("Investment-grade charts from your transaction data — computed locally, never sampled").
- **Upload zone (REAL)** — drag-and-drop / click-to-choose a `.csv`. On select → `POST /api/datasets` → shows "Loaded `filename` · N rows · M columns" and a small column-preview chip row. Then auto-fires `POST /api/datasets/{id}/analyze`.
- **Progress spinner (REAL spinner; staged text is indicative)** — while analyzing, a spinner with staged captions: "Profiling data…" → "Detecting columns…" → "Building charts…". `Assumed:` Phase-1 staged text is client-side timed/indicative (true streamed progress is a later enhancement) — labelled subtly so it is not read as precise per-node telemetry.
- **Mapping panel (REAL)** — above the pack: the detected roles (date / amount / category / counterparty → column names) as labeled chips, plus the assumption note in a muted callout ("Best-guess interpretation — no configuration needed").
- **Chart pack (REAL)** — the 3 charts from `charts[]`, each in an IB-style card: title, subtitle, interactive Plotly figure, footnote. Rendered in order (trend, top-N, distribution).

**Right sidebar (all clearly LABELLED NON-FUNCTIONAL STUBS — "Coming soon"):**
- **Ask for a chart** — a disabled text box ("Ask in plain English… — Phase 2").
- **Cost & tokens** — a greyed panel ("Token usage & cost — Phase 2").
- **Export** — disabled "Download PNG/SVG" + "Export pack" buttons ("Phase 4").
- **History** — a greyed list ("Past analyses — Phase 4").

Each stub carries a visible "Coming soon" / phase badge so it is never mistaken for a broken control.

**Actions available:**
- Upload a CSV (real).
- Hover charts for exact values; zoom/pan via Plotly toolbar (real).
- (Stubs are visibly disabled.)

## Error States

- **No file / wrong type:** inline message under the upload zone ("Please choose a .csv file").
- **Upload parse error (400):** red callout with the server message ("Couldn't parse that CSV — check the file").
- **Dataset expired (404 on analyze):** callout prompting re-upload.
- **No chartable columns (422):** callout ("No numeric column found to chart — this file may not be transactional").
- **Gemini/LLM error surfaced (500/502):** callout ("Chart planning failed — please retry"); if the deterministic fallback plan succeeded, charts still render and no error shows.
- **Loading:** the staged spinner (above); the chart area shows skeleton placeholders until figures arrive.
- **Network error:** "Network error — is the server running?" (matches skeleton pattern).

## Tech Stack

Next.js 15 + React 19 + Tailwind v4 (static export, `basePath: '/app'`), `plotly.js-dist-min` + `react-plotly.js` for charts. Playwright (`frontend/tests/e2e/`) for the smoke test. Tailwind v4 requires `postcss.config.mjs` (`@tailwindcss/postcss`) and `@source "../";` in global CSS — never removed. `NODE_OPTIONS=--no-experimental-webstorage` on `dev`/`build`/`start` scripts (Node ≥25 safety).

**Playwright Phase-1 smoke (`frontend/tests/e2e/chart_pack.spec.ts`):** against the live app at `http://localhost:8001/app/` — upload `samples/transactions_sample.csv`, wait for analysis to finish, assert (1) the mapping panel shows the four roles, (2) three chart cards render with a Plotly SVG/canvas node each (not a spinner or error), (3) the page is styled. A 200/CSS check alone is not sufficient.
