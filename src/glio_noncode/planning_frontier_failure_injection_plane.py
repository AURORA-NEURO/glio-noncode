"""Named failure injection assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_failure_injection_plane(fixture, evaluation):
    return build_named_planning_plane("failure-injection", "resilience", fixture, evaluation, lambda f, e: len(f.control_records) >= 12, "negative cases exist")
__all__ = ["build_planning_failure_injection_plane"]
