"""Accessibility report for review exports and state visibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierOperationAccessibility:
    operation: str
    has_text_label: bool
    has_state_label: bool
    has_uncertainty_label: bool
    has_refusal_label: bool
    passed: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierAccessibilityReport:
    operations: tuple[CellContextBetaFrontierOperationAccessibility, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cell_context_beta_frontier_accessibility(
    evaluation: CellContextBetaFrontierEvaluation,
) -> CellContextBetaFrontierAccessibilityReport:
    operations = []
    for operation in sorted({item.operation for item in evaluation.records}):
        rows = tuple(item for item in evaluation.records if item.operation == operation)
        accessible = CellContextBetaFrontierOperationAccessibility(
            operation,
            bool(rows),
            all(bool(item.observed_state) for item in rows),
            all("uncertainty" in item.adapter.measurements for item in rows),
            any(item.observed_state == "out_of_domain" for item in rows),
            bool(rows)
            and all(bool(item.observed_state) for item in rows)
            and all("uncertainty" in item.adapter.measurements for item in rows)
            and any(item.observed_state == "out_of_domain" for item in rows),
        )
        operations.append(accessible)
    return CellContextBetaFrontierAccessibilityReport(
        tuple(operations), all(item.passed for item in operations)
    )


__all__ = [
    "CellContextBetaFrontierAccessibilityReport",
    "CellContextBetaFrontierOperationAccessibility",
    "evaluate_cell_context_beta_frontier_accessibility",
]
