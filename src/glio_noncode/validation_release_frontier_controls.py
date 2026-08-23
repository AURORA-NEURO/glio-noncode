"""Control coverage and expected denial/review boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseControlRow:
    operation: str
    control_count: int
    non_ready_count: int
    issue_codes: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseControlCoverage:
    rows: tuple[ValidationReleaseControlRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_control_coverage(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseControlCoverage:
    rows = []
    for operation in sorted({item.operation.value for item in evaluation.executions}):
        controls = tuple(item for item in evaluation.executions if item.operation.value == operation and item.role.value == "control")
        codes = tuple(sorted({code for item in controls for code in item.issue_codes}))
        body = {"operation": operation, "control_count": len(controls), "non_ready_count": sum(item.observed_state.value not in {"ready", "packaged", "updated"} for item in controls), "issue_codes": codes, "accepted": len(controls) == 3 and all(item.observed_state.value not in {"ready", "packaged", "updated"} for item in controls)}
        rows.append(ValidationReleaseControlRow(**body, content_address=content_hash(body)))
    return ValidationReleaseControlCoverage(tuple(rows), all(item.accepted for item in rows), content_hash(tuple(rows)))


__all__ = ["ValidationReleaseControlCoverage", "ValidationReleaseControlRow", "build_validation_release_control_coverage"]
