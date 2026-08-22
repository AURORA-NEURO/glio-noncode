"""Review view models that expose evidence without raw observation payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierReviewRow:
    record_id: str
    operation: str
    role: str
    state: str
    candidate_ids: tuple[str, ...]
    evidence_count: int
    uncertainty: float
    review_required: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierReviewView:
    rows: tuple[CellContextBetaFrontierReviewRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.rows:
            raise ValueError("beta review view is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def review_count(self) -> int:
        return sum(item.review_required for item in self.rows)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"review_count": self.review_count}


def build_cell_context_beta_frontier_view(
    evaluation: CellContextBetaFrontierEvaluation,
) -> CellContextBetaFrontierReviewView:
    rows = tuple(
        CellContextBetaFrontierReviewRow(
            row.record_id,
            row.operation,
            row.role,
            row.observed_state,
            tuple(row.adapter.measurements.get("candidate_ids", ())),
            len(row.adapter.measurements.get("evidence_ids", ())),
            float(row.adapter.measurements.get("uncertainty", 1.0)),
            row.observed_state != "supported",
        )
        for row in evaluation.records
    )
    return CellContextBetaFrontierReviewView(rows, evaluation.accepted)


__all__ = [
    "CellContextBetaFrontierReviewRow",
    "CellContextBetaFrontierReviewView",
    "build_cell_context_beta_frontier_view",
]
