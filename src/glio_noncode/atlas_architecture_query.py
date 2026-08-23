"""Read-only queries over sanitized D05 atlas projections."""

from __future__ import annotations

from typing import Any

from .atlas_architecture_contracts import (
    AtlasArchitectureEvaluation,
    AtlasArchitectureFixture,
    AtlasArchitectureScenario,
)


def atlas_cases_for_operation(
    fixture: AtlasArchitectureFixture, operation: str
) -> tuple[dict[str, Any], ...]:
    return tuple(case.to_dict() for case in fixture.cases if case.operation.value == operation)


def atlas_receipts_for_state(
    evaluation: AtlasArchitectureEvaluation, state: str
) -> tuple[dict[str, Any], ...]:
    return tuple(
        receipt.to_dict()
        for receipt in evaluation.receipts
        if receipt.observed_state.value == state
    )


def atlas_control_case_ids(fixture: AtlasArchitectureFixture) -> tuple[str, ...]:
    return tuple(
        case.case_id
        for case in fixture.cases
        if case.scenario is not AtlasArchitectureScenario.POSITIVE
    )


__all__ = ["atlas_cases_for_operation", "atlas_control_case_ids", "atlas_receipts_for_state"]
