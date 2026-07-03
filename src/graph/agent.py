from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    load_dataset, profile, detect_columns,
    plan_charts, plan_from_nl, compute_figures, finalize, handle_error,
)
from graph.edges import guard, route_request


def _build_graph():
    g = StateGraph(AgentState)
    for name, fn in [
        ("load_dataset", load_dataset), ("profile", profile),
        ("detect_columns", detect_columns), ("plan_charts", plan_charts),
        ("plan_from_nl", plan_from_nl), ("compute_figures", compute_figures),
        ("finalize", finalize), ("handle_error", handle_error),
    ]:
        g.add_node(name, fn)

    g.set_entry_point("load_dataset")

    # Linear guarded edges up to detect_columns.
    for src, nxt in [("load_dataset", "profile"), ("profile", "detect_columns")]:
        g.add_conditional_edges(
            src, guard(nxt), {nxt: nxt, "handle_error": "handle_error"},
        )

    # Phase-2 branch: auto chart-pack vs NL request.
    g.add_conditional_edges(
        "detect_columns", route_request,
        {"plan_charts": "plan_charts", "plan_from_nl": "plan_from_nl", "handle_error": "handle_error"},
    )

    # Both planning paths converge on compute_figures.
    for src in ("plan_charts", "plan_from_nl"):
        g.add_conditional_edges(
            src, guard("compute_figures"),
            {"compute_figures": "compute_figures", "handle_error": "handle_error"},
        )
    g.add_conditional_edges(
        "compute_figures", guard("finalize"),
        {"finalize": "finalize", "handle_error": "handle_error"},
    )

    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
