"""Runner: create the AnalysisRun, invoke the graph, assemble the response.

`run_agent` drives the auto chart-pack path; `run_ask` drives the Phase-2 NL path.
Both return a plain dict matching the contract in spec/api.md. On a fatal pipeline
error the dict carries `error_code` so the API can map it to an HTTP status.

Both paths register each computed chart (spec + its exact aggregated table) into
the session DatasetStore, keyed by the chart's session-unique id, so the
`/charts/{cid}/table` drawer works for auto-pack AND asked charts.
"""
from __future__ import annotations

import time

from analysis.store import get_store
from db.models import AnalysisRun
from db.session import create_db_session, init_db
from graph.agent import agentic_ai
from graph.nodes import DECLINE_MESSAGE
from graph.state import AgentState
from observability.events import get_logger

log = get_logger("agent.runner")

_EMPTY_USAGE = {"prompt_tokens": None, "completion_tokens": None, "estimated_cost_usd": None}


def _strip_table(chart: dict) -> dict:
    """Return the chart as the API contract exposes it (no internal `table`)."""
    return {k: v for k, v in chart.items() if k != "table"}


def _create_pending_run(dataset_id: str, filename: str, row_count: int, request_text: str | None) -> str:
    with create_db_session() as session:
        run = AnalysisRun(
            dataset_id=dataset_id,
            filename=filename,
            row_count=row_count,
            status="pending",
            request_text=request_text,
        )
        session.add(run)
        session.flush()
        return run.id


def run_agent(dataset_id: str, request_text: str | None = None) -> dict:
    init_db()

    entry = get_store().get(dataset_id)
    if entry is None:
        return {
            "dataset_id": dataset_id,
            "status": "failed",
            "error_code": "dataset_not_found",
            "error": f"Dataset {dataset_id} is not in memory (expired or evicted). Please re-upload.",
        }

    run_id = _create_pending_run(dataset_id, entry.filename, int(len(entry.dataframe)), request_text)

    initial: AgentState = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "request_text": request_text,
        "chart_id_prefix": "c",
        "chart_id_start": 1,
        "started_ms": time.perf_counter() * 1000,
        "error": None,
        "error_code": None,
    }
    final = agentic_ai.invoke(initial)

    status = final.get("status", "failed")
    if status != "completed" or final.get("error"):
        return {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "status": "failed",
            "error_code": final.get("error_code") or "internal",
            "error": final.get("error") or "Analysis failed.",
        }

    charts = final.get("charts", [])
    # Register the fresh auto-pack (spec + aggregated table) for the /table drawer.
    get_store().set_auto_charts(dataset_id, charts)

    return {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "status": "completed",
        "column_mapping": final.get("column_mapping"),
        "profile": final.get("profile"),
        "charts": [_strip_table(c) for c in charts],
        "usage": final.get("usage") or dict(_EMPTY_USAGE),
        "elapsed_ms": int(final.get("elapsed_ms", 0)),
    }


def run_ask(dataset_id: str, request_text: str) -> dict:
    """Drive the NL path: map ONE request to ONE chart (or a friendly decline),
    append it to the session pack, and return the ask payload."""
    init_db()

    store = get_store()
    entry = store.get(dataset_id)
    if entry is None:
        return {
            "dataset_id": dataset_id,
            "status": "failed",
            "error_code": "dataset_not_found",
            "error": f"Dataset {dataset_id} is not in memory (expired or evicted). Please re-upload.",
        }

    run_id = _create_pending_run(dataset_id, entry.filename, int(len(entry.dataframe)), request_text)
    next_index = store.count_asked_charts(dataset_id) + 1

    initial: AgentState = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "request_text": request_text,
        "history": store.get_messages(dataset_id),
        "chart_id_prefix": "q",
        "chart_id_start": next_index,
        "started_ms": time.perf_counter() * 1000,
        "error": None,
        "error_code": None,
    }
    final = agentic_ai.invoke(initial)

    status = final.get("status", "failed")
    if status != "completed" or final.get("error"):
        return {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "status": "failed",
            "error_code": final.get("error_code") or "internal",
            "error": final.get("error") or "Ask failed.",
        }

    charts = final.get("charts", [])
    usage = final.get("usage") or dict(_EMPTY_USAGE)
    elapsed_ms = int(final.get("elapsed_ms", 0))
    declined = bool(final.get("declined", False))
    message = final.get("message")
    chart_response = None

    if charts:
        chart_full = charts[0]
        store.append_chart(dataset_id, chart_full)
        store.append_message(dataset_id, {
            "request_text": request_text,
            "chart_id": chart_full["id"],
            "chart_title": chart_full.get("title"),
            "chart_type": chart_full.get("type"),
            "declined": False,
        })
        chart_response = _strip_table(chart_full)
        declined = False
        message = None
    else:
        # No chart produced. Either the LLM declined, or a valid spec computed empty.
        declined = True
        message = message or DECLINE_MESSAGE
        store.append_message(dataset_id, {
            "request_text": request_text,
            "chart_id": None,
            "chart_title": None,
            "chart_type": None,
            "declined": True,
        })

    log.info(
        "ask.completed",
        run_id=run_id,
        dataset_id=dataset_id,
        request_len=len(request_text or ""),
        declined=declined,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        elapsed_ms=elapsed_ms,
    )

    return {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "status": "completed",
        "declined": declined,
        "message": message,
        "chart": chart_response,
        "usage": usage,
        "elapsed_ms": elapsed_ms,
    }
