"""Assurance assertions combining independent release evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierLineage, CohortAlphaFrontierPolicy, CohortAlphaFrontierQualityGate, CohortAlphaFrontierReplayReceipt
from .cohort_alpha_frontier_integrity import CohortAlphaFrontierIntegrityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAssuranceAssertion:
    assertion_id: str
    statement: str
    observed: bool
    evidence_addresses: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAssuranceReport:
    assertions: tuple[CohortAlphaFrontierAssuranceAssertion, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_alpha_frontier_assurance(quality: CohortAlphaFrontierQualityGate, lineage: CohortAlphaFrontierLineage, replay: CohortAlphaFrontierReplayReceipt, integrity: CohortAlphaFrontierIntegrityReport, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierAssuranceReport:
    raw = (("quality", "all release quality checks pass", quality.accepted, (quality.content_address,)), ("lineage", "source to result lineage is closed", lineage.closed, (lineage.content_address,)), ("replay", "repeated evaluation is deterministic", replay.deterministic, (replay.content_address,)), ("integrity", "content addresses and identities are coherent", integrity.accepted, (integrity.content_address,)), ("policy", "publication, review, and quarantine are partitioned", len(policy.decisions) == policy.publishable_count + policy.review_count + policy.quarantine_count, (policy.content_address,)))
    assertions = tuple(CohortAlphaFrontierAssuranceAssertion(assertion_id, statement, observed, addresses, content_hash({"id": assertion_id, "statement": statement, "observed": observed, "addresses": addresses}, prefix="alpha-assurance")) for assertion_id, statement, observed, addresses in raw)
    return CohortAlphaFrontierAssuranceReport(assertions, all(item.observed for item in assertions), content_hash(assertions, prefix="alpha-assurance-report"))


__all__ = ["CohortAlphaFrontierAssuranceAssertion", "CohortAlphaFrontierAssuranceReport", "evaluate_cohort_alpha_frontier_assurance"]
