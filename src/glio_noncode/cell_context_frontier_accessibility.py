"""Accessibility summary for downstream context consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierOperationAccessibility:
    operation: str
    row_count: int
    supported_count: int
    review_count: int
    refusal_count: int
    state_counts: dict[str, int]
    available: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.operation or self.row_count < 1 or not self.detail:
            raise ValidationError("cell accessibility row is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierAccessibilityReport:
    operations: tuple[CellContextFrontierOperationAccessibility, ...]
    accepted: bool
    available_operation_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.operations) != 4:
            raise ValidationError("cell accessibility requires four operations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def operation(self, operation: str) -> CellContextFrontierOperationAccessibility:
        for item in self.operations:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cell_context_frontier_accessibility(
    evaluation: CellContextFrontierEvaluation,
) -> CellContextFrontierAccessibilityReport:
    rows = []
    for operation in sorted({item.operation for item in evaluation.records}):
        items = tuple(item for item in evaluation.records if item.operation == operation)
        state_counts = {
            state: sum(item.observed_state == state for item in items)
            for state in sorted({item.observed_state for item in items})
        }
        rows.append(
            CellContextFrontierOperationAccessibility(
                operation,
                len(items),
                sum(item.observed_state == "supported" for item in items),
                sum(
                    item.observed_state in {"partial", "ambiguous", "contradictory", "abstained"}
                    for item in items
                ),
                sum(item.observed_state == "out_of_domain" for item in items),
                state_counts,
                any(item.observed_state == "supported" for item in items),
                "operation has a supported path and explicit controls",
            )
        )
    return CellContextFrontierAccessibilityReport(
        tuple(rows), all(item.available for item in rows), sum(item.available for item in rows)
    )


__all__ = [
    "CellContextFrontierAccessibilityReport",
    "CellContextFrontierOperationAccessibility",
    "evaluate_cell_context_frontier_accessibility",
]
