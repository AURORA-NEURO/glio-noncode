"""Hash-linked operational audit events for aggregate lifecycle runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierAuditEvent:
    """One append-only event linked to the preceding event address."""

    sequence: int
    event_type: str
    subject: str
    state: str
    previous_address: str
    content_address: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("audit sequence starts at one")
        for name in ("event_type", "subject", "state", "previous_address", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierAuditLog:
    """An ordered event log with a complete chain check."""

    run_id: str
    events: tuple[LifecycleBetaFrontierAuditEvent, ...]
    accepted: bool
    content_address: str

    @property
    def head_address(self) -> str:
        return self.events[-1].content_address if self.events else "sha256:empty"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"head_address": self.head_address}


def append_lifecycle_beta_frontier_audit_event(
    events: Iterable[LifecycleBetaFrontierAuditEvent],
    *,
    event_type: str,
    subject: str,
    state: str,
) -> LifecycleBetaFrontierAuditEvent:
    """Append one event while deriving its sequence and predecessor address."""

    prior = tuple(events)
    sequence = len(prior) + 1
    previous_address = prior[-1].content_address if prior else "sha256:genesis"
    body = {
        "sequence": sequence,
        "event_type": event_type,
        "subject": subject,
        "state": state,
        "previous_address": previous_address,
    }
    return LifecycleBetaFrontierAuditEvent(**body, content_address=content_hash(body))


def build_lifecycle_beta_frontier_audit_log(run_id: str, stages: Iterable[Any]) -> LifecycleBetaFrontierAuditLog:
    """Translate completed runtime stages into a verifiable event chain."""

    require_non_empty(run_id, "run_id")
    events: list[LifecycleBetaFrontierAuditEvent] = []
    for stage in stages:
        events.append(
            append_lifecycle_beta_frontier_audit_event(
                events,
                event_type="stage-completed",
                subject=str(stage.stage_id),
                state=str(stage.state),
            )
        )
    accepted, _ = verify_lifecycle_beta_frontier_audit_log(tuple(events))
    body = {"run_id": run_id, "events": tuple(events), "accepted": accepted}
    return LifecycleBetaFrontierAuditLog(**body, content_address=content_hash(body))


def verify_lifecycle_beta_frontier_audit_log(
    events: Iterable[LifecycleBetaFrontierAuditEvent],
) -> tuple[bool, tuple[str, ...]]:
    """Validate sequence, predecessor links, and event content addresses."""

    rows = tuple(events)
    issues: list[str] = []
    for index, event in enumerate(rows, start=1):
        expected_previous = rows[index - 2].content_address if index > 1 else "sha256:genesis"
        body = {
            "sequence": event.sequence,
            "event_type": event.event_type,
            "subject": event.subject,
            "state": event.state,
            "previous_address": event.previous_address,
        }
        if event.sequence != index:
            issues.append(f"sequence:{index}")
        if event.previous_address != expected_previous:
            issues.append(f"predecessor:{index}")
        if event.content_address != content_hash(body):
            issues.append(f"address:{index}")
    return (not issues, tuple(issues))


__all__ = [
    "LifecycleBetaFrontierAuditEvent",
    "LifecycleBetaFrontierAuditLog",
    "append_lifecycle_beta_frontier_audit_event",
    "build_lifecycle_beta_frontier_audit_log",
    "verify_lifecycle_beta_frontier_audit_log",
]
