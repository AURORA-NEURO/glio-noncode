"""Validation matrix tying each operation to positive and control evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    SequenceGrammarOperation,
    SequenceGrammarRole,
    SequenceGrammarState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarValidationRow:
    operation: SequenceGrammarOperation
    positive_record_id: str
    control_record_ids: tuple[str, ...]
    criterion: str
    evidence: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.positive_record_id.strip()
            or not self.control_record_ids
            or not self.criterion.strip()
        ):
            raise ValidationError("validation row is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "positive_record_id": self.positive_record_id,
                        "control_record_ids": self.control_record_ids,
                        "criterion": self.criterion,
                        "evidence": self.evidence,
                        "accepted": self.accepted,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarValidationReport:
    accepted: bool
    rows: tuple[SequenceGrammarValidationRow, ...]
    fixture_id: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.rows) != 4:
            raise ValidationError("four validation rows are required")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"accepted": self.accepted, "rows": self.rows, "fixture_id": self.fixture_id}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture_id": self.fixture_id,
            "row_count": len(self.rows),
            "rows": [row.to_dict() for row in self.rows],
            "content_address": self.content_address,
        }


def build_sequence_grammar_validation_matrix(
    fixture: SequenceGrammarFixture, evaluation: SequenceGrammarEvaluation
) -> SequenceGrammarValidationReport:
    rows: list[SequenceGrammarValidationRow] = []
    for operation in SequenceGrammarOperation:
        executions = tuple(item for item in evaluation.executions if item.operation is operation)
        positive = next(item for item in executions if item.role is SequenceGrammarRole.POSITIVE)
        controls = tuple(item for item in executions if item.role is SequenceGrammarRole.CONTROL)
        accepted = positive.adapter_state is SequenceGrammarState.SUPPORTED and all(
            control.issue_codes for control in controls
        )
        rows.append(
            SequenceGrammarValidationRow(
                operation,
                positive.record_id,
                tuple(control.record_id for control in controls),
                "positive supported with explicit negative controls",
                f"positive={positive.adapter_state.value}; controls={len(controls)}",
                accepted,
            )
        )
    return SequenceGrammarValidationReport(
        all(row.accepted for row in rows), tuple(rows), fixture.fixture_id
    )


__all__ = [
    "SequenceGrammarValidationReport",
    "SequenceGrammarValidationRow",
    "build_sequence_grammar_validation_matrix",
]
