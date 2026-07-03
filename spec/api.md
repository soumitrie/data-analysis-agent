# API — Ledger Lens

Both slices build to this contract. The frontend depends only on these shapes (no runtime dependency on backend internals). All responses use the skeleton envelope: `{ "data": <payload> | null, "error": <null | {code, message}> }` (see `src/api/_common.py`).

---

## API Style

REST over HTTP, FastAPI, port 8001. Routes registered in `src/api/__init__.py`; endpoints in `src/api/datasets.py`. The old `/runs` endpoints are replaced.

---

## Endpoints

### `POST /api/datasets` — upload a CSV

**Purpose:** parse the uploaded CSV into an in-memory DataFrame, store it, return counts + column previews. No LLM call. Fast.

**Request:** `multipart/form-data`, field `file` = the CSV.

**Response 200:**
```json
{
  "data": {
    "dataset_id": "9f1c...uuid",
    "filename": "transactions_sample.csv",
    "row_count": 5000,
    "column_count": 6,
    "columns": [
      { "name": "txn_date", "dtype": "string", "sample_values": ["2024-03-14", "2024-03-15"] },
      { "name": "amount", "dtype": "float64", "sample_values": ["-1250.75", "4300.00"] }
    ]
  },
  "error": null
}
```
> `sample_values` are for the UI column preview only. `Assumed:` up to 3 sample values per column — this is a client-side preview, distinct from the LLM path (the LLM never receives this response; it only gets the aggregated `LLMProfile`).

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Not a CSV / unparseable / empty file / exceeds row cap (1,000,000) |
| 413 | File too large (server upload limit) |
| 500 | Internal error |

---

### `POST /api/datasets/{dataset_id}/analyze` — auto chart pack

**Purpose:** run the LangGraph agent (profile → detect → plan (Gemini) → compute) and return the column mapping, assumption note, aggregated profile, and the Plotly chart pack.

**Request body:** `{}` (Phase 1: auto-pack, no parameters).

**Response 200:**
```json
{
  "data": {
    "run_id": "3a2b...uuid",
    "dataset_id": "9f1c...uuid",
    "status": "completed",
    "column_mapping": {
      "date": "txn_date",
      "amount": "amount",
      "category": "category",
      "counterparty": "counterparty",
      "assumption_note": "Interpreted 'txn_date' as the transaction date, 'amount' as the signed transaction amount, 'category' as the transaction type, and 'counterparty' as the payee. Charts assume these roles."
    },
    "profile": {
      "row_count": 5000,
      "date_range": { "start": "2024-01-01", "end": "2024-12-31" },
      "amount_summary": { "sum": 1284300.5, "mean": 256.86, "min": -9800.0, "max": 12400.0 }
    },
    "charts": [
      {
        "id": "c1",
        "type": "time_series",
        "title": "Total Transaction Value Over Time",
        "subtitle": "Monthly · USD",
        "figure": { "data": [ /* Plotly traces */ ], "layout": { /* IB house-style layout */ } },
        "computed_summary": { "total": 1284300.5, "n_buckets": 12 },
        "rationale": "The dataset spans 12 months; a monthly trend shows value flow over time."
      },
      {
        "id": "c2",
        "type": "top_n_breakdown",
        "title": "Top Counterparties by Total Value",
        "subtitle": "Top 10 · USD",
        "figure": { "data": [ ], "layout": { } },
        "computed_summary": { "top_n": 10, "covered_share": 0.72 },
        "rationale": "Value is concentrated among a few counterparties."
      },
      {
        "id": "c3",
        "type": "distribution",
        "title": "Distribution of Transaction Sizes",
        "subtitle": "Histogram · USD",
        "figure": { "data": [ ], "layout": { } },
        "computed_summary": { "n_bins": 40, "total_count": 5000 },
        "rationale": "Reveals the spread and tail of individual transaction amounts."
      }
    ],
    "usage": { "prompt_tokens": 900, "completion_tokens": 220, "estimated_cost_usd": null },
    "elapsed_ms": 4200
  },
  "error": null
}
```

> `figure` is a complete Plotly figure JSON (`data` + `layout`) with the IB house-style template already applied server-side. The frontend renders it directly with `react-plotly.js`. `usage.estimated_cost_usd` is `null` until cost rates are configured (its UI display is a Phase-1 **stub**; the values are logged from Phase 1).

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | `dataset_id` not in the in-memory store (expired/evicted → re-upload) |
| 422 | No chartable columns detected (e.g. no numeric column) |
| 502 | Gemini unavailable and default-plan fallback also failed |
| 500 | Internal error (`status: "failed"`, `error` populated) |

---

### `POST /api/datasets/{dataset_id}/ask` — NL chart request (Phase 2)

