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
_NL_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "plan_from_nl.md"
_MAX_CHARTS = 3
_MAX_HISTORY = 6

DECLINE_MESSAGE = (
    "Couldn't map that request to the loaded columns — try naming a metric and a "
    "grouping, e.g. 'monthly total by category'."
)


def _parse_llm_json(text: str) -> dict:
    """Parse the first JSON object from a JSON-mode LLM reply, tolerating the common
    benign artifacts of the Gemini thinking model: an optional ```json fence and
    trailing data after the object (e.g. a stray extra closing brace — observed
    intermittently on this model). Returns the first top-level object.

    Raises ValueError if no JSON object can be recovered — the caller then declines
    gracefully (HTTP 200), never a 5xx.
    """
    s = (text or "").strip()
    if not s:
        raise ValueError("empty response")
    if s.startswith("```"):
        s = s[3:]
        if s[:4].lower() == "json":
            s = s[4:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    try:
        obj, _ = json.JSONDecoder().raw_decode(s)
    except json.JSONDecodeError:
        start = s.find("{")
        if start == -1:
            raise ValueError("no JSON object in response")
        obj, _ = json.JSONDecoder().raw_decode(s[start:])
    if not isinstance(obj, dict):
        raise ValueError("top-level JSON is not an object")
    return obj


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def _load_nl_prompt() -> str:
    return _NL_PROMPT_PATH.read_text(encoding="utf-8").strip()


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
            parsed = _parse_llm_json(result.text)
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


def build_nl_messages(
    profile: dict, mapping: dict, request_text: str | None, history: list | None
) -> tuple[str, str]:
    """Build the (system, user) messages for the NL mapper from AGGREGATES ONLY.

    The user payload contains the LLMProfile, detected roles, the user's request,
    and a SHORT summary of prior requests (their text + resulting chart titles) —
    never a raw transaction row and never a raw cell value beyond category labels.
    """
    system = _load_nl_prompt()
    roles = {k: mapping.get(k) for k in ("date", "amount", "category", "counterparty")}
    hist = []
    for h in (history or [])[-_MAX_HISTORY:]:
        hist.append({
            "request": h.get("request_text"),
            "resulted_in": h.get("chart_title") or ("declined" if h.get("declined") else None),
        })
    payload = {
        "profile": profile,
        "column_roles": roles,
        "request": request_text,
        "history": hist,
    }
    user = json.dumps(payload, ensure_ascii=False, default=str)
    return system, user


def _validate_nl_spec(spec: dict, mapping: dict) -> dict | None:
    """Validate one NL chart spec against the whitelist + detected roles. Returns a
    cleaned spec, or None if it cannot be satisfied with the available columns."""
    if not isinstance(spec, dict):
        return None
    ctype = spec.get("type")
    if ctype not in figures.WHITELIST:
        return None

    clean: dict = {"type": ctype}
    for key in ("title", "subtitle", "rationale"):
        if spec.get(key):
            clean[key] = str(spec[key])

    sign = str(spec.get("sign") or "all").lower()
    clean["sign"] = sign if sign in ("inflow", "outflow", "all") else "all"

    def _valid_group(role):
        return role in ("category", "counterparty") and mapping.get(role)

    if ctype == "time_series":
        if not (mapping.get("date") and mapping.get("amount")):
            return None
        bucket = str(spec.get("bucket") or "").lower()
        if bucket in ("day", "week", "month"):
            clean["bucket"] = bucket
        gr = spec.get("group_role")
        if gr and _valid_group(gr):
            clean["group_role"] = gr
            try:
                clean["top_k"] = max(1, int(spec.get("top_k") or figures.DEFAULT_GROUP_K))
            except (TypeError, ValueError):
                clean["top_k"] = figures.DEFAULT_GROUP_K
        return clean

    if ctype == "top_n_breakdown":
        if not mapping.get("amount"):
            return None
        gr = spec.get("group_role")
        if _valid_group(gr):
            clean["group_role"] = gr
        elif mapping.get("counterparty"):
            clean["group_role"] = "counterparty"
        elif mapping.get("category"):
            clean["group_role"] = "category"
        else:
            return None
        metric = str(spec.get("metric") or "sum").lower()
        clean["metric"] = metric if metric in ("sum", "count", "mean") else "sum"
        try:
            clean["top_n"] = max(1, int(spec.get("top_n") or figures.DEFAULT_TOP_N))
        except (TypeError, ValueError):
            clean["top_n"] = figures.DEFAULT_TOP_N
        return clean

    if ctype == "distribution":
        if not mapping.get("amount"):
            return None
        return clean

    return None


def plan_from_nl(state: AgentState) -> AgentState:
    """Map ONE plain-English request to ONE validated chart spec via Gemini.

    Unlike the auto path, an unmappable request DECLINES (no default-plan fallback):
    it sets `declined=True` and a friendly `message`, and produces no chart. Only a
    genuine Gemini transport failure (both attempts) becomes a fatal error.
    """
    t0 = time.perf_counter()
    mapping = state["column_mapping"]
    request_text = state.get("request_text")
    system, user = build_nl_messages(
        state["profile"], mapping, request_text, state.get("history")
    )

    usage = {"prompt_tokens": None, "completion_tokens": None, "estimated_cost_usd": None}
    spec: dict | None = None
    transport_failures = 0
    got_response = False
    model = ""

    for attempt in (1, 2):
        # --- Transport: ONLY the network call may count as a transport failure. ---
        # A genuine exception from call_model_with_usage means Gemini is unreachable;
        # after both attempts that becomes a fatal 502.
        try:
            client = LLMClient()
            model = client.model
            result = client.call_model_with_usage(user, system=system, response_json=True)
        except Exception as exc:
            transport_failures += 1
            log.warning("llm.plan_from_nl.transport_error", attempt=attempt, error=str(exc))
            continue

        # A response WAS received — no retry beyond this point. Parsing/validation
        # failures below are a graceful decline (200), never a transport failure.
        got_response = True
        usage = {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "estimated_cost_usd": _estimated_cost(result.prompt_tokens, result.completion_tokens),
        }

        # --- Parse/validate the RECEIVED response. Loose JSON (prose / markdown fence
        # / trailing data), an explicit LLM decline, or an un-mappable/invalid spec all
        # DECLINE gracefully (200) — they are not transport failures. ---
        try:
            parsed = _parse_llm_json(result.text)
            if parsed.get("declined") is True or "chart" not in parsed:
                spec = None
            else:
                spec = _validate_nl_spec(parsed.get("chart"), mapping)
        except Exception as exc:
            # Gemini responded, but with non-strict JSON (common on an un-chartable
            # prompt). Decline gracefully — do NOT count this as a transport failure.
            log.info("llm.plan_from_nl.unparseable", attempt=attempt, error=str(exc))
            spec = None

        log.info(
            "llm.plan_from_nl",
            model=model,
            attempt=attempt,
            request_len=len(request_text or ""),
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            mapped=bool(spec),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
        break

    if spec is not None:
        return {**state, "chart_plan": [spec], "usage": usage, "declined": False, "message": None}

    # No chart. Only a genuine transport failure (no response ever received, both
    # attempts exhausted) is fatal (502). A received-but-unusable response declines.
    if not got_response and transport_failures >= 2:
        return {
            **state,
            "usage": usage,
            "error": "Chart planning is temporarily unavailable. Please try again.",
            "error_code": "planning_failed",
        }

    log.info("run.declined", request_len=len(request_text or ""))
    return {
        **state,
        "chart_plan": [],
        "usage": usage,
        "declined": True,
        "message": DECLINE_MESSAGE,
    }


def compute_figures(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    df = state["dataframe"]
    mapping = state["column_mapping"]
    prefix = state.get("chart_id_prefix", "c")
    start = int(state.get("chart_id_start", 1))
    charts = []
    for offset, spec in enumerate(state.get("chart_plan", [])):
        try:
            chart = figures.compute_chart(df, spec, mapping)
            chart["id"] = f"{prefix}{start + offset}"
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
