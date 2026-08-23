"""Claim wording guard for lifecycle receipts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseClaimBoundary:
    prohibited_claims: tuple[str, ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def evaluate_evidence_release_claim_boundary(evaluation: Any) -> EvidenceReleaseClaimBoundary:
    prohibited = ("clinical efficacy", "individual diagnosis", "causal certainty")
    body = {"prohibited_claims": prohibited, "accepted": evaluation.accepted}
    return EvidenceReleaseClaimBoundary(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseClaimBoundary", "evaluate_evidence_release_claim_boundary"]
