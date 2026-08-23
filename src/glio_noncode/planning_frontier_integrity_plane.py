"""Named integrity assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_integrity_plane(fixture, evaluation):
    return build_named_planning_plane("integrity", "quality", fixture, evaluation, lambda f, e: f.content_address.startswith("sha256:"), "fixture address is present")
__all__ = ["build_planning_integrity_plane"]
