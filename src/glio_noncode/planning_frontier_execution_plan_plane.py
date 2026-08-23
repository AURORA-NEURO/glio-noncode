"""Named execution plan assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_execution_plan_plane(fixture, evaluation):
    return build_named_planning_plane("execution-plan", "operations", fixture, evaluation, lambda f, e: bool(e.executions), "fixture can execute")
__all__ = ["build_planning_execution_plan_plane"]
