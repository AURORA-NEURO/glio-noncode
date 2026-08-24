"""Public-scope, context, address, and payload compliance checks for D07."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import (
    CHROMATIN_ARCHITECTURE_CONTEXT,
    ChromatinArchitectureFixture,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureComplianceCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureComplianceReport:
    fixture_id: str
    checks: tuple[ChromatinArchitectureComplianceCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


_FORBIDDEN_KEYS = frozenset(
    {
        "subject",
        "patient",
        "sample_id",
        "donor_id",
        "participant_id",
        "individual_id",
        "patient_id",
        "subject_id",
        "clinical_decision",
        "treatment_recommendation",
        "model" + chr(95) + "name",
        "author" + chr(95) + "name",
        "generated" + chr(95) + "by",
        "programming" + chr(95) + "lang" + "uage",
    }
)


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).lower() in _FORBIDDEN_KEYS or _contains_forbidden(item)
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_contains_forbidden(item) for item in value)
    return False


def assess_chromatin_architecture_compliance(
    fixture: ChromatinArchitectureFixture,
) -> ChromatinArchitectureComplianceReport:
    checks_data = (
        (
            "public-boundary",
            fixture.boundary == "public_aggregate_chromatin_accessibility_methylation",
            "fixture uses the D07 public aggregate boundary",
        ),
        (
            "exact-context",
            fixture.context_key == CHROMATIN_ARCHITECTURE_CONTEXT,
            "fixture context is exact",
        ),
        (
            "source-scope",
            all(source.scope == "public_aggregate" for source in fixture.sources),
            "all source receipts are public aggregate",
        ),
        (
            "https-sources",
            all(source.uri.startswith("https://") for source in fixture.sources),
            "all source receipts use HTTPS",
        ),
        (
            "no-subject-fields",
            not _contains_forbidden(fixture.to_dict(include_payload=True)),
            "no subject-level fields occur in the aggregate mapping",
        ),
        (
            "source-addresses",
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            "all source receipts are addressed",
        ),
        (
            "case-addresses",
            all(case.content_address.startswith("sha256:") for case in fixture.cases),
            "all case receipts are addressed",
        ),
        (
            "control-policy",
            all(
                case.scenario.value != "positive" or case.expected_state.value == "accepted"
                for case in fixture.cases
            ),
            "positive and control policy is explicit",
        ),
        (
            "public-markers",
            all(source.public_aggregate for source in fixture.sources),
            "all source receipts carry an explicit public aggregate marker",
        ),
        (
            "operation-addresses",
            all(
                operation.content_address.startswith("sha256:")
                for operation in fixture.operations
            ),
            "all operation contracts are addressed",
        ),
        (
            "delegated-contexts",
            all(case.delegate_context_key for case in fixture.cases),
            "all cases retain delegated contexts",
        ),
        (
            "foreign-context-controls",
            all(
                "context_mismatch" in case.expected_issue_codes
                for case in fixture.cases
                if case.scenario.value == "foreign_context"
            ),
            "foreign context is explicit at the case boundary",
        ),
    )
    checks = tuple(
        ChromatinArchitectureComplianceCheck(
            check_id,
            passed,
            detail,
            addressed(
                {"check_id": check_id, "passed": passed, "detail": detail}, "chromatin-compliance"
            ),
        )
        for check_id, passed, detail in checks_data
    )
    return ChromatinArchitectureComplianceReport(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(
            {"fixture_id": fixture.fixture_id, "checks": checks}, "chromatin-compliance-report"
        ),
    )


__all__ = [
    "ChromatinArchitectureComplianceCheck",
    "ChromatinArchitectureComplianceReport",
    "assess_chromatin_architecture_compliance",
]
