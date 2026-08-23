"""Named boundary report assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_boundary_report_plane(fixture, evaluation):
    return build_named_planning_plane("boundary-report", "boundary", fixture, evaluation, lambda f, e: bool(f.evidence_boundary), "allowed uses are bounded")
__all__ = ["build_planning_boundary_report_plane"]
