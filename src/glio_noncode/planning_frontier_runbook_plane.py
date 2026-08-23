"""Named runbook assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_runbook_plane(fixture, evaluation):
    return build_named_planning_plane("runbook", "operations", fixture, evaluation, lambda f, e: bool(f.fixture_id), "operator sequence is documented")
__all__ = ["build_planning_runbook_plane"]
