"""Named performance assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_performance_plane(fixture, evaluation):
    return build_named_planning_plane("performance", "engineering", fixture, evaluation, lambda f, e: len(f.records) <= 1000, "bounded fixture remains small")
__all__ = ["build_planning_performance_plane"]
