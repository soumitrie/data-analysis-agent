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

### `GET /health` — liveness (existing skeleton endpoint, unchanged)

**Response 200:** `{ "data": { "status": "ok" }, "error": null }`

---

## Deferred endpoints (Phase 2+ — not built in Phase 1)

| Endpoint | Phase | Purpose |
|----------|-------|---------|
| `POST /api/datasets/{id}/ask` | 2 | NL chart request over the loaded dataset |
| `GET /api/datasets/{id}/charts/{cid}/table` | 2 | Aggregated data table behind a chart |
| `GET /api/datasets/{id}/charts/{cid}/export?format=png\|svg` | 4 | Static publication image |
| `GET /api/datasets/{id}/export` | 4 | Full-pack bundle |
| `GET /api/runs` / `GET /api/runs/{id}` | 4 | History list + reopen a past analysis |

## Authentication

None — single-user localhost tool. No auth header; bind to localhost.
