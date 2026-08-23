"""Cross-plane invariants for the C05-C12 surface."""

from typing import Any

from .validation_beta_frontier_fixture_eval import ValidationBetaFrontierEvaluation
from .validation_beta_frontier_public_data import ValidationBetaFrontierFixture


def run_validation_beta_frontier_invariants(fixture: ValidationBetaFrontierFixture, evaluation: ValidationBetaFrontierEvaluation) -> dict[str, Any]:
    checks = {"one_positive_per_operation": all(sum(item.record_id.endswith("POS-001") for item in evaluation.rows if item.operation is operation) == 1 for operation in {item.operation for item in evaluation.rows}), "three_controls_per_operation": all(sum("CTRL" in item.record_id for item in evaluation.rows if item.operation is operation) == 3 for operation in {item.operation for item in evaluation.rows}), "source_closure": all(set(item.source_ids).issubset(fixture.source_map()) for item in fixture.records), "expected_states_accepted": evaluation.accepted}
    return {"checks": checks, "accepted": all(checks.values())}


__all__ = ["run_validation_beta_frontier_invariants"]
