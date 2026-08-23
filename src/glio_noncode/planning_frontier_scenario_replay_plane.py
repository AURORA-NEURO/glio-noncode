"""Named scenario replay assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_scenario_replay_plane(fixture, evaluation):
    return build_named_planning_plane("scenario-replay", "reproducibility", fixture, evaluation, lambda f, e: bool(e.executions), "scenario replay is available")
__all__ = ["build_planning_scenario_replay_plane"]
