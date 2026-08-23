"""Named review view assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_views_plane(fixture, evaluation):
    return build_named_planning_plane("views", "consumer", fixture, evaluation, lambda f, e: bool(e.executions), "review rows remain visible")
__all__ = ["build_planning_views_plane"]
