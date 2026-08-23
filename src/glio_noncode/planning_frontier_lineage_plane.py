"""Named lineage assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_lineage_plane(fixture, evaluation):
    return build_named_planning_plane("lineage", "evidence", fixture, evaluation, lambda f, e: all(r.source_ids for r in f.records), "records retain source joins")
__all__ = ["build_planning_lineage_plane"]
