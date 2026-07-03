from collections.abc import Callable

from graph.state import AgentState


def guard(next_node: str) -> Callable[[AgentState], str]:
    """Return a conditional-edge function: route to `handle_error` when the state
    carries an error, otherwise to `next_node`."""
    def _route(state: AgentState) -> str:
        return "handle_error" if state.get("error") else next_node
    return _route
