"""Review-safe context projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .cell_context_frontier_policy import CellContextFrontierPolicyReport
from .cell_context_frontier_public_data import CellContextFrontierFixture
from .cell_context_frontier_release import CellContextFrontierReleaseManifest
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierReviewRow:
    record_id: str
    operation: str
    role: str
    observed_state: str
    decision: str
    issue_codes: tuple[str, ...]
    candidate_summary: str
    uncertainty: float | None
    review_required: bool
    release_eligible: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.operation or not self.observed_state:
            raise ValidationError("cell review row is incomplete")
        if self.uncertainty is not None and not 0.0 <= self.uncertainty <= 1.0:
            raise ValidationError("cell review uncertainty is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierReviewView:
    view_id: str
    context_key: str
    rows: tuple[CellContextFrontierReviewRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.view_id or not self.context_key or not self.rows:
            raise ValidationError("cell review view is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def review_rows(self) -> tuple[CellContextFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.review_required)

    @property
    def release_rows(self) -> tuple[CellContextFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.release_eligible)

    @property
    def refusal_rows(self) -> tuple[CellContextFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.decision == "refuse")

    def for_operation(self, operation: str) -> tuple[CellContextFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "review_count": len(self.review_rows),
            "release_count": len(self.release_rows),
            "refusal_count": len(self.refusal_rows),
        }


def build_cell_context_frontier_view(
    fixture: CellContextFrontierFixture,
    evaluation: CellContextFrontierEvaluation,
    policy: CellContextFrontierPolicyReport,
    release: CellContextFrontierReleaseManifest,
) -> CellContextFrontierReviewView:
    decisions = {item.record_id: item for item in policy.decisions}
    rows = []
    for item in evaluation.records:
        decision = decisions[item.record_id]
        candidate_ids = item.adapter.measurements.get(
            "candidate_ids", item.adapter.measurements.get("territory_candidates", ())
        )
        uncertainty = item.adapter.measurements.get("uncertainty")
        rows.append(
            CellContextFrontierReviewRow(
                item.record_id,
                item.operation,
                item.role,
                item.observed_state,
                decision.decision,
                item.observed_issue_codes,
                ",".join(str(value) for value in candidate_ids) or "none",
                uncertainty,
                decision.review_required,
                decision.release_eligible,
            )
        )
    accepted = (
        release.accepted
        and len(rows) == len(evaluation.records)
        and len({item.record_id for item in rows}) == len(rows)
    )
    return CellContextFrontierReviewView(
        "glio-noncode-d08-c01-c04-review-view", fixture.context_key, tuple(rows), accepted
    )


__all__ = [
    "CellContextFrontierReviewRow",
    "CellContextFrontierReviewView",
    "build_cell_context_frontier_view",
]
