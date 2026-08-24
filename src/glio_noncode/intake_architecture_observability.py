"""Sanitized runtime trace events for D01 operations and stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .intake_architecture_contracts import IntakeArchitectureRuntime, addressed


@dataclass(frozen=True, slots=True)
class IntakeArchitectureTraceEvent:
    event_id: str
    ordinal: int
    event_type: str
    stage_key: str
    state: str
    input_address: str
    output_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ordinal": self.ordinal,
            "event_type": self.event_type,
            "stage_key": self.stage_key,
            "state": self.state,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class IntakeArchitectureTrace:
    trace_id: str
    events: tuple[IntakeArchitectureTraceEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "events": [item.to_dict() for item in self.events],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def build_intake_architecture_trace(runtime: IntakeArchitectureRuntime) -> IntakeArchitectureTrace:
    events = []
    for ordinal, stage in enumerate(runtime.stages, start=1):
        body = {
            "event_id": f"intake-trace:{ordinal:03d}",
            "ordinal": ordinal,
            "event_type": "runtime_stage",
            "stage_key": stage.stage_id,
            "state": stage.state.value,
            "input_address": stage.input_address,
            "output_address": stage.output_address,
        }
        events.append(
            IntakeArchitectureTraceEvent(
                **body, content_address=addressed(body, "intake-trace-event")
            )
        )
    body = {
        "trace_id": "intake-trace-d02",
        "events": tuple(events),
        "accepted": len(events) == 24 and all(":" in item.output_address for item in events),
    }
    return IntakeArchitectureTrace(**body, content_address=addressed(body, "intake-trace"))


def audit_intake_architecture_trace(trace: IntakeArchitectureTrace) -> tuple[str, ...]:
    issues = []
    if tuple(item.ordinal for item in trace.events) != tuple(range(1, len(trace.events) + 1)):
        issues.append("trace_ordinal")
    if len({item.event_id for item in trace.events}) != len(trace.events):
        issues.append("trace_event_ids")
    if any(item.stage_key == "" for item in trace.events):
        issues.append("trace_stage_key")
    return tuple(sorted(set(issues)))


__all__ = [
    "IntakeArchitectureTraceEvent",
    "IntakeArchitectureTrace",
    "build_intake_architecture_trace",
    "audit_intake_architecture_trace",
]
