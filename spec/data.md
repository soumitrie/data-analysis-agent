# Data Model — Ledger Lens

---

## Storage Technology

Two tiers:

1. **In-memory `DatasetStore`** (`src/analysis/store.py`) — the parsed pandas DataFrame for each uploaded file, keyed by `dataset_id`, held for the session. **Raw transaction rows live only here, in process memory — never written to disk, never sent to the LLM.** `Assumed:` LRU cap of a small number of datasets (default 4) with oldest-evicted; a per-dataset row cap of 1,000,000. Cleared on process restart.
2. **SQLite** (`sqlite:///./data/agent.db`) + SQLAlchemy 2.0 — persists `AnalysisRun` metadata only (mapping, chart plan, token usage, status). Schema created by `Base.metadata.create_all` in `init_db()` at startup (skeleton convention; **no Alembic**). SQLite is the production driver.

## Entities

### Entity: AnalysisRun

One row per analyze invocation. Stores metadata and the chart *plan/spec* — never raw rows or full figure data (figures are recomputed/returned live; `chart_specs` holds only the compact plan + titles for reopen in Phase 4).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid, PK) | yes | Primary key (`run_id`) |
| dataset_id | str | yes | The in-memory dataset this run analyzed |
| filename | str | yes | Uploaded file name (for history display) |
| row_count | int | yes | Rows in the analyzed dataset (full count) |
| status | str | yes | `pending` → `completed` \| `failed` |
| request_text | str \| null | no | NULL for auto-pack; NL text for Phase-2 requests |
| column_mapping | JSON (Text) | yes | `{date, amount, category, counterparty, assumption_note}` |
| chart_specs | JSON (Text) | no | Validated chart plan (type/title/roles/agg per chart) — no figure data |
| prompt_tokens | int \| null | no | Gemini prompt tokens |
| completion_tokens | int \| null | no | Gemini completion tokens |
| estimated_cost_usd | float \| null | no | From configurable per-1k rates |
| elapsed_ms | int \| null | no | Total run time |
| error_message | str \| null | no | Set when status = failed |
| created_at | timestamp | yes | Row creation |
| updated_at | timestamp | yes | Last update (on completion) |

`Assumed:` the skeleton's `RunRow` is replaced by `AnalysisRun` (the capability-slot swap); the old `runs` table/tests are removed. Cost rates via `AGENT_LLM_INPUT_COST_PER_1K` / `AGENT_LLM_OUTPUT_COST_PER_1K` (default 0 → cost shown as "n/a" until set).

### In-memory objects (not DB rows)

- **DatasetEntry** (`DatasetStore` value): `{dataset_id, filename, dataframe, created_at, messages: list, charts: list}`. `messages`/`charts` are populated from Phase 2 (session conversation + chart history).
- **LLMProfile** (`profile` node output, the ONLY LLM-bound payload): `{row_count, columns: [{name, dtype, cardinality, role}], date_range: {start,end}, amount_summary: {sum,mean,min,max,q1,median,q3}, top_categories: [{label, total, count}]}`. Contains aggregates + category *labels* only — no raw rows.

### Relationships

`AnalysisRun.dataset_id` references an in-memory `DatasetEntry` (soft reference; the entry may be evicted while the run row persists — reopen in Phase 4 then requires re-upload if evicted). Multiple `AnalysisRun` rows may share one `dataset_id` (auto-pack + subsequent NL requests).

## Sample CSV schema (`samples/transactions_sample.csv`)

A few thousand realistic rows (`Assumed:` ~5,000) so the Phase-1 gate proves full-data (not sampled) computation — the file must be large enough that a naive sample of the first N rows yields a different total than the full sum.

| Column | Type | Example | Detected role |
|--------|------|---------|---------------|
| txn_date | date (ISO) | 2024-03-14 | date |
| amount | float (signed) | -1250.75 | amount |
| category | string (low-cardinality, ~8 values) | "Wire Out" | category |
| counterparty | string (higher-cardinality, ~40 values) | "Meridian Capital LLC" | counterparty |
| currency | string | "USD" | (unused Phase 1) |
| txn_id | string | "TX0001042" | (id, unused) |

Rows span ~12 months (so the trend chart buckets by month), amounts range across several orders of magnitude (so the histogram is meaningful), and totals per counterparty/category are skewed (so top-N is informative). A small number of nulls/duplicates are included so the Phase-3 data-quality panel has something to flag.

## Data Lifecycle

- **Create:** DataFrame created on upload (in-memory); `AnalysisRun` created (`pending`) at analyze start.
- **Update:** `AnalysisRun` → `completed`/`failed` at finalize/handle_error.
- **Delete:** DataFrames evicted by LRU or on process restart (never persisted). `AnalysisRun` rows persist until the SQLite file is deleted; no auto-archival in scope.

## Sensitive Data

Raw transaction rows are the sensitive asset. Protections: (1) rows live only in process memory, never on disk, never in the DB; (2) only `LLMProfile` (aggregates + category labels) is sent to Gemini — enforced in the `plan_charts` node and asserted by the Phase-1 gate; (3) no auth/PII fields are stored in SQLite beyond the filename and aggregate metadata.
