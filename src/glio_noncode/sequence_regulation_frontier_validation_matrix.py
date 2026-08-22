"""Validation matrix for operation inputs and release outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationFixture,
    SequenceRegulationOperation,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationValidationCase:
    case_id: str
    operation: str
    input_kind: str
    expected_result: str
    passed: bool
    detail: str

    def __post_init__(self) -> None:
        if not self.case_id or not self.operation or not self.detail:
            raise ValidationError("validation case is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationValidationReport:
    cases: tuple[SequenceRegulationValidationCase, ...]
    accepted: bool
    passed_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.cases:
            raise ValidationError("validation report requires cases")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_regulation_validation_matrix(
    fixture: SequenceRegulationFixture,
    evaluation: SequenceRegulationEvaluation,
) -> SequenceRegulationValidationReport:
    cases = tuple(
        SequenceRegulationValidationCase(
            case_id=f"validation:{item.record_id}",
            operation=item.adapter.operation.value,
            input_kind=item.role,
            expected_result=item.expected_state.value,
            passed=item.accepted,
            detail="expected state and issue path match"
            if item.accepted
            else "expected path differs",
        )
        for item in evaluation.records
    )
    cases += tuple(
        SequenceRegulationValidationCase(
            f"coverage:{operation.value}",
            operation.value,
            "operation",
            "represented",
            any(item.adapter.operation is operation for item in evaluation.records),
            "operation has at least one record",
        )
        for operation in SequenceRegulationOperation
    )
    return SequenceRegulationValidationReport(
        cases, all(case.passed for case in cases), sum(case.passed for case in cases)
    )


__all__ = [
    "SequenceRegulationValidationCase",
    "SequenceRegulationValidationReport",
    "build_sequence_regulation_validation_matrix",
]
