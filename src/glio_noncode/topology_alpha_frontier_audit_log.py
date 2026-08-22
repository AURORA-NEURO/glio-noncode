"""Append-only audit log representation for one alpha execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_pipeline import TopologyAlphaFrontierPipelineReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierAuditEvent:
    sequence: int
    event_id: str
    run_id: str
    event_kind: str
    subject_id: str
    state: str
    detail: str
    previous_address: str
    event_address: str
    observed_at: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierAuditLog:
    run_id: str
    events: tuple[TopologyAlphaFrontierAuditEvent, ...]
    closed: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_kind(self, event_kind: str) -> tuple[TopologyAlphaFrontierAuditEvent, ...]:
        return tuple(item for item in self.events if item.event_kind == event_kind)

    def tail(self) -> TopologyAlphaFrontierAuditEvent:
        if not self.events:
            raise LookupError("audit log is empty")
        return self.events[-1]

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "events": [item.to_dict() for item in self.events], "closed": self.closed, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_audit_log(pipeline: TopologyAlphaFrontierPipelineReport) -> TopologyAlphaFrontierAuditLog:
    now = datetime.now(UTC).isoformat()
    previous = pipeline.fixture.content_address
    events = []
    for index, stage in enumerate(pipeline.stages, start=1):
        address = content_hash({"run_id": pipeline.run_id, "sequence": index, "stage_id": stage.stage_id, "status": stage.status, "previous": previous})
        events.append(TopologyAlphaFrontierAuditEvent(index, f"audit-{index:02d}", pipeline.run_id, "stage", stage.stage_id, stage.status, stage.detail, previous, address, now))
        previous = address
    accepted = len(events) == 12 and tuple(item.sequence for item in events) == tuple(range(1, 13)) and all(item.event_address.startswith("sha256:") for item in events)
    return TopologyAlphaFrontierAuditLog(pipeline.run_id, tuple(events), True, accepted)


__all__ = ["TopologyAlphaFrontierAuditEvent", "TopologyAlphaFrontierAuditLog", "build_topology_alpha_frontier_audit_log"]
