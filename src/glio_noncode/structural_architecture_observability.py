"""Sanitized stage events for local operation and release monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash
from .structural_architecture_contracts import StructuralArchitectureRuntime, addressed


@dataclass(frozen=True, slots=True)
class StructuralArchitectureEvent:
    sequence: int
    event_type: str
    stage_id: str
    state: str
    detail: str
    input_address: str
    output_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "stage_id": self.stage_id,
            "state": self.state,
            "detail": self.detail,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class StructuralArchitectureObservabilityReport:
    run_id: str
    events: tuple[StructuralArchitectureEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "events": [item.to_dict() for item in self.events],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def observe_structural_architecture(
    runtime: StructuralArchitectureRuntime,
) -> StructuralArchitectureObservabilityReport:
    events: list[StructuralArchitectureEvent] = []
    for sequence, stage in enumerate(runtime.stages, 1):
        body = {
            "sequence": sequence,
            "event_type": "stage_receipt",
            "stage_id": stage.stage_id,
            "state": stage.state.value,
            "detail": stage.detail,
            "input_address": stage.input_address,
            "output_address": stage.output_address,
        }
        events.append(StructuralArchitectureEvent(**body, content_address=content_hash(body)))
    accepted = len(events) == len(runtime.stages) and all(
        item.output_address.startswith("sha256:") for item in events
    )
    body = {"run_id": runtime.run_id, "events": events, "accepted": accepted}
    return StructuralArchitectureObservabilityReport(
        run_id=runtime.run_id,
        events=tuple(events),
        accepted=accepted,
        content_address=addressed(body, "structural-observability"),
    )


__all__ = [
    "StructuralArchitectureEvent",
    "StructuralArchitectureObservabilityReport",
    "observe_structural_architecture",
]