**Purpose:** map a plain-English request over the already-loaded dataset onto EXACTLY
ONE parameterized chart spec (Gemini), validated against the whitelist + detected
roles, then computed locally by pandas over the FULL DataFrame. The new chart is
appended to the session pack. Prior requests in the session give follow-ups context.

**Privacy:** Gemini receives ONLY the aggregated `LLMProfile`, the detected roles, and
a SHORT summary of prior requests (their text + resulting chart titles) — never a raw
transaction row.

**Request body:** `{ "request_text": "monthly total by category" }`

**Response 200:**
```json
{
  "data": {
    "run_id": "…uuid",
    "dataset_id": "…uuid",
    "status": "completed",
    "declined": false,
    "message": null,
    "chart": {
      "id": "q1",
      "type": "time_series",
      "title": "Monthly Total by Category",
      "subtitle": "Monthly · by category",
      "figure": { "data": [ ], "layout": { } },
      "computed_summary": { "total": -10911467.34, "n_buckets": 12, "freq": "ME", "group_by": "category", "series": ["Wire Out", "…"], "sign": "all", "metric": "sum" },
      "rationale": "Monthly value split across the top categories."
    },
    "usage": { "prompt_tokens": 1629, "completion_tokens": 113, "estimated_cost_usd": null },
    "elapsed_ms": 5200
  },
  "error": null
}
```

- **Mappable request** → `declined: false`, `message: null`, `chart` = a new `ChartObj`
  with a session-unique id (asked ids are `q1`, `q2`, …).
- **Un-mappable request** (Gemini can't map it to the available columns/whitelist, e.g.
  "tell me a joke") → **still HTTP 200** with `declined: true`, `chart: null`,
  `message: "Couldn't map that request to the loaded columns — try naming a metric and
  a grouping, e.g. 'monthly total by category'."`. Never a fabricated chart.
- `ChartObj` is identical to the analyze charts:
  `{ id, type, title, subtitle, figure:{data,layout}, computed_summary, rationale }`
  (the internal aggregated table is served by `/charts/{cid}/table`, not inlined).
- **NL chart parameters** (chosen by Gemini, validated locally): `time_series` supports
  `bucket` (`day`/`week`/`month`), an optional `group_role` (`category`/`counterparty`,
  top-K series via `top_k`) and a `sign` filter (`inflow`/`outflow`/`all`);
  `top_n_breakdown` supports `group_role`, `top_n`, `metric` (`sum`/`count`/`mean`) and
  `sign`; `distribution` supports `sign`. Every param is validated against the detected
  roles — an invalid/absent role is dropped or declined, never guessed.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | `request_text` empty/blank |
| 404 | `DATASET_NOT_FOUND` — dataset expired/evicted (re-upload) |
| 502 | `PLANNING_FAILED` — Gemini unreachable after one retry AND no chart produced (a genuine "can't map" is the 200 decline above, not a 502) |
| 500 | Internal error |

---

### `GET /api/datasets/{dataset_id}/charts/{chart_id}/table` — aggregated data table (Phase 2)

**Purpose:** the exact aggregated data behind a chart (auto-pack OR asked). The rows are
**bucket-level aggregates ONLY, never raw transactions**, and the numbers EXACTLY equal
the chart's plotted series (figure and table are built from the same aggregated arrays
and stored together in the session).

**Response 200:**
```json
{
  "data": {
    "chart_id": "c2",
    "columns": ["Counterparty", "Total amount"],
    "rows": [["Apex Global Markets", -3137823.19], ["Sterling & Rowe", -1505874.47]]
  },
  "error": null
}
```
> Table shapes by chart type: `time_series` (ungrouped) → `["Period", "Total amount"]`;
> `time_series` (grouped) → `["Period", <series…>]` (one value column per series);
> `top_n_breakdown` → `[<group>, <metric label>]` (ranked, largest first);
> `distribution` → `["Bin center (amount)", "Transactions"]`.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | `CHART_NOT_FOUND` — the dataset or chart id is not in the session store |

---

### `GET /health` — liveness (existing skeleton endpoint, unchanged)

**Response 200:** `{ "data": { "status": "ok" }, "error": null }`

---

## Deferred endpoints (Phase 3+ — not built yet)

| Endpoint | Phase | Purpose |
|----------|-------|---------|
| `GET /api/datasets/{id}/charts/{cid}/export?format=png\|svg` | 4 | Static publication image |
| `GET /api/datasets/{id}/export` | 4 | Full-pack bundle |
| `GET /api/runs` / `GET /api/runs/{id}` | 4 | History list + reopen a past analysis |

## Authentication

None — single-user localhost tool. No auth header; bind to localhost.
