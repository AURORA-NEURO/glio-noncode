"""Compact release summary for a reviewer or CI artifact."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseSummary:
    row_count: int
    state_counts: dict[str, int]
    release_id: str
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_summary(evaluation: Any, metrics: Any, release: Any) -> EvidenceReleaseSummary:
    body = {"row_count": metrics.row_count, "state_counts": metrics.state_counts, "release_id": release.release_id, "accepted": release.accepted and evaluation.accepted}
    return EvidenceReleaseSummary(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseSummary", "build_evidence_release_summary"]
