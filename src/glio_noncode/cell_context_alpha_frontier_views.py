"""Review-safe view models for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierReviewRow:
    record_id: str
    operation: str
    role: str
    state: str
    candidate_ids: tuple[str, ...]
    result_count: int
    issue_codes: tuple[str, ...]
    review_required: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierReviewView:
    rows: tuple[CellContextAlphaFrontierReviewRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def review_count(self) -> int:
        return sum(item.review_required for item in self.rows)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"review_count": self.review_count}


def build_cell_context_alpha_frontier_view(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> CellContextAlphaFrontierReviewView:
    rows = tuple(
        CellContextAlphaFrontierReviewRow(
            row.record_id,
            row.operation,
            row.role,
            row.observed_state,
            tuple(row.adapter.measurements.get("candidate_ids", ())),
            int(row.adapter.measurements.get("result_count", 0)),
            row.observed_issue_codes,
            row.observed_state != "supported",
        )
        for row in evaluation.records
    )
    return CellContextAlphaFrontierReviewView(rows, evaluation.accepted)


__all__ = [
    "CellContextAlphaFrontierReviewRow",
    "CellContextAlphaFrontierReviewView",
    "build_cell_context_alpha_frontier_view",
]
