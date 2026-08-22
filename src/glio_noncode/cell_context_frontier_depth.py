"""A depth ledger for the four Domain 08 operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierDepthDimension:
    dimension_id: str
    operation: str
    evidence_score: float
    control_score: float
    receipt_score: float
    release_score: float
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.dimension_id or not self.operation or not self.detail:
            raise ValidationError("cell depth dimension is incomplete")
        for value in (
            self.evidence_score,
            self.control_score,
            self.receipt_score,
            self.release_score,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValidationError("cell depth score must be in range")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def total_score(self) -> float:
        return round(
            (self.evidence_score + self.control_score + self.receipt_score + self.release_score)
            / 4,
            6,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"total_score": self.total_score}


@dataclass(frozen=True, slots=True)
class CellContextFrontierDepthReport:
    dimensions: tuple[CellContextFrontierDepthDimension, ...]
    mean_score: float
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.dimensions) != 4 or not 0.0 <= self.mean_score <= 1.0:
            raise ValidationError("cell depth report is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def by_operation(self, operation: str) -> CellContextFrontierDepthDimension:
        for item in self.dimensions:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_cell_context_frontier_depth(
    evaluation: CellContextFrontierEvaluation,
) -> CellContextFrontierDepthReport:
    dimensions = []
    for operation in sorted({item.operation for item in evaluation.records}):
        items = tuple(item for item in evaluation.records if item.operation == operation)
        evidence = sum(item.observed_state == "supported" for item in items) / len(items)
        controls = sum(item.role == "control" for item in items) / 3
        receipts = sum(item.adapter.content_address.startswith("sha256:") for item in items) / len(
            items
        )
        release = sum(item.state_matches and item.issue_floor_matches for item in items) / len(
            items
        )
        dimensions.append(
            CellContextFrontierDepthDimension(
                f"{operation}:depth",
                operation,
                evidence,
                min(controls, 1.0),
                receipts,
                release,
                "four-row operation has evidence, controls, receipts, and reconciliation",
            )
        )
    mean_score = round(sum(item.total_score for item in dimensions) / len(dimensions), 6)
    return CellContextFrontierDepthReport(tuple(dimensions), mean_score, mean_score >= 0.75)


__all__ = [
    "CellContextFrontierDepthDimension",
    "CellContextFrontierDepthReport",
    "audit_cell_context_frontier_depth",
]
