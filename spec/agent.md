# Agent — Ledger Lens

Required: this project uses LangGraph. This file is the source of truth for the agent graph.

---

## Agent Architecture Pattern

| Pattern | Use when |
|---------|----------|
| **Single-agent loop** | One LLM drives a deterministic tool-call loop. |
| **Graph (LangGraph)** | Multi-step pipeline with conditional edges. |
| **Multi-agent** | Specialised sub-agents with an orchestrator. |
| **Supervisor** | One supervisor dispatches to workers. |
| **Human-in-the-loop** | Pauses for user review. |

**Chosen:** **Graph (LangGraph)** — a fixed, mostly-linear pipeline (`load_dataset → profile → detect_columns → plan_charts → compute_figures → finalize`) with a single conditional error edge. A single LLM call (`plan_charts`) selects charts; all computation is deterministic. No loop, no multi-agent, no HITL is needed for Phase 1. Phase 2 adds one conditional branch (`route_request`: auto-pack vs NL request); Phase 3/4 add sibling nodes (`write_summary`, `data_quality`, `anomaly_scan`, `suggest_followups`). **The base graph is sufficient — no patterns beyond the base pipeline are required, so no separate "Agentic Stack Upgrade" phase is planned.**

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `plan_charts` | Google Gemini | `gemini-3.1-pro-preview` (default; `AGENT_LLM_MODEL` override) | Chart selection needs strong reasoning over the profile; one call, well within the 30s budget. Quality over latency. |
| `write_summary` *(Phase 3)* | Google Gemini | `gemini-3.1-pro-preview` | Executive narrative quality matters. |
| `suggest_followups` *(Phase 4)* | Google Gemini | `gemini-2.5-flash` | Short suggestions — latency-sensitive, cheaper model. |

Provider is resolved by `src/llm/client.py` auto-detect (Gemini key set → Gemini). **No Anthropic.**

**Fallback behaviour:** production resilience only — `plan_charts` wraps the Gemini call in try/except with one retry/backoff. On persistent failure it sets `state["error"]`; `Assumed:` it then falls back to a deterministic default 3-chart plan (trend / top-N / distribution) so a pack still renders, logging the degradation. Tests call the real Gemini API with the key from `.env`.

**Prompt strategy:** system prompt (`src/prompts/plan_charts.md`) defines the role, the whitelist of chart types, and the strict output contract. User message = the JSON `LLMProfile` (schema + aggregates only). Output is **structured JSON** (a `chart_plan` array); the node parses and validates it against the whitelist, dropping any invalid spec.

---

## Tools & Tool Calling

This agent uses **no LLM-invoked tools** — the pipeline is fixed and the LLM emits a plan, not tool calls. The deterministic "tools" are internal Python functions the nodes call directly:

| Function | Description | Inputs | Output | Side-effects |
|----------|-------------|--------|--------|--------------|
| `analysis.profiling.build_profile` | Aggregated profile for the LLM | DataFrame | `LLMProfile` | none |
| `analysis.columns.detect_roles` | Assign column roles + assumption note | DataFrame, profile | `ColumnMapping` | none |
| `analysis.figures.compute_chart` | Compute one chart's exact figures + Plotly fig | DataFrame, chart spec, mapping | Plotly figure dict | none |
| `analysis.store.get_dataset` | Fetch session DataFrame | `dataset_id` | DataFrame | none |

**Tool selection strategy:** none (fixed pipeline). **Tool failure handling:** each node try/excepts; a compute failure on one chart drops that chart and continues (partial), a fatal failure sets `state["error"]`.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                          # set at initialisation (AnalysisRun.id)
    dataset_id: str                      # set at initialisation; key into DatasetStore

    # Input / loaded data
    dataframe: object                    # pandas.DataFrame, loaded by load_dataset (in-process ref, never serialized to LLM/DB)
    request_text: str | None             # None for auto-pack; set for Phase-2 NL requests

    # Pipeline data (populated progressively)
    profile: dict                        # LLMProfile — aggregated, the ONLY data sent to the LLM (build_profile)
    column_mapping: dict                 # {date, amount, category, counterparty} + assumption_note (detect_roles)
    chart_plan: list                     # validated chart specs from Gemini (plan_charts)
    usage: dict                          # {prompt_tokens, completion_tokens, estimated_cost_usd} (plan_charts)

    # Output
    charts: list                         # [{id, type, title, subtitle, figure, computed_summary, rationale}] (compute_figures)
    status: str                          # "completed" | "failed" (finalize / handle_error)

    # Control
    error: str | None                    # set by any node on fatal failure
    elapsed_ms: int                      # set by finalize
