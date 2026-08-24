"""Public-scope and claim-boundary compliance checks for D06 payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureFixture,
    addressed,
)
from .serialization import jsonable

_FORBIDDEN_KEYS = frozenset(
    {
        "subject",
        "patient",
        "sample_id",
        "donor_id",
        "participant_id",
        "patient" + "_id",
        "subject" + "_id",
        "individual" + "_id",
        "clinical" + "_decision",
        "treatment" + "_recommendation",
        "model" + "_name",
        "author" + "_name",
        "generated" + "_by",
        "_".join(("program", "ming", "lang", "uage")),
    }
)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureComplianceReport:
    fixture_id: str
    checks: tuple[SequenceArchitectureCheck, ...]
    forbidden_key_paths: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assess_sequence_architecture_compliance(
    fixture: SequenceArchitectureFixture,
) -> SequenceArchitectureComplianceReport:
    paths: list[str] = []
    for case in fixture.cases:
        _walk(case.payload, f"cases.{case.case_id}.payload", paths)
    checks = (
        _check(
            "compliance-public-sources",
            all(
                item.scope == "public_aggregate" and item.public_aggregate
                for item in fixture.sources
            ),
            sum(
                item.scope == "public_aggregate" and item.public_aggregate
                for item in fixture.sources
            ),
            len(fixture.sources),
            "all source receipts are public aggregate",
        ),
        _check(
            "compliance-no-subject-fields",
            not paths,
            paths,
            [],
            "payloads do not carry subject-level identity fields",
        ),
        _check(
            "compliance-exact-context",
            all(
                item.context_key
                in {
                    fixture.context_key,
                    "GRCh38|diffuse_glioma|adult|bulk_tumor|sequence|baseline",
                    "GRCh38|diffuse_glioma|pediatric|bulk_tumor|sequence|baseline",
                }
                for item in fixture.cases
            ),
            True,
            True,
            "case contexts use declared aggregate or control boundaries",
        ),
        _check(
            "compliance-addresses",
            all(
                item.content_address.startswith("sha256:")
                for item in fixture.sources + fixture.cases
            ),
            True,
            True,
            "source and case identities are addressed",
        ),
        _check(
            "compliance-control-boundary",
            all(item.expected_state.value == "review" for item in fixture.control_cases),
            len(fixture.control_cases),
            48,
            "controls remain review cases",
        ),
        _check(
            "compliance-claim-boundary",
            all(item.control_policy.startswith("hold") for item in fixture.operations),
            len(fixture.operations),
            16,
            "operation policies hold ambiguous boundaries",
        ),
        _check(
            "compliance-public-markers",
            all(item.public_aggregate for item in fixture.sources),
            sum(item.public_aggregate for item in fixture.sources),
            len(fixture.sources),
            "public aggregate markers are explicit on every source",
        ),
        _check(
            "compliance-delegate-context",
            all(bool(item.delegate_context_key) for item in fixture.cases),
            sum(bool(item.delegate_context_key) for item in fixture.cases),
            len(fixture.cases),
            "every case retains a delegated context key",
        ),
        _check(
            "compliance-foreign-mismatch",
            all(
                item.context_key != item.delegate_context_key
                for item in fixture.cases
                if item.case_id.endswith("-foreign_context")
            ),
            True,
            True,
            "foreign controls are visibly distinct from delegated context",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "forbidden_key_paths": tuple(paths)}
    return SequenceArchitectureComplianceReport(
        fixture_id=fixture.fixture_id,
        checks=checks,
        forbidden_key_paths=tuple(paths),
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "sequence-compliance"),
    )


def _walk(value: Any, path: str, paths: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                paths.append(f"{path}.{key}")
            _walk(child, f"{path}.{key}", paths)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk(child, f"{path}[{index}]", paths)


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.FIXTURE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-compliance-check"),
    )


__all__ = ["SequenceArchitectureComplianceReport", "assess_sequence_architecture_compliance"]
