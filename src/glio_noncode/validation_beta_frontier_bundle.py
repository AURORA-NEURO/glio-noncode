"""Release bundle facade."""

from .validation_beta_frontier_governance import ValidationBetaFrontierReleaseBundle, assemble_validation_beta_frontier_bundle


def validation_beta_frontier_bundle_artifact_count(bundle: ValidationBetaFrontierReleaseBundle) -> int:
    return len(bundle.artifact_ids)


__all__ = ["ValidationBetaFrontierReleaseBundle", "assemble_validation_beta_frontier_bundle", "validation_beta_frontier_bundle_artifact_count"]
