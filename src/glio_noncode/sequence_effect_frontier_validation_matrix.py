"""Validation matrix connecting operations to controls and release surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_public_data import SequenceEffectFixture, SequenceEffectOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectValidationRow:
    validation_id: str
    operation: SequenceEffectOperation
    positive_record_id: str
    control_record_ids: tuple[str, ...]
    required_fields: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self, "content_address", content_hash(jsonable(self) | {"content_address": ""})
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectValidationReport:
    rows: tuple[SequenceEffectValidationRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"rows": self.rows, "accepted": self.accepted}),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "rows": [item.to_dict() for item in self.rows],
            "content_address": self.content_address,
        }


def build_sequence_effect_validation_matrix(
    fixture: SequenceEffectFixture, evaluation: SequenceEffectEvaluation
) -> SequenceEffectValidationReport:
    rows = tuple(
        SequenceEffectValidationRow(
            operation.value,
            operation,
            next(
                item.record_id for item in fixture.positive_records if item.operation is operation
            ),
            tuple(
                item.record_id for item in fixture.control_records if item.operation is operation
            ),
            ("context_key", "source_ids", "content_address"),
            all(item.accepted for item in evaluation.executions if item.operation is operation),
        )
        for operation in SequenceEffectOperation
    )
    return SequenceEffectValidationReport(
        rows, len(rows) == 4 and all(item.accepted for item in rows)
    )


__all__ = [
    "SequenceEffectValidationReport",
    "SequenceEffectValidationRow",
    "build_sequence_effect_validation_matrix",
]
