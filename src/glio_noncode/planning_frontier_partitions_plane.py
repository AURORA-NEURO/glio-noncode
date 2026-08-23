"""Named partition assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_partitions_plane(fixture, evaluation):
    return build_named_planning_plane("partitions", "engineering", fixture, evaluation, lambda f, e: bool(f.positive_records and f.control_records), "positive and control partitions exist")
__all__ = ["build_planning_partitions_plane"]
