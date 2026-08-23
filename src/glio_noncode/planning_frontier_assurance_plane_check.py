"""Named assurance self-description plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_assurance_plane_check(fixture, evaluation):
    return build_named_planning_plane("assurance", "quality", fixture, evaluation, lambda f, e: bool(f.records and e.checks), "assurance matrix is self-describing")
__all__ = ["build_planning_assurance_plane_check"]
