"""Named run manifest assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_run_manifest_plane(fixture, evaluation):
    return build_named_planning_plane("run-manifest", "release", fixture, evaluation, lambda f, e: bool(f.content_address), "run identity is stable")
__all__ = ["build_planning_run_manifest_plane"]
