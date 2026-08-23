"""Named summary assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_summary_plane(fixture, evaluation):
    return build_named_planning_plane("summary", "consumer", fixture, evaluation, lambda f, e: bool(e.content_address), "summary is generated")
__all__ = ["build_planning_summary_plane"]
