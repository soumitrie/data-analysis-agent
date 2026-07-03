from collections.abc import Callable

from graph.state import AgentState


def guard(next_node: str) -> Callable[[AgentState], str]:
    """Return a conditional-edge function: route to `handle_error` when the state
    carries an error, otherwise to `next_node`."""
    def _route(state: AgentState) -> str:
        return "handle_error" if state.get("error") else next_node
    return _route


def route_request(state: AgentState) -> str:
    """Phase-2 branch after `detect_columns`: an error routes to `handle_error`; a
    request carrying `request_text` takes the NL path (`plan_from_nl`); otherwise the
    auto chart-pack path (`plan_charts`)."""
    if state.get("error"):
        return "handle_error"
    if state.get("request_text"):
        return "plan_from_nl"
    return "plan_charts"
