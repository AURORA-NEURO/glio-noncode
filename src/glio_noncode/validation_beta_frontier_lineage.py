"""Lineage projections and closure assertions."""

from .validation_beta_frontier_fixture_eval import ValidationBetaFrontierEvaluation
from .validation_beta_frontier_governance import ValidationBetaFrontierLineage, build_validation_beta_frontier_lineage
from .validation_beta_frontier_public_data import ValidationBetaFrontierFixture


def verify_validation_beta_frontier_lineage(lineage: ValidationBetaFrontierLineage) -> bool:
    return lineage.closed and not lineage.orphan_ids and bool(lineage.edges)


__all__ = ["ValidationBetaFrontierLineage", "build_validation_beta_frontier_lineage", "verify_validation_beta_frontier_lineage"]
