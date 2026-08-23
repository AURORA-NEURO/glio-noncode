"""Named policy assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_policy_plane(fixture, evaluation):
    return build_named_planning_plane("policy", "boundary", fixture, evaluation, lambda f, e: True, "planning-only boundary")
__all__ = ["build_planning_policy_plane"]
