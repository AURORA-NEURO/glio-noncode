"""Named decision ledger assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_decision_ledger_plane(fixture, evaluation):
    return build_named_planning_plane("decision-ledger", "consumer", fixture, evaluation, lambda f, e: bool(e.executions), "states are decision-relevant")
__all__ = ["build_planning_decision_ledger_plane"]
