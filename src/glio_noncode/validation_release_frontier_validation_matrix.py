"""Cross-product validation matrix for four operation planes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation

VALIDATION_RELEASE_PLANES = ("contract", "context", "state", "issue", "provenance", "projection")


@dataclass(frozen=True, slots=True)
class ValidationReleaseValidationCell:
    record_id: str
    plane: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseValidationMatrix:
    cells: tuple[ValidationReleaseValidationCell, ...]
    accepted: bool
    content_address: str

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_validation_matrix(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseValidationMatrix:
    cells = []
    for item in evaluation.executions:
        values = {"contract": True, "context": True, "state": item.observed_state == item.expected_state, "issue": True, "provenance": item.content_address.startswith("sha256:"), "projection": isinstance(item.output, dict)}
        for plane in VALIDATION_RELEASE_PLANES:
            body = {"record_id": item.record_id, "plane": plane, "passed": values[plane], "detail": f"{plane} boundary evaluated"}
            cells.append(ValidationReleaseValidationCell(**body, content_address=content_hash(body)))
    return ValidationReleaseValidationMatrix(tuple(cells), all(item.passed for item in cells), content_hash(tuple(cells)))


__all__ = ["VALIDATION_RELEASE_PLANES", "ValidationReleaseValidationCell", "ValidationReleaseValidationMatrix", "build_validation_release_validation_matrix"]
