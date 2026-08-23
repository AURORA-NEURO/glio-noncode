"""Claim-to-evidence links for descriptive cohort statements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_policy import CohortFoundationPolicy


@dataclass(frozen=True, slots=True)
class CohortFoundationClaimEvidenceLink:
    claim_id: str
    record_id: str
    claim_text: str
    evidence_addresses: tuple[str, ...]
    context_key: str
    disposition: str
    allowed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationClaimEvidenceLedger:
    ledger_id: str
    links: tuple[CohortFoundationClaimEvidenceLink, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_claim_evidence_ledger(evaluation: CohortFoundationEvaluation, policy: CohortFoundationPolicy, context_key: str) -> CohortFoundationClaimEvidenceLedger:
    links = []
    for execution in evaluation.executions:
        decision = policy.decision_for(execution.record_id)
        claim = f"{execution.operation.value} returned {execution.actual_state} for an aggregate record"
        body = {"record_id": execution.record_id, "claim": claim, "evidence": (execution.content_address,), "context": context_key, "disposition": decision.disposition}
        links.append(CohortFoundationClaimEvidenceLink(content_hash((execution.record_id, "claim"), prefix="claim"), execution.record_id, claim, (execution.content_address,), context_key, decision.disposition.value, decision.disposition.value == "allow_descriptive", content_hash(body)))
    body = {"ledger_id": "cohort-foundation-frontier-claim-evidence", "links": links}
    return CohortFoundationClaimEvidenceLedger(body["ledger_id"], tuple(links), all(bool(item.evidence_addresses) and item.context_key == context_key for item in links), content_hash(body))


__all__ = ["CohortFoundationClaimEvidenceLedger", "CohortFoundationClaimEvidenceLink", "build_cohort_foundation_frontier_claim_evidence_ledger"]
