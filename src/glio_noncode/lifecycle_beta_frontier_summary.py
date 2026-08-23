"""Compact summary projection for dashboards and release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_metrics import LifecycleBetaFrontierMetrics
from .lifecycle_beta_frontier_quality_gate import LifecycleBetaFrontierQualityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierSummary:
    fixture_id: str
    version: str
    operation_count: int
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    failed_check_count: int
    quality_accepted: bool
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_summary(fixture: LifecycleBetaFrontierFixture, evaluation: LifecycleBetaFrontierEvaluation, metrics: LifecycleBetaFrontierMetrics, quality: LifecycleBetaFrontierQualityReport) -> LifecycleBetaFrontierSummary:
    body = {"fixture_id": fixture.fixture_id, "version": fixture.fixture_version, "operation_count": len(metrics.operation_metrics), "record_count": len(evaluation.executions), "positive_count": metrics.positive_count, "control_count": metrics.control_count, "accepted_count": metrics.accepted_count, "failed_check_count": len(evaluation.failed_check_ids), "quality_accepted": quality.accepted, "state_counts": metrics.state_counts, "issue_counts": metrics.issue_counts}
    return LifecycleBetaFrontierSummary(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierSummary", "build_lifecycle_beta_frontier_summary"]
