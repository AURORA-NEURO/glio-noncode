"""Named recovery assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_recovery_plane(fixture, evaluation):
    return build_named_planning_plane("recovery", "resilience", fixture, evaluation, lambda f, e: any(x.observed_state.value != "ready_for_review" for x in e.executions), "held states are recoverable for review")
__all__ = ["build_planning_recovery_plane"]
