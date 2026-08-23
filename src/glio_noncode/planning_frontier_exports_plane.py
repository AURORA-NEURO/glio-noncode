"""Named export assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_exports_plane(fixture, evaluation):
    return build_named_planning_plane("exports", "consumer", fixture, evaluation, lambda f, e: bool(e.executions), "structured rows are exportable")
__all__ = ["build_planning_exports_plane"]
