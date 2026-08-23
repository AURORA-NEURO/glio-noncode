"""Named review metrics assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_review_metrics_plane(fixture, evaluation):
    return build_named_planning_plane("review-metrics", "consumer", fixture, evaluation, lambda f, e: bool(e.checks), "review volume is measurable")
__all__ = ["build_planning_review_metrics_plane"]
