"""Named validation matrix assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_validation_matrix_plane(fixture, evaluation):
    return build_named_planning_plane("validation-matrix", "quality", fixture, evaluation, lambda f, e: len(e.checks) == len(f.records) * 5, "five planes per row")
__all__ = ["build_planning_validation_matrix_plane"]
