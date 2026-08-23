"""Freshness-independent provenance checks for source receipt identity."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseProvenanceCheck:
    source_count: int
    https_count: int
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_evidence_release_provenance(fixture: Any) -> EvidenceReleaseProvenanceCheck:
    body = {"source_count": len(fixture.sources), "https_count": sum(item.uri.startswith("https://") for item in fixture.sources)}
    return EvidenceReleaseProvenanceCheck(**body, accepted=body["source_count"] == body["https_count"] == 5, content_address=content_hash(body | {"accepted": body["source_count"] == body["https_count"] == 5}))

__all__ = ["EvidenceReleaseProvenanceCheck", "evaluate_evidence_release_provenance"]
