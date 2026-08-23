"""Named provenance assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_provenance_plane(fixture, evaluation):
    return build_named_planning_plane("provenance", "evidence", fixture, evaluation, lambda f, e: bool(f.sources), "source receipts close")
__all__ = ["build_planning_provenance_plane"]
