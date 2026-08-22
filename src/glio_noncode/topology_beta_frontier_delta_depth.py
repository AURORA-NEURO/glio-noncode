"""State and signal delta summaries by operation."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierDeltaObservation:
    operation: str
    positive_state: str
    control_states: tuple[str, ...]
    positive_signal: float | None
    control_signals: tuple[float, ...]
    state_transition_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierDeltaDepthReport:
    observations: tuple[TopologyBetaFrontierDeltaObservation, ...]
    mean_transition_count: float
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> TopologyBetaFrontierDeltaObservation:
        for item in self.observations:
            if item.operation == operation:
                return item
        raise KeyError(operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"observations": [item.to_dict() for item in self.observations], "mean_transition_count": self.mean_transition_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _signal(row: Any) -> float | None:
    measurements = row.adapter.measurements
    for key in ("normalized_contact_score", "activity_by_contact_score", "median_signal", "contact_component"):
        value = measurements.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    signals = measurements.get("signals")
    return float(signals[0]) if signals else None


def audit_topology_beta_frontier_deltas(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierDeltaDepthReport:
    observations = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = evaluation.by_operation(operation)
        positive = next(item for item in rows if item.role == "positive")
        controls = tuple(item for item in rows if item.role == "control")
        transitions = sum(item.observed_state != positive.observed_state for item in controls)
        observations.append(TopologyBetaFrontierDeltaObservation(operation, positive.observed_state, tuple(item.observed_state for item in controls), _signal(positive), tuple(value for item in controls if (value := _signal(item)) is not None), transitions, "positive and control states remain separate"))
    values = tuple(observations)
    return TopologyBetaFrontierDeltaDepthReport(values, mean(item.state_transition_count for item in values), bool(values) and all(item.state_transition_count >= 2 for item in values))


__all__ = ["TopologyBetaFrontierDeltaDepthReport", "TopologyBetaFrontierDeltaObservation", "audit_topology_beta_frontier_deltas"]
