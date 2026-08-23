"""Structured trace projection for coordination stages and event addresses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coordination_architecture_contracts import CoordinationRuntime, addressed


@dataclass(frozen=True, slots=True)
class CoordinationTraceEvent:
    ordinal: int
    stage_id: str
    state: str
    input_address: str
    output_address: str
    event_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "stage_id": self.stage_id,
            "state": self.state,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "event_address": self.event_address,
        }


@dataclass(frozen=True, slots=True)
class CoordinationTrace:
    trace_id: str
    events: tuple[CoordinationTraceEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "events": tuple(item.to_dict() for item in self.events), "accepted": self.accepted, "content_address": self.content_address}


def build_coordination_trace(runtime: CoordinationRuntime) -> CoordinationTrace:
    events = []
    for stage in runtime.stages:
        body = {
            "ordinal": stage.ordinal,
            "stage_id": stage.stage_id,
            "state": stage.state.value,
            "input_address": stage.input_address,
            "output_address": stage.output_address,
        }
        events.append(CoordinationTraceEvent(**body, event_address=addressed(body, "coordination-trace-event")))
    body = {"trace_id": f"{runtime.run_id}:trace", "events": tuple(events), "accepted": all(item.state == "accepted" for item in events)}
    return CoordinationTrace(**body, content_address=addressed(body, "coordination-trace"))


def verify_coordination_trace(trace: CoordinationTrace) -> tuple[str, ...]:
    issues: list[str] = []
    if tuple(item.ordinal for item in trace.events) != tuple(range(1, len(trace.events) + 1)):
        issues.append("trace_ordinal_gap")
    if any(not item.input_address or not item.output_address for item in trace.events):
        issues.append("trace_address_missing")
    return tuple(sorted(set(issues)))


__all__ = ["CoordinationTraceEvent", "CoordinationTrace", "build_coordination_trace", "verify_coordination_trace"]
