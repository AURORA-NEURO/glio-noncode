"""Release manifest and bounded-use projections."""

from .validation_beta_frontier_governance import (
    ValidationBetaFrontierReleaseCheck,
    ValidationBetaFrontierReleaseManifest,
    build_validation_beta_frontier_release_manifest,
)


def validation_beta_frontier_release_ready(manifest: ValidationBetaFrontierReleaseManifest) -> bool:
    return manifest.ready and bool(manifest.publishable_records) and bool(manifest.quarantined_records)


__all__ = ["ValidationBetaFrontierReleaseCheck", "ValidationBetaFrontierReleaseManifest", "build_validation_beta_frontier_release_manifest", "validation_beta_frontier_release_ready"]
