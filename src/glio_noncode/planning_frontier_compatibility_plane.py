"""Named compatibility assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_compatibility_plane(fixture, evaluation):
    return build_named_planning_plane("compatibility", "engineering", fixture, evaluation, lambda f, e: len(f.operations) == 4, "schema and adapters both cover four operations")
__all__ = ["build_planning_compatibility_plane"]
