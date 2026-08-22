"""Reconcile operation results with expected fixture paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationReconciliationItem:
    record_id: str
    state_match: bool
    issue_match: bool
    difference: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValidationError("reconciliation item requires record ID")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationReconciliation:
    items: tuple[SequenceRegulationReconciliationItem, ...]
    accepted: bool
    difference_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.items:
            raise ValidationError("reconciliation requires items")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_sequence_regulation(
    evaluation: SequenceRegulationEvaluation,
) -> SequenceRegulationReconciliation:
    items = tuple(
        SequenceRegulationReconciliationItem(
            item.record_id,
            item.state_match,
            item.issue_match,
            "matched" if item.accepted else "expected and observed paths differ",
        )
        for item in evaluation.records
    )
    differences = sum(item.difference != "matched" for item in items)
    return SequenceRegulationReconciliation(items, differences == 0, differences)


__all__ = [
    "SequenceRegulationReconciliation",
    "SequenceRegulationReconciliationItem",
    "reconcile_sequence_regulation",
]
