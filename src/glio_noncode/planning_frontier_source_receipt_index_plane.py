"""Named source receipt index assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_source_receipt_index_plane(fixture, evaluation):
    return build_named_planning_plane("source-receipt-index", "evidence", fixture, evaluation, lambda f, e: all(s.content_address.startswith("sha256:") for s in f.sources), "source receipt index is addressable")
__all__ = ["build_planning_source_receipt_index_plane"]
