"""Claim register that keeps lifecycle receipts distinct from claim strength."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseClaimRegister:
    claims: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_claim_register(claim_ids: Iterable[str], *, boundary: str = "lifecycle receipt") -> EvidenceReleaseClaimRegister:
    claims = tuple({"claim_id": str(claim_id), "lifecycle_state": "registered", "scientific_status": "not adjudicated", "boundary": boundary} for claim_id in claim_ids)
    body = {"claims": claims, "accepted": all(item["scientific_status"] == "not adjudicated" for item in claims)}
    return EvidenceReleaseClaimRegister(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseClaimRegister", "build_evidence_release_claim_register"]
