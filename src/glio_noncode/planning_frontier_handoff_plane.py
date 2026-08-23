"""Named handoff assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_handoff_plane(fixture, evaluation):
    return build_named_planning_plane("handoff", "consumer", fixture, evaluation, lambda f, e: bool(f.fixture_id), "handoff can identify fixture")
__all__ = ["build_planning_handoff_plane"]
