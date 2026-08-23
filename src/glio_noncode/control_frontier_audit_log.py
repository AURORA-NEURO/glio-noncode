"""Hash-linked stage audit log for control frontier runtime runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ControlFrontierAuditEvent:
    sequence: int
    event_type: str
    subject: str
    state: str
    previous_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierAuditLog:
    run_id: str
    events: tuple[ControlFrontierAuditEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"head_address": self.events[-1].content_address if self.events else "sha256:genesis"}


def append_control_frontier_audit_event(events: Iterable[ControlFrontierAuditEvent], *, event_type: str, subject: str, state: str) -> ControlFrontierAuditEvent:
    prior = tuple(events)
    body = {"sequence": len(prior) + 1, "event_type": event_type, "subject": subject, "state": state, "previous_address": prior[-1].content_address if prior else "sha256:genesis"}
    return ControlFrontierAuditEvent(**body, content_address=content_hash(body))


def verify_control_frontier_audit_log(events: Iterable[ControlFrontierAuditEvent]) -> tuple[bool, tuple[str, ...]]:
    rows = tuple(events)
    issues = []
    for index, event in enumerate(rows, start=1):
        previous = rows[index - 2].content_address if index > 1 else "sha256:genesis"
        body = {"sequence": event.sequence, "event_type": event.event_type, "subject": event.subject, "state": event.state, "previous_address": event.previous_address}
        if event.sequence != index:
            issues.append(f"sequence:{index}")
        if event.previous_address != previous:
            issues.append(f"predecessor:{index}")
        if event.content_address != content_hash(body):
            issues.append(f"address:{index}")
    return not issues, tuple(issues)


def build_control_frontier_audit_log(run_id: str, stages: Iterable[Any]) -> ControlFrontierAuditLog:
    require_non_empty(run_id, "run_id")
    events: list[ControlFrontierAuditEvent] = []
    for stage in stages:
        events.append(append_control_frontier_audit_event(events, event_type="stage-completed", subject=str(stage.stage_id), state=str(stage.state)))
    accepted, _ = verify_control_frontier_audit_log(events)
    body = {"run_id": run_id, "events": tuple(events), "accepted": accepted}
    return ControlFrontierAuditLog(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierAuditEvent", "ControlFrontierAuditLog", "append_control_frontier_audit_event", "build_control_frontier_audit_log", "verify_control_frontier_audit_log"]
