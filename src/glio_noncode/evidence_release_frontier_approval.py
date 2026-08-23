"""Two-person approval receipt for high-impact release actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .evidence_release_frontier_attestation import EvidenceReleaseAttestation, attestations_are_independent
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseApproval:
    record_id: str
    attestations: tuple[EvidenceReleaseAttestation, ...]
    approved: bool
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_evidence_release_approval(record_id: str, attestations: tuple[EvidenceReleaseAttestation, ...], *, required_decision: str = "accept") -> EvidenceReleaseApproval:
    independent = attestations_are_independent(attestations)
    decisions_match = bool(attestations) and all(item.decision == required_decision for item in attestations)
    approved = independent and len(attestations) >= 2 and decisions_match
    reason = "two independent approvals" if approved else "two independent matching approvals required"
    body = {"record_id": record_id, "attestations": attestations, "approved": approved, "reason": reason}
    return EvidenceReleaseApproval(**body, content_address=content_hash(body))


def approval_payload(approval: EvidenceReleaseApproval) -> Mapping[str, Any]:
    return {"record_id": approval.record_id, "approved": approval.approved, "reason": approval.reason, "attestation_addresses": tuple(item.content_address for item in approval.attestations)}


__all__ = ["EvidenceReleaseApproval", "approval_payload", "evaluate_evidence_release_approval"]
