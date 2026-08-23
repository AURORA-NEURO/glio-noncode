"""Version and operation compatibility receipt."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .evidence_release_frontier_contracts import EvidenceReleaseOperation
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseCompatibility:
    version: str
    operation_count: int
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_evidence_release_compatibility() -> EvidenceReleaseCompatibility:
    body = {"version": "evidence-release-schema-v1", "operation_count": len(tuple(EvidenceReleaseOperation))}
    return EvidenceReleaseCompatibility(**body, accepted=body["operation_count"] == 4, content_address=content_hash(body | {"accepted": body["operation_count"] == 4}))

__all__ = ["EvidenceReleaseCompatibility", "evaluate_evidence_release_compatibility"]
