"""Named package manifest assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_package_manifest_plane(fixture, evaluation):
    return build_named_planning_plane("package-manifest", "release", fixture, evaluation, lambda f, e: bool(f.records and e.executions), "package inventory is closed")
__all__ = ["build_planning_package_manifest_plane"]
