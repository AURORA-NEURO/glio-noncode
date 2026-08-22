"""Stable read models for review tables and machine-readable summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_fixture_eval import CausalFrontierEvaluation
from .causal_frontier_metrics import CausalFrontierMetricsReport
from .causal_frontier_policy import CausalFrontierPolicyDecision
from .causal_frontier_public_data import CausalFrontierFixture
from .causal_frontier_release import CausalFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFrontierReviewRow:
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
class CausalFrontierReviewView:
    fixture_id: str
    rows: tuple[CausalFrontierReviewRow, ...]
    metric_values: tuple[tuple[str, float], ...]
    policy_values: tuple[tuple[str, str], ...]
    release_state: str
    content_address: str

    def accepted_rows(self) -> tuple[CausalFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.accepted)

    def issue_rows(self) -> tuple[CausalFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted_row_count": len(self.accepted_rows()), "issue_row_count": len(self.issue_rows())}


def build_causal_frontier_review_view(
    fixture: CausalFrontierFixture,
    evaluation: CausalFrontierEvaluation,
    metrics: CausalFrontierMetricsReport,
    policies: tuple[CausalFrontierPolicyDecision, ...],
    release: CausalFrontierReleaseManifest,
) -> CausalFrontierReviewView:
    rows = tuple(
        CausalFrontierReviewRow(
            record_id=record.record_id,
            operation=record.operation.value,
            role=record.role.value,
            state=execution.state,
            issue_codes=execution.issue_codes,
            accepted=execution.accepted,
            source_count=len(record.source_ids),
            content_address=execution.content_address,
        )
        for record, execution in zip(fixture.records, evaluation.executions, strict=True)
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "rows": rows,
        "metric_values": tuple((item.metric_id, item.value) for item in metrics.metrics),
        "policy_values": tuple((item.operation.value, item.decision.value) for item in policies),
        "release_state": release.state.value,
    }
    return CausalFrontierReviewView(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierReviewRow", "CausalFrontierReviewView", "build_causal_frontier_review_view"]
