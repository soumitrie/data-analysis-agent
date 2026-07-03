# Architecture — Ledger Lens

---

## System Overview

Ledger Lens is a single-user, localhost web application. A Next.js UI (static-exported, served by FastAPI at `:8001/app/`) lets the user upload one transaction CSV. FastAPI parses the file into a pandas DataFrame held **in memory** for the session, then runs a LangGraph agent that (1) profiles the data, (2) detects each column's role, (3) asks Google Gemini — given ONLY the schema and aggregated numbers — to select the most insightful charts, and (4) computes every figure locally with pandas and renders it as a Plotly figure under a fixed IB house style. Raw rows never leave the process; the LLM only ever sees schema + aggregates. Run metadata (mapping, chart plan, token usage) is stored in SQLite.

## Component Map

```
Browser (Next.js UI @ :8001/app/)
    │  multipart upload / JSON analyze
    ▼
FastAPI (src/api)  ──────────────►  In-memory DatasetStore (pandas DataFrame, session-scoped)
    │                                        ▲
    │ run_analysis(dataset_id)               │ read full data (local only)
    ▼                                        │
LangGraph agent (src/graph)                  │
  load_dataset → profile → detect_columns → plan_charts ──► Gemini API (schema + aggregates ONLY)
                                    │                          │ chart plan JSON
                                    ▼                          ▼
                            compute_figures (pandas + Plotly house style) ── finalize
    │                                        │
    ▼                                        ▼
SQLite (AnalysisRun: mapping, plan, tokens)  Plotly figure JSON → Browser renders
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| UI (Next.js/Plotly) | Upload, show mapping + assumption note, render Plotly chart pack in IB house style, labelled stubs |
| API (FastAPI) | Upload → parse → store; analyze → run agent → return figures; error envelope |
| Dataset store (in-memory) | Holds the parsed DataFrame for the session, keyed by `dataset_id`; never persisted to disk |
| Agent (LangGraph) | Orchestrates profile → detect → plan (Gemini) → compute → finalize |
| Analysis engine (pandas) | Column-role detection, aggregated profiling, and **all** deterministic figure computation |
| House style (Plotly template) | The single source of IB palette/typography/spacing applied to every figure |
| LLM (Gemini) | Selects/labels charts from schema + aggregates only; never sees or computes raw figures |
| Storage (SQLite) | `AnalysisRun` metadata: mapping, chart plan, token usage, status |

## Data Flow

1. **Trigger:** user uploads a CSV in the browser → `POST /api/datasets`.
2. FastAPI parses the CSV into a pandas DataFrame, stores it in the in-memory `DatasetStore` under a new `dataset_id`, returns row/column counts + column previews.
3. UI auto-calls `POST /api/datasets/{dataset_id}/analyze`.
4. `run_analysis(dataset_id)` invokes the LangGraph agent:
   - `load_dataset` — fetch the DataFrame from the store into state (by reference).
   - `profile` — compute an aggregated profile (row count, date span, amount summary stats, per-column cardinality, top categories by aggregated total). **This aggregated profile is the only data that will reach the LLM.**
   - `detect_columns` — deterministically assign roles (date/amount/category/counterparty) + build the assumption note.
   - `plan_charts` — call Gemini with schema + aggregated profile ONLY; Gemini returns a validated chart-plan JSON (list of chart specs from a fixed whitelist).
   - `compute_figures` — for each planned chart, pandas computes the exact figures over the **full** DataFrame and builds a Plotly figure with the IB house-style template.
   - `finalize` — persist `AnalysisRun`, assemble the response.
5. **Output:** JSON with column mapping, assumption note, aggregated profile, and an array of Plotly figure specs → the browser renders the chart pack.

## Privacy / Accuracy / Scale Architecture

- **Privacy — what crosses to Gemini:** exactly the `LLMProfile` object — column names + dtypes + detected roles, row count, date range, amount summary statistics (sum/mean/min/max/quartiles), per-column cardinalities, and the top-K category labels **with their aggregated totals**. No individual transaction row, no raw cell value beyond category *labels* and column *names*, is ever serialized into the prompt. The `plan_charts` node builds the prompt solely from `LLMProfile`; the compute node never calls the LLM. The Phase-1 gate asserts the serialized prompt contains no raw-row fingerprint.
- **Accuracy — who computes figures:** the LLM outputs only a *plan* (which chart type, which column role, which aggregation, top-N, time bucket). Every displayed number is computed by `src/analysis/figures.py` with pandas over the full DataFrame. Chart specs from the LLM are validated against a whitelist; an unknown/invalid spec is dropped, never guessed.
- **Scale:** the profile uses vectorized pandas aggregations (`groupby`, `describe`, `value_counts`) — O(n) passes, never per-row Python loops. Profiling for the LLM aggregates/caps to top-K; figure computation aggregates the full data but only ever *emits* bucket-level series (never per-row), keeping payloads small even at ~1M rows within the ~30s budget. `Assumed:` a per-analysis row cap of 1,000,000 rows and an in-memory store cap of a few datasets (LRU eviction) — documented in `data.md`.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Google Gemini API | Chart selection/labeling from schema + aggregates | `plan_charts` sets `state.error`; graph routes to `handle_error`; API returns error envelope. `Assumed:` on Gemini failure, fall back to a deterministic default 3-chart plan so the pack still renders (degraded, logged) |
| pandas | Parse CSV, profile, compute every figure | Parse error → 400 at upload; compute error → node sets `error` |
| SQLite (file `./data/agent.db`) | Persist `AnalysisRun` metadata | `init_db()` create-all at startup; write failure logged, does not block figure return |

## Stack

> Concrete choices for this project. Generic every-project rules (model-naming, DB driver placement, dev port, real-key test rule) live in `harness/patterns/tech-stack.md`.

- **Language:** Python 3.12+ (backend), TypeScript (frontend).
- **Agent framework:** LangGraph (already wired in the skeleton).
- **LLM provider + model:** **Google Gemini**, via `AGENT_GEMINI_API_KEY`. Provider auto-detected by `src/config/settings.py` (`llm_provider` blank → Gemini when the Gemini key is set). Default model `gemini-3.1-pro`, configurable via `AGENT_LLM_MODEL`. The skeleton ships `src/llm/providers/gemini.py`. **No Anthropic** in this project.
- **Backend:** FastAPI, served by uvicorn on port 8001; single-origin static-serves the frontend at `/app`.
- **Database + ORM:** SQLite (`sqlite:///./data/agent.db`) + SQLAlchemy 2.0. Schema created via `Base.metadata.create_all` in `init_db()` — **no Alembic** (skeleton convention; SQLite single-user tool). SQLite is the production driver, so tests run on SQLite (production-equivalent per the test-environment rule).
- **Frontend:** Next.js 15 + React 19, static export (`output: 'export'`, `basePath: '/app'`), Tailwind v4, Plotly for interactive charts.
- **Dependency management:** uv + `pyproject.toml` (Python); pnpm (frontend).

