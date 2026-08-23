"""Compact release summary facade."""

from typing import Any

from .validation_beta_frontier_fixture_eval import ValidationBetaFrontierEvaluation
from .validation_beta_frontier_governance import ValidationBetaFrontierQualityGate, ValidationBetaFrontierReleaseManifest, validation_beta_frontier_summary
from .validation_beta_frontier_public_data import ValidationBetaFrontierFixture


def build_validation_beta_frontier_summary(fixture: ValidationBetaFrontierFixture, evaluation: ValidationBetaFrontierEvaluation, quality: ValidationBetaFrontierQualityGate, release: ValidationBetaFrontierReleaseManifest) -> dict[str, Any]:
    return validation_beta_frontier_summary(fixture, evaluation, quality, release)


__all__ = ["build_validation_beta_frontier_summary", "validation_beta_frontier_summary"]
