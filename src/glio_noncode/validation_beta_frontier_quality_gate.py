"""Quality gate entry points for CI and local release rehearsal."""

from .validation_beta_frontier_contracts import ValidationBetaFrontierContractRegistry
from .validation_beta_frontier_fixture_eval import ValidationBetaFrontierEvaluation
from .validation_beta_frontier_governance import (
    ValidationBetaFrontierLineage,
    ValidationBetaFrontierQualityGate,
    ValidationBetaFrontierReconciliation,
    evaluate_validation_beta_frontier_quality,
)
from .validation_beta_frontier_public_data import ValidationBetaFrontierFixture
from .validation_beta_frontier_schema import ValidationBetaFrontierSchemaReport


def run_validation_beta_frontier_quality_gate() -> ValidationBetaFrontierQualityGate:
    from .validation_beta_frontier_fixture_eval import evaluate_validation_beta_frontier_fixture
    from .validation_beta_frontier_governance import build_validation_beta_frontier_lineage
    from .validation_beta_frontier_public_data import default_validation_beta_frontier_fixture

    fixture = default_validation_beta_frontier_fixture()
    evaluation = evaluate_validation_beta_frontier_fixture(fixture)
    return evaluate_validation_beta_frontier_quality(fixture, evaluation, lineage=build_validation_beta_frontier_lineage(fixture, evaluation))


__all__ = ["ValidationBetaFrontierQualityGate", "evaluate_validation_beta_frontier_quality", "run_validation_beta_frontier_quality_gate"]
