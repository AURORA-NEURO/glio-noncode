"""Independent row validation matrix for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierValidationCell:
    operation: str
    scenario: str
    expected_state: str
    observed_state: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierValidationReport:
    cells: tuple[CellContextAlphaFrontierValidationCell, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.cells) != 16:
            raise ValueError("alpha validation matrix requires sixteen cells")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_alpha_frontier_validation_matrix(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> CellContextAlphaFrontierValidationReport:
    cells = tuple(
        CellContextAlphaFrontierValidationCell(
            row.operation,
            row.record_id,
            row.record.expected_state.value,
            row.observed_state,
            row.state_matches and row.issue_floor_matches,
            "expected state and issue floor agree"
            if row.state_matches and row.issue_floor_matches
            else "validation mismatch",
        )
        for row in evaluation.records
    )
    return CellContextAlphaFrontierValidationReport(cells, all(item.passed for item in cells))


def validate_cell_context_alpha_frontier_matrix(
    report: CellContextAlphaFrontierValidationReport,
) -> bool:
    return report.accepted and all(item.passed for item in report.cells)


__all__ = [
    "CellContextAlphaFrontierValidationCell",
    "CellContextAlphaFrontierValidationReport",
    "build_cell_context_alpha_frontier_validation_matrix",
    "validate_cell_context_alpha_frontier_matrix",
]
