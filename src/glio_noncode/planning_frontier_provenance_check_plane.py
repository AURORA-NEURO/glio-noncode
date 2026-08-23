"""Named provenance check assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_provenance_check_plane(fixture, evaluation):
    return build_named_planning_plane("provenance-check", "evidence", fixture, evaluation, lambda f, e: all(x.content_address.startswith("sha256:") for x in e.executions), "content addresses are present")
__all__ = ["build_planning_provenance_check_plane"]
