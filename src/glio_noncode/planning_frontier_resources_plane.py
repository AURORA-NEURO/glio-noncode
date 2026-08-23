"""Named resource assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_resources_plane(fixture, evaluation):
    return build_named_planning_plane("resources", "operations", fixture, evaluation, lambda f, e: bool(f.sources), "public source list is available")
__all__ = ["build_planning_resources_plane"]
