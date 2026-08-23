"""Combined assurance receipt for release gates and depth checks."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseAssuranceSummary:
    quality_accepted: bool
    depth_accepted: bool
    reconciliation_accepted: bool
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_assurance_summary(quality: Any, depth: Any, reconciliation: Any) -> EvidenceReleaseAssuranceSummary:
    body = {"quality_accepted": quality.accepted, "depth_accepted": depth.accepted, "reconciliation_accepted": reconciliation.accepted}
    return EvidenceReleaseAssuranceSummary(**body, accepted=all(body.values()), content_address=content_hash(body | {"accepted": all(body.values())}))

__all__ = ["EvidenceReleaseAssuranceSummary", "build_evidence_release_assurance_summary"]
