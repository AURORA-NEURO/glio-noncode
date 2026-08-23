"""Named invariant assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_invariants_plane(fixture, evaluation):
    return build_named_planning_plane("invariants", "quality", fixture, evaluation, lambda f, e: len(f.records) == 16 and len(f.positive_records) == 4, "row and role counts are balanced")
__all__ = ["build_planning_invariants_plane"]
