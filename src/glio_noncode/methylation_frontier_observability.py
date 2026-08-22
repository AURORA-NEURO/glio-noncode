"""Structured events for methylation runtime inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_runtime import MethylationFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierEvent:
    sequence: int
    event_type: str
    stage_id: str | None
    record_id: str | None
    state: str
    severity: str
    address: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.sequence < 1 or not self.event_type or not self.state or not self.severity:
            raise ValidationError("event identity is invalid")
        if not self.address or not self.detail:
            raise ValidationError("event address and detail are required")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierObservabilityReport:
    run_id: str
    events: tuple[MethylationFrontierEvent, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.run_id or not self.events:
            raise ValidationError("observability requires run and events")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def events_for(self, event_type: str) -> tuple[MethylationFrontierEvent, ...]:
        return tuple(event for event in self.events if event.event_type == event_type)

    def by_severity(self, severity: str) -> tuple[MethylationFrontierEvent, ...]:
        return tuple(event for event in self.events if event.severity == severity)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "event_count": len(self.events),
            "error_count": len(self.by_severity("error")),
            "warning_count": len(self.by_severity("warning")),
        }


def _event(
    sequence: int,
    event_type: str,
    stage_id: str | None,
    record_id: str | None,
    state: str,
    severity: str,
    address: str,
    detail: str,
) -> MethylationFrontierEvent:
    return MethylationFrontierEvent(
        sequence=sequence,
        event_type=event_type,
        stage_id=stage_id,
        record_id=record_id,
        state=state,
        severity=severity,
        address=address,
        detail=detail,
    )


def observe_methylation_frontier(
    runtime: MethylationFrontierRuntimeReport,
) -> MethylationFrontierObservabilityReport:
    """Emit one completion event per stage and one event per evaluated row."""

    events: list[MethylationFrontierEvent] = []
    sequence = 1
    for stage in runtime.stages:
        events.append(
            _event(
                sequence,
                "stage_completed",
                stage.stage_id,
                None,
                stage.status,
                "info" if stage.status == "passed" else "error",
                stage.content_address,
                stage.detail,
            )
        )
        sequence += 1
    for item in runtime.evaluation.records:
        severity = "info" if item.accepted and not item.observed_issue_codes else "warning"
        events.append(
            _event(
                sequence,
                "record_evaluated",
                None,
                item.record_id,
                item.observed_state.value,
                severity,
                item.adapter.content_address,
                "expected path matched" if item.accepted else "expected and observed paths differ",
            )
        )
        sequence += 1
    body = {"run_id": runtime.run_id, "events": tuple(events)}
    return MethylationFrontierObservabilityReport(
        **body,
        accepted=all(event.content_address.startswith("sha256:") for event in events),
    )


__all__ = [
    "MethylationFrontierEvent",
    "MethylationFrontierObservabilityReport",
    "observe_methylation_frontier",
]
