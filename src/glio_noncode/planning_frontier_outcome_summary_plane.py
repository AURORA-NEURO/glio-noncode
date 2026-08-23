"""Named outcome summary assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_outcome_summary_plane(fixture, evaluation):
    return build_named_planning_plane("outcome-summary", "consumer", fixture, evaluation, lambda f, e: bool(e.executions), "outcomes summarize state")
__all__ = ["build_planning_outcome_summary_plane"]
