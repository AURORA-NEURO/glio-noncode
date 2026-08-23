"""Named schema diagnostics assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_schema_diagnostics_plane(fixture, evaluation):
    return build_named_planning_plane("schema-diagnostics", "engineering", fixture, evaluation, lambda f, e: True, "schema failures are diagnosable")
__all__ = ["build_planning_schema_diagnostics_plane"]
