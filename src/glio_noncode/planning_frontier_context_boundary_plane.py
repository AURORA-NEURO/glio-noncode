"""Named context boundary assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_context_boundary_plane(fixture, evaluation):
    return build_named_planning_plane("context-boundary", "boundary", fixture, evaluation, lambda f, e: any(x.observed_state.value == "blocked" for x in e.executions), "foreign contexts are held")
__all__ = ["build_planning_context_boundary_plane"]
