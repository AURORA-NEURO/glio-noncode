"""Metrics that expose coverage, controls, and state distributions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture, CausalAlphaFrontierOperation
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierOperationMetric:
    operation: CausalAlphaFrontierOperation
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    state_counts: dict[str, int]
    issue_count: int
    coverage_fraction: float
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"operation": self.operation, "record_count": self.record_count, "positive_count": self.positive_count, "control_count": self.control_count, "accepted_count": self.accepted_count, "state_counts": dict(self.state_counts), "issue_count": self.issue_count, "coverage_fraction": self.coverage_fraction}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierMetrics:
    fixture_id: str
    total_records: int
    total_sources: int
    positive_records: int
    control_records: int
    foreign_records: int
    accepted_records: int
    operations: tuple[CausalAlphaFrontierOperationMetric, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def accepted_fraction(self) -> float:
        return round(self.accepted_records / max(1, self.total_records), 6)

    def operation(self, operation: CausalAlphaFrontierOperation | str) -> CausalAlphaFrontierOperationMetric:
        value = CausalAlphaFrontierOperation(str(operation))
        return next(item for item in self.operations if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "total_records": self.total_records, "total_sources": self.total_sources, "positive_records": self.positive_records, "control_records": self.control_records, "foreign_records": self.foreign_records, "accepted_records": self.accepted_records, "accepted_fraction": self.accepted_fraction, "operations": [item.to_dict() for item in self.operations], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_metrics(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation) -> CausalAlphaFrontierMetrics:
    metrics: list[CausalAlphaFrontierOperationMetric] = []
    for operation in CausalAlphaFrontierOperation:
        records = fixture.operation_records(operation)
        rows = evaluation.evaluation.for_operation(operation)
        state_counts: dict[str, int] = {}
        for row in rows:
            state_counts[row.observed_state.value] = state_counts.get(row.observed_state.value, 0) + 1
        metrics.append(CausalAlphaFrontierOperationMetric(operation, len(records), sum(item.role.value == "positive" for item in records), sum(item.role.value == "control" for item in records), sum(item.accepted for item in rows), dict(sorted(state_counts.items())), sum(len(item.observed_issue_codes) for item in rows), round(sum(item.accepted for item in rows) / max(1, len(rows)), 6)))
    accepted_records = sum(item.accepted for item in evaluation.evaluation.results)
    return CausalAlphaFrontierMetrics(fixture.fixture_id, len(fixture.records), len(fixture.sources), len(fixture.positive_records), len(fixture.control_records), sum(item.context_key == fixture.foreign_context_key for item in fixture.records), accepted_records, tuple(metrics), evaluation.accepted and all(item.record_count == 4 for item in metrics))


__all__ = ["CausalAlphaFrontierMetrics", "CausalAlphaFrontierOperationMetric", "build_causal_alpha_frontier_metrics"]
