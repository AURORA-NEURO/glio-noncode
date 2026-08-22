"""State, control, and provenance metrics for Domain 14 lifecycle review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_fixture_eval import EvidenceLifecycleEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleMetric:
    metric_id: str
    value: float
    numerator: int
    denominator: int
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleMetricsReport:
    evaluation_address: str
    metrics: tuple[EvidenceLifecycleMetric, ...]
    content_address: str

    def by_id(self, metric_id: str) -> EvidenceLifecycleMetric:
        return next(item for item in self.metrics if item.metric_id == metric_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _metric(metric_id: str, numerator: int, denominator: int, detail: str) -> EvidenceLifecycleMetric:
    value = 0.0 if denominator == 0 else round(numerator / denominator, 6)
    body = {"metric_id": metric_id, "value": value, "numerator": numerator, "denominator": denominator, "detail": detail}
    return EvidenceLifecycleMetric(**body, content_address=content_hash(body))


def measure_evidence_lifecycle(evaluation: EvidenceLifecycleEvaluation) -> EvidenceLifecycleMetricsReport:
    total = len(evaluation.executions)
    positives = tuple(item for item in evaluation.executions if item.role.value == "positive")
    controls = tuple(item for item in evaluation.executions if item.role.value == "control")
    accepted = sum(item.accepted for item in positives)
    addressed = sum(item.content_address.startswith("sha256:") for item in evaluation.executions)
    issue_rows = sum(bool(item.issue_codes) for item in evaluation.executions)
    metrics = (
        _metric("positive_acceptance_rate", accepted, len(positives), "positive rows accepted"),
        _metric("control_rejection_rate", sum(not item.accepted for item in controls), len(controls), "controls remain non-publishable"),
        _metric("execution_acceptance_rate", sum(item.accepted for item in evaluation.executions), total, "all execution roles"),
        _metric("address_coverage", addressed, total, "execution addresses"),
        _metric("issue_row_rate", issue_rows, total, "rows retaining issue codes"),
        _metric("citation_positive_rate", sum(item.operation.value == "citation_resolution" and item.accepted for item in positives), 1, "citation positive path"),
        _metric("graph_positive_rate", sum(item.operation.value == "graph_construction" and item.accepted for item in positives), 1, "graph positive path"),
        _metric("edge_positive_rate", sum(item.operation.value == "edge_validation" and item.accepted for item in positives), 1, "edge positive path"),
        _metric("disagreement_positive_rate", sum(item.operation.value == "disagreement_tracking" and item.accepted for item in positives), 1, "disagreement positive path"),
        _metric("supported_state_rate", sum(item.state == "supported" for item in evaluation.executions), total, "supported observed states"),
        _metric("review_state_rate", sum(item.state not in {"supported", "clear"} for item in evaluation.executions), total, "states retaining review work"),
        _metric("issue_code_diversity", len({code for item in evaluation.executions for code in item.issue_codes}), 12, "declared issue vocabulary coverage"),
        _metric("check_pass_rate", evaluation.passed_checks, len(evaluation.checks), "evaluation check coverage"),
    )
    body = {"evaluation_address": evaluation.content_address, "metrics": metrics}
    return EvidenceLifecycleMetricsReport(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleMetric", "EvidenceLifecycleMetricsReport", "measure_evidence_lifecycle"]
