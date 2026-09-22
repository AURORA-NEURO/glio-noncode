"""Dataset manifest with explicit, operation-specific cohort expectations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import (
    C09_C12_CONTEXT,
    C09_C12_EXPECTED_RECORD_IDS_BY_OPERATION,
    C09_C12_OPERATIONS,
    CohortAlphaFrontierDataAudit,
    CohortAlphaFrontierFixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierExpectedClaim:
    """One pipeline claim and the exact supported records expected to back it."""

    operation: str
    claim_id: str
    claim_text: str
    evidence_record_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


C09_C12_EXPECTED_CLAIMS = (
    CohortAlphaFrontierExpectedClaim(
        "C09", "claim-C09", "clonality timing summary", ("c09-positive",)
    ),
    CohortAlphaFrontierExpectedClaim(
        "C10", "claim-C10", "primary recurrence comparison", ("c10-positive",)
    ),
    CohortAlphaFrontierExpectedClaim(
        "C11", "claim-C11", "treatment-selection signal summary", ("c11-positive",)
    ),
    CohortAlphaFrontierExpectedClaim(
        "C12", "claim-C12", "cross-cohort replication summary", ("c12-positive",)
    ),
)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierDatasetManifest:
    dataset_id: str
    fixture_id: str
    fixture_content_address: str
    version: str
    context_key: str
    operations: tuple[str, ...]
    observed_operations: tuple[str, ...]
    expected_record_ids_by_operation: tuple[tuple[str, tuple[str, ...]], ...]
    observed_record_ids_by_operation: tuple[tuple[str, tuple[str, ...]], ...]
    missing_record_ids_by_operation: tuple[tuple[str, tuple[str, ...]], ...]
    extra_record_ids_by_operation: tuple[tuple[str, tuple[str, ...]], ...]
    expected_claims: tuple[CohortAlphaFrontierExpectedClaim, ...]
    expected_record_count: int
    record_count: int
    source_count: int
    exclusion_rules: tuple[str, ...]
    coverage_state: str
    accepted: bool
    content_address: str

    @property
    def expected_claim_count(self) -> int:
        return len(self.expected_claims)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _coverage_state(
    *,
    missing: tuple[tuple[str, tuple[str, ...]], ...],
    extra: tuple[tuple[str, tuple[str, ...]], ...],
    audit: CohortAlphaFrontierDataAudit,
    context_valid: bool,
) -> str:
    has_missing = any(record_ids for _, record_ids in missing)
    has_extra = any(record_ids for _, record_ids in extra)
    if has_missing and has_extra:
        return "inconsistent"
    if has_extra:
        return "unexpected"
    if has_missing:
        return "partial"
    if not audit.accepted or not context_valid:
        return "invalid"
    return "complete"


def build_cohort_alpha_frontier_dataset_manifest(
    fixture: CohortAlphaFrontierFixture,
    audit: CohortAlphaFrontierDataAudit,
) -> CohortAlphaFrontierDatasetManifest:
    """Compare observed row identities against manifest-declared operation sets.

    Record expectations and supported-claim expectations are separate: one
    operation can have many structural input/control records but contributes a
    different, explicitly enumerated number of pipeline claims.
    """

    exclusions = (
        "non-adult context",
        "post-treatment context",
        "unreceipted source",
        "causal or clinical decision claims",
    )
    expected_by_operation = C09_C12_EXPECTED_RECORD_IDS_BY_OPERATION
    expected_lookup = dict(expected_by_operation)
    observed_operations = fixture.operations
    all_operations = tuple(sorted(set(C09_C12_OPERATIONS) | set(observed_operations)))
    observed_by_operation = tuple(
        (
            operation,
            tuple(record.record_id for record in fixture.records if record.operation == operation),
        )
        for operation in all_operations
    )
    observed_lookup = dict(observed_by_operation)
    missing = tuple(
        (
            operation,
            tuple(sorted(set(record_ids) - set(observed_lookup.get(operation, ())))),
        )
        for operation, record_ids in expected_by_operation
    )
    extra = tuple(
        (
            operation,
            tuple(
                sorted(
                    set(observed_lookup.get(operation, ()))
                    - set(expected_lookup.get(operation, ()))
                )
            ),
        )
        for operation in all_operations
    )
    context_valid = fixture.context_key == C09_C12_CONTEXT
    coverage_state = _coverage_state(
        missing=missing,
        extra=extra,
        audit=audit,
        context_valid=context_valid,
    )
    accepted = coverage_state == "complete"
    expected_record_count = sum(len(record_ids) for _, record_ids in expected_by_operation)
    body = {
        "dataset_id": "cohort-alpha-frontier-c09-c12",
        "fixture_id": fixture.fixture_id,
        "fixture_content_address": fixture.content_address,
        "version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "operations": C09_C12_OPERATIONS,
        "observed_operations": observed_operations,
        "expected_record_ids_by_operation": expected_by_operation,
        "observed_record_ids_by_operation": observed_by_operation,
        "missing_record_ids_by_operation": missing,
        "extra_record_ids_by_operation": extra,
        "expected_claims": C09_C12_EXPECTED_CLAIMS,
        "expected_record_count": expected_record_count,
        "record_count": len(fixture.records),
        "source_count": len(fixture.sources),
        "exclusion_rules": exclusions,
        "coverage_state": coverage_state,
        "accepted": accepted,
    }
    return CohortAlphaFrontierDatasetManifest(
        dataset_id=body["dataset_id"],
        fixture_id=fixture.fixture_id,
        fixture_content_address=fixture.content_address,
        version=fixture.fixture_version,
        context_key=fixture.context_key,
        operations=C09_C12_OPERATIONS,
        observed_operations=observed_operations,
        expected_record_ids_by_operation=expected_by_operation,
        observed_record_ids_by_operation=observed_by_operation,
        missing_record_ids_by_operation=missing,
        extra_record_ids_by_operation=extra,
        expected_claims=C09_C12_EXPECTED_CLAIMS,
        expected_record_count=expected_record_count,
        record_count=len(fixture.records),
        source_count=len(fixture.sources),
        exclusion_rules=exclusions,
        coverage_state=coverage_state,
        accepted=accepted,
        content_address=content_hash(body, prefix="alpha-dataset-manifest"),
    )


__all__ = [
    "C09_C12_EXPECTED_CLAIMS",
    "CohortAlphaFrontierDatasetManifest",
    "CohortAlphaFrontierExpectedClaim",
    "build_cohort_alpha_frontier_dataset_manifest",
]
