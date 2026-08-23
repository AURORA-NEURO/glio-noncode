"""Release-note payload for the C05-C12 slice."""

from typing import Any

from .validation_beta_frontier_public_data import VALIDATION_BETA_FRONTIER_FIXTURE_VERSION


def validation_beta_frontier_release_notes() -> dict[str, Any]:
    return {"version": VALIDATION_BETA_FRONTIER_FIXTURE_VERSION, "scope": "Domain 13 C05-C12", "added": ("context-gated perturbation planning", "public aggregate model eligibility", "lossless guide/oligo adaptation", "deterministic controls and power planning", "state-aware release and review controls"), "excluded": ("efficacy", "off-target safety", "clinical use", "automatic execution"), "migration": "No migration is required for the independent C05-C12 fixture namespace."}


__all__ = ["validation_beta_frontier_release_notes"]
