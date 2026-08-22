"""Validation matrix that maps operations to checks and release evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_public_data import ChromatinContextFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierValidationCell:
    operation: str
    layer: str
    check_id: str
    required: bool
    evidence: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.operation or not self.layer or not self.check_id or not self.evidence:
            raise ValidationError("validation cell is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierValidationReport:
    cells: tuple[ChromatinContextFrontierValidationCell, ...]
    accepted: bool
    required_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.cells) < 24:
            raise ValidationError("validation matrix requires at least twenty-four cells")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(self, operation: str) -> tuple[ChromatinContextFrontierValidationCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def for_layer(self, layer: str) -> tuple[ChromatinContextFrontierValidationCell, ...]:
        return tuple(item for item in self.cells if item.layer == layer)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_context_frontier_validation_matrix() -> (
    ChromatinContextFrontierValidationReport
):
    layers = (
        ("data", "public receipt and aggregate boundary"),
        ("schema", "typed payload and context key"),
        ("primitive", "low-level operation result"),
        ("uncertainty", "partial, ambiguous, and abstained paths"),
        ("release", "policy, lineage, and export receipt"),
        ("replay", "deterministic content address"),
    )
    cells = tuple(
        ChromatinContextFrontierValidationCell(
            operation.value, layer, f"{operation.value}:{layer}", True, evidence
        )
        for operation in ChromatinContextFrontierOperation
        for layer, evidence in layers
    )
    return ChromatinContextFrontierValidationReport(
        cells, True, sum(item.required for item in cells)
    )


def validate_chromatin_context_frontier_matrix(
    report: ChromatinContextFrontierValidationReport,
) -> bool:
    return (
        report.accepted
        and report.required_count == sum(item.required for item in report.cells)
        and len({item.operation for item in report.cells}) == 4
        and len({item.layer for item in report.cells}) == 6
    )


__all__ = [
    "ChromatinContextFrontierValidationCell",
    "ChromatinContextFrontierValidationReport",
    "build_chromatin_context_frontier_validation_matrix",
    "validate_chromatin_context_frontier_matrix",
]
