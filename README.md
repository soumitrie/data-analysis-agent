# Ledger Lens

> Investment-banking-grade transaction visualization. Upload one transaction CSV and get a publication-quality, auto-generated chart pack — with every figure computed locally over the full dataset and raw rows never leaving your machine.

**Status: Phase 2 — Ask + Observe.** On top of the Phase-1 auto chart pack (upload the bundled sample CSV → auto-detected column mapping + a 3-chart IB-house-style Plotly pack, every number computed locally over the full data), the user can now type a plain-English chart request, expand any chart to see the exact aggregated data table behind it, and read the per-analysis Gemini token count + estimated cost. Remaining later-phase features (the full chart arsenal, executive summary, data-quality flags, export, history) appear in the UI only as clearly-labelled non-functional stubs.

---

## How it works

1. You upload a CSV → FastAPI parses it into an in-memory pandas DataFrame (raw rows stay in process memory, never on disk).
2. A LangGraph agent runs: `load_dataset → profile → detect_columns → plan_charts (Gemini) → compute_figures → finalize`.
3. Google Gemini sees **only** an aggregated profile (schema, cardinalities, date range, amount summary stats, top category labels + totals) — never a raw transaction row — and returns a validated chart plan.
4. A local pandas engine computes every displayed figure **exactly over the full dataset** and renders each as a Plotly figure under the IB house style.

## Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js + pnpm (for the frontend build)
- A Google Gemini API key

## Configure

Copy `.env.example` to `.env` and set your key:

```
AGENT_GEMINI_API_KEY=your-key-here
```

- Provider is auto-detected — with the Gemini key set, the app uses Google Gemini (no Anthropic).
- Default model is `gemini-3.1-pro` (resolves to the current preview alias on the live API); override with `AGENT_LLM_MODEL`.
- Optional cost rates: `AGENT_LLM_INPUT_COST_PER_1K` / `AGENT_LLM_OUTPUT_COST_PER_1K` (USD per 1,000 tokens). When unset, estimated cost is reported as `null` ("n/a"); token counts are always logged.

## Run

```bash
cd frontend && pnpm build        # produces frontend/out/
cd .. && uv run python -m src    # starts uvicorn on port 8001 (single worker)
```

- App UI: `http://localhost:8001/app/`
- Health check: `http://localhost:8001/health` → `{"data":{"status":"ok"},"error":null}`

The server is a single process / single worker by design — the in-memory dataset store is process-local.

## Try it (the Phase-1 journey)

1. Open `http://localhost:8001/app/`.
2. Click the upload area and choose `samples/transactions_sample.csv` (a ~5,000-row realistic transaction file bundled in the repo).
3. Within ~30s you see: a mapping panel ("Interpreted `txn_date` as date, `amount` as amount, `category` as category, `counterparty` as counterparty" + assumption note), then three interactive charts (trend line, top-counterparties bar, transaction-size histogram). Hover any chart for exact values.
4. The greyed-out "Ask for a chart", "Export", "Cost & tokens", and "History" panels are **labelled stubs** ("Coming soon") — not bugs.

### Upload from the command line (API only)

```bash
# Upload → get a dataset_id
curl -s -X POST http://localhost:8001/api/datasets \
  -F "file=@samples/transactions_sample.csv"

# Analyze → get the chart pack
curl -s -X POST http://localhost:8001/api/datasets/<dataset_id>/analyze

# Phase 2 — Ask for a chart in plain English (adds a new chart to the pack)
curl -s -X POST http://localhost:8001/api/datasets/<dataset_id>/ask \
  -H "Content-Type: application/json" \
  -d '{"request_text": "monthly total by category"}'

# Phase 2 — the exact aggregated data behind any chart (auto-pack id c1.. or asked id q1..)
curl -s http://localhost:8001/api/datasets/<dataset_id>/charts/<chart_id>/table
```

## Phase 2 — Ask + Observe (natural-language requests + data table + cost/tokens)

With a dataset loaded, three Phase-1 stubs are now real:

