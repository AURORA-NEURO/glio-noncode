"""Structured trace events for alpha replay records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierTraceEvent:
    event_id: str
    run_id: str
    record_id: str
    operation: str
    state: str
    issue_count: int
    evidence_count: int
    content_address: str
    observed_at: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierObservabilityReport:
    run_id: str
    events: tuple[TopologyAlphaFrontierTraceEvent, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[TopologyAlphaFrontierTraceEvent, ...]:
        return tuple(item for item in self.events if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "events": [item.to_dict() for item in self.events], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_trace(evaluation: TopologyAlphaFrontierEvaluation, run_id: str) -> TopologyAlphaFrontierObservabilityReport:
    now = datetime.now(UTC).isoformat()
    events = tuple(TopologyAlphaFrontierTraceEvent(f"event-{row.record_id}", run_id, row.record_id, row.operation, row.observed_state, len(row.observed_issue_codes), len(row.adapter.evidence_ids), row.adapter.content_address, now) for row in evaluation.rows)
    return TopologyAlphaFrontierObservabilityReport(run_id, events, len(events) == len(evaluation.rows) and all(item.event_id for item in events))


__all__ = ["TopologyAlphaFrontierObservabilityReport", "TopologyAlphaFrontierTraceEvent", "build_topology_alpha_frontier_trace"]
