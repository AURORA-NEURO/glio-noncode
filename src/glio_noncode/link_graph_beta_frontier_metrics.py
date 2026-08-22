"""Operation balance and replay metrics for the beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierOperation, default_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_support import issue_counts, state_counts
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierOperationMetric:
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    state_matches: int
    issue_matches: int
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierMetrics:
    record_count: int
    positive_count: int
    control_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    operations: tuple[LinkGraphBetaFrontierOperationMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def state_accuracy(self) -> float:
        return sum(item.state_matches for item in self.operations) / self.record_count if self.record_count else 0.0

    def for_operation(self, operation: str) -> LinkGraphBetaFrontierOperationMetric:
        return next(item for item in self.operations if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_count": self.record_count, "positive_count": self.positive_count, "control_count": self.control_count, "state_counts": self.state_counts, "issue_counts": self.issue_counts, "operations": [item.to_dict() for item in self.operations], "state_accuracy": self.state_accuracy, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_metrics(evaluation: LinkGraphBetaFrontierEvaluation, fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierMetrics:
    value = fixture or default_link_graph_beta_frontier_fixture()
    operations = tuple(LinkGraphBetaFrontierOperationMetric(operation.value, len(rows := evaluation.by_operation(operation.value)), sum(row.role == "positive" for row in rows), sum(row.role == "control" for row in rows), sum(row.state_match for row in rows), sum(row.issue_match for row in rows), all(row.state_match and row.issue_match for row in rows)) for operation in LinkGraphBetaFrontierOperation)
    return LinkGraphBetaFrontierMetrics(len(evaluation.rows), len(value.positive_records), len(value.control_records), state_counts(evaluation), issue_counts(evaluation), operations, evaluation.accepted)


__all__ = ["LinkGraphBetaFrontierMetrics", "LinkGraphBetaFrontierOperationMetric", "build_link_graph_beta_frontier_metrics"]
