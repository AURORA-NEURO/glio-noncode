"""Operation-by-layer validation matrix for Domain 08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_public_data import CellContextFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierValidationCell:
    operation: str
    layer: str
    check_id: str
    required: bool
    evidence: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.operation or not self.layer or not self.check_id or not self.evidence:
            raise ValidationError("cell validation cell is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierValidationReport:
    cells: tuple[CellContextFrontierValidationCell, ...]
    accepted: bool
    required_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.cells) < 24:
            raise ValidationError("cell validation matrix requires twenty-four cells")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(self, operation: str) -> tuple[CellContextFrontierValidationCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def for_layer(self, layer: str) -> tuple[CellContextFrontierValidationCell, ...]:
        return tuple(item for item in self.cells if item.layer == layer)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_frontier_validation_matrix() -> CellContextFrontierValidationReport:
    layers = (
        ("data", "public receipt and aggregate boundary"),
        ("schema", "typed observation payload and exact context"),
        ("primitive", "low-level resolver result"),
        ("uncertainty", "ambiguity contradiction missingness and refusal"),
        ("release", "policy lineage and export receipt"),
        ("replay", "deterministic content address"),
    )
    cells = tuple(
        CellContextFrontierValidationCell(
            operation.value, layer, f"{operation.value}:{layer}", True, evidence
        )
        for operation in CellContextFrontierOperation
        for layer, evidence in layers
    )
    return CellContextFrontierValidationReport(cells, True, sum(item.required for item in cells))


def validate_cell_context_frontier_matrix(report: CellContextFrontierValidationReport) -> bool:
    return (
        report.accepted
        and report.required_count == sum(item.required for item in report.cells)
        and len({item.operation for item in report.cells}) == 4
        and len({item.layer for item in report.cells}) == 6
    )


__all__ = [
    "CellContextFrontierValidationCell",
    "CellContextFrontierValidationReport",
    "build_cell_context_frontier_validation_matrix",
    "validate_cell_context_frontier_matrix",
]
