"""Named access assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_access_plane(fixture, evaluation):
    return build_named_planning_plane("access", "consumer", fixture, evaluation, lambda f, e: all(s.uri.startswith("https://") for s in f.sources), "public sources are HTTPS")
__all__ = ["build_planning_access_plane"]
