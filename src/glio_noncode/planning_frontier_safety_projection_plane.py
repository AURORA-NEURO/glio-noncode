"""Named safety projection assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_safety_projection_plane(fixture, evaluation):
    return build_named_planning_plane("safety-projection", "boundary", fixture, evaluation, lambda f, e: True, "safety is a projection check")
__all__ = ["build_planning_safety_projection_plane"]
