"""Named query assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_query_plane(fixture, evaluation):
    return build_named_planning_plane("query", "consumer", fixture, evaluation, lambda f, e: len({x.operation for x in e.executions}) == 4, "operation counts are queryable")
__all__ = ["build_planning_query_plane"]
