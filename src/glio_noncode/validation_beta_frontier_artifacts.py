"""Addressed artifact inventory entry points."""

from .validation_beta_frontier_governance import ValidationBetaFrontierArtifact, ValidationBetaFrontierArtifactInventory, build_validation_beta_frontier_artifact_inventory


def validation_beta_frontier_artifact_ids(inventory: ValidationBetaFrontierArtifactInventory) -> tuple[str, ...]:
    return tuple(item.artifact_id for item in inventory.artifacts)


__all__ = ["ValidationBetaFrontierArtifact", "ValidationBetaFrontierArtifactInventory", "build_validation_beta_frontier_artifact_inventory", "validation_beta_frontier_artifact_ids"]