```

---

## Nodes / Steps

### `load_dataset`
**Reads:** `dataset_id`. **Writes:** `dataframe`, `error`.
**LLM call:** no.
**External calls:** DatasetStore (in-memory). On failure (dataset missing/expired) → set `error`.
**Behaviour:** fetch the session DataFrame by `dataset_id`. If absent, fatal error (client must re-upload).

### `profile`
**Reads:** `dataframe`. **Writes:** `profile`.
**LLM call:** no.
**Behaviour:** vectorized pandas aggregation → `LLMProfile`: per-column name/dtype/cardinality/sample-non-PII descriptors, row count, candidate date range, amount summary stats, top-K category labels with aggregated totals. This is the only data that will reach the LLM.

### `detect_columns`
**Reads:** `dataframe`, `profile`. **Writes:** `column_mapping`.
**LLM call:** no.
**Behaviour:** deterministic heuristics assign roles — date (parseable-as-datetime majority or name match), amount (numeric, signed/name match), category (low-cardinality string), counterparty (higher-cardinality string / name match). Builds a human-readable assumption note. Best-guess, never interrogates.

### `plan_charts`
**Reads:** `profile`, `column_mapping`, `request_text`. **Writes:** `chart_plan`, `usage`, `error`.
**LLM call:** **yes** — Gemini, system=`prompts/plan_charts.md`, user=`LLMProfile` JSON. Output: structured `chart_plan` JSON.
**External calls:** Gemini — on failure: retry once, then fall back to default plan (logged) or set `error`.
**Behaviour:** Gemini picks the most insightful charts (Phase 1: aim for the 3 arsenal-breadth charts) from the whitelist; node validates each spec (known type, referenced roles exist) and drops invalids. Captures token usage.

### `compute_figures`
**Reads:** `dataframe`, `chart_plan`, `column_mapping`. **Writes:** `charts`.
**LLM call:** no.
**Behaviour:** for each valid spec, pandas computes exact figures over the **full** DataFrame and builds a Plotly figure with the IB house-style template. A per-chart failure drops that chart (partial) and logs; the pack still returns.

### `finalize`
**Reads:** all. **Writes:** `status`, `elapsed_ms`.
**Behaviour:** persist `AnalysisRun` (mapping, plan, usage, status), set `status="completed"`, record elapsed.

### `handle_error`
**Reads:** `error`, `run_id`. **Writes:** `status="failed"`.
**Behaviour:** persist failed `AnalysisRun` with `error_message`, log with `run_id`, terminate.

---

## Graph / Flow Topology

```
START
  │
  ▼
load_dataset ──(error)──► handle_error ──► END
  │
  ▼
profile ──(error)──► handle_error
  │
  ▼
detect_columns ──(error)──► handle_error
  │
  ▼
plan_charts ──(error)──► handle_error
  │
  ▼
compute_figures ──(error)──► handle_error
  │
  ▼
finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `load_dataset` | `state.get("error")` | `handle_error` else `profile` |
| `profile` | `state.get("error")` | `handle_error` else `detect_columns` |
| `detect_columns` | `state.get("error")` | `handle_error` else `plan_charts` |
| `plan_charts` | `state.get("error")` | `handle_error` else `compute_figures` |
| `compute_figures` | `state.get("error")` | `handle_error` else `finalize` |

