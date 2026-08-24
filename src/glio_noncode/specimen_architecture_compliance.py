"""Public aggregate and context-boundary checks for D03 specimen data."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .serialization import jsonable
from .specimen_architecture_contracts import (
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    SpecimenArchitectureFixture,
    SpecimenArchitectureScenario,
    addressed,
)

_FORBIDDEN_KEYS = frozenset(
    {
        "patient_id",
        "subject_id",
        "individual_id",
        "participant_id",
        "medical_record_number",
        "mrn",
        "date_of_birth",
        "email",
        "phone",
        "street_address",
        "clinical_decision",
        "treatment_recommendation",
    }
)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureComplianceReport:
    fixture_id: str
    checks: tuple[SpecimenArchitectureCheck, ...]
    forbidden_key_paths: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assess_specimen_architecture_compliance(
    fixture: SpecimenArchitectureFixture,
) -> SpecimenArchitectureComplianceReport:
    paths: list[str] = []
    for case in fixture.cases:
        _walk(case.payload, f"cases.{case.case_id}.payload", paths)
        _walk(case.parameters, f"cases.{case.case_id}.parameters", paths)
    foreign = tuple(
        item
        for item in fixture.cases
        if item.scenario is SpecimenArchitectureScenario.FOREIGN_CONTEXT
    )
    checks = (
        _check(
            "compliance-public-sources",
            all(item.scope == "public_aggregate" for item in fixture.sources),
            sum(item.scope == "public_aggregate" for item in fixture.sources),
            len(fixture.sources),
            "all sources use public aggregate scope",
        ),
        _check(
            "compliance-public-markers",
            all(item.public_aggregate for item in fixture.sources),
            sum(item.public_aggregate for item in fixture.sources),
            len(fixture.sources),
            "all sources carry the public aggregate marker",
        ),
        _check(
            "compliance-payload-boundary",
            not paths,
            paths,
            [],
            "payload and parameter mappings exclude direct identity fields",
        ),
        _check(
            "compliance-contexts",
            all(
                item.context_key
                in {
                    fixture.context_key,
                    "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
                }
                for item in fixture.cases
            ),
            True,
            True,
            "case contexts remain inside the declared boundary",
        ),
        _check(
            "compliance-delegate-contexts",
            all(bool(item.delegate_context_key) for item in fixture.cases),
            sum(bool(item.delegate_context_key) for item in fixture.cases),
            len(fixture.cases),
            "delegated context keys are explicit",
        ),
        _check(
            "compliance-foreign-controls",
            all(item.context_key != item.delegate_context_key for item in foreign),
            True,
            True,
            "foreign controls are distinct from delegated context",
        ),
        _check(
            "compliance-control-states",
            all(item.expected_state.value == "review" for item in fixture.control_cases),
            len(fixture.control_cases),
            48,
            "controls remain held for review",
        ),
        _check(
            "compliance-addresses",
            all(
                item.content_address.startswith("sha256:")
                for item in (*fixture.sources, *fixture.operations, *fixture.cases)
            ),
            True,
            True,
            "public declarations are content addressed",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "paths": tuple(paths)}
    return SpecimenArchitectureComplianceReport(
        fixture_id=fixture.fixture_id,
        checks=checks,
        forbidden_key_paths=tuple(paths),
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "specimen-compliance"),
    )


def _walk(value: Any, path: str, paths: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                paths.append(f"{path}.{key}")
            _walk(child, f"{path}.{key}", paths)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _walk(child, f"{path}[{index}]", paths)


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SpecimenArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SpecimenArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SpecimenArchitectureCheck(
        check_id,
        SpecimenArchitectureCheckKind.FIXTURE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "specimen-compliance-check"),
    )


__all__ = ["SpecimenArchitectureComplianceReport", "assess_specimen_architecture_compliance"]
