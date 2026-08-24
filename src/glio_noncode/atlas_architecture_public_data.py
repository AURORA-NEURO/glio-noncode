"""Public aggregate D05 fixture built from the four atlas family fixtures.

The source fixtures are compact public receipts already maintained by the
regulatory, molecular, alpha-evidence, and frontier modules. This module
normalizes their positive records into one D05 boundary and adds explicit
architecture-level controls. No upstream archive is copied into the fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .atlas_alpha_evidence_fixture_eval import evaluate_atlas_alpha_evidence_fixture
from .atlas_alpha_evidence_public_data import default_atlas_alpha_evidence_fixture
from .atlas_architecture_contracts import (
    ATLAS_ARCHITECTURE_BOUNDARY,
    ATLAS_ARCHITECTURE_CASE_COUNT,
    ATLAS_ARCHITECTURE_CONTEXT,
    ATLAS_ARCHITECTURE_FOREIGN_CONTEXT,
    ATLAS_ARCHITECTURE_OPERATION_COUNT,
    ATLAS_ARCHITECTURE_SOURCE_COUNT,
    ATLAS_ARCHITECTURE_VERSION,
    AtlasArchitectureCase,
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    AtlasArchitectureDataAudit,
    AtlasArchitectureFamily,
    AtlasArchitectureFixture,
    AtlasArchitectureOperation,
    AtlasArchitectureOperationSpec,
    AtlasArchitecturePlane,
    AtlasArchitectureScenario,
    AtlasArchitectureSource,
    AtlasArchitectureState,
    addressed,
)
from .frontier_atlas_fixture_eval import evaluate_frontier_atlas_fixture
from .frontier_atlas_public_data import default_frontier_atlas_fixture
from .molecular_atlas_fixture_eval import evaluate_molecular_atlas_fixture
from .molecular_atlas_public_data import default_molecular_atlas_fixture
from .regulatory_atlas_fixture_eval import evaluate_regulatory_atlas_fixture
from .regulatory_atlas_public_data import default_regulatory_atlas_fixture
from .serialization import canonical_json

ATLAS_ARCHITECTURE_FIXTURE_FILE = "atlas-architecture-public-aggregate.json"

_FAMILY_ORDER = (
    AtlasArchitectureFamily.REGULATORY,
    AtlasArchitectureFamily.MOLECULAR,
    AtlasArchitectureFamily.ALPHA_EVIDENCE,
    AtlasArchitectureFamily.FRONTIER,
)
_FAMILY_PLANES = {
    AtlasArchitectureFamily.REGULATORY: AtlasArchitecturePlane.REGULATORY,
    AtlasArchitectureFamily.MOLECULAR: AtlasArchitecturePlane.MOLECULAR,
    AtlasArchitectureFamily.ALPHA_EVIDENCE: AtlasArchitecturePlane.EVIDENCE,
    AtlasArchitectureFamily.FRONTIER: AtlasArchitecturePlane.FRONTIER,
}
_CONTROL_RESULT = {
    AtlasArchitectureScenario.FOREIGN_CONTEXT: "out_of_domain",
    AtlasArchitectureScenario.MALFORMED_INPUT: "invalid",
    AtlasArchitectureScenario.IDENTITY_CONFLICT: "contradictory",
}
_CONTROL_ISSUE = {
    AtlasArchitectureScenario.FOREIGN_CONTEXT: "context_mismatch",
    AtlasArchitectureScenario.MALFORMED_INPUT: "malformed_input",
    AtlasArchitectureScenario.IDENTITY_CONFLICT: "identity_conflict",
}


def default_atlas_architecture_fixture(path: str | Path | None = None) -> AtlasArchitectureFixture:
    """Build the D05 fixture or load a caller-supplied canonical export."""

    if path is not None:
        return AtlasArchitectureFixture.from_file(path)
    return _build_default_fixture()


def load_atlas_architecture_mapping(path: str | Path | None = None) -> dict[str, Any]:
    """Return a JSON-compatible D05 fixture mapping."""

    fixture = default_atlas_architecture_fixture(path)
    return fixture.to_dict()


def atlas_architecture_fixture_json(fixture: AtlasArchitectureFixture | None = None) -> str:
    """Return deterministic JSON for export, replay, and bundle use."""

    return canonical_json((fixture or default_atlas_architecture_fixture()).to_dict())


def audit_atlas_architecture_data(
    fixture: AtlasArchitectureFixture | None = None,
) -> AtlasArchitectureDataAudit:
    """Audit source receipts, operation joins, scenario balance, and scope."""

    value = fixture or default_atlas_architecture_fixture()
    operation_ids = {item.operation_id for item in value.operations}
    source_ids = set(value.source_ids)
    checks = (
        _check(
            "fixture-version",
            value.version == ATLAS_ARCHITECTURE_VERSION,
            value.version,
            ATLAS_ARCHITECTURE_VERSION,
            "D05 version is closed",
        ),
        _check(
            "fixture-boundary",
            value.boundary == ATLAS_ARCHITECTURE_BOUNDARY,
            value.boundary,
            ATLAS_ARCHITECTURE_BOUNDARY,
            "public aggregate atlas boundary is explicit",
        ),
        _check(
            "fixture-context",
            value.context_key == ATLAS_ARCHITECTURE_CONTEXT and value.context_key.count("|") == 5,
            value.context_key,
            ATLAS_ARCHITECTURE_CONTEXT,
            "six-field architecture context is exact",
        ),
        _check(
            "source-count",
            len(value.sources) == ATLAS_ARCHITECTURE_SOURCE_COUNT
            and len(source_ids) == len(value.sources),
            len(value.sources),
            ATLAS_ARCHITECTURE_SOURCE_COUNT,
            "twenty family source receipts are unique",
        ),
        _check(
            "source-scope",
            all(
                item.uri.startswith("https://")
                and item.scope == "public_aggregate"
                and bool(item.license)
                for item in value.sources
            ),
            tuple(item.source_id for item in value.sources),
            "HTTPS public aggregate source receipts",
            "source scope and licenses are explicit",
        ),
        _check(
            "operation-count",
            len(value.operations) == ATLAS_ARCHITECTURE_OPERATION_COUNT,
            len(value.operations),
            ATLAS_ARCHITECTURE_OPERATION_COUNT,
            "all D05 capabilities have operation cards",
        ),
        _check(
            "case-count",
            len(value.cases) == ATLAS_ARCHITECTURE_CASE_COUNT,
            len(value.cases),
            ATLAS_ARCHITECTURE_CASE_COUNT,
            "four contracts cover each operation",
        ),
        _check(
            "operation-joins",
            all(item.operation_id in operation_ids for item in value.cases),
            tuple(sorted({item.operation_id for item in value.cases})),
            tuple(sorted(operation_ids)),
            "cases resolve to operation cards",
        ),
        _check(
            "source-joins",
            all(set(item.source_ids).issubset(source_ids) for item in value.cases),
            tuple(sorted({source for item in value.cases for source in item.source_ids})),
            tuple(sorted(source_ids)),
            "cases resolve to source receipts",
        ),
        _check(
            "scenario-balance",
            _scenario_balance(value),
            _scenario_counts(value),
            "one positive plus three controls per operation",
            "scenario balance is closed",
        ),
        _check(
            "family-coverage",
            {item.family for item in value.operations} == set(_FAMILY_ORDER),
            tuple(sorted(item.family.value for item in value.operations)),
            tuple(item.value for item in _FAMILY_ORDER),
            "all four D05 adapter families are represented",
        ),
        _check(
            "address-coverage",
            all(
                item.content_address.startswith("sha256:")
                for item in (*value.sources, *value.operations, *value.cases)
            ),
            len(value.sources) + len(value.operations) + len(value.cases),
            ATLAS_ARCHITECTURE_SOURCE_COUNT
            + ATLAS_ARCHITECTURE_OPERATION_COUNT
            + ATLAS_ARCHITECTURE_CASE_COUNT,
            "all declarations are content addressed",
        ),
        _check(
            "payload-scope",
            not _sensitive_paths(value.to_dict()),
            _sensitive_paths(value.to_dict()),
            "no direct identity fields",
            "aggregate atlas mechanics remain bounded",
        ),
        _check(
            "public-markers",
            all(item.public_aggregate for item in value.sources),
            sum(item.public_aggregate for item in value.sources),
            ATLAS_ARCHITECTURE_SOURCE_COUNT,
            "every source carries an explicit public aggregate marker",
        ),
        _check(
            "delegate-contexts",
            all(bool(item.delegate_context_key) for item in value.cases),
            sum(bool(item.delegate_context_key) for item in value.cases),
            ATLAS_ARCHITECTURE_CASE_COUNT,
            "every case retains a delegated context key",
        ),
        _check(
            "foreign-context-controls",
            all(
                item.context_key != item.delegate_context_key
                for item in value.cases
                if item.scenario is AtlasArchitectureScenario.FOREIGN_CONTEXT
            ),
            True,
            True,
            "foreign controls remain distinct from delegated context",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"fixture_id": value.fixture_id, "checks": checks, "accepted": accepted}
    return AtlasArchitectureDataAudit(
        value.fixture_id,
        tuple(checks),
        accepted,
        addressed(body, "atlas-data-audit"),
    )


def _build_default_fixture() -> AtlasArchitectureFixture:
    family_inputs = (
        (
            AtlasArchitectureFamily.REGULATORY,
            default_regulatory_atlas_fixture(),
            evaluate_regulatory_atlas_fixture,
        ),
        (
            AtlasArchitectureFamily.MOLECULAR,
            default_molecular_atlas_fixture(),
            evaluate_molecular_atlas_fixture,
        ),
        (
            AtlasArchitectureFamily.ALPHA_EVIDENCE,
            default_atlas_alpha_evidence_fixture(),
            evaluate_atlas_alpha_evidence_fixture,
        ),
        (
            AtlasArchitectureFamily.FRONTIER,
            default_frontier_atlas_fixture(),
            evaluate_frontier_atlas_fixture,
        ),
    )
    sources: list[AtlasArchitectureSource] = []
    positive_cases: list[AtlasArchitectureCase] = []
    source_by_family: dict[AtlasArchitectureFamily, tuple[str, ...]] = {}
    for family, family_fixture, evaluator in family_inputs:
        family_source_ids: list[str] = []
        for source in family_fixture.sources:
            source_id = f"{family.value}:{source.source_id}"
            body = {
                "source_id": source_id,
                "family": family,
                "title": source.title,
                "uri": source.uri,
                "version": getattr(source, "release", "public-release"),
                "scope": "public_aggregate",
                "license": source.license,
                "public_aggregate": True,
            }
            sources.append(
                AtlasArchitectureSource(**body, content_address=addressed(body, "atlas-source"))
            )
            family_source_ids.append(source_id)
        source_by_family[family] = tuple(family_source_ids)
        evaluation = evaluator(family_fixture)
        receipt_by_id = {item.record_id: item for item in evaluation.receipts}
        for record in family_fixture.positive_records:
            capability_number = int(record.record_id.split("-")[0][1:])
            receipt = receipt_by_id[record.record_id]
            operation = AtlasArchitectureOperation(record.operation.value)
            payload = _normalize_payload(record.payload, family)
            body = {
                "case_id": f"D05-C{capability_number:02d}-POSITIVE",
                "operation_id": f"D05-C{capability_number:02d}",
                "capability_id": f"GNC-D05-C{capability_number:02d}",
                "operation": operation,
                "family": family,
                "scenario": AtlasArchitectureScenario.POSITIVE,
                "context_key": ATLAS_ARCHITECTURE_CONTEXT,
                "delegate_context_key": ATLAS_ARCHITECTURE_CONTEXT,
                "source_ids": family_source_ids,
                "payload": payload,
                "expected_state": AtlasArchitectureState.ACCEPTED,
                "expected_result_state": receipt.adapter_state,
                "expected_issue_codes": tuple(record.expected_issue_codes),
                "expected_counts": {
                    "primary_count": receipt.primary_count,
                    "secondary_count": receipt.secondary_count,
                },
                "description": record.description,
            }
            positive_cases.append(
                AtlasArchitectureCase(**body, content_address=addressed(body, "atlas-case"))
            )
    operations = _operation_specs(source_by_family)
    cases = list(positive_cases)
    for operation in operations:
        positive = next(
            item for item in positive_cases if item.operation_id == operation.operation_id
        )
        for scenario in (
            AtlasArchitectureScenario.FOREIGN_CONTEXT,
            AtlasArchitectureScenario.MALFORMED_INPUT,
            AtlasArchitectureScenario.IDENTITY_CONFLICT,
        ):
            body = {
                "case_id": f"{positive.operation_id}-{scenario.value}",
                "operation_id": positive.operation_id,
                "capability_id": positive.capability_id,
                "operation": positive.operation,
                "family": positive.family,
                "scenario": scenario,
                "context_key": (
                    ATLAS_ARCHITECTURE_FOREIGN_CONTEXT
                    if scenario is AtlasArchitectureScenario.FOREIGN_CONTEXT
                    else ATLAS_ARCHITECTURE_CONTEXT
                ),
                "delegate_context_key": ATLAS_ARCHITECTURE_CONTEXT,
                "source_ids": positive.source_ids,
                "payload": {
                    "aggregate_only": True,
                    "control_scenario": scenario.value,
                    "family": positive.family.value,
                    "operation": positive.operation.value,
                },
                "expected_state": AtlasArchitectureState.REVIEW,
                "expected_result_state": _CONTROL_RESULT[scenario],
                "expected_issue_codes": (_CONTROL_ISSUE[scenario],),
                "expected_counts": {},
                "description": f"D05 boundary control: {scenario.value}",
            }
            cases.append(
                AtlasArchitectureCase(**body, content_address=addressed(body, "atlas-case"))
            )
    fixture_body = {
        "fixture_id": "atlas-architecture-public-aggregate-v1",
        "version": ATLAS_ARCHITECTURE_VERSION,
        "boundary": ATLAS_ARCHITECTURE_BOUNDARY,
        "context_key": ATLAS_ARCHITECTURE_CONTEXT,
        "sources": tuple(sources),
        "operations": operations,
        "cases": tuple(cases),
    }
    return AtlasArchitectureFixture(
        **fixture_body,
        content_address=addressed(fixture_body, "atlas-fixture"),
    )


def _operation_specs(
    source_by_family: dict[AtlasArchitectureFamily, tuple[str, ...]],
) -> tuple[AtlasArchitectureOperationSpec, ...]:
    definitions = (
        (AtlasArchitectureFamily.REGULATORY, AtlasArchitectureOperation.CCRE_TRACK_PARSE),
        (AtlasArchitectureFamily.REGULATORY, AtlasArchitectureOperation.BRAIN_CELL_PROFILE),
        (AtlasArchitectureFamily.REGULATORY, AtlasArchitectureOperation.ADULT_GLIO_PROFILE),
        (AtlasArchitectureFamily.REGULATORY, AtlasArchitectureOperation.PEDIATRIC_GLIO_PROFILE),
        (AtlasArchitectureFamily.MOLECULAR, AtlasArchitectureOperation.IDH_MUTANT_PROFILE),
        (AtlasArchitectureFamily.MOLECULAR, AtlasArchitectureOperation.IDH_WILDTYPE_PROFILE),
        (AtlasArchitectureFamily.MOLECULAR, AtlasArchitectureOperation.H3K27_PROFILE),
        (AtlasArchitectureFamily.MOLECULAR, AtlasArchitectureOperation.HISTONE_HARMONIZATION),
        (
            AtlasArchitectureFamily.ALPHA_EVIDENCE,
            AtlasArchitectureOperation.OPEN_CHROMATIN_HARMONIZATION,
        ),
        (
            AtlasArchitectureFamily.ALPHA_EVIDENCE,
            AtlasArchitectureOperation.METHYLATION_HARMONIZATION,
        ),
        (
            AtlasArchitectureFamily.ALPHA_EVIDENCE,
            AtlasArchitectureOperation.REGULATORY_ROLE_CLASSIFICATION,
        ),
        (AtlasArchitectureFamily.ALPHA_EVIDENCE, AtlasArchitectureOperation.SUPER_ENHANCER_ATLAS),
        (AtlasArchitectureFamily.FRONTIER, AtlasArchitectureOperation.BOUNDARY_ATLAS),
        (AtlasArchitectureFamily.FRONTIER, AtlasArchitectureOperation.HOTSPOT_ATLAS),
        (AtlasArchitectureFamily.FRONTIER, AtlasArchitectureOperation.EVIDENCE_TIER),
        (AtlasArchitectureFamily.FRONTIER, AtlasArchitectureOperation.SNAPSHOT_PUBLISH),
    )
    nodes: list[AtlasArchitectureOperationSpec] = []
    for ordinal, (family, operation) in enumerate(definitions, start=1):
        operation_id = f"D05-C{ordinal:02d}"
        body = {
            "operation_id": operation_id,
            "capability_id": f"GNC-D05-C{ordinal:02d}",
            "ordinal": ordinal,
            "operation": operation,
            "family": family,
            "plane": _FAMILY_PLANES[family],
            "input_contract": f"{family.value}.public_aggregate_input",
            "output_contract": "atlas_architecture.sanitized_receipt",
            "dependencies": tuple(f"D05-C{index:02d}" for index in range(1, ordinal)),
            "source_ids": source_by_family[family],
            "control_policy": "exact_context_positive_or_hold_explicit_control",
        }
        nodes.append(
            AtlasArchitectureOperationSpec(
                **body,
                content_address=addressed(body, "atlas-operation"),
            )
        )
    return tuple(nodes)


def _normalize_payload(payload: dict[str, Any], family: AtlasArchitectureFamily) -> dict[str, Any]:
    """Copy a positive payload and align frontier row contexts to D05."""

    result = dict(payload)
    if family is not AtlasArchitectureFamily.FRONTIER:
        return result
    raw = result.get("input_text")
    if not isinstance(raw, str):
        return result
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return result
    rows = parsed.get("records") if isinstance(parsed, dict) else None
    if not isinstance(rows, list):
        return result
    result["input_text"] = json.dumps(
        {
            **parsed,
            "records": [{**row, "context_key": ATLAS_ARCHITECTURE_CONTEXT} for row in rows],
        },
        sort_keys=True,
    )
    return result


def _scenario_counts(fixture: AtlasArchitectureFixture) -> dict[str, int]:
    return {
        scenario.value: sum(item.scenario is scenario for item in fixture.cases)
        for scenario in AtlasArchitectureScenario
    }


def _scenario_balance(fixture: AtlasArchitectureFixture) -> bool:
    expected = {item.value for item in AtlasArchitectureScenario}
    return all(
        {item.scenario.value for item in fixture.cases if item.operation_id == operation}
        == expected
        for operation in {item.operation_id for item in fixture.operations}
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
            next_path = f"{path}.{key}"
            if str(key).lower() in forbidden:
                found.append(next_path)
            found.extend(_sensitive_paths(item, next_path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_sensitive_paths(item, f"{path}[{index}]"))
    return tuple(found)


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id,
        AtlasArchitectureCheckKind.FIXTURE,
        passed,
        observed,
        required,
        detail,
        addressed(body, "atlas-data-check"),
    )


__all__ = [
    "ATLAS_ARCHITECTURE_FIXTURE_FILE",
    "atlas_architecture_fixture_json",
    "audit_atlas_architecture_data",
    "default_atlas_architecture_fixture",
    "load_atlas_architecture_mapping",
]
