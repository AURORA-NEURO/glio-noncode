"""Append-only audit events for platform-control runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierAuditEvent:
    event_id: str
    kind: str
    sequence: int
    payload_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierAuditLog:
    run_id: str
    events: tuple[PlatformFrontierAuditEvent, ...]
    contiguous: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_audit_log(run_id: str, event_rows: tuple[dict[str, Any], ...]) -> PlatformFrontierAuditLog:
    events = []
    for sequence, row in enumerate(event_rows, start=1):
        body = {"event_id": str(row["event_id"]), "kind": str(row["kind"]), "sequence": sequence, "payload_address": str(row["payload_address"])}
        events.append(PlatformFrontierAuditEvent(**body, content_address=content_hash(body)))
    contiguous = tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1))
    return PlatformFrontierAuditLog(run_id, tuple(events), contiguous, contiguous and len({item.event_id for item in events}) == len(events), content_hash(tuple(events)))


def append_platform_frontier_audit_event(log: PlatformFrontierAuditLog, event_id: str, kind: str, payload: Any) -> PlatformFrontierAuditLog:
    row = {"event_id": event_id, "kind": kind, "payload_address": content_hash(payload)}
    return build_platform_frontier_audit_log(log.run_id, tuple(item.to_dict() for item in log.events) + (row,))


def verify_platform_frontier_audit_log(log: PlatformFrontierAuditLog) -> tuple[str, ...]:
    issues = []
    if not log.contiguous:
        issues.append("non_contiguous")
    if len({item.event_id for item in log.events}) != len(log.events):
        issues.append("duplicate_event_id")
    return tuple(issues)


__all__ = ["PlatformFrontierAuditEvent", "PlatformFrontierAuditLog", "append_platform_frontier_audit_event", "build_platform_frontier_audit_log", "verify_platform_frontier_audit_log"]