| Key library | Version | Purpose |
|-------------|---------|---------|
| langgraph | (skeleton pin) | Agent graph orchestration |
| google-genai | (skeleton pin) | Gemini client (`src/llm/providers/gemini.py`) |
| pandas | ^2.2 | CSV parse, profiling, all figure computation |
| plotly | ^5.x | Server-side figure construction + house-style template (Python) |
| structlog | (skeleton pin) | Structured token/latency/request logging |
| fastapi / uvicorn | (skeleton pin) | API + server |
| SQLAlchemy | 2.0 | `AnalysisRun` persistence |
| python-multipart | ^0.0.9 | Multipart CSV upload parsing in FastAPI |
| plotly.js-dist-min + react-plotly.js | latest | Client-side interactive chart rendering |
| @playwright/test | latest | Frontend E2E smoke (`tests/e2e/`) |
| kaleido | ^0.2 | *(Phase 4)* static PNG/SVG export |

**Avoid:** sending any raw row to the LLM; using the LLM to compute or estimate a displayed figure; per-row Python loops in profiling/computation (use vectorized pandas); SQLite-as-substitute reasoning that a passing test proves PostgreSQL (N/A — SQLite *is* production here); Anthropic provider.

## Deployment Model

Local long-running service: `cd frontend && pnpm build` (produces `frontend/out/`), then `uv run python -m src` starts uvicorn on port 8001, which serves both the API and the static UI at `/app`. Single process, single worker (`reload=False`) — required because the DatasetStore is in-process memory. Health check at `/health`.
