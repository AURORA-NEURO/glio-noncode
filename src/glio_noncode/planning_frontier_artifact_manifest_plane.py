"""Named artifact manifest assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_artifact_manifest_plane(fixture, evaluation):
    return build_named_planning_plane("artifact-manifest", "release", fixture, evaluation, lambda f, e: all(r.content_address.startswith("sha256:") for r in f.records), "artifact addresses are retained")
__all__ = ["build_planning_artifact_manifest_plane"]
