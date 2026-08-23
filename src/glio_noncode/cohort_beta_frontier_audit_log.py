"""Append-only audit entries for the release rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .cohort_beta_frontier_runtime_types import CohortBetaFrontierRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAuditEntry:
    sequence: int
    event_type: str
    subject: str
    accepted: bool
    previous_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAuditLog:
    entries: tuple[CohortBetaFrontierAuditEntry, ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_audit_log(stages: Iterable[CohortBetaFrontierRuntimeStage]) -> CohortBetaFrontierAuditLog:
    entries = []
    previous = "root"
    for stage in stages:
        body = {"sequence": stage.ordinal, "event_type": stage.stage_id, "subject": stage.output_address, "accepted": stage.accepted, "previous_address": previous}
        entry = CohortBetaFrontierAuditEntry(stage.ordinal, stage.stage_id, stage.output_address, stage.accepted, previous, content_hash(body, prefix="audit-entry"))
        entries.append(entry)
        previous = entry.content_address
    values = tuple(entries)
    return CohortBetaFrontierAuditLog(values, bool(values) and tuple(item.sequence for item in values) == tuple(range(1, len(values) + 1)), content_hash(values, prefix="audit-log"))


__all__ = ["CohortBetaFrontierAuditEntry", "CohortBetaFrontierAuditLog", "build_cohort_beta_frontier_audit_log"]
