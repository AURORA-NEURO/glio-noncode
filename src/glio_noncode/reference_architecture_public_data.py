"""Public aggregate fixture intake and source audit for D04."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .reference_architecture_contracts import (
    REFERENCE_ARCHITECTURE_CASE_COUNT,
    REFERENCE_ARCHITECTURE_CONTEXT,
    REFERENCE_ARCHITECTURE_OPERATION_COUNT,
    ReferenceArchitectureCheck,
    ReferenceArchitectureCheckKind,
    ReferenceArchitectureDataAudit,
    ReferenceArchitectureFixture,
    ReferenceArchitectureScenario,
    addressed,
)
from .serialization import canonical_json, jsonable

REFERENCE_ARCHITECTURE_FIXTURE_FILE = "reference-architecture-public-aggregate.json"


def default_reference_architecture_fixture(
    path: str | Path | None = None,
) -> ReferenceArchitectureFixture:
    """Load the checked-in D04 fixture or a caller-supplied replay fixture."""

    fixture_path = Path(path) if path is not None else _repository_fixture_path()
    return ReferenceArchitectureFixture.from_file(fixture_path)


def reference_architecture_fixture_json(
    fixture: ReferenceArchitectureFixture | None = None,
) -> str:
    """Return canonical JSON for fixture export and deterministic comparison."""

    return canonical_json((fixture or default_reference_architecture_fixture()).to_dict())


def audit_reference_architecture_data(
    fixture: ReferenceArchitectureFixture | None = None,
) -> ReferenceArchitectureDataAudit:
    """Audit source scope, exact context, operation joins, and case balance."""

    value = fixture or default_reference_architecture_fixture()
    checks: list[ReferenceArchitectureCheck] = []
    operation_ids = {item.operation_id for item in value.operations}
    source_ids = set(value.source_ids)
    checks.extend(
        (
            _check(
                "fixture-version",
                value.version == "2026.08.reference-architecture.v1",
                value.version,
                "closed D04 version",
                "fixture version is supported",
            ),
            _check(
                "fixture-boundary",
                value.boundary == "public_aggregate_reference_context_and_release",
                value.boundary,
                "public aggregate reference boundary",
                "release boundary is explicit",
            ),
            _check(
                "fixture-context",
                value.context_key == REFERENCE_ARCHITECTURE_CONTEXT
                and value.context_key.count("|") == 5,
                value.context_key,
                REFERENCE_ARCHITECTURE_CONTEXT,
                "one exact six-field reference context",
            ),
            _check(
                "source-floor",
                len(value.sources) >= 12 and len(source_ids) == len(value.sources),
                len(value.sources),
                ">=12 unique public sources",
                "source receipts are unique",
            ),
            _check(
                "source-scope",
                all(
                    item.uri.startswith("https://")
                    and item.scope == "public_aggregate"
                    and item.license
                    for item in value.sources
                ),
                tuple(item.source_id for item in value.sources),
                "HTTPS public aggregate sources",
                "sources are reviewable and aggregate",
            ),
            _check(
                "operation-count",
                len(value.operations) == REFERENCE_ARCHITECTURE_OPERATION_COUNT,
                len(value.operations),
                REFERENCE_ARCHITECTURE_OPERATION_COUNT,
                "all sixteen reference operations are declared",
            ),
            _check(
                "case-count",
                len(value.cases) == REFERENCE_ARCHITECTURE_CASE_COUNT,
                len(value.cases),
                REFERENCE_ARCHITECTURE_CASE_COUNT,
                "four cases cover every operation",
            ),
            _check(
                "operation-joins",
                all(item.operation_id in operation_ids for item in value.cases),
                tuple(sorted({item.operation_id for item in value.cases})),
                tuple(sorted(operation_ids)),
                "every case joins an operation spec",
            ),
            _check(
                "source-joins",
                all(set(item.source_ids).issubset(source_ids) for item in value.cases),
                tuple(sorted({source for item in value.cases for source in item.source_ids})),
                tuple(sorted(source_ids)),
                "every case joins declared source IDs",
            ),
            _check(
                "operation-addresses",
                all(item.content_address.startswith("sha256:") for item in value.operations),
                len(value.operations),
                REFERENCE_ARCHITECTURE_OPERATION_COUNT,
                "operation specs are content addressed",
            ),
            _check(
                "case-addresses",
                all(item.content_address.startswith("sha256:") for item in value.cases),
                len(value.cases),
                REFERENCE_ARCHITECTURE_CASE_COUNT,
                "case declarations are content addressed",
            ),
            _check(
                "scenario-balance",
                _scenario_balance(value),
                _scenario_counts(value),
                "one positive plus three controls per operation",
                "scenario balance is closed",
            ),
            _check(
                "payload-scope",
                not _sensitive_paths(value.to_dict()),
                _sensitive_paths(value.to_dict()),
                "no direct identity fields",
                "aggregate reference mechanics remain bounded",
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
                    if item.scenario is ReferenceArchitectureScenario.FOREIGN_CONTEXT
                ),
                True,
                True,
                "foreign controls remain distinct from delegated context",
            ),
        )
    )
    accepted = all(item.passed for item in checks)
    body = {"fixture_id": value.fixture_id, "checks": checks, "accepted": accepted}
    return ReferenceArchitectureDataAudit(
        value.fixture_id, tuple(checks), accepted, addressed(body, "reference-data-audit")
    )


def load_reference_architecture_mapping(path: str | Path | None = None) -> dict[str, Any]:
    """Return a JSON-compatible fixture mapping for API callers."""

    return jsonable(default_reference_architecture_fixture(path).to_dict())


def _scenario_counts(fixture: ReferenceArchitectureFixture) -> dict[str, int]:
    return {
        scenario.value: sum(item.scenario is scenario for item in fixture.cases)
        for scenario in ReferenceArchitectureScenario
    }


def _scenario_balance(fixture: ReferenceArchitectureFixture) -> bool:
    expected = set(ReferenceArchitectureScenario)
    return all(
        len([case for case in fixture.cases if case.operation_id == operation.operation_id]) == 4
        and {case.scenario for case in fixture.cases if case.operation_id == operation.operation_id}
        == expected
        for operation in fixture.operations
    )


def _repository_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / REFERENCE_ARCHITECTURE_FIXTURE_FILE


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> ReferenceArchitectureCheck:
    kind = (
        ReferenceArchitectureCheckKind.SOURCE
        if check_id.startswith("source")
        else ReferenceArchitectureCheckKind.FIXTURE
    )
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceArchitectureCheck(
        check_id, kind, passed, observed, required, detail, addressed(body, "reference-data-check")
    )


def _sensitive_paths(value: Any, path: str = "fixture") -> tuple[str, ...]:
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
    "REFERENCE_ARCHITECTURE_FIXTURE_FILE",
    "audit_reference_architecture_data",
    "default_reference_architecture_fixture",
    "load_reference_architecture_mapping",
    "reference_architecture_fixture_json",
]
