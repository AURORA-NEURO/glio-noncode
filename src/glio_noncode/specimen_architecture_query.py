"""Read-only queries over architecture receipts and controls."""

from __future__ import annotations

from typing import Any

from .specimen_architecture_contracts import (
    SpecimenArchitectureEvaluation,
    SpecimenArchitectureFixture,
    SpecimenArchitectureScenario,
)


def cases_for_operation(
    fixture: SpecimenArchitectureFixture, operation: str
) -> tuple[dict[str, Any], ...]:
    """Return sanitized case declarations for one operation."""

    return tuple(case.to_dict() for case in fixture.cases if case.operation.value == operation)


def receipts_for_state(
    evaluation: SpecimenArchitectureEvaluation, state: str
) -> tuple[dict[str, Any], ...]:
    """Return receipt projections matching an observed architecture state."""

    return tuple(
        receipt.to_dict()
        for receipt in evaluation.receipts
        if receipt.observed_state.value == state
    )


def control_case_ids(fixture: SpecimenArchitectureFixture) -> tuple[str, ...]:
    """Return controls in deterministic fixture order."""

    return tuple(
        case.case_id
        for case in fixture.cases
        if case.scenario is not SpecimenArchitectureScenario.POSITIVE
    )


__all__ = ["cases_for_operation", "control_case_ids", "receipts_for_state"]
