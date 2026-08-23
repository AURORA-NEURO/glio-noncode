"""Publication policy for signed research dossier receipts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .evidence_release_frontier_support import normalized_issue_codes
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleasePublicationDecision:
    dossier_id: str
    allowed: bool
    reasons: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_evidence_release_publication_policy(dossier: Mapping[str, Any], *, verified: bool, release_accepted: bool) -> EvidenceReleasePublicationDecision:
    reasons = []
    dossier_id = str(dossier.get("dossier_id", ""))
    if not dossier_id:
        reasons.append("dossier_id_missing")
    if not verified:
        reasons.append("signature_unverified")
    if not release_accepted:
        reasons.append("release_gate_failed")
    if not dossier.get("audience"):
        reasons.append("audience_missing")
    normalized = normalized_issue_codes(reasons)
    body = {"dossier_id": dossier_id, "allowed": not normalized, "reasons": normalized}
    return EvidenceReleasePublicationDecision(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleasePublicationDecision", "evaluate_evidence_release_publication_policy"]
