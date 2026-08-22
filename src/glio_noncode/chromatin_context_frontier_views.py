"""Projection views that hide payload internals while retaining decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .chromatin_context_frontier_policy import ChromatinContextFrontierPolicyReport
from .chromatin_context_frontier_public_data import ChromatinContextFrontierFixture
from .chromatin_context_frontier_release import ChromatinContextFrontierReleaseManifest
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierReviewRow:
    record_id: str
    operation: str
    role: str
    observed_state: str
    decision: str
    issue_codes: tuple[str, ...]
    signal_summary: str
    review_required: bool
    release_eligible: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.operation or not self.observed_state:
            raise ValidationError("review row is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierReviewView:
    view_id: str
    context_key: str
    rows: tuple[ChromatinContextFrontierReviewRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.view_id or not self.context_key or not self.rows:
            raise ValidationError("review view is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def review_rows(self) -> tuple[ChromatinContextFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.review_required)

    @property
    def release_rows(self) -> tuple[ChromatinContextFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.release_eligible)

    @property
    def refusal_rows(self) -> tuple[ChromatinContextFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.decision == "refuse")

    def for_state(self, state: str) -> tuple[ChromatinContextFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.observed_state == state)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "review_row_count": len(self.review_rows),
            "release_row_count": len(self.release_rows),
            "refusal_row_count": len(self.refusal_rows),
        }


def build_chromatin_context_frontier_view(
    fixture: ChromatinContextFrontierFixture,
    evaluation: ChromatinContextFrontierEvaluation,
    policy: ChromatinContextFrontierPolicyReport,
    release: ChromatinContextFrontierReleaseManifest,
) -> ChromatinContextFrontierReviewView:
    policy_map = {item.record_id: item for item in policy.decisions}
    rows = []
    for item in evaluation.records:
        decision = policy_map[item.record_id]
        measurement = item.adapter.measurements
        signal = measurement.get(
            "median_signal", measurement.get("signal", measurement.get("delta"))
        )
        signal_summary = "unavailable" if signal is None else f"value={signal}"
        rows.append(
            ChromatinContextFrontierReviewRow(
                item.record_id,
                item.operation,
                item.role,
                item.observed_state,
                decision.decision,
                item.observed_issue_codes,
                signal_summary,
                decision.review_required,
                decision.release_eligible,
            )
        )
    accepted = (
        release.accepted
        and len(rows) == len(evaluation.records)
        and len({item.record_id for item in rows}) == len(rows)
    )
    return ChromatinContextFrontierReviewView(
        "glio-noncode-d07-c01-c04-review-view", fixture.context_key, tuple(rows), accepted
    )


__all__ = [
    "ChromatinContextFrontierReviewRow",
    "ChromatinContextFrontierReviewView",
    "build_chromatin_context_frontier_view",
]
