"""Independent validation matrix for the four prior families."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierValidationCell:
    operation: str
    scenario: str
    expected_state: str
    observed_count: int
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.operation or not self.scenario or not self.detail:
            raise ValidationError("beta validation cell is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierValidationReport:
    cells: tuple[CellContextBetaFrontierValidationCell, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.cells) != 16:
            raise ValidationError("beta validation matrix must have sixteen cells")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_scenarios(self) -> tuple[str, ...]:
        return tuple(item.scenario for item in self.cells if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_scenarios": list(self.failed_scenarios)}


def build_cell_context_beta_frontier_validation_matrix(
    evaluation: CellContextBetaFrontierEvaluation,
) -> CellContextBetaFrontierValidationReport:
    cells = tuple(
        CellContextBetaFrontierValidationCell(
            row.operation,
            row.record_id,
            row.record.expected_state.value,
            int(row.state_matches),
            row.state_matches and row.issue_floor_matches,
            "state and issue floor are aligned"
            if row.state_matches and row.issue_floor_matches
            else "validation mismatch",
        )
        for row in evaluation.records
    )
    return CellContextBetaFrontierValidationReport(cells, all(item.passed for item in cells))


def validate_cell_context_beta_frontier_matrix(
    report: CellContextBetaFrontierValidationReport,
) -> bool:
    return report.accepted and all(item.passed for item in report.cells)


__all__ = [
    "CellContextBetaFrontierValidationCell",
    "CellContextBetaFrontierValidationReport",
    "build_cell_context_beta_frontier_validation_matrix",
    "validate_cell_context_beta_frontier_matrix",
]
