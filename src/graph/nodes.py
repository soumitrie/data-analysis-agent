"""LangGraph nodes for the Ledger Lens charting pipeline.

Pipeline: load_dataset → profile → detect_columns → plan_charts (Gemini)
          → compute_figures → finalize   (+ handle_error)

Privacy invariant: only the aggregated LLMProfile ever reaches Gemini. The
`plan_charts` node builds its prompt SOLELY from the profile + detected roles —
never from a raw transaction row.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from analysis import columns as col_detect
from analysis import figures, profiling
from analysis.store import get_store
from config.settings import get_settings
from db.models import AnalysisRun
from db.session import create_db_session
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger

log = get_logger("agent.graph")

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "plan_charts.md"
_MAX_CHARTS = 3


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def _elapsed_ms(state: AgentState) -> int:
    started = state.get("started_ms")
    if started is None:
        return 0
    return int((time.perf_counter() * 1000) - started)


# --------------------------------------------------------------------------- #
#  Nodes
# --------------------------------------------------------------------------- #

def load_dataset(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    dataset_id = state.get("dataset_id", "")
    entry = get_store().get(dataset_id)
    if entry is None:
        log.warning("node.load_dataset.missing", dataset_id=dataset_id)
        return {
            **state,
            "error": f"Dataset {dataset_id} is not in memory (expired or evicted). Please re-upload.",
            "error_code": "dataset_not_found",
        }
    log.info(
        "node.load_dataset",
        dataset_id=dataset_id,
        row_count=int(len(entry.dataframe)),
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
    )
    return {**state, "dataframe": entry.dataframe, "filename": entry.filename}


def profile(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    try:
        prof = profiling.build_profile(state["dataframe"])
    except Exception as exc:  # pragma: no cover - defensive
        log.error("node.profile.error", error=str(exc))
        return {**state, "error": f"Profiling failed: {exc}", "error_code": "internal"}
    log.info(
        "node.profile",
        row_count=prof["row_count"],
        columns=len(prof["columns"]),
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
    )
    return {**state, "profile": prof}


def detect_columns(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    try:
        mapping = col_detect.detect_roles(state["dataframe"], state.get("profile"))
    except Exception as exc:  # pragma: no cover - defensive
        log.error("node.detect_columns.error", error=str(exc))
        return {**state, "error": f"Column detection failed: {exc}", "error_code": "internal"}

    if not mapping.get("amount"):
        log.warning("node.detect_columns.no_chartable", mapping=mapping)
        return {
            **state,
            "column_mapping": mapping,
            "error": "No numeric amount column detected; there is nothing to chart.",
            "error_code": "no_chartable_columns",
        }

    profiling.apply_roles(state.get("profile", {}), mapping)
    log.info(
        "node.detect_columns",
        mapping={k: v for k, v in mapping.items() if k != "assumption_note"},
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
    )
    return {**state, "column_mapping": mapping}


def build_plan_messages(profile: dict, mapping: dict, request_text: str | None) -> tuple[str, str]:
    """Build the (system, user) messages for Gemini from AGGREGATES ONLY.

    The user payload contains the LLMProfile and the detected column roles — no
    raw transaction row and no raw cell value beyond category labels/column names.
    """
    system = _load_prompt()
    roles = {k: mapping.get(k) for k in ("date", "amount", "category", "counterparty")}
    payload = {
        "profile": profile,
        "column_roles": roles,
        "request": request_text,
    }
    user = json.dumps(payload, ensure_ascii=False, default=str)
    return system, user


def _validate_plan(raw_plan: list, mapping: dict) -> list:
    valid = []
    for spec in raw_plan:
        if not isinstance(spec, dict):
            continue
        ctype = spec.get("type")
        if ctype not in figures.WHITELIST:
            continue
        if ctype == "time_series" and not (mapping.get("date") and mapping.get("amount")):
            continue
        if ctype == "top_n_breakdown" and not (
            mapping.get("amount") and (mapping.get("counterparty") or mapping.get("category"))
        ):
            continue
        if ctype == "distribution" and not mapping.get("amount"):
            continue
        valid.append(spec)
        if len(valid) >= _MAX_CHARTS:
            break
    return valid


def _default_plan(mapping: dict) -> list:
    plan = []
    if mapping.get("date") and mapping.get("amount"):
        plan.append({"type": "time_series"})
    if mapping.get("amount") and (mapping.get("counterparty") or mapping.get("category")):
        plan.append({"type": "top_n_breakdown"})
    if mapping.get("amount"):
        plan.append({"type": "distribution"})
    return plan[:_MAX_CHARTS]


def _estimated_cost(prompt_tokens, completion_tokens) -> float | None:
    s = get_settings()
    in_rate = s.llm_input_cost_per_1k
    out_rate = s.llm_output_cost_per_1k
    if not in_rate and not out_rate:
        return None
    pt = prompt_tokens or 0
    ct = completion_tokens or 0
    return round((pt / 1000.0) * in_rate + (ct / 1000.0) * out_rate, 6)


def plan_charts(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    mapping = state["column_mapping"]
    system, user = build_plan_messages(state["profile"], mapping, state.get("request_text"))

    usage = {"prompt_tokens": None, "completion_tokens": None, "estimated_cost_usd": None}
    plan: list = []
    degraded = False
    model = ""

    for attempt in (1, 2):
        try:
            client = LLMClient()
            model = client.model
            result = client.call_model_with_usage(user, system=system, response_json=True)
            parsed = json.loads(result.text)
            raw_plan = parsed.get("chart_plan", []) if isinstance(parsed, dict) else []
            plan = _validate_plan(raw_plan, mapping)
            usage = {
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "estimated_cost_usd": _estimated_cost(result.prompt_tokens, result.completion_tokens),
            }
            log.info(
                "llm.plan_charts",
                model=model,
                attempt=attempt,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                planned=len(plan),
                latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            )
            if plan:
                break
        except Exception as exc:
            log.warning("llm.plan_charts.error", attempt=attempt, error=str(exc))
            continue

    if not plan:
        plan = _default_plan(mapping)
        degraded = True
        log.warning("llm.plan_charts.degraded", model=model, fallback_charts=len(plan))

    if not plan:
        return {
            **state,
            "error": "Chart planning failed and no default plan could be built.",
            "error_code": "planning_failed",
        }

    return {**state, "chart_plan": plan, "usage": usage, "degraded": degraded}


def compute_figures(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    df = state["dataframe"]
    mapping = state["column_mapping"]
    charts = []
    for idx, spec in enumerate(state.get("chart_plan", []), start=1):
        try:
            chart = figures.compute_chart(df, spec, mapping)
            chart["id"] = f"c{idx}"
            charts.append(chart)
        except Exception as exc:
            log.warning("node.compute_figures.dropped", chart_type=spec.get("type"), error=str(exc))
            continue
    log.info(
        "node.compute_figures",
        requested=len(state.get("chart_plan", [])),
        computed=len(charts),
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
    )
    return {**state, "charts": charts}


def _persist_run(state: AgentState, status: str) -> None:
    run_id = state.get("run_id")
    if not run_id:
        return
    usage = state.get("usage") or {}
    try:
        with create_db_session() as session:
            run = session.get(AnalysisRun, run_id)
            if run is None:
                return
            run.status = status
            run.row_count = int(len(state["dataframe"])) if state.get("dataframe") is not None else run.row_count
            if state.get("filename"):
                run.filename = state["filename"]
            if state.get("column_mapping") is not None:
                run.column_mapping = json.dumps(state["column_mapping"], default=str)
            if state.get("chart_plan") is not None:
                run.chart_specs = json.dumps(state["chart_plan"], default=str)
            run.prompt_tokens = usage.get("prompt_tokens")
            run.completion_tokens = usage.get("completion_tokens")
            run.estimated_cost_usd = usage.get("estimated_cost_usd")
            run.elapsed_ms = state.get("elapsed_ms")
            run.error_message = state.get("error")
    except Exception as exc:  # persistence must never block the figure return
        log.error("db.persist.error", run_id=run_id, error=str(exc))


def finalize(state: AgentState) -> AgentState:
    elapsed = _elapsed_ms(state)
    out = {**state, "status": "completed", "elapsed_ms": elapsed}
    _persist_run(out, "completed")
    log.info(
        "run.completed",
        run_id=state.get("run_id"),
        dataset_id=state.get("dataset_id"),
        charts=len(state.get("charts", [])),
        degraded=state.get("degraded", False),
        elapsed_ms=elapsed,
    )
    return out


def handle_error(state: AgentState) -> AgentState:
    elapsed = _elapsed_ms(state)
    out = {**state, "status": "failed", "elapsed_ms": elapsed}
    _persist_run(out, "failed")
    log.error(
        "run.failed",
        run_id=state.get("run_id"),
        dataset_id=state.get("dataset_id"),
        error_code=state.get("error_code"),
        error=state.get("error"),
        elapsed_ms=elapsed,
    )
    return out
