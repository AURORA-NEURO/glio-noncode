"""Named source registry assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_source_registry_plane(fixture, evaluation):
    return build_named_planning_plane("source-registry", "evidence", fixture, evaluation, lambda f, e: len({s.source_id for s in f.sources}) == len(f.sources), "source IDs are unique")
__all__ = ["build_planning_source_registry_plane"]
