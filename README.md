# Ledger Lens

> Investment-banking-grade transaction visualization. Upload one transaction CSV and get a publication-quality, auto-generated chart pack — with every figure computed locally over the full dataset and raw rows never leaving your machine.

**Status: Phase 1 — Upload → Auto Chart Pack.** This README honestly reflects what is built today: a user uploads the bundled sample CSV and, with zero configuration, gets an auto-detected column mapping (with a visible assumption note) plus a 3-chart Plotly pack — time-series trend, top-N breakdown, and transaction-size distribution — all under one IB house style. Later-phase features (natural-language chart requests, the full chart arsenal, executive summary, data-quality flags, export, cost/token display, history) appear in the UI only as clearly-labelled non-functional stubs.

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
```

## API (Phase 1)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/datasets` | Upload a CSV (multipart `file`) → `{dataset_id, row_count, column_count, columns[]}` |
| `POST` | `/api/datasets/{dataset_id}/analyze` | Run the agent → `{run_id, status, column_mapping, profile, charts[], usage, elapsed_ms}` |
| `GET`  | `/health` | Liveness |

All responses use the envelope `{ "data": ..., "error": ... }`.

## Test

The gate runs against the **real** Gemini API using `AGENT_GEMINI_API_KEY` from `.env`, on the SQLite production driver:

```bash
uv run pytest tests/integration/test_chart_pack.py tests/unit -q
```

This asserts, among other things, that the trend chart's total equals `df['amount'].sum()` over the full dataset, that the histogram count equals `len(df)`, and that the serialized Gemini prompt contains **no raw transaction row**.

## Data & privacy

- **Raw rows** live only in the in-memory `DatasetStore` (LRU-capped to a few datasets; per-dataset cap of 1,000,000 rows). They are never written to disk and never sent to the LLM.
- **SQLite** (`./data/agent.db`, created automatically via `Base.metadata.create_all` — no Alembic) stores only `AnalysisRun` metadata: mapping, chart plan, token usage, status.
- Only the aggregated `LLMProfile` is ever sent to Gemini.

## Observability

Structured JSON logs go to stdout for every request/response, LLM call (model, prompt/completion tokens, latency), and pipeline node (name, elapsed, error). Raw rows and secrets are never logged.
