"""Payload-aware but deterministic D06 queries."""

from __future__ import annotations

from .sequence_architecture_contracts import (
    SequenceArchitectureEvaluation,
    SequenceArchitectureFixture,
    SequenceArchitectureState,
)


def sequence_cases_for_operation(
    fixture: SequenceArchitectureFixture, operation: str
) -> tuple[dict[str, object], ...]:
    return tuple(
        item.to_dict()
        for item in fixture.cases
        if item.operation_id == operation or item.operation.value == operation
    )


def sequence_receipts_for_state(
    evaluation: SequenceArchitectureEvaluation, state: str
) -> tuple[dict[str, object], ...]:
    selected = SequenceArchitectureState(state)
    return tuple(item.to_dict() for item in evaluation.receipts if item.observed_state is selected)


def sequence_control_case_ids(fixture: SequenceArchitectureFixture) -> tuple[str, ...]:
    return tuple(item.case_id for item in fixture.control_cases)


__all__ = [
    "sequence_cases_for_operation",
    "sequence_control_case_ids",
    "sequence_receipts_for_state",
]
