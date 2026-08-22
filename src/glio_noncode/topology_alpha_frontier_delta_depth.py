"""Positive-control state transitions for each alpha operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierDeltaObservation:
    operation: str
    positive_state: str
    control_states: tuple[str, ...]
    positive_measurement_keys: tuple[str, ...]
    control_measurement_key_counts: tuple[int, ...]
    state_transition_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierDeltaDepthReport:
    observations: tuple[TopologyAlphaFrontierDeltaObservation, ...]
    mean_transition_count: float
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> TopologyAlphaFrontierDeltaObservation:
        for item in self.observations:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"observations": [item.to_dict() for item in self.observations], "mean_transition_count": self.mean_transition_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_topology_alpha_frontier_deltas(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierDeltaDepthReport:
    values = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = evaluation.by_operation(operation)
        positive = next(item for item in rows if item.role == "positive")
        controls = tuple(item for item in rows if item.role == "control")
        values.append(TopologyAlphaFrontierDeltaObservation(operation, positive.observed_state, tuple(item.observed_state for item in controls), tuple(sorted(positive.adapter.measurements)), tuple(len(item.adapter.measurements) for item in controls), sum(item.observed_state != positive.observed_state for item in controls), "positive and control outputs remain separate"))
    values = tuple(values)
    return TopologyAlphaFrontierDeltaDepthReport(values, sum(item.state_transition_count for item in values) / len(values), bool(values) and all(item.state_transition_count >= 2 for item in values))


__all__ = ["TopologyAlphaFrontierDeltaDepthReport", "TopologyAlphaFrontierDeltaObservation", "audit_topology_alpha_frontier_deltas"]
