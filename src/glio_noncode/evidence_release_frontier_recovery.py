"""Recovery actions that never auto-promote a blocked lifecycle row."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseRecoveryPlan:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_recovery_plan(evaluation: Any) -> EvidenceReleaseRecoveryPlan:
    actions = {"blocked": "quarantine and correct context", "review": "obtain required receipt or reviewer", "rejected": "repair schema", "ready": "retain for review", "reclassified": "record transition", "superseded": "retain history", "bundled": "store bundle", "signed": "verify receipt"}
    rows = tuple({"record_id": item.record_id, "state": item.observed_state.value, "recovery_action": actions[item.observed_state.value]} for item in evaluation.executions)
    body = {"rows": rows, "accepted": all(item["recovery_action"] for item in rows)}
    return EvidenceReleaseRecoveryPlan(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseRecoveryPlan", "build_evidence_release_recovery_plan"]
