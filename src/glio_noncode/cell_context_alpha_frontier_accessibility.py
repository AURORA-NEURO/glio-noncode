"""Accessibility checks for alpha review surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierOperationAccessibility:
    operation: str
    has_operation_label: bool
    has_state_label: bool
    has_issue_label: bool
    has_delta_or_candidate_label: bool
    passed: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierAccessibilityReport:
    operations: tuple[CellContextAlphaFrontierOperationAccessibility, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cell_context_alpha_frontier_accessibility(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> CellContextAlphaFrontierAccessibilityReport:
    operations = []
    for operation in sorted({item.operation for item in evaluation.records}):
        rows = tuple(item for item in evaluation.records if item.operation == operation)
        has_special = all(
            bool(
                item.adapter.measurements.get("candidate_ids")
                or item.adapter.measurements.get("results")
                or item.observed_state in {"partial", "ambiguous", "out_of_domain", "abstained"}
            )
            for item in rows
        )
        item = CellContextAlphaFrontierOperationAccessibility(
            operation,
            bool(rows),
            all(bool(row.observed_state) for row in rows),
            all(row.observed_issue_codes is not None for row in rows),
            has_special,
            bool(rows)
            and has_special
            and any(row.observed_state == "out_of_domain" for row in rows),
        )
        operations.append(item)
    return CellContextAlphaFrontierAccessibilityReport(
        tuple(operations), all(item.passed for item in operations)
    )


__all__ = [
    "CellContextAlphaFrontierAccessibilityReport",
    "CellContextAlphaFrontierOperationAccessibility",
    "evaluate_cell_context_alpha_frontier_accessibility",
]
