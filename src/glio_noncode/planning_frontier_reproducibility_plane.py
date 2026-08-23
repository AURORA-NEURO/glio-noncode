"""Named reproducibility assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_reproducibility_plane(fixture, evaluation):
    return build_named_planning_plane("reproducibility", "engineering", fixture, evaluation, lambda f, e: bool(f.content_address), "same fixture gives same address")
__all__ = ["build_planning_reproducibility_plane"]
