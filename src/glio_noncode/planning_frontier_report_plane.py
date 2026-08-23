"""Named report assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_report_plane(fixture, evaluation):
    return build_named_planning_plane("report", "consumer", fixture, evaluation, lambda f, e: bool(f.evidence_boundary), "report boundary is explicit")
__all__ = ["build_planning_report_plane"]
