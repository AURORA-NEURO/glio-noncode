"""Delta and direction retention checks for topology evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierDeltaObservation:
    record_id: str
    direction: str
    delta: float | None
    relative_delta: float | None
    missingness_retained: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierDeltaDepthReport:
    observations: tuple[TopologyContextFrontierDeltaObservation, ...]
    directions: tuple[str, ...]
    missing_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "observations": [item.to_dict() for item in self.observations],
            "directions": self.directions,
            "missing_count": self.missing_count,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_topology_context_frontier_deltas(
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierDeltaDepthReport:
    observations = tuple(
        TopologyContextFrontierDeltaObservation(
            item.record_id,
            str(item.adapter.measurements.get("direction", "not-applicable")),
            item.adapter.measurements.get("delta"),
            item.adapter.measurements.get("relative_delta"),
            item.adapter.measurements.get("delta") is None
            or item.adapter.measurements.get("relative_delta") is None,
        )
        for item in evaluation.by_operation("insulation_delta")
    )
    directions = tuple(sorted({item.direction for item in observations}))
    missing_count = sum(item.missingness_retained for item in observations)
    return TopologyContextFrontierDeltaDepthReport(
        observations, directions, missing_count, "decrease" in directions and missing_count >= 1
    )


__all__ = [
    "TopologyContextFrontierDeltaDepthReport",
    "TopologyContextFrontierDeltaObservation",
    "audit_topology_context_frontier_deltas",
]
