from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    load_dataset, profile, detect_columns,
    plan_charts, compute_figures, finalize, handle_error,
)
from graph.edges import guard


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
        g.add_conditional_edges(
            src, guard(nxt),
            {nxt: nxt, "handle_error": "handle_error"},
        )

    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
