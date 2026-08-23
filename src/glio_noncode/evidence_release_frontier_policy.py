"""Policy boundary: lifecycle receipts do not establish scientific truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleasePolicy:
    allowed_states: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    public_aggregate_only: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_evidence_release_policy() -> EvidenceReleasePolicy:
    body = {"allowed_states": ("ready", "review", "blocked", "reclassified", "superseded", "bundled", "signed", "verified", "rejected", "abstained"), "prohibited_claims": ("clinical efficacy", "patient outcome", "causal certainty", "individual diagnosis"), "public_aggregate_only": True}
    return EvidenceReleasePolicy(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleasePolicy", "default_evidence_release_policy"]
