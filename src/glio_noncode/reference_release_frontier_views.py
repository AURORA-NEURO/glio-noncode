"""Review-oriented projections for release and control inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_policy import ReferenceReleasePolicyReport
from .reference_release_frontier_public_data import ReferenceReleaseFixture
from .reference_release_frontier_release import ReferenceReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseReviewRow:
    """One bounded row for human review and export."""

    row_id: str
    record_id: str
    operation: str
    role: str
    state: str
    accepted: bool
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    review_priority: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseReviewView:
    """Stable review table with explicit priority ordering."""

    fixture_id: str
    release_address: str
    rows: tuple[ReferenceReleaseReviewRow, ...]
    columns: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"row_count": len(self.rows)}


def _priority(state: str, issue_count: int) -> int:
    if state == "blocked":
        return 100 + issue_count
    if state == "review":
        return 80 + issue_count
    if state == "drift":
        return 60 + issue_count
    return 10


def build_reference_release_review_view(
    fixture: ReferenceReleaseFixture,
    evaluation: ReferenceReleaseEvaluation,
    policy: ReferenceReleasePolicyReport,
    manifest: ReferenceReleaseManifest,
) -> ReferenceReleaseReviewView:
    """Build rows in stable record order with policy-informed priorities."""

    policy_map = {item.record_id: item for item in policy.decisions}
    record_map = fixture.record_map()
    rows: list[ReferenceReleaseReviewRow] = []
    for execution in evaluation.executions:
        record = record_map[execution.record_id]
        decision = policy_map[execution.record_id]
        priority = _priority(execution.state, len(execution.issue_codes))
        if not decision.allowed:
            priority += 5
        body = {
            "row_id": f"review-row:{execution.record_id}",
            "record_id": execution.record_id,
            "operation": execution.operation.value,
            "role": execution.role.value,
            "state": execution.state,
            "accepted": execution.accepted,
            "issue_codes": execution.issue_codes,
            "source_ids": record.source_ids,
            "review_priority": priority,
        }
        rows.append(
            ReferenceReleaseReviewRow(
                **body, content_address=content_hash(body, prefix="review-row")
            )
        )
    columns = (
        "row_id",
        "record_id",
        "operation",
        "role",
        "state",
        "accepted",
        "issue_codes",
        "source_ids",
        "review_priority",
    )
    accepted = len(rows) == len(evaluation.executions) and all(
        row.row_id.startswith("review-row:") for row in rows
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "release_address": manifest.content_address,
        "rows": tuple(rows),
        "columns": columns,
        "accepted": accepted,
    }
    return ReferenceReleaseReviewView(
        **body, content_address=content_hash(body, prefix="review-view")
    )


def verify_reference_release_review_view(view: ReferenceReleaseReviewView) -> tuple[str, ...]:
    """Return table closure and priority ordering failures."""

    failures: list[str] = []
    if not view.accepted:
        failures.append("view-not-accepted")
    if len(view.rows) != 16:
        failures.append("row-count")
    if len(set(row.record_id for row in view.rows)) != len(view.rows):
        failures.append("row-duplicates")
    if any(
        not set(row.issue_codes)
        <= {
            "missing_source_uri",
            "missing_checksum",
            "missing_license",
            "checksum_unverified",
            "provenance_context_mismatch",
            "bundle_context_mismatch",
            "bundle_unavailable",
            "bundle_missing_reference_id",
            "release_check_failed",
        }
        for row in view.rows
    ):
        failures.append("issue-vocabulary")
    if any(row.review_priority < 0 for row in view.rows):
        failures.append("priority-range")
    if not view.content_address.startswith("review-view:"):
        failures.append("view-address")
    return tuple(failures)


__all__ = [
    "ReferenceReleaseReviewRow",
    "ReferenceReleaseReviewView",
    "build_reference_release_review_view",
    "verify_reference_release_review_view",
]
