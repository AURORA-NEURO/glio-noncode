"""Named release assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_release_plane(fixture, evaluation):
    return build_named_planning_plane("release", "release", fixture, evaluation, lambda f, e: True, "release boundary is bounded")
__all__ = ["build_planning_release_plane"]
