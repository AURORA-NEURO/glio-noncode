"""Sanitized review view for chromatin-alpha release consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .chromatin_alpha_frontier_policy import ChromatinAlphaFrontierPolicyReport
from .chromatin_alpha_frontier_public_data import ChromatinAlphaFrontierFixture
from .chromatin_alpha_frontier_release import ChromatinAlphaFrontierReleaseManifest
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReviewRow:
    row_id: str
    record_id: str
    operation: str
    role: str
    state: str
    decision: str
    expected_state: str
    state_match: bool
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    context_key: str
    measurements: dict[str, Any]
    notes: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.row_id or not self.record_id or not self.operation or not self.context_key:
            raise ValidationError("review row identity is incomplete")
        if not self.notes:
            raise ValidationError("review row notes are required")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReviewView:
    fixture_id: str
    rows: tuple[ChromatinAlphaFrontierReviewRow, ...]
    source_matrix: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    release_state: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.rows or not self.source_matrix:
            raise ValidationError("review view requires fixture, rows, and sources")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def review_count(self) -> int:
        return sum(row.decision != "release" for row in self.rows)

    @property
    def accepted_record_ids(self) -> tuple[str, ...]:
        return tuple(row.record_id for row in self.rows if row.decision == "release")

    def by_operation(self, operation: str) -> tuple[ChromatinAlphaFrontierReviewRow, ...]:
        return tuple(row for row in self.rows if row.operation == operation)

    def by_state(self, state: str) -> tuple[ChromatinAlphaFrontierReviewRow, ...]:
        return tuple(row for row in self.rows if row.state == state)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "review_count": self.review_count,
            "accepted_record_ids": list(self.accepted_record_ids),
        }


def build_chromatin_alpha_frontier_view(
    fixture: ChromatinAlphaFrontierFixture,
    evaluation: ChromatinAlphaFrontierEvaluation,
    policy: ChromatinAlphaFrontierPolicyReport,
    release: ChromatinAlphaFrontierReleaseManifest,
) -> ChromatinAlphaFrontierReviewView:
    records = fixture.record_map()
    decisions = {decision.record_id: decision for decision in policy.decisions}
    rows = tuple(
        ChromatinAlphaFrontierReviewRow(
            row_id=f"chromatin-alpha-review-{index:03d}",
            record_id=item.record_id,
            operation=item.operation,
            role=item.role,
            state=item.observed_state,
            decision=decisions[item.record_id].decision,
            expected_state=item.expected_state,
            state_match=item.state_match,
            issue_codes=item.observed_issue_codes,
            source_ids=records[item.record_id].source_ids,
            context_key=fixture.context_key,
            measurements=dict(item.adapter.measurements),
            notes=decisions[item.record_id].reasons[0],
        )
        for index, item in enumerate(evaluation.records, start=1)
    )
    source_matrix = tuple(
        {
            "source_id": source.source_id,
            "title": source.title,
            "uri": source.uri,
            "source_kind": source.source_kind,
            "release": source.release,
            "scope": source.scope,
            "context_key": source.context_key,
            "content_address": source.content_address,
        }
        for source in fixture.sources
    )
    summary = {
        "row_count": len(rows),
        "positive_count": len(fixture.positive_records),
        "control_count": len(fixture.control_records),
        "release_count": sum(row.decision == "release" for row in rows),
        "review_count": sum(row.decision != "release" for row in rows),
        "issue_row_count": sum(bool(row.issue_codes) for row in rows),
        "operation_counts": {
            operation: sum(row.operation == operation for row in rows)
            for operation in sorted({row.operation for row in rows})
        },
        "state_counts": {
            state: sum(row.state == state for row in rows)
            for state in sorted({row.state for row in rows})
        },
    }
    return ChromatinAlphaFrontierReviewView(
        fixture_id=fixture.fixture_id,
        rows=rows,
        source_matrix=source_matrix,
        summary=summary,
        release_state="ready" if release.accepted else "held",
        accepted=all(row.content_address.startswith("sha256:") for row in rows),
    )


def filter_chromatin_alpha_frontier_review_queue(
    view: ChromatinAlphaFrontierReviewView,
    *,
    states: tuple[str, ...] = (),
) -> tuple[ChromatinAlphaFrontierReviewRow, ...]:
    return tuple(
        row
        for row in view.rows
        if row.decision != "release" and (not states or row.state in states)
    )


def chromatin_alpha_frontier_review_summary(
    view: ChromatinAlphaFrontierReviewView,
) -> dict[str, Any]:
    return view.summary | {"content_address": view.content_address}


__all__ = [
    "ChromatinAlphaFrontierReviewRow",
    "ChromatinAlphaFrontierReviewView",
    "build_chromatin_alpha_frontier_view",
    "chromatin_alpha_frontier_review_summary",
    "filter_chromatin_alpha_frontier_review_queue",
]
