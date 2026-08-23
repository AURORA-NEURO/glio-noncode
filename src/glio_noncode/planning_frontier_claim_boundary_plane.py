"""Named claim boundary assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_claim_boundary_plane(fixture, evaluation):
    return build_named_planning_plane("claim-boundary", "boundary", fixture, evaluation, lambda f, e: True, "no efficacy claim is emitted")
__all__ = ["build_planning_claim_boundary_plane"]
