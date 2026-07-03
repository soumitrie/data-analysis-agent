from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    dataset_id: str

    # Input / loaded data
    dataframe: object            # pandas.DataFrame (in-process ref; never serialized to LLM/DB)
    filename: str
    request_text: str | None     # None for auto-pack; set for Phase-2 NL requests
    history: list                # Phase-2 conversation summaries (no raw rows) for the NL prompt

    # Pipeline data (populated progressively)
    profile: dict                # LLMProfile — aggregated, the ONLY data sent to the LLM
    column_mapping: dict         # {date, amount, category, counterparty, assumption_note}
    chart_plan: list             # validated chart specs from Gemini
    usage: dict                  # {prompt_tokens, completion_tokens, estimated_cost_usd}
    chart_id_prefix: str         # "c" for auto-pack, "q" for asked charts
    chart_id_start: int          # first numeric suffix for chart ids
    declined: bool               # Phase-2 NL: request could not be mapped to a chart
    message: str | None          # Phase-2 NL: friendly decline message (else None)

    # Output
    charts: list                 # [{id, type, title, subtitle, figure, computed_summary, rationale, table}]
    status: str                  # "completed" | "failed"

    # Control
    error: str | None            # human-readable error on fatal failure
    error_code: str | None       # machine code: dataset_not_found | no_chartable_columns | planning_failed | internal
    started_ms: float            # perf_counter ms at pipeline start (for elapsed)
    degraded: bool               # True when the LLM plan fell back to the default
    elapsed_ms: int
