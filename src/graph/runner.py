"""Runner: create the AnalysisRun, invoke the graph, assemble the response.

Returns a plain dict matching the analyze contract (spec/api.md). On a fatal
pipeline error the dict carries `error_code` so the API can map it to an HTTP
status; otherwise it carries the full chart pack.
"""
from __future__ import annotations

import time

from analysis.store import get_store
from db.models import AnalysisRun
from db.session import create_db_session, init_db
from graph.agent import agentic_ai
from graph.state import AgentState


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

    # Create the pending run row; nodes update it at finalize / handle_error.
    with create_db_session() as session:
        run = AnalysisRun(
            dataset_id=dataset_id,
            filename=entry.filename,
            row_count=int(len(entry.dataframe)),
            status="pending",
            request_text=request_text,
        )
        session.add(run)
        session.flush()
        run_id = run.id

    initial: AgentState = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "request_text": request_text,
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

    return {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "status": "completed",
        "column_mapping": final.get("column_mapping"),
        "profile": final.get("profile"),
        "charts": final.get("charts", []),
        "usage": final.get("usage")
        or {"prompt_tokens": None, "completion_tokens": None, "estimated_cost_usd": None},
        "elapsed_ms": int(final.get("elapsed_ms", 0)),
    }
