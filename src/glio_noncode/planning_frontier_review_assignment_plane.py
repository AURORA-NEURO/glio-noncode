"""Named review assignment assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_review_assignment_plane(fixture, evaluation):
    return build_named_planning_plane("review-assignment", "consumer", fixture, evaluation, lambda f, e: bool(f.control_records), "control rows can be assigned")
__all__ = ["build_planning_review_assignment_plane"]
