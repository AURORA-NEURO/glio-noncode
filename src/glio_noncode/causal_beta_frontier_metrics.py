"""Operation and state metrics for C05-C08 replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture, CausalBetaFrontierOperation, default_causal_beta_frontier_fixture
from .causal_beta_frontier_support import issue_counts, state_counts
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierOperationMetric:
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
class CausalBetaFrontierMetrics:
    record_count: int
    positive_count: int
    control_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    operations: tuple[CausalBetaFrontierOperationMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def state_accuracy(self) -> float:
        return round(sum(item.state_matches for item in self.operations) / self.record_count, 9) if self.record_count else 0.0

    @property
    def issue_accuracy(self) -> float:
        return round(sum(item.issue_matches for item in self.operations) / self.record_count, 9) if self.record_count else 0.0

    def for_operation(self, operation: str) -> CausalBetaFrontierOperationMetric:
        return next(item for item in self.operations if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_count": self.record_count, "positive_count": self.positive_count, "control_count": self.control_count, "state_counts": self.state_counts, "issue_counts": self.issue_counts, "operations": [item.to_dict() for item in self.operations], "state_accuracy": self.state_accuracy, "issue_accuracy": self.issue_accuracy, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_metrics(evaluation: CausalBetaFrontierEvaluation, fixture: CausalBetaFrontierFixture | None = None) -> CausalBetaFrontierMetrics:
    value = fixture or default_causal_beta_frontier_fixture()
    operations = tuple(CausalBetaFrontierOperationMetric(operation.value, len(rows := evaluation.by_operation(operation.value)), sum(item.role == "positive" for item in rows), sum(item.role == "control" for item in rows), sum(item.state_match for item in rows), sum(item.issue_match for item in rows), bool(rows) and all(item.state_match and item.issue_match for item in rows)) for operation in CausalBetaFrontierOperation)
    return CausalBetaFrontierMetrics(len(evaluation.rows), len(value.positive_records), len(value.control_records), state_counts(evaluation), issue_counts(evaluation), operations, evaluation.accepted)


__all__ = ["CausalBetaFrontierMetrics", "CausalBetaFrontierOperationMetric", "build_causal_beta_frontier_metrics"]
