# Capability: Transaction Chart Pack

**Phase 1.** The full primary journey, first-time-right.

## What It Does
Given one uploaded transaction CSV, auto-detects each column's role, has Gemini select the most insightful charts from schema + aggregates only, computes every figure locally with pandas over the full dataset, and renders a 3-chart publication-grade Plotly pack (time-series trend, top-N breakdown, transaction-size distribution) under the IB house style — with the detected mapping + assumption note shown above the pack.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| CSV file | multipart file | user upload (`POST /api/datasets`) | yes |
| dataset_id | str | prior upload response | yes (for analyze) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| column_mapping + assumption_note | JSON | mapping panel in UI |
| profile (aggregated) | JSON | UI (and internal) |
| charts[] (Plotly figure JSON + computed_summary) | JSON | chart cards in UI |
| usage (tokens, est. cost) | JSON | logged + stored (UI display stubbed to Phase 2) |
| AnalysisRun row | DB record | SQLite |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini | `plan_charts` — select charts from `LLMProfile` (schema + aggregates only) | retry once, then deterministic default 3-chart plan (logged); if that fails, `handle_error` → 502 |
| pandas | parse, profile, compute every figure over full data | parse error → 400; per-chart compute error → drop chart (partial); fatal → `handle_error` |
| SQLite | persist `AnalysisRun` | log; does not block figure return |

## Business Rules
- Only `LLMProfile` (schema + aggregates + category labels) is ever sent to Gemini — **no raw rows**.
- Every displayed figure is computed by pandas over the **full** DataFrame — never sampled, never LLM-produced.
- No clarification gate: the agent states a best-guess mapping with an assumption note and proceeds.
- Chart specs from Gemini are validated against the whitelist (`time_series`, `top_n_breakdown`, `distribution` for Phase 1); invalid specs are dropped, never guessed.
- The pack targets 3 charts proving arsenal breadth; if the data supports fewer (e.g. no date column → no time series), render what is valid and note it.
- The IB house style (Plotly template) is applied to every figure server-side.
- Time bucket for the trend is chosen from the date span (day/week/month); top-N default N=10; histogram bins chosen from amount spread.

## Success Criteria
- [ ] Uploading `samples/transactions_sample.csv` returns `status: "completed"` with exactly 3 charts within 30s.
- [ ] The trend chart's `computed_summary.total` equals `df['amount'].sum()` over the full dataset (asserted in the gate — proves full-data, not sampled).
- [ ] The histogram's `computed_summary.total_count` equals `len(df)` (full row count).
- [ ] The column_mapping correctly assigns date=`txn_date`, amount=`amount`, category=`category`, counterparty=`counterparty` on the sample, and `assumption_note` is non-empty.
- [ ] The serialized Gemini prompt contains no raw transaction row (asserted: no `txn_id` value and no full-row fingerprint present in the prompt payload).
- [ ] Each returned `figure` is a valid Plotly figure (`data` + `layout`) carrying the house-style template (navy/accent palette, Inter font, house margins).
- [ ] `GET /health` is 200 and the app boots via `uv run python -m src`.
- [ ] Playwright smoke: three chart cards render with a Plotly SVG/canvas each and the mapping panel shows all four roles.
