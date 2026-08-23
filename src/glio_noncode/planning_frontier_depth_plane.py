"""Named depth assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_depth_plane(fixture, evaluation):
    return build_named_planning_plane("depth", "quality", fixture, evaluation, lambda f, e: len(f.operations) == 4, "four operations are closed")
__all__ = ["build_planning_depth_plane"]
