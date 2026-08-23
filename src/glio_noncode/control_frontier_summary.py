"""Compact summary projection for control frontier dashboards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierFixture
from .control_frontier_metrics import ControlFrontierMetrics
from .control_frontier_quality_gate import ControlFrontierQualityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierSummary:
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


def build_control_frontier_summary(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation, metrics: ControlFrontierMetrics, quality: ControlFrontierQualityReport) -> ControlFrontierSummary:
    body = {"fixture_id": fixture.fixture_id, "version": fixture.fixture_version, "operation_count": len(metrics.operation_metrics), "record_count": metrics.record_count, "positive_count": metrics.positive_count, "control_count": metrics.control_count, "accepted_count": metrics.accepted_count, "failed_check_count": len(evaluation.failed_check_ids), "quality_accepted": quality.accepted, "state_counts": metrics.state_counts, "issue_counts": metrics.issue_counts}
    return ControlFrontierSummary(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierSummary", "build_control_frontier_summary"]
