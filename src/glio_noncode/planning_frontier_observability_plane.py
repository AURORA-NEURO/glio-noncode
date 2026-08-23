"""Named observability assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_observability_plane(fixture, evaluation):
    return build_named_planning_plane("observability", "operations", fixture, evaluation, lambda f, e: len(e.executions) == 16, "execution count is visible")
__all__ = ["build_planning_observability_plane"]
