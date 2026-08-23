"""Named source citation assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_source_citations_plane(fixture, evaluation):
    return build_named_planning_plane("source-citations", "evidence", fixture, evaluation, lambda f, e: all(s.uri for s in f.sources), "source URLs are retained")
__all__ = ["build_planning_source_citations_plane"]
