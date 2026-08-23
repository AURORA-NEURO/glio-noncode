"""Append-only audit entries for C09-C12 release transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_runtime_types import CohortAlphaFrontierRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAuditEntry:
    sequence: int
    event: str
    stage_id: str
    accepted: bool
    previous_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAuditLog:
    entries: tuple[CohortAlphaFrontierAuditEntry, ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_audit_log(stages: tuple[CohortAlphaFrontierRuntimeStage, ...]) -> CohortAlphaFrontierAuditLog:
    previous = "root"
    entries = []
    for index, stage in enumerate(stages, 1):
        body = {"sequence": index, "event": "stage_completed", "stage": stage.stage_id, "accepted": stage.accepted, "previous": previous, "output": stage.output_address}
        address = content_hash(body, prefix="alpha-audit-entry")
        entries.append(CohortAlphaFrontierAuditEntry(index, "stage_completed", stage.stage_id, stage.accepted, previous, address))
        previous = address
    values = tuple(entries)
    return CohortAlphaFrontierAuditLog(values, bool(values) and tuple(item.sequence for item in values) == tuple(range(1, len(values) + 1)) and values[-1].content_address == previous, content_hash(values, prefix="alpha-audit-log"))


__all__ = ["CohortAlphaFrontierAuditEntry", "CohortAlphaFrontierAuditLog", "build_cohort_alpha_frontier_audit_log"]
