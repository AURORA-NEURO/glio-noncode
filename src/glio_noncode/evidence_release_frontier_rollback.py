"""Rollback decision for a failed release gate."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseRollbackDecision:
    action: str
    reason: str
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def decide_evidence_release_rollback(accepted: bool, reason: str = "quality gate") -> EvidenceReleaseRollbackDecision:
    body = {"action": "retain-release" if accepted else "quarantine-release", "reason": reason, "accepted": bool(accepted)}
    return EvidenceReleaseRollbackDecision(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseRollbackDecision", "decide_evidence_release_rollback"]
