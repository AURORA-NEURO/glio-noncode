"""Scenario matrix across operation, role, and observed state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseScenarioCell:
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseScenarioMatrix:
    cells: tuple[ValidationReleaseScenarioCell, ...]
    accepted: bool
    content_address: str

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_validation_release_scenarios(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseScenarioMatrix:
    cells = []
    for item in evaluation.executions:
        body = {"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "expected_state": item.expected_state.value, "observed_state": item.observed_state.value, "accepted": item.observed_state == item.expected_state}
        cells.append(ValidationReleaseScenarioCell(**body, content_address=content_hash(body)))
    return ValidationReleaseScenarioMatrix(tuple(cells), all(item.accepted for item in cells), content_hash(tuple(cells)))


__all__ = ["ValidationReleaseScenarioCell", "ValidationReleaseScenarioMatrix", "evaluate_validation_release_scenarios"]
