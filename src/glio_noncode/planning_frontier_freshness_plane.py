"""Named freshness assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_freshness_plane(fixture, evaluation):
    return build_named_planning_plane("freshness", "evidence", fixture, evaluation, lambda f, e: all(s.version for s in f.sources), "versions are nonempty")
__all__ = ["build_planning_freshness_plane"]
