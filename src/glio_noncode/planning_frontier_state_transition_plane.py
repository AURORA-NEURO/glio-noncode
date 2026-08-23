"""Named state transition assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_state_transition_plane(fixture, evaluation):
    return build_named_planning_plane("state-transition", "quality", fixture, evaluation, lambda f, e: len({x.observed_state for x in e.executions}) >= 3, "states have explicit transitions")
__all__ = ["build_planning_state_transition_plane"]
