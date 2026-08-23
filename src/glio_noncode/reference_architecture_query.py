"""Read-only queries over D04 case and receipt projections."""

from __future__ import annotations

from typing import Any

from .reference_architecture_contracts import (
    ReferenceArchitectureEvaluation,
    ReferenceArchitectureFixture,
    ReferenceArchitectureScenario,
)


def reference_cases_for_operation(
    fixture: ReferenceArchitectureFixture, operation: str
) -> tuple[dict[str, Any], ...]:
    return tuple(case.to_dict() for case in fixture.cases if case.operation.value == operation)


def reference_receipts_for_state(
    evaluation: ReferenceArchitectureEvaluation, state: str
) -> tuple[dict[str, Any], ...]:
    return tuple(
        receipt.to_dict()
        for receipt in evaluation.receipts
        if receipt.observed_state.value == state
    )


def reference_control_case_ids(fixture: ReferenceArchitectureFixture) -> tuple[str, ...]:
    return tuple(
        case.case_id
        for case in fixture.cases
        if case.scenario is not ReferenceArchitectureScenario.POSITIVE
    )


__all__ = [
    "reference_cases_for_operation",
    "reference_control_case_ids",
    "reference_receipts_for_state",
]
