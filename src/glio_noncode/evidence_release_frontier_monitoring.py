"""Monitoring projection for gate health and non-terminal row counts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseMonitoringSnapshot:
    evaluated_rows: int
    held_rows: int
    blocked_rows: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_monitoring_snapshot(evaluation: Any) -> EvidenceReleaseMonitoringSnapshot:
    held = sum(item.observed_state.value == "review" for item in evaluation.executions)
    blocked = sum(item.observed_state.value == "blocked" for item in evaluation.executions)
    body = {"evaluated_rows": len(evaluation.executions), "held_rows": held, "blocked_rows": blocked, "accepted": evaluation.accepted}
    return EvidenceReleaseMonitoringSnapshot(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseMonitoringSnapshot", "build_evidence_release_monitoring_snapshot"]
