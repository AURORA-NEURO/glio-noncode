"""Public aggregate fixture intake for the composed Domain 03 boundary.

The architecture fixture is deliberately a second boundary around the four
existing specimen planes.  It owns source receipts, operation identity,
scenario balance, and scope checks; the scientific adapters continue to own
their typed payload semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .serialization import canonical_json, jsonable
from .specimen_architecture_contracts import (
    SPECIMEN_ARCHITECTURE_CASE_COUNT,
    SPECIMEN_ARCHITECTURE_CONTEXT,
    SPECIMEN_ARCHITECTURE_OPERATION_COUNT,
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    SpecimenArchitectureDataAudit,
    SpecimenArchitectureFixture,
    SpecimenArchitectureScenario,
    addressed,
)

SPECIMEN_ARCHITECTURE_FIXTURE_FILE = "specimen-architecture-public-aggregate.json"


def default_specimen_architecture_fixture(
    path: str | Path | None = None,
) -> SpecimenArchitectureFixture:
    """Load the checked-in fixture or an explicitly supplied replay fixture."""

    fixture_path = Path(path) if path is not None else _repository_fixture_path()
    return SpecimenArchitectureFixture.from_file(fixture_path)


def specimen_architecture_fixture_json(
    fixture: SpecimenArchitectureFixture | None = None,
) -> str:
    """Return canonical fixture JSON for exports and address comparisons."""

    return canonical_json((fixture or default_specimen_architecture_fixture()).to_dict())


def audit_specimen_architecture_data(
    fixture: SpecimenArchitectureFixture | None = None,
) -> SpecimenArchitectureDataAudit:
    """Audit the public source boundary before any adapter receives a case."""

    value = fixture or default_specimen_architecture_fixture()
    checks: list[SpecimenArchitectureCheck] = []
    operation_ids = {item.operation_id for item in value.operations}
    source_ids = set(value.source_ids)
    cases_by_operation = {
        operation_id: tuple(case for case in value.cases if case.operation_id == operation_id)
        for operation_id in operation_ids
    }
    checks.extend(
        (
            _check("fixture-version", True, value.version, value.version, "version is closed"),
            _check(
                "fixture-boundary",
                value.boundary == "public_aggregate_specimen_context_and_release",
                value.boundary,
                "public aggregate boundary",
                "fixture declares an explicit release boundary",
            ),
            _check(
                "fixture-context",
                value.context_key == SPECIMEN_ARCHITECTURE_CONTEXT
                and value.context_key.count("|") == 5,
                value.context_key,
                SPECIMEN_ARCHITECTURE_CONTEXT,
                "one six-field context anchors the fixture",
            ),
            _check(
                "source-floor",
                len(value.sources) >= 6 and len(source_ids) == len(value.sources),
                len(value.sources),
                ">=6 unique sources",
                "source receipts are unique",
            ),
            _check(
                "source-scope",
                all(
                    source.uri.startswith("https://")
                    and source.scope == "public_aggregate"
                    and source.license
                    for source in value.sources
                ),
                tuple(source.source_id for source in value.sources),
                "HTTPS public aggregate sources",
                "sources are reviewable public receipts",
            ),
            _check(
                "operation-floor",
                len(value.operations) == SPECIMEN_ARCHITECTURE_OPERATION_COUNT,
                len(value.operations),
                SPECIMEN_ARCHITECTURE_OPERATION_COUNT,
                "all sixteen specimen operations are declared",
            ),
            _check(
                "case-floor",
                len(value.cases) == SPECIMEN_ARCHITECTURE_CASE_COUNT,
                len(value.cases),
                SPECIMEN_ARCHITECTURE_CASE_COUNT,
                "every operation has four explicit scenarios",
            ),
            _check(
                "case-operation-join",
                all(case.operation_id in operation_ids for case in value.cases),
                tuple(sorted({case.operation_id for case in value.cases})),
                tuple(sorted(operation_ids)),
                "every case joins to one operation spec",
            ),
            _check(
                "case-source-join",
                all(set(case.source_ids).issubset(source_ids) for case in value.cases),
                tuple(sorted({source for case in value.cases for source in case.source_ids})),
                tuple(sorted(source_ids)),
                "every case joins only to declared sources",
            ),
            _check(
                "operation-addresses",
                all(item.content_address.startswith("sha256:") for item in value.operations),
                len(
                    [
                        item
                        for item in value.operations
                        if item.content_address.startswith("sha256:")
                    ]
                ),
                len(value.operations),
                "operation specifications are addressed",
            ),
            _check(
                "scenario-balance",
                all(
                    len(cases_by_operation[operation_id]) == 4
                    and sum(
                        case.scenario is SpecimenArchitectureScenario.POSITIVE
                        for case in cases_by_operation[operation_id]
                    )
                    == 1
                    and {case.scenario for case in cases_by_operation[operation_id]}
                    == {
                        SpecimenArchitectureScenario.POSITIVE,
                        SpecimenArchitectureScenario.FOREIGN_CONTEXT,
                        SpecimenArchitectureScenario.MALFORMED_INPUT,
                        SpecimenArchitectureScenario.IDENTITY_CONFLICT,
                    }
                    for operation_id in operation_ids
                ),
                tuple(
                    len(cases_by_operation[operation_id]) for operation_id in sorted(operation_ids)
                ),
                "positive plus three controls per operation",
                "positive and conservative controls are balanced",
            ),
            _check(
                "payload-scope",
                not _sensitive_paths(value.to_dict()),
                _sensitive_paths(value.to_dict()),
                "no direct subject identifiers",
                "aggregate mechanics may be retained without subject-level identity",
            ),
            _check(
                "public-markers",
                all(item.public_aggregate for item in value.sources),
                sum(item.public_aggregate for item in value.sources),
                len(value.sources),
                "every source carries an explicit public aggregate marker",
            ),
            _check(
                "delegate-contexts",
                all(bool(item.delegate_context_key) for item in value.cases),
                sum(bool(item.delegate_context_key) for item in value.cases),
                len(value.cases),
                "every case retains a delegated context key",
            ),
            _check(
                "foreign-context-controls",
                all(
                    item.context_key != item.delegate_context_key
                    for item in value.cases
                    if item.scenario is SpecimenArchitectureScenario.FOREIGN_CONTEXT
                ),
                True,
                True,
                "foreign controls remain distinct from delegated context",
            ),
        )
    )
    accepted = all(item.passed for item in checks)
    body = {"fixture_id": value.fixture_id, "checks": checks, "accepted": accepted}
    return SpecimenArchitectureDataAudit(
        fixture_id=value.fixture_id,
        checks=tuple(checks),
        accepted=accepted,
        content_address=addressed(body, "specimen-data-audit"),
    )


def load_specimen_architecture_mapping(path: str | Path | None = None) -> dict[str, Any]:
    """Return a plain JSON-compatible mapping for API and CLI callers."""

    return jsonable(default_specimen_architecture_fixture(path).to_dict())


def _repository_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / SPECIMEN_ARCHITECTURE_FIXTURE_FILE


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> SpecimenArchitectureCheck:
    kind = (
        SpecimenArchitectureCheckKind.SOURCE
        if check_id.startswith("source")
        else SpecimenArchitectureCheckKind.FIXTURE
    )
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SpecimenArchitectureCheck(
        check_id=check_id,
        kind=kind,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "specimen-data-check"),
    )


def _sensitive_paths(value: Any, path: str = "fixture") -> tuple[str, ...]:
    """Find direct identity fields while allowing aggregate specimen labels."""

    forbidden = {
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
    }
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in forbidden:
                found.append(child)
            found.extend(_sensitive_paths(item, child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_sensitive_paths(item, f"{path}[{index}]"))
    return tuple(found)


__all__ = [
    "SPECIMEN_ARCHITECTURE_FIXTURE_FILE",
    "audit_specimen_architecture_data",
    "default_specimen_architecture_fixture",
    "load_specimen_architecture_mapping",
    "specimen_architecture_fixture_json",
]
