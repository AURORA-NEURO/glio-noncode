"""Named operational assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_operational_plane(fixture, evaluation):
    return build_named_planning_plane("operational", "operations", fixture, evaluation, lambda f, e: bool(e.executions), "stage count is nonzero")
__all__ = ["build_planning_operational_plane"]
