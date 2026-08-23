"""Named attestation assurance plane."""
from .planning_frontier_assurance_plane import build_named_planning_plane
def build_planning_attestation_plane(fixture, evaluation):
    return build_named_planning_plane("attestation", "release", fixture, evaluation, lambda f, e: e.accepted, "release can attest accepted state")
__all__ = ["build_planning_attestation_plane"]
