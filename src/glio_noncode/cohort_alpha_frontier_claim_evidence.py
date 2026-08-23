"""Claim-to-evidence mapping that enforces the descriptive claim ceiling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierClaimEvidence:
    claim_id: str
    operation: str
    claim_text: str
    evidence_record_ids: tuple[str, ...]
    allowed: bool
    limitation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierClaimEvidenceReport:
    claims: tuple[CohortAlphaFrontierClaimEvidence, ...]
    allowed_count: int
    blocked_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_claim_evidence(fixture: CohortAlphaFrontierFixture, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierClaimEvidenceReport:
    claims = []
    for operation, claim in (("C09", "clonality timing summary"), ("C10", "primary recurrence comparison"), ("C11", "treatment-selection signal summary"), ("C12", "cross-cohort replication summary")):
        ids = tuple(record.record_id for record in fixture.records if record.operation == operation and policy.for_record(record.record_id).disposition.value == "publish")
        allowed = bool(ids) and all("causal" not in claim and "clinical" not in claim for _ in ids)
        limitation = "descriptive aggregate only; not a causal or clinical decision claim"
        claims.append(CohortAlphaFrontierClaimEvidence(f"claim-{operation}", operation, claim, ids, allowed, limitation, content_hash({"operation": operation, "claim": claim, "ids": ids, "allowed": allowed, "limitation": limitation}, prefix="alpha-claim-evidence")))
    values = tuple(claims)
    return CohortAlphaFrontierClaimEvidenceReport(values, sum(item.allowed for item in values), sum(not item.allowed for item in values), len(values) == 4 and all(item.allowed and item.evidence_record_ids for item in values), content_hash(values, prefix="alpha-claim-report"))


__all__ = ["CohortAlphaFrontierClaimEvidence", "CohortAlphaFrontierClaimEvidenceReport", "build_cohort_alpha_frontier_claim_evidence"]
