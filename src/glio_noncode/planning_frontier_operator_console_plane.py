"""Named operator console assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_operator_console_plane(fixture, evaluation):
    return build_named_planning_plane("operator-console", "operations", fixture, evaluation, lambda f, e: len(f.operations) == 4, "operation names are discoverable")
__all__ = ["build_planning_operator_console_plane"]
