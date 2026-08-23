"""Named review SLA assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_review_sla_plane(fixture, evaluation):
    return build_named_planning_plane("review-sla", "operations", fixture, evaluation, lambda f, e: True, "review states have no silent release")
__all__ = ["build_planning_review_sla_plane"]
