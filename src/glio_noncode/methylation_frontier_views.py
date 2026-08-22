"""Sanitized review views for methylation evidence consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_fixture_eval import MethylationFrontierEvaluation
from .methylation_frontier_policy import MethylationFrontierPolicyReport
from .methylation_frontier_public_data import MethylationFrontierFixture
from .methylation_frontier_release import MethylationFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierReviewRow:
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
    notes: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.row_id or not self.record_id or not self.operation:
            raise ValidationError("review row identity is required")
        if not self.context_key or not self.notes:
            raise ValidationError("review row context and notes are required")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierReviewView:
    fixture_id: str
    rows: tuple[MethylationFrontierReviewRow, ...]
    source_matrix: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    release_state: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.rows or not self.source_matrix:
            raise ValidationError("review view requires rows and source matrix")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def by_operation(self, operation: str) -> tuple[MethylationFrontierReviewRow, ...]:
        return tuple(row for row in self.rows if row.operation == operation)

    def by_state(self, state: str) -> tuple[MethylationFrontierReviewRow, ...]:
        return tuple(row for row in self.rows if row.state == state)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_methylation_frontier_review_view(
    fixture: MethylationFrontierFixture,
    evaluation: MethylationFrontierEvaluation,
    policy: MethylationFrontierPolicyReport,
    release: MethylationFrontierReleaseManifest,
) -> MethylationFrontierReviewView:
    """Build a review-safe table with evidence state and decision context."""

    decisions = {decision.record_id: decision for decision in policy.decisions}
    records = {record.record_id: record for record in fixture.records}
    rows = tuple(
        MethylationFrontierReviewRow(
            row_id=f"methylation-review-{index:03d}",
            record_id=item.record_id,
            operation=records[item.record_id].operation.value,
            role=item.role,
            state=item.observed_state.value,
            decision="release" if decisions[item.record_id].release_allowed else "review",
            expected_state=item.expected_state.value,
            state_match=item.state_match,
            issue_codes=item.observed_issue_codes,
            source_ids=records[item.record_id].source_ids,
            context_key=fixture.context_key,
            notes=decisions[item.record_id].reasons[0],
        )
        for index, item in enumerate(evaluation.records, start=1)
    )
    source_matrix = tuple(
        {
            "source_id": source.source_id,
            "uri": source.uri,
            "source_version": source.source_version,
            "checksum": source.checksum,
            "context_key": source.context_key,
            "public_aggregate": source.public_aggregate,
        }
        for source in fixture.sources
    )
    summary = {
        "row_count": len(rows),
        "positive_count": len(fixture.positive_records),
        "control_count": len(fixture.control_records),
        "release_count": sum(row.decision == "release" for row in rows),
        "review_count": sum(row.decision == "review" for row in rows),
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
    return MethylationFrontierReviewView(
        fixture_id=fixture.fixture_id,
        rows=rows,
        source_matrix=source_matrix,
        summary=summary,
        release_state="ready" if release.accepted else "held",
    )


__all__ = [
    "MethylationFrontierReviewRow",
    "MethylationFrontierReviewView",
    "build_methylation_frontier_review_view",
]
