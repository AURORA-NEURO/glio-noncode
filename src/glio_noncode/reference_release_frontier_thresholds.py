"""Explicit quantitative floors for the reference release frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_lineage import ReferenceReleaseLineageGraph
from .reference_release_frontier_metrics import ReferenceReleaseMetricsReport
from .reference_release_frontier_public_data import ReferenceReleaseFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseThreshold:
    """One named floor or ceiling."""

    threshold_id: str
    metric: str
    operator: str
    target: float
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseThresholdResult:
    """Measured threshold result."""

    threshold_id: str
    observed: float
    target: float
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseThresholdReport:
    """Threshold configuration and measured results."""

    thresholds: tuple[ReferenceReleaseThreshold, ...]
    results: tuple[ReferenceReleaseThresholdResult, ...]
    accepted: bool
    content_address: str

    @property
    def failed_threshold_ids(self) -> tuple[str, ...]:
        return tuple(item.threshold_id for item in self.results if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_threshold_ids": list(self.failed_threshold_ids)}


def _threshold(
    index: int, metric: str, operator: str, target: float, rationale: str
) -> ReferenceReleaseThreshold:
    body = {
        "threshold_id": f"release-threshold-{index:02d}",
        "metric": metric,
        "operator": operator,
        "target": target,
        "rationale": rationale,
    }
    return ReferenceReleaseThreshold(**body, content_address=content_hash(body, prefix="threshold"))


def default_reference_release_thresholds() -> tuple[ReferenceReleaseThreshold, ...]:
    """Return release floors tied to fixture, lineage, and output boundaries."""

    return (
        _threshold(1, "source_count", ">=", 5, "five public source receipts are required"),
        _threshold(2, "record_count", "=", 16, "all four operations have four records"),
        _threshold(3, "positive_count", "=", 4, "one positive path per operation"),
        _threshold(4, "control_count", "=", 12, "three controls per operation"),
        _threshold(5, "check_count", ">=", 48, "three execution checks per record"),
        _threshold(6, "operation_count", "=", 4, "all C13-C16 operations are covered"),
        _threshold(7, "lineage_nodes", ">=", 100, "lineage retains source and receipt depth"),
        _threshold(8, "lineage_edges", ">=", 100, "lineage retains relation depth"),
        _threshold(9, "sanitized", "=", 1, "outputs exclude raw rows"),
        _threshold(10, "accepted", "=", 1, "evaluation must pass before release"),
        _threshold(11, "addressed_executions", "=", 16, "every execution is content addressed"),
        _threshold(12, "issue_vocabulary", ">=", 1, "controls retain at least one declared issue"),
    )


def build_reference_release_threshold_report(
    fixture: ReferenceReleaseFixture,
    evaluation: ReferenceReleaseEvaluation,
    metrics: ReferenceReleaseMetricsReport,
    lineage: ReferenceReleaseLineageGraph,
) -> ReferenceReleaseThresholdReport:
    """Measure all declared thresholds against current reports."""

    threshold_map = {item.metric: item for item in default_reference_release_thresholds()}
    observed = {
        "source_count": float(len(fixture.sources)),
        "record_count": float(len(fixture.records)),
        "positive_count": float(evaluation.positive_count),
        "control_count": float(evaluation.control_count),
        "check_count": float(len(evaluation.checks)),
        "operation_count": float(len({item.operation for item in evaluation.executions})),
        "lineage_nodes": float(len(lineage.nodes)),
        "lineage_edges": float(len(lineage.edges)),
        "sanitized": float(metrics.sanitized),
        "accepted": float(evaluation.accepted),
        "addressed_executions": float(
            sum(item.content_address.startswith("sha256:") for item in evaluation.executions)
        ),
        "issue_vocabulary": float(
            len({code for item in evaluation.executions for code in item.issue_codes})
        ),
    }
    results: list[ReferenceReleaseThresholdResult] = []
    for threshold in threshold_map.values():
        value = observed[threshold.metric]
        passed = (
            value >= threshold.target
            if threshold.operator == ">="
            else value <= threshold.target
            if threshold.operator == "<="
            else value == threshold.target
        )
        body = {
            "threshold_id": threshold.threshold_id,
            "observed": value,
            "target": threshold.target,
            "passed": passed,
            "detail": f"{threshold.metric} {threshold.operator} {threshold.target}",
        }
        results.append(
            ReferenceReleaseThresholdResult(
                **body, content_address=content_hash(body, prefix="threshold-result")
            )
        )
    results_tuple = tuple(results)
    body = {
        "thresholds": tuple(threshold_map.values()),
        "results": results_tuple,
        "accepted": all(item.passed for item in results_tuple),
    }
    return ReferenceReleaseThresholdReport(
        **body, content_address=content_hash(body, prefix="threshold-report")
    )


def verify_reference_release_thresholds(report: ReferenceReleaseThresholdReport) -> tuple[str, ...]:
    """Return threshold coverage and address failures."""

    failures: list[str] = []
    if len(report.thresholds) != 12 or len(report.results) != 12:
        failures.append("threshold-count")
    if {item.threshold_id for item in report.thresholds} != {
        item.threshold_id for item in report.results
    }:
        failures.append("threshold-coverage")
    if any(not item.content_address.startswith("threshold:") for item in report.thresholds):
        failures.append("threshold-address")
    if any(not item.content_address.startswith("threshold-result:") for item in report.results):
        failures.append("threshold-result-address")
    if not report.content_address.startswith("threshold-report:"):
        failures.append("threshold-report-address")
    return tuple(failures)


__all__ = [
    "ReferenceReleaseThreshold",
    "ReferenceReleaseThresholdReport",
    "ReferenceReleaseThresholdResult",
    "build_reference_release_threshold_report",
    "default_reference_release_thresholds",
    "verify_reference_release_thresholds",
]
