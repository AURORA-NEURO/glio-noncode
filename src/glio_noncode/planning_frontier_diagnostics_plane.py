"""Named diagnostics assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_diagnostics_plane(fixture, evaluation):
    return build_named_planning_plane("diagnostics", "operations", fixture, evaluation, lambda f, e: bool(e.executions), "state distribution is measurable")
__all__ = ["build_planning_diagnostics_plane"]
