"""Named release transcript assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_release_transcript_plane(fixture, evaluation):
    return build_named_planning_plane("release-transcript", "release", fixture, evaluation, lambda f, e: bool(e.content_address), "release transcript is deterministic")
__all__ = ["build_planning_release_transcript_plane"]
