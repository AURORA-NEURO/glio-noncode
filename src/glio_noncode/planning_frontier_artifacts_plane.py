"""Named artifact assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_artifacts_plane(fixture, evaluation):
    return build_named_planning_plane("artifacts", "release", fixture, evaluation, lambda f, e: all(r.content_address.startswith("sha256:") for r in f.records), "records have addresses")
__all__ = ["build_planning_artifacts_plane"]
