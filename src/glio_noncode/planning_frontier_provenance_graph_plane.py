"""Named provenance graph assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_provenance_graph_plane(fixture, evaluation):
    return build_named_planning_plane("provenance-graph", "evidence", fixture, evaluation, lambda f, e: all(r.source_ids for r in f.records), "source-to-record edges exist")
__all__ = ["build_planning_provenance_graph_plane"]