- **Ask box** (`POST /api/datasets/{id}/ask`) — type a plain-English request
  ("monthly total by category", "top 5 counterparties by total outflow"). Gemini maps
  it to ONE parameterized chart spec from the whitelist (`time_series` /
  `top_n_breakdown` / `distribution`, with bucket / grouping / sign / metric / top-N
  parameters), which is validated against the detected roles and **computed locally by
  pandas over the full data** — the LLM never produces a number. The new chart is
  appended to the pack with a session-unique id (`q1`, `q2`, …). Prior requests this
  session give follow-ups context. An out-of-scope request (e.g. "tell me a joke")
  returns **HTTP 200 with `declined:true`, `chart:null`, and a friendly message** — never
  a fabricated chart or a 5xx.
- **Data table drawer** (`GET /api/datasets/{id}/charts/{cid}/table`) — the exact
  aggregated, bucket-level rows behind any chart (auto-pack or asked). The numbers
  EXACTLY equal the chart's plotted series (figure and table are built from the same
  aggregated arrays). **Never returns a raw transaction row.**
- **Cost & tokens** — the `analyze` and `ask` responses both carry
  `usage: {prompt_tokens, completion_tokens, estimated_cost_usd}` with real Gemini token
  counts. `estimated_cost_usd` is computed from `AGENT_LLM_INPUT_COST_PER_1K` /
  `AGENT_LLM_OUTPUT_COST_PER_1K` when set, else `null` ("n/a").

**Privacy is unchanged:** Gemini receives ONLY the aggregated `LLMProfile`, the detected
roles, and a short summary of prior requests — never a raw transaction row.

## API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/datasets` | Upload a CSV (multipart `file`) → `{dataset_id, row_count, column_count, columns[]}` |
| `POST` | `/api/datasets/{dataset_id}/analyze` | Run the agent → `{run_id, status, column_mapping, profile, charts[], usage, elapsed_ms}` |
| `POST` | `/api/datasets/{dataset_id}/ask` | NL chart request → `{run_id, status, declined, message, chart, usage, elapsed_ms}` (Phase 2) |
| `GET`  | `/api/datasets/{dataset_id}/charts/{chart_id}/table` | Aggregated data behind a chart → `{chart_id, columns, rows}` (Phase 2) |
| `GET`  | `/health` | Liveness |

All responses use the envelope `{ "data": ..., "error": ... }`.

## Test

The gate runs against the **real** Gemini API using `AGENT_GEMINI_API_KEY` from `.env`, on the SQLite production driver:

```bash
# Phase 1 gate
uv run pytest tests/integration/test_chart_pack.py tests/unit -q

# Phase 2 gate (NL ask + aggregated table + cost/tokens)
uv run pytest tests/integration/test_ask.py tests/unit -q

# Full suite
uv run pytest -q
```

These assert, among other things, that the trend chart's total equals
`df['amount'].sum()` over the full dataset, that the histogram count equals `len(df)`,
that an asked chart's data table EXACTLY equals an independent pandas aggregation over
the full data (and contains only aggregated buckets), that an un-chartable request
declines gracefully, and that the serialized Gemini prompt (auto AND NL) contains **no
raw transaction row**.

## Data & privacy

- **Raw rows** live only in the in-memory `DatasetStore` (LRU-capped to a few datasets; per-dataset cap of 1,000,000 rows). They are never written to disk and never sent to the LLM.
- **SQLite** (`./data/agent.db`, created automatically via `Base.metadata.create_all` — no Alembic) stores only `AnalysisRun` metadata: mapping, chart plan, token usage, status.
- Only the aggregated `LLMProfile` is ever sent to Gemini.

## Observability

Structured JSON logs go to stdout for every request/response, LLM call (model, prompt/completion tokens, latency), and pipeline node (name, elapsed, error). The Phase-2 `ask` path additionally logs `dataset_id`, `run_id`, request length, token counts, latency, and the `declined` flag. Raw rows and secrets are never logged.
