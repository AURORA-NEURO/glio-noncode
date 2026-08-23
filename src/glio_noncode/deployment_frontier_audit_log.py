"""Append-only audit log for deployment frontier stage events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierAuditEvent:
    sequence: int
    event_id: str
    event_type: str
    subject_id: str
    state: str
    detail: str
    previous_address: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierAuditLog:
    events: tuple[DeploymentFrontierAuditEvent, ...]
    contiguous: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_audit_log(stage_ids: tuple[str, ...], *, run_id: str = "deployment-frontier-run") -> DeploymentFrontierAuditLog:
    events = []
    previous = None
    for sequence, stage_id in enumerate(stage_ids, start=1):
        body = {"sequence": sequence, "event_id": f"{run_id}:{sequence:03d}", "event_type": "stage_completed", "subject_id": stage_id, "state": "completed", "detail": "stage receipt retained", "previous_address": previous}
        event = DeploymentFrontierAuditEvent(**body, content_address=deployment_address(body))
        events.append(event)
        previous = event.content_address
    return DeploymentFrontierAuditLog(tuple(events), tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1)), deployment_address(tuple(events)))


def append_deployment_frontier_audit_event(log: DeploymentFrontierAuditLog, stage_id: str) -> DeploymentFrontierAuditLog:
    return build_deployment_frontier_audit_log(tuple(item.subject_id for item in log.events) + (stage_id,))


def verify_deployment_frontier_audit_log(log: DeploymentFrontierAuditLog) -> tuple[str, ...]:
    return () if log.contiguous else ("sequence_gap",)


__all__ = ["DeploymentFrontierAuditEvent", "DeploymentFrontierAuditLog", "append_deployment_frontier_audit_event", "build_deployment_frontier_audit_log", "verify_deployment_frontier_audit_log"]
