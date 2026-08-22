"""Pairwise comparison helpers for positive and control rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierComparison:
    operation: str
    positive_record_id: str
    control_record_id: str
    positive_state: str
    control_state: str
    state_changed: bool
    positive_issue_codes: tuple[str, ...]
    control_issue_codes: tuple[str, ...]
    measurement_keys: tuple[str, ...]
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierComparisonReport:
    comparisons: tuple[TopologyAlphaFrontierComparison, ...]
    operation_count: int
    changed_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[TopologyAlphaFrontierComparison, ...]:
        return tuple(item for item in self.comparisons if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"comparisons": [item.to_dict() for item in self.comparisons], "operation_count": self.operation_count, "changed_count": self.changed_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_comparisons(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierComparisonReport:
    comparisons = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = evaluation.by_operation(operation)
        positive = next(item for item in rows if item.role == "positive")
        for control in (item for item in rows if item.role == "control"):
            comparisons.append(TopologyAlphaFrontierComparison(operation, positive.record_id, control.record_id, positive.observed_state, control.observed_state, positive.observed_state != control.observed_state, positive.observed_issue_codes, control.observed_issue_codes, tuple(sorted(set(positive.adapter.measurements) | set(control.adapter.measurements))), "state and measurement differences remain descriptive; controls are not a causal comparator"))
    values = tuple(comparisons)
    return TopologyAlphaFrontierComparisonReport(values, len({item.operation for item in values}), sum(item.state_changed for item in values), len(values) == 12 and all(item.measurement_keys for item in values))


__all__ = ["TopologyAlphaFrontierComparison", "TopologyAlphaFrontierComparisonReport", "build_topology_alpha_frontier_comparisons"]
