"""Named replay assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_replay_plane(fixture, evaluation):
    return build_named_planning_plane("replay", "reproducibility", fixture, evaluation, lambda f, e: all(x.content_address.startswith("sha256:") for x in e.executions), "addresses are deterministic")
__all__ = ["build_planning_replay_plane"]
