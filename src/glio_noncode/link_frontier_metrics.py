"""Operational metrics for Domain 10 link evidence."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .link_frontier_fixture_eval import LinkFrontierEvaluation
from .link_frontier_public_data import LinkFrontierFixture, LinkFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierMetrics:
    fixture_id: str
    record_count: int
    positive_count: int
    control_count: int
    execution_count: int
    passed_check_count: int
    failed_check_count: int
    state_counts: dict[str, int]
    operation_counts: dict[str, int]
    issue_counts: dict[str, int]
    positive_acceptance_rate: float
    control_rejection_rate: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def compute_link_frontier_metrics(
    fixture: LinkFrontierFixture,
    evaluation: LinkFrontierEvaluation,
) -> LinkFrontierMetrics:
    states = Counter(item.state for item in evaluation.executions)
    operations = Counter(item.operation.value for item in evaluation.executions)
    issues = Counter(code for item in evaluation.executions for code in item.issue_codes)
    positive_ids = {item.record_id for item in fixture.positive_records}
    control_ids = {item.record_id for item in fixture.control_records}
    accepted_ids = {item.record_id for item in evaluation.executions if item.accepted}
    positive_rate = len(positive_ids & accepted_ids) / max(1, len(positive_ids))
    rejected_controls = control_ids - accepted_ids
    body = {
        "fixture_id": fixture.fixture_id,
        "record_count": len(fixture.records),
        "positive_count": len(positive_ids),
        "control_count": len(control_ids),
        "execution_count": len(evaluation.executions),
        "passed_check_count": evaluation.passed_checks,
        "failed_check_count": len(evaluation.failed_check_ids),
        "state_counts": dict(sorted(states.items())),
        "operation_counts": dict(sorted(operations.items())),
        "issue_counts": dict(sorted(issues.items())),
        "positive_acceptance_rate": round(positive_rate, 6),
        "control_rejection_rate": round(len(rejected_controls) / max(1, len(control_ids)), 6),
    }
    return LinkFrontierMetrics(**body, content_address=content_hash(body))


def link_frontier_metric_checks(metrics: LinkFrontierMetrics) -> tuple[tuple[str, bool, Any], ...]:
    return (
        ("records", metrics.record_count == 16, metrics.record_count),
        ("positives", metrics.positive_count == 4, metrics.positive_count),
        ("controls", metrics.control_count == 12, metrics.control_count),
        ("executions", metrics.execution_count == metrics.record_count, metrics.execution_count),
        ("positive_rate", metrics.positive_acceptance_rate == 1.0, metrics.positive_acceptance_rate),
        ("control_rate", metrics.control_rejection_rate == 1.0, metrics.control_rejection_rate),
        ("operations", set(metrics.operation_counts) == {item.value for item in LinkFrontierOperation}, metrics.operation_counts),
    )


__all__ = ["LinkFrontierMetrics", "compute_link_frontier_metrics", "link_frontier_metric_checks"]
