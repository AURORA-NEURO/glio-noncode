"""Named data dictionary assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_data_dictionary_plane(fixture, evaluation):
    return build_named_planning_plane("data-dictionary", "consumer", fixture, evaluation, lambda f, e: len(f.operations) == 4, "fields have operation ownership")
__all__ = ["build_planning_data_dictionary_plane"]
