"""Named reconciliation assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_reconciliation_plane(fixture, evaluation):
    return build_named_planning_plane("reconciliation", "quality", fixture, evaluation, lambda f, e: e.accepted, "expected states reconcile")
__all__ = ["build_planning_reconciliation_plane"]
