"""Named controls assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_controls_plane(fixture, evaluation):
    return build_named_planning_plane("controls", "quality", fixture, evaluation, lambda f, e: len(f.control_records) == 12, "control roles are present")
__all__ = ["build_planning_controls_plane"]
