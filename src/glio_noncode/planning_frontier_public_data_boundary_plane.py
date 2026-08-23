"""Named public-data boundary assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_public_data_boundary_plane(fixture, evaluation):
    return build_named_planning_plane("public-data-boundary", "boundary", fixture, evaluation, lambda f, e: f.evidence_boundary == "public_aggregate_planning_evidence", "fixture uses aggregate public receipts")
__all__ = ["build_planning_public_data_boundary_plane"]
