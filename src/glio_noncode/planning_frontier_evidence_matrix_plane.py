"""Named evidence matrix assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_evidence_matrix_plane(fixture, evaluation):
    return build_named_planning_plane("evidence-matrix", "evidence", fixture, evaluation, lambda f, e: bool(f.evidence_boundary), "public evidence is explicit")
__all__ = ["build_planning_evidence_matrix_plane"]
