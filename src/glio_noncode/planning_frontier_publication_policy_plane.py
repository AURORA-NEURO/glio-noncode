"""Named publication policy assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_publication_policy_plane(fixture, evaluation):
    return build_named_planning_plane("publication-policy", "boundary", fixture, evaluation, lambda f, e: True, "public aggregate scope is retained")
__all__ = ["build_planning_publication_policy_plane"]
