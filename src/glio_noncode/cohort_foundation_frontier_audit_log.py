"""Append-only audit log for release and review transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFoundationAuditLogEntry:
    ordinal: int
    event_type: str
    subject_id: str
    previous_address: str
    current_address: str
    actor_role: str
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationAuditLog:
    log_id: str
    entries: tuple[CohortFoundationAuditLogEntry, ...]
    append_only: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_audit_log(subject_id: str, addresses: Iterable[str]) -> CohortFoundationAuditLog:
    values = tuple(addresses)
    entries = tuple(CohortFoundationAuditLogEntry(index, "state-observed", subject_id, values[index - 2] if index > 1 else "", address, "data-review", "deterministic runtime observation", content_hash((index, subject_id, address, values[index - 2] if index > 1 else ""))) for index, address in enumerate(values, start=1))
    body = {"log_id": "cohort-foundation-frontier-audit-log", "entries": entries}
    return CohortFoundationAuditLog(body["log_id"], entries, tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), content_hash(body))


__all__ = ["CohortFoundationAuditLog", "CohortFoundationAuditLogEntry", "build_cohort_foundation_frontier_audit_log"]
