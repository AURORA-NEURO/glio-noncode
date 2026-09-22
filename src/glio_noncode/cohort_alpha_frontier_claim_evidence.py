"""Claim-to-evidence mapping with manifest-backed operation coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_dataset_manifest import (
    CohortAlphaFrontierDatasetManifest,
    build_cohort_alpha_frontier_dataset_manifest,
)
from .cohort_alpha_frontier_governance import (
    CohortAlphaFrontierDisposition,
    CohortAlphaFrontierPolicy,
)
from .cohort_alpha_frontier_public_data import (
    CohortAlphaFrontierFixture,
    audit_cohort_alpha_frontier_data,
)
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
    expected_evidence_record_ids: tuple[str, ...] = ()
    missing_evidence_record_ids: tuple[str, ...] = ()
    unexpected_evidence_record_ids: tuple[str, ...] = ()
    coverage_state: str = "partial"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierClaimEvidenceReport:
    claims: tuple[CohortAlphaFrontierClaimEvidence, ...]
    allowed_count: int
    blocked_count: int
    accepted: bool
    content_address: str
    dataset_manifest_address: str | None = None
    expected_claim_count: int = 0
    complete_claim_count: int = 0
    missing_claim_count: int = 0
    extra_claim_count: int = 0
    coverage_state: str = "partial"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _claim_coverage_state(
    expected: tuple[str, ...], observed: tuple[str, ...]
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    missing = tuple(sorted(set(expected) - set(observed)))
    unexpected = tuple(sorted(set(observed) - set(expected)))
    if missing and unexpected:
        state = "inconsistent"
    elif unexpected:
        state = "unexpected"
    elif missing:
        state = "partial"
    else:
        state = "complete"
    return state, missing, unexpected


def build_cohort_alpha_frontier_claim_evidence(
    fixture: CohortAlphaFrontierFixture,
    policy: CohortAlphaFrontierPolicy,
    manifest: CohortAlphaFrontierDatasetManifest | None = None,
) -> CohortAlphaFrontierClaimEvidenceReport:
    """Reconcile publishable evidence IDs with each manifest-declared claim.

    The denominator is the manifest's expected claim set, never the number of
    claims or supporting rows that happen to be present in an input fixture.
    """

    selected_manifest = manifest or build_cohort_alpha_frontier_dataset_manifest(
        fixture, audit_cohort_alpha_frontier_data(fixture)
    )
    manifest_matches_fixture = (
        selected_manifest.fixture_id == fixture.fixture_id
        and selected_manifest.fixture_content_address == fixture.content_address
    )
    decisions = {item.record_id: item for item in policy.decisions}
    claims: list[CohortAlphaFrontierClaimEvidence] = []
    for expected in selected_manifest.expected_claims:
        observed_ids = tuple(
            record.record_id
            for record in fixture.records
            if record.operation == expected.operation
            and (decision := decisions.get(record.record_id)) is not None
            and decision.disposition is CohortAlphaFrontierDisposition.PUBLISH
        )
        state, missing, unexpected = _claim_coverage_state(
            expected.evidence_record_ids, observed_ids
        )
        claim_text_allowed = not any(
            term in expected.claim_text.casefold() for term in ("causal", "clinical")
        )
        allowed = state == "complete" and claim_text_allowed and manifest_matches_fixture
        if not manifest_matches_fixture:
            limitation = "dataset manifest does not describe the supplied fixture"
            state = "inconsistent"
        elif missing:
            limitation = "partial evidence coverage; expected supporting records are missing"
        elif unexpected:
            limitation = "unexpected publishable evidence records require manifest review"
        elif not claim_text_allowed:
            limitation = "claim wording exceeds the descriptive research-use boundary"
        else:
            limitation = "descriptive aggregate only; not a causal or clinical decision claim"
        body = {
            "claim_id": expected.claim_id,
            "operation": expected.operation,
            "claim_text": expected.claim_text,
            "evidence_record_ids": observed_ids,
            "expected_evidence_record_ids": expected.evidence_record_ids,
            "missing_evidence_record_ids": missing,
            "unexpected_evidence_record_ids": unexpected,
            "coverage_state": state,
            "allowed": allowed,
            "limitation": limitation,
        }
        claims.append(
            CohortAlphaFrontierClaimEvidence(
                claim_id=expected.claim_id,
                operation=expected.operation,
                claim_text=expected.claim_text,
                evidence_record_ids=observed_ids,
                allowed=allowed,
                limitation=limitation,
                content_address=content_hash(body, prefix="alpha-claim-evidence"),
                expected_evidence_record_ids=expected.evidence_record_ids,
                missing_evidence_record_ids=missing,
                unexpected_evidence_record_ids=unexpected,
                coverage_state=state,
            )
        )

    values = tuple(claims)
    missing_claim_count = sum(bool(item.missing_evidence_record_ids) for item in values)
    extra_claim_count = sum(bool(item.unexpected_evidence_record_ids) for item in values)
    complete_claim_count = sum(item.coverage_state == "complete" for item in values)
    if missing_claim_count and extra_claim_count:
        coverage_state = "inconsistent"
    elif not manifest_matches_fixture:
        coverage_state = "inconsistent"
    elif extra_claim_count:
        coverage_state = "unexpected"
    elif missing_claim_count:
        coverage_state = "partial"
    elif selected_manifest.coverage_state != "complete":
        coverage_state = selected_manifest.coverage_state
    else:
        coverage_state = "complete"
    allowed_count = sum(item.allowed for item in values)
    accepted = (
        selected_manifest.accepted
        and bool(values)
        and len(values) == selected_manifest.expected_claim_count
        and all(item.allowed for item in values)
    )
    body = {
        "claims": values,
        "expected_claim_count": selected_manifest.expected_claim_count,
        "complete_claim_count": complete_claim_count,
        "missing_claim_count": missing_claim_count,
        "extra_claim_count": extra_claim_count,
        "dataset_manifest_address": selected_manifest.content_address,
        "allowed_count": allowed_count,
        "blocked_count": len(values) - allowed_count,
        "coverage_state": coverage_state,
        "accepted": accepted,
    }
    return CohortAlphaFrontierClaimEvidenceReport(
        claims=values,
        allowed_count=allowed_count,
        blocked_count=len(values) - allowed_count,
        accepted=accepted,
        content_address=content_hash(body, prefix="alpha-claim-report"),
        dataset_manifest_address=selected_manifest.content_address,
        expected_claim_count=selected_manifest.expected_claim_count,
        complete_claim_count=complete_claim_count,
        missing_claim_count=missing_claim_count,
        extra_claim_count=extra_claim_count,
        coverage_state=coverage_state,
    )


__all__ = [
    "CohortAlphaFrontierClaimEvidence",
    "CohortAlphaFrontierClaimEvidenceReport",
    "build_cohort_alpha_frontier_claim_evidence",
]
