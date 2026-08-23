"""Evidence ledger for each bounded claim emitted by C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_claim_boundary import CohortBetaFrontierClaimBoundary
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierClaimEvidence:
    claim_id: str
    operation: str
    claim: str
    supporting_records: tuple[str, ...]
    source_count: int
    bounded: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierClaimEvidenceLedger:
    claims: tuple[CohortBetaFrontierClaimEvidence, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_claim_evidence_ledger(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation, boundary: CohortBetaFrontierClaimBoundary) -> CohortBetaFrontierClaimEvidenceLedger:
    claims = []
    for operation in ("C05", "C06", "C07", "C08"):
        rows = tuple(item for item in evaluation.rows if item.operation == operation and item.observed_state.value == "supported")
        claim = boundary.operation_claims[operation][0]
        body = {"operation": operation, "claim": claim, "records": tuple(item.record_id for item in rows), "sources": len({source_id for record in fixture.records if record.operation == operation for source_id in record.source_ids})}
        claims.append(CohortBetaFrontierClaimEvidence(f"claim:{operation}", operation, claim, tuple(item.record_id for item in rows), body["sources"], bool(rows), content_hash(body, prefix="claim-evidence")))
    return CohortBetaFrontierClaimEvidenceLedger(tuple(claims), len(claims) == 4 and all(item.bounded for item in claims), content_hash(claims, prefix="claim-ledger"))


__all__ = ["CohortBetaFrontierClaimEvidence", "CohortBetaFrontierClaimEvidenceLedger", "build_cohort_beta_frontier_claim_evidence_ledger"]
