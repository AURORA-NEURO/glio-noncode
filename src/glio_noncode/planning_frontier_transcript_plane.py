"""Named transcript assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_transcript_plane(fixture, evaluation):
    return build_named_planning_plane("transcript", "release", fixture, evaluation, lambda f, e: bool(e.content_address), "execution transcript exists")
__all__ = ["build_planning_transcript_plane"]