*Phase 2:* insert `route_request` after `load_dataset` → branches to `profile` (auto-pack) or `plan_from_nl` (NL request). *Phase 3:* `write_summary` + `data_quality` run after `compute_figures`. *Phase 4:* `anomaly_scan` + `suggest_followups` after compute.

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state | DataFrame ref, profile, mapping, plan, charts |
| **Across runs** | SQLite `AnalysisRun` + in-memory DatasetStore | run metadata (persisted); parsed DataFrame (in-memory, session only) |
| **Conversation** | *(Phase 2)* per-session message + chart history in the DatasetStore | prior NL requests + resulting charts, so follow-ups have context |

**Context window management:** only the compact `LLMProfile` (aggregates + top-K) goes to Gemini — bounded regardless of dataset size. Phase 2 appends a short summarized history of prior requests, not full data.

---

## Human-in-the-Loop Checkpoints

None. By design the agent never interrogates the user before charting — it makes a best guess and states an assumption note. (The between-phase human testing gate is a build-process gate, not a runtime checkpoint.)

---

## Error Handling & Recovery

**Node-level:** each node try/excepts; fatal errors set `state["error"]` and route to `handle_error`. A per-chart compute failure is partial — drop the chart, continue.

**Graph-level (`handle_error`):**
- Reads: `state.error`, `state.run_id`
- Updates DB: `AnalysisRun.status = "failed"`, `error_message`, `completed_at`
- Logs error with `run_id` context; terminates.

**Resume / retry strategy:** no checkpointer (runs are short, <30s). Failed runs are re-triggered by re-calling analyze; the DataFrame remains in the store, so no re-upload is needed unless the store evicted it.

**Partial failure:** a Gemini failure degrades to a deterministic default plan (logged); a single chart's compute failure drops just that chart. The pack renders whatever succeeded.

---

## Observability

Wired in Phase 1 — never deferred.

| Signal | What | Where |
|--------|------|-------|
| **Request/response** | dataset_id, run_id, row_count, chart count, status | structlog JSON → stdout (`src/observability`) |
| **LLM calls** | model, prompt_tokens, completion_tokens, latency_ms, estimated_cost_usd | structlog JSON + stored in `AnalysisRun.usage` |
| **Per-node** | node name, elapsed_ms, error if any | structlog JSON |
| **Run outcome** | status, total elapsed_ms, error | SQLite `AnalysisRun` + structlog |

`Assumed:` LangSmith tracing is optional and off by default (no Anthropic/LangSmith key required); structured stdout logging is the required Phase-1 observability. If `LANGCHAIN_API_KEY` is present, tracing may be enabled via env — not required for the gate.

---

## Concurrency Model

- **Run isolation:** single-user, single worker. Analyses run one at a time per process; the in-memory store is process-local, so `reload=False` and a single uvicorn worker are required.
- **Parallel nodes within a run:** none in Phase 1 (linear). *(Phase 3+ `write_summary`/`data_quality` may run as parallel siblings after compute if beneficial.)*
- **Checkpointing:** none (short runs, no HITL).

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (
    load_dataset, profile, detect_columns,
    plan_charts, compute_figures, finalize, handle_error,
)
from graph.edges import guard  # guard(next) -> lambda s: "handle_error" if s.get("error") else next

def _build_graph():
    g = StateGraph(AgentState)
    for name, fn in [
        ("load_dataset", load_dataset), ("profile", profile),
        ("detect_columns", detect_columns), ("plan_charts", plan_charts),
        ("compute_figures", compute_figures), ("finalize", finalize),
        ("handle_error", handle_error),
    ]:
        g.add_node(name, fn)

    g.set_entry_point("load_dataset")
    steps = ["load_dataset", "profile", "detect_columns", "plan_charts", "compute_figures"]
    nexts = ["profile", "detect_columns", "plan_charts", "compute_figures", "finalize"]
    for src, nxt in zip(steps, nexts):
        g.add_conditional_edges(src, guard(nxt),
                                {nxt: nxt, "handle_error": "handle_error"})

    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()

agentic_ai = _build_graph()
```
