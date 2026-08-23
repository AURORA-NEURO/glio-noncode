"""Named scenario matrix assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_scenario_matrix_plane(fixture, evaluation):
    return build_named_planning_plane("scenario-matrix", "quality", fixture, evaluation, lambda f, e: len(f.operations) == 4, "all four operations have scenarios")
__all__ = ["build_planning_scenario_matrix_plane"]
