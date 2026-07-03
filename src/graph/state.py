from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    dataset_id: str

    # Input / loaded data
    dataframe: object            # pandas.DataFrame (in-process ref; never serialized to LLM/DB)
    filename: str
    request_text: str | None     # None for auto-pack; set for Phase-2 NL requests

    # Pipeline data (populated progressively)
    profile: dict                # LLMProfile — aggregated, the ONLY data sent to the LLM
    column_mapping: dict         # {date, amount, category, counterparty, assumption_note}
    chart_plan: list             # validated chart specs from Gemini
    usage: dict                  # {prompt_tokens, completion_tokens, estimated_cost_usd}

    # Output
    charts: list                 # [{id, type, title, subtitle, figure, computed_summary, rationale}]
    status: str                  # "completed" | "failed"

    # Control
    error: str | None            # human-readable error on fatal failure
    error_code: str | None       # machine code: dataset_not_found | no_chartable_columns | planning_failed | internal
    started_ms: float            # perf_counter ms at pipeline start (for elapsed)
    degraded: bool               # True when the LLM plan fell back to the default
    elapsed_ms: int
