"""Named quality gate assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_quality_gate_plane(fixture, evaluation):
    return build_named_planning_plane("quality-gate", "quality", fixture, evaluation, lambda f, e: e.accepted, "evaluation accepted")
__all__ = ["build_planning_quality_gate_plane"]
