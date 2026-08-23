"""Named review protocol assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_review_protocol_plane(fixture, evaluation):
    return build_named_planning_plane("review-protocol", "operations", fixture, evaluation, lambda f, e: any(x.issue_codes for x in e.executions), "protocol preserves issue codes")
__all__ = ["build_planning_review_protocol_plane"]
