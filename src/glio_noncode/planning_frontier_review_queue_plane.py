"""Named review queue assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_review_queue_plane(fixture, evaluation):
    return build_named_planning_plane("review-queue", "consumer", fixture, evaluation, lambda f, e: any(x.observed_state.value != "ready_for_review" for x in e.executions), "held rows are retained")
__all__ = ["build_planning_review_queue_plane"]
