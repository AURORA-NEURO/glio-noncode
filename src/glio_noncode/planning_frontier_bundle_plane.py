"""Named bundle assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_bundle_plane(fixture, evaluation):
    return build_named_planning_plane("bundle", "release", fixture, evaluation, lambda f, e: bool(f.content_address and e.content_address), "fixture and evaluation can be bundled")
__all__ = ["build_planning_bundle_plane"]
