"""Public aggregate fixture and source audit for the composed D02 boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .serialization import canonical_json, jsonable
from .structural_architecture_contracts import (
    STRUCTURAL_ARCHITECTURE_CASE_COUNT,
    STRUCTURAL_ARCHITECTURE_CONTEXT,
    STRUCTURAL_ARCHITECTURE_OPERATION_COUNT,
    StructuralArchitectureCheck,
    StructuralArchitectureCheckKind,
    StructuralArchitectureDataAudit,
    StructuralArchitectureFixture,
    StructuralArchitectureScenario,
    addressed,
)

ARCHITECTURE_FIXTURE_FILE = "structural-architecture-public-aggregate.json"


def default_structural_architecture_fixture(
    path: str | Path | None = None,
) -> StructuralArchitectureFixture:
    """Load the checked-in aggregate D02 fixture.

    The fixture is intentionally kept beside the repository examples so the
    exact source receipts and operation payloads are reviewable without a
    service dependency.  Callers can supply another path for offline replay.
    """

    fixture_path = Path(path) if path is not None else _repository_fixture_path()
    return StructuralArchitectureFixture.from_file(fixture_path)


def structural_architecture_fixture_json(
    fixture: StructuralArchitectureFixture | None = None,
) -> str:
    """Return canonical JSON for export and content-address verification."""

    return canonical_json((fixture or default_structural_architecture_fixture()).to_dict())


def audit_structural_architecture_data(
    fixture: StructuralArchitectureFixture | None = None,
) -> StructuralArchitectureDataAudit:
    """Audit source scope, operation coverage, case identity, and boundaries."""

    value = fixture or default_structural_architecture_fixture()
    checks: list[StructuralArchitectureCheck] = []
    checks.append(
        _check("fixture-version", True, value.version, "supported", "fixture version is closed")
    )
    checks.append(
        _check("fixture-boundary", True, value.boundary, "closed", "boundary is explicit")
    )
    checks.append(
        _check(
            "fixture-context",
            value.context_key == STRUCTURAL_ARCHITECTURE_CONTEXT
            and value.context_key.count("|") == 5,
            value.context_key,
            STRUCTURAL_ARCHITECTURE_CONTEXT,
            "one six-field context anchors every operation",
        )
    )
    checks.append(
        _check(
            "source-count",
            len(value.sources) >= 6 and len(value.source_ids) == len(value.sources),
            len(value.sources),
            ">=6 unique public sources",
            "source receipts are unique and aggregate",
        )
    )
    checks.append(
        _check(
            "source-scope",
            all(
                source.uri.startswith("https://") and source.scope == "public_aggregate"
                for source in value.sources
            ),
            tuple(source.source_id for source in value.sources),
            "HTTPS public aggregate receipts",
            "sources contain no local or subject-level scope",
        )
    )
    checks.append(
        _check(
            "operation-count",
            len(value.operations) == STRUCTURAL_ARCHITECTURE_OPERATION_COUNT,
            len(value.operations),
            STRUCTURAL_ARCHITECTURE_OPERATION_COUNT,
            "all C01-C16 operation specs are present",
        )
    )
    checks.append(
        _check(
            "case-count",
            len(value.cases) == STRUCTURAL_ARCHITECTURE_CASE_COUNT,
            len(value.cases),
            STRUCTURAL_ARCHITECTURE_CASE_COUNT,
            "each operation has one positive and three controls",
        )
    )
    checks.append(
        _check(
            "operation-case-join",
            all(
                case.operation_id in {item.operation_id for item in value.operations}
                for case in value.cases
            ),
            tuple(sorted({case.operation_id for case in value.cases})),
            tuple(sorted(value.operation_ids)),
            "every case joins to a declared operation",
        )
    )
    checks.append(
        _check(
            "case-identity",
            len({case.case_id for case in value.cases}) == len(value.cases),
            len({case.case_id for case in value.cases}),
            len(value.cases),
            "case IDs are deterministic and unique",
        )
    )
    checks.append(
        _check(
            "positive-controls",
            all(
                sum(
                    case.scenario is StructuralArchitectureScenario.POSITIVE
                    for case in value.cases
                    if case.operation == operation
                )
                == 1
                for operation in value.operation_ids
            ),
            tuple(
                sum(
                    case.scenario is StructuralArchitectureScenario.POSITIVE
                    for case in value.cases
                    if case.operation.value == operation
                )
                for operation in value.operation_ids
            ),
            "one positive per operation",
            "positive and control scenarios are balanced",
        )
    )
    checks.append(
        _check(
            "payload-scope",
            not _sensitive_paths(value.to_dict()),
            _sensitive_paths(value.to_dict()),
            "no subject-level fields",
            "fixture payloads remain aggregate mechanics data",
        )
    )
    accepted = all(item.passed for item in checks)
    body = {"fixture_id": value.fixture_id, "checks": checks, "accepted": accepted}
    return StructuralArchitectureDataAudit(
        fixture_id=value.fixture_id,
        checks=tuple(checks),
        accepted=accepted,
        content_address=addressed(body, "structural-data-audit"),
    )


def load_structural_architecture_mapping(path: str | Path) -> dict[str, Any]:
    """Read a fixture mapping for callers that need a plain JSON boundary."""

    fixture = default_structural_architecture_fixture(path)
    return jsonable(fixture.to_dict())


def _repository_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / ARCHITECTURE_FIXTURE_FILE


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> StructuralArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": StructuralArchitectureCheckKind.SOURCE
        if check_id.startswith("source")
        else StructuralArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return StructuralArchitectureCheck(
        **body,
        content_address=addressed(body, "structural-data-check"),
    )


def _sensitive_paths(value: Any, path: str = "fixture") -> tuple[str, ...]:
    """Find common subject-level keys without inspecting values."""

    forbidden = {"patient_id", "subject_id", "individual_id", "mrn", "specimen_id", "sample_name"}
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in forbidden:
                found.append(child)
            found.extend(_sensitive_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_sensitive_paths(item, f"{path}[{index}]"))
    return tuple(found)


__all__ = [
    "ARCHITECTURE_FIXTURE_FILE",
    "audit_structural_architecture_data",
    "default_structural_architecture_fixture",
    "load_structural_architecture_mapping",
    "structural_architecture_fixture_json",
]
