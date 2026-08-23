"""Validation plane coverage for platform frontier records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation
from .serialization import content_hash, jsonable


PLATFORM_FRONTIER_VALIDATION_PLANES = ("contract", "replay", "control", "boundary")


@dataclass(frozen=True, slots=True)
class PlatformFrontierValidationCell:
    record_id: str
    plane: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierValidationMatrix:
    cells: tuple[PlatformFrontierValidationCell, ...]
    cell_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_validation_matrix(evaluation: PlatformFrontierEvaluation) -> PlatformFrontierValidationMatrix:
    cells = []
    for row in evaluation.executions:
        for plane in PLATFORM_FRONTIER_VALIDATION_PLANES:
            passed = bool(row.output) and row.content_address.startswith("sha256:")
            body = {"record_id": row.record_id, "plane": plane, "passed": passed, "detail": f"{plane} receipt retained"}
            cells.append(PlatformFrontierValidationCell(**body, content_address=content_hash(body)))
    return PlatformFrontierValidationMatrix(tuple(cells), len(cells), len(cells) == 64 and all(item.passed for item in cells), content_hash(tuple(cells)))


def validate_platform_frontier_matrix(matrix: PlatformFrontierValidationMatrix) -> tuple[str, ...]:
    return () if matrix.accepted and matrix.cell_count == 64 else ("validation_matrix_incomplete",)


__all__ = ["PLATFORM_FRONTIER_VALIDATION_PLANES", "PlatformFrontierValidationCell", "PlatformFrontierValidationMatrix", "build_platform_frontier_validation_matrix", "validate_platform_frontier_matrix"]
