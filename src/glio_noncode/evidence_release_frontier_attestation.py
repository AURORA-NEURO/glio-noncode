"""Per-row attestation receipts for reviewer decisions and publication gates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .evidence_release_frontier_support import address, required_text, safe_output
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseAttestation:
    record_id: str
    reviewer_id: str
    decision: str
    rationale: str
    observed_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_attestation(record_id: str, reviewer_id: str, decision: str, rationale: str, observed: Mapping[str, Any]) -> EvidenceReleaseAttestation:
    record = required_text(record_id, "record_id")
    reviewer = required_text(reviewer_id, "reviewer_id")
    chosen = required_text(decision, "decision")
    explanation = required_text(rationale, "rationale")
    observed_address = address(safe_output(observed))
    body = {"record_id": record, "reviewer_id": reviewer, "decision": chosen, "rationale": explanation, "observed_address": observed_address}
    return EvidenceReleaseAttestation(**body, content_address=address(body))


def attestations_are_independent(attestations: tuple[EvidenceReleaseAttestation, ...]) -> bool:
    return len({item.reviewer_id for item in attestations}) == len(attestations) and all(item.content_address.startswith("sha256:") for item in attestations)


__all__ = ["EvidenceReleaseAttestation", "attestations_are_independent", "build_evidence_release_attestation"]
