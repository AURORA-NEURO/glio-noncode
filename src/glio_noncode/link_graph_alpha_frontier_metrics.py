"""Reproducible state, control, and operation metrics for link paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture, LinkGraphAlphaFrontierOperation
from .link_graph_alpha_frontier_support import expected_state_counts, issue_counts, operation_counts, result_state_counts
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierOperationMetric:
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    state_match_count: int
    issue_match_count: int
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierMetrics:
    record_count: int
    positive_count: int
    control_count: int
    state_counts: dict[str, int]
    expected_state_counts: dict[str, int]
    issue_counts: dict[str, int]
    operations: tuple[LinkGraphAlphaFrontierOperationMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def state_accuracy(self) -> float:
        return sum(item.state_match_count for item in self.operations) / self.record_count if self.record_count else 0.0

    @property
    def issue_accuracy(self) -> float:
        return sum(item.issue_match_count for item in self.operations) / self.record_count if self.record_count else 0.0

    def for_operation(self, operation: str) -> LinkGraphAlphaFrontierOperationMetric:
        for item in self.operations:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_count": self.record_count, "positive_count": self.positive_count, "control_count": self.control_count, "state_counts": self.state_counts, "expected_state_counts": self.expected_state_counts, "issue_counts": self.issue_counts, "operations": [item.to_dict() for item in self.operations], "state_accuracy": self.state_accuracy, "issue_accuracy": self.issue_accuracy, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_metrics(evaluation: LinkGraphAlphaFrontierEvaluation, fixture: LinkGraphAlphaFrontierFixture | None = None) -> LinkGraphAlphaFrontierMetrics:
    values = fixture
    operations = []
    for operation in LinkGraphAlphaFrontierOperation:
        rows = evaluation.by_operation(operation.value)
        operations.append(LinkGraphAlphaFrontierOperationMetric(operation.value, len(rows), sum(row.role == "positive" for row in rows), sum(row.role == "control" for row in rows), sum(row.state_match for row in rows), sum(row.issue_match for row in rows), all(row.state_match and row.issue_match for row in rows)))
    record_count = len(evaluation.rows)
    positive_count = len(evaluation.positives())
    control_count = len(evaluation.controls())
    return LinkGraphAlphaFrontierMetrics(record_count, positive_count, control_count, result_state_counts(evaluation), expected_state_counts(values) if values else {}, issue_counts(evaluation), tuple(operations), evaluation.accepted)


__all__ = ["LinkGraphAlphaFrontierMetrics", "LinkGraphAlphaFrontierOperationMetric", "build_link_graph_alpha_frontier_metrics"]
