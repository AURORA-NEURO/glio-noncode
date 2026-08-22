"""Review rows for cohort convergence artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_fixture_eval import CohortFrontierEvaluation
from .cohort_frontier_metrics import CohortFrontierMetricsReport
from .cohort_frontier_policy import CohortFrontierPolicyDecision
from .cohort_frontier_public_data import CohortFrontierFixture
from .cohort_frontier_release import CohortFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFrontierReviewRow:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    accepted: bool
    source_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierReviewView:
    fixture_id: str
    rows: tuple[CohortFrontierReviewRow, ...]
    metric_values: tuple[tuple[str, float], ...]
    policy_values: tuple[tuple[str, str], ...]
    release_state: str
    content_address: str

    def accepted_rows(self) -> tuple[CohortFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.accepted)

    def issue_rows(self) -> tuple[CohortFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted_row_count": len(self.accepted_rows()), "issue_row_count": len(self.issue_rows())}


def build_cohort_frontier_review_view(fixture: CohortFrontierFixture, evaluation: CohortFrontierEvaluation, metrics: CohortFrontierMetricsReport, policies: tuple[CohortFrontierPolicyDecision, ...], release: CohortFrontierReleaseManifest) -> CohortFrontierReviewView:
    rows = tuple(CohortFrontierReviewRow(record.record_id, record.operation.value, record.role.value, execution.state, execution.issue_codes, execution.accepted, len(record.source_ids), execution.content_address) for record, execution in zip(fixture.records, evaluation.executions, strict=True))
    body = {"fixture_id": fixture.fixture_id, "rows": rows, "metric_values": tuple((item.metric_id, item.value) for item in metrics.metrics), "policy_values": tuple((item.operation.value, item.decision.value) for item in policies), "release_state": release.state.value}
    return CohortFrontierReviewView(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierReviewRow", "CohortFrontierReviewView", "build_cohort_frontier_review_view"]
