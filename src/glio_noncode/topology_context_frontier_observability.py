"""Compact trace events for topology context runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierTraceEvent:
    event_id: str
    record_id: str
    operation: str
    state: str
    duration_ms: int
    result_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierObservabilityReport:
    run_id: str
    events: tuple[TopologyContextFrontierTraceEvent, ...]
    counters: dict[str, int]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "run_id": self.run_id,
            "events": [item.to_dict() for item in self.events],
            "counters": self.counters,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_trace(
    evaluation: TopologyContextFrontierEvaluation,
    run_id: str = "topology-context-frontier",
) -> TopologyContextFrontierObservabilityReport:
    events = tuple(
        TopologyContextFrontierTraceEvent(
            f"event-{item.record_id}",
            item.record_id,
            item.operation,
            item.observed_state,
            1,
            item.adapter.content_address,
        )
        for item in evaluation.rows
    )
    counters = {
        "records": len(events),
        "supported": sum(item.state == "supported" for item in events),
        "review": sum(item.state != "supported" for item in events),
    }
    return TopologyContextFrontierObservabilityReport(run_id, events, counters, len(events) == 16)


__all__ = [
    "TopologyContextFrontierObservabilityReport",
    "TopologyContextFrontierTraceEvent",
    "build_topology_context_frontier_trace",
]
