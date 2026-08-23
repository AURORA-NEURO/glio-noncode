"""Append-only ordered stage audit log."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationReleaseAuditEvent:
    sequence: int
    stage_id: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseAuditLog:
    events: tuple[ValidationReleaseAuditEvent, ...]
    contiguous: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_audit_log(stage_ids: tuple[str, ...]) -> ValidationReleaseAuditLog:
    events = []
    for sequence, stage_id in enumerate(stage_ids, start=1):
        body = {"sequence": sequence, "stage_id": stage_id}
        events.append(ValidationReleaseAuditEvent(**body, content_address=content_hash(body)))
    return ValidationReleaseAuditLog(tuple(events), tuple(item.sequence for item in events) == tuple(range(1, len(events) + 1)), content_hash(tuple(events)))


def append_validation_release_audit_event(log: ValidationReleaseAuditLog, stage_id: str) -> ValidationReleaseAuditLog:
    return build_validation_release_audit_log(tuple(item.stage_id for item in log.events) + (stage_id,))


def verify_validation_release_audit_log(log: ValidationReleaseAuditLog) -> tuple[str, ...]:
    errors = []
    if not log.contiguous:
        errors.append("non-contiguous")
    return tuple(errors)


__all__ = ["ValidationReleaseAuditEvent", "ValidationReleaseAuditLog", "append_validation_release_audit_event", "build_validation_release_audit_log", "verify_validation_release_audit_log"]
