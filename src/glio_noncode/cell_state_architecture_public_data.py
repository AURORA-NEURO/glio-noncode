"""Public aggregate data contract for D08 cell state, disease, and territory."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import evaluate_cell_context_alpha_frontier_fixture
from .cell_context_alpha_frontier_public_data import default_cell_context_alpha_frontier_fixture
from .cell_context_beta_frontier_fixture_eval import evaluate_cell_context_beta_frontier_fixture
from .cell_context_beta_frontier_public_data import default_cell_context_beta_frontier_fixture
from .cell_context_frontier_fixture_eval import evaluate_cell_context_frontier_fixture
from .cell_context_frontier_public_data import default_cell_context_frontier_fixture
from .cell_state_architecture_contracts import (
    CELL_STATE_ARCHITECTURE_BOUNDARY,
    CELL_STATE_ARCHITECTURE_CONTEXT,
    CELL_STATE_ARCHITECTURE_FOREIGN_CONTEXT,
    CELL_STATE_ARCHITECTURE_VERSION,
    CellStateArchitectureCase,
    CellStateArchitectureCheck,
    CellStateArchitectureCheckKind,
    CellStateArchitectureDataAudit,
    CellStateArchitectureFamily,
    CellStateArchitectureFixture,
    CellStateArchitectureOperation,
    CellStateArchitectureOperationSpec,
    CellStateArchitecturePlane,
    CellStateArchitectureScenario,
    CellStateArchitectureSource,
    CellStateArchitectureState,
    addressed,
)
from .cell_state_frontier_fixture_eval import evaluate_cell_state_frontier_fixture
from .cell_state_frontier_public_data import default_cell_state_frontier_fixture
from .serialization import jsonable

CELL_STATE_ARCHITECTURE_FIXTURE_FILE = "cell-state-architecture-public-aggregate.json"

_FAMILY_ORDER = (
    CellStateArchitectureFamily.CONTEXT,
    CellStateArchitectureFamily.BETA,
    CellStateArchitectureFamily.ALPHA,
    CellStateArchitectureFamily.STATE,
)
_FAMILY_PLANES = {
    CellStateArchitectureFamily.CONTEXT: CellStateArchitecturePlane.TAXONOMY,
    CellStateArchitectureFamily.BETA: CellStateArchitecturePlane.PRIOR,
    CellStateArchitectureFamily.ALPHA: CellStateArchitecturePlane.TERRITORY,
    CellStateArchitectureFamily.STATE: CellStateArchitecturePlane.CELL_STATE,
}
_FAMILY_OPERATIONS = {
    CellStateArchitectureFamily.CONTEXT: (
        CellStateArchitectureOperation.DISEASE_ONTOLOGY,
        CellStateArchitectureOperation.AGE_ROUTE,
        CellStateArchitectureOperation.MOLECULAR_STATE,
        CellStateArchitectureOperation.TERRITORY_ASSEMBLY,
    ),
    CellStateArchitectureFamily.BETA: (
        CellStateArchitectureOperation.DEVELOPMENTAL_LINEAGE,
        CellStateArchitectureOperation.GBM_MALIGNANT_STATE,
        CellStateArchitectureOperation.IDH_MUTANT_LINEAGE,
        CellStateArchitectureOperation.H3K27_DEVELOPMENTAL_STATE,
    ),
    CellStateArchitectureFamily.ALPHA: (
        CellStateArchitectureOperation.SPATIAL_NICHE,
        CellStateArchitectureOperation.CORE_MARGIN,
        CellStateArchitectureOperation.RECURRENCE_STATE,
        CellStateArchitectureOperation.TREATMENT_INDUCED,
    ),
    CellStateArchitectureFamily.STATE: (
        CellStateArchitectureOperation.ABUNDANCE_INTERVAL,
        CellStateArchitectureOperation.REFERENCE_MAPPING,
        CellStateArchitectureOperation.OOD_DETECTION,
        CellStateArchitectureOperation.CONTEXT_PUBLICATION,
    ),
}


def _family_fixture_map() -> dict[CellStateArchitectureFamily, Any]:
    return {
        CellStateArchitectureFamily.CONTEXT: default_cell_context_frontier_fixture(),
        CellStateArchitectureFamily.BETA: default_cell_context_beta_frontier_fixture(),
        CellStateArchitectureFamily.ALPHA: default_cell_context_alpha_frontier_fixture(),
        CellStateArchitectureFamily.STATE: default_cell_state_frontier_fixture(),
    }


def _family_evaluation_map(
    fixtures: Mapping[CellStateArchitectureFamily, Any],
) -> dict[CellStateArchitectureFamily, Any]:
    return {
        CellStateArchitectureFamily.CONTEXT: evaluate_cell_context_frontier_fixture(
            fixtures[CellStateArchitectureFamily.CONTEXT]
        ),
        CellStateArchitectureFamily.BETA: evaluate_cell_context_beta_frontier_fixture(
            fixtures[CellStateArchitectureFamily.BETA]
        ),
        CellStateArchitectureFamily.ALPHA: evaluate_cell_context_alpha_frontier_fixture(
            fixtures[CellStateArchitectureFamily.ALPHA]
        ),
        CellStateArchitectureFamily.STATE: evaluate_cell_state_frontier_fixture(
            fixtures[CellStateArchitectureFamily.STATE]
        ),
    }


def _record_dict(record: Any) -> dict[str, Any]:
    try:
        return dict(record.to_dict(include_payload=True))
    except TypeError:
        return dict(record.to_dict())


def _source_registry(
    fixtures: Mapping[CellStateArchitectureFamily, Any],
) -> tuple[
    tuple[CellStateArchitectureSource, ...], dict[tuple[CellStateArchitectureFamily, str], str]
]:
    sources: list[CellStateArchitectureSource] = []
    mapping: dict[tuple[CellStateArchitectureFamily, str], str] = {}
    for family in _FAMILY_ORDER:
        for source in fixtures[family].sources:
            raw = jsonable(source)
            original_id = str(raw["source_id"])
            source_id = f"{family.value}:{original_id}"
            mapping[(family, original_id)] = source_id
            body = {
                "source_id": source_id,
                "family": family,
                "title": str(raw.get("title", original_id)),
                "uri": str(raw.get("uri", "https://example.org/public-source")),
                "version": str(raw.get("release", raw.get("version", "public"))),
                "scope": "public_aggregate",
                "license": "public source receipt",
                "public_aggregate": True,
            }
            sources.append(
                CellStateArchitectureSource(
                    **body, content_address=addressed(body, "cell-state-source")
                )
            )
    return tuple(sources), mapping


def _positive_metadata(
    evaluations: Mapping[CellStateArchitectureFamily, Any],
) -> dict[tuple[CellStateArchitectureFamily, str], tuple[str, tuple[str, ...], dict[str, Any]]]:
    result: dict[
        tuple[CellStateArchitectureFamily, str], tuple[str, tuple[str, ...], dict[str, Any]]
    ] = {}
    for family in _FAMILY_ORDER:
        evaluation = evaluations[family]
        rows = tuple(
            getattr(evaluation, "executions", None)
            or getattr(evaluation, "records", None)
            or getattr(evaluation, "receipts", None)
            or ()
        )
        for row in rows:
            role = str(getattr(getattr(row, "role", None), "value", getattr(row, "role", None)))
            if role != "positive":
                continue
            adapter = getattr(row, "adapter", row)
            state = (
                getattr(adapter, "state", None)
                or getattr(row, "observed_state", None)
                or "supported"
            )
            issues = getattr(adapter, "issue_codes", None) or getattr(
                row, "observed_issue_codes", ()
            )
            result[(family, str(row.record_id))] = (
                str(getattr(state, "value", state)),
                tuple(str(item) for item in issues),
                _sanitize(jsonable(row)),
            )
    return result


def _state_payload(ordinal: int) -> dict[str, Any]:
    if ordinal == 13:
        return {
            "records": [
                {
                    "context_key": CELL_STATE_ARCHITECTURE_CONTEXT,
                    "count": 40,
                    "sample_id": "aggregate-sample-a",
                    "state_id": "stem_like",
                    "total_cells": 100,
                }
            ],
            "interval_multiplier": 1.96,
        }
    if ordinal == 14:
        return {
            "records": [
                {
                    "cell_id": "aggregate-cell-001",
                    "context_key": CELL_STATE_ARCHITECTURE_CONTEXT,
                    "reference_scores": {"differentiated": 0.2, "stem_like": 0.92},
                }
            ],
            "minimum_score": 0.6,
            "minimum_margin": 0.1,
        }
    if ordinal == 15:
        return {
            "records": [
                {
                    "cell_id": "aggregate-cell-in-domain",
                    "context_key": CELL_STATE_ARCHITECTURE_CONTEXT,
                    "distance": 0.5,
                    "support_boundary": 3.0,
                    "support_score": 0.9,
                }
            ],
            "maximum_distance": 3.0,
            "minimum_support": 0.5,
        }
    return {
        "context_key": CELL_STATE_ARCHITECTURE_CONTEXT,
        "cell_ids": ["aggregate-cell-001", "aggregate-cell-002"],
        "mapping_address": "sha256:aggregate-mapping",
        "abundance_address": "sha256:aggregate-abundance",
        "ood_address": "sha256:aggregate-ood",
        "envelope_id": "d08-public-cell-state-release",
    }


def _sanitize(value: Any) -> Any:
    hidden = {
        "payload",
        "input_text",
        "track_text",
        "raw_text",
        "records_text",
        "subject_id",
        "patient_id",
        "participant_id",
        "individual_id",
    }
    if isinstance(value, Mapping):
        return {str(key): _sanitize(item) for key, item in value.items() if str(key) not in hidden}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def _case(
    operation: CellStateArchitectureOperationSpec,
    scenario: CellStateArchitectureScenario,
    context_key: str,
    source_ids: tuple[str, ...],
    delegate_context_key: str,
    payload: dict[str, Any],
    expected_state: CellStateArchitectureState,
    expected_result_state: str,
    expected_issue_codes: tuple[str, ...],
    expected_counts: dict[str, int],
    description: str,
) -> CellStateArchitectureCase:
    body = {
        "case_id": f"{operation.operation_id}-{scenario.value}",
        "operation_id": operation.operation_id,
        "capability_id": operation.capability_id,
        "operation": operation.operation,
        "family": operation.family,
        "plane": operation.plane,
        "scenario": scenario,
        "context_key": context_key,
        "delegate_context_key": delegate_context_key,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_result_state": expected_result_state,
        "expected_issue_codes": expected_issue_codes,
        "expected_counts": expected_counts,
        "description": description,
    }
    return CellStateArchitectureCase(**body, content_address=addressed(body, "cell-state-case"))


def _operations(
    fixtures: Mapping[CellStateArchitectureFamily, Any],
    source_maps: Mapping[tuple[CellStateArchitectureFamily, str], str],
) -> tuple[CellStateArchitectureOperationSpec, ...]:
    operations: list[CellStateArchitectureOperationSpec] = []
    ordinal = 0
    for family in _FAMILY_ORDER:
        source_ids = tuple(
            sorted(
                source_maps[(family, str(source.source_id))] for source in fixtures[family].sources
            )
        )
        for operation in _FAMILY_OPERATIONS[family]:
            ordinal += 1
            body = {
                "operation_id": f"D08-C{ordinal:02d}",
                "capability_id": f"GNC-D08-C{ordinal:02d}",
                "ordinal": ordinal,
                "operation": operation,
                "family": family,
                "plane": _FAMILY_PLANES[family],
                "input_contract": f"cell_state.{operation.value}.public_record.v1",
                "output_contract": f"cell_state.{operation.value}.receipt.v1",
                "dependencies": (f"D08-C{ordinal - 1:02d}",) if ordinal > 1 else (),
                "source_ids": source_ids,
                "control_policy": (
                    "hold context mismatch, malformed input, and identity conflict "
                    "before delegation"
                ),
            }
            operations.append(
                CellStateArchitectureOperationSpec(
                    **body, content_address=addressed(body, "cell-state-operation")
                )
            )
    return tuple(operations)


def _cases(
    fixtures: Mapping[CellStateArchitectureFamily, Any],
    operations: tuple[CellStateArchitectureOperationSpec, ...],
    source_maps: Mapping[tuple[CellStateArchitectureFamily, str], str],
    metadata: Mapping[
        tuple[CellStateArchitectureFamily, str], tuple[str, tuple[str, ...], dict[str, Any]]
    ],
) -> tuple[CellStateArchitectureCase, ...]:
    cases: list[CellStateArchitectureCase] = []
    for operation in operations:
        family = operation.family
        records = fixtures[family].positive_records
        record = records[list(_FAMILY_OPERATIONS[family]).index(operation.operation)]
        record_dict = _record_dict(record)
        source_ids = tuple(source_maps[(family, str(source_id))] for source_id in record.source_ids)
        result_state, issue_codes, summary = metadata.get(
            (family, str(record.record_id)), ("supported", (), {})
        )
        operation_payload = (
            _state_payload(operation.ordinal)
            if family is CellStateArchitectureFamily.STATE
            else record_dict.get("payload", record_dict)
        )
        if family is CellStateArchitectureFamily.STATE:
            result_state = "published" if operation.ordinal == 16 else "accepted"
            issue_codes = ()
        positive_payload = {
            "family_record_id": str(record.record_id),
            "family_context_key": str(
                getattr(record, "context_key", CELL_STATE_ARCHITECTURE_CONTEXT)
            ),
            "family_record": record_dict,
            "family_summary": summary,
            "operation_payload": operation_payload,
        }
        cases.append(
            _case(
                operation,
                CellStateArchitectureScenario.POSITIVE,
                CELL_STATE_ARCHITECTURE_CONTEXT,
                source_ids,
                str(getattr(record, "context_key", CELL_STATE_ARCHITECTURE_CONTEXT)),
                positive_payload,
                CellStateArchitectureState.ACCEPTED,
                result_state,
                issue_codes,
                {"primary": 1, "secondary": 1},
                f"public aggregate positive path for {operation.capability_id}",
            )
        )
        controls = (
            (
                CellStateArchitectureScenario.FOREIGN_CONTEXT,
                CELL_STATE_ARCHITECTURE_FOREIGN_CONTEXT,
                "out_of_domain",
                ("context_mismatch",),
                "foreign context is held before family execution",
            ),
            (
                CellStateArchitectureScenario.MALFORMED_INPUT,
                CELL_STATE_ARCHITECTURE_CONTEXT,
                "invalid",
                ("malformed_input",),
                "malformed aggregate input is held before family execution",
            ),
            (
                CellStateArchitectureScenario.IDENTITY_CONFLICT,
                CELL_STATE_ARCHITECTURE_CONTEXT,
                "contradictory",
                ("identity_conflict",),
                "identity conflict is held before family execution",
            ),
        )
        for scenario, control_context, state, codes, detail in controls:
            control_payload = {
                "family_record_id": str(record.record_id),
                "operation_payload": operation_payload,
                "control": scenario.value,
                "malformed": scenario is CellStateArchitectureScenario.MALFORMED_INPUT,
                "identity_conflict": scenario is CellStateArchitectureScenario.IDENTITY_CONFLICT,
            }
            cases.append(
                _case(
                    operation,
                    scenario,
                    control_context,
                    source_ids,
                    str(getattr(record, "context_key", CELL_STATE_ARCHITECTURE_CONTEXT)),
                    control_payload,
                    CellStateArchitectureState.REVIEW,
                    state,
                    codes,
                    {"primary": 0, "secondary": 0},
                    detail,
                )
            )
    return tuple(cases)


def default_cell_state_architecture_fixture(
    path: str | Path | None = None,
) -> CellStateArchitectureFixture:
    if path is not None:
        return CellStateArchitectureFixture.from_file(path)
    fixtures = _family_fixture_map()
    evaluations = _family_evaluation_map(fixtures)
    sources, source_maps = _source_registry(fixtures)
    operations = _operations(fixtures, source_maps)
    cases = _cases(fixtures, operations, source_maps, _positive_metadata(evaluations))
    body = {
        "fixture_id": "d08-cell-state-architecture-public-aggregate",
        "version": CELL_STATE_ARCHITECTURE_VERSION,
        "boundary": CELL_STATE_ARCHITECTURE_BOUNDARY,
        "context_key": CELL_STATE_ARCHITECTURE_CONTEXT,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return CellStateArchitectureFixture(
        **body, content_address=addressed(body, "cell-state-fixture")
    )


def cell_state_architecture_fixture_json(
    fixture: CellStateArchitectureFixture | None = None,
) -> str:
    return (
        json.dumps(
            (fixture or default_cell_state_architecture_fixture()).to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def load_cell_state_architecture_mapping(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("D08 cell state architecture JSON must be an object")
    return dict(raw)


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> CellStateArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": CellStateArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CellStateArchitectureCheck(**body, content_address=addressed(body, "cell-state-check"))


def _scenario_counts(fixture: CellStateArchitectureFixture) -> dict[str, int]:
    return {
        scenario.value: sum(item.scenario is scenario for item in fixture.cases)
        for scenario in CellStateArchitectureScenario
    }


def audit_cell_state_architecture_data(
    fixture: CellStateArchitectureFixture,
) -> CellStateArchitectureDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    checks = (
        _check(
            "fixture-version",
            fixture.version == CELL_STATE_ARCHITECTURE_VERSION,
            fixture.version,
            CELL_STATE_ARCHITECTURE_VERSION,
            "D08 version is pinned",
        ),
        _check(
            "fixture-boundary",
            fixture.boundary == CELL_STATE_ARCHITECTURE_BOUNDARY,
            fixture.boundary,
            CELL_STATE_ARCHITECTURE_BOUNDARY,
            "D08 is public aggregate cell-state data",
        ),
        _check(
            "fixture-context",
            fixture.context_key == CELL_STATE_ARCHITECTURE_CONTEXT,
            fixture.context_key,
            CELL_STATE_ARCHITECTURE_CONTEXT,
            "aggregate context is exact",
        ),
        _check(
            "source-count",
            len(fixture.sources) == 18,
            len(fixture.sources),
            18,
            "four family registries conserve eighteen sources",
        ),
        _check(
            "operation-count",
            len(fixture.operations) == 16,
            len(fixture.operations),
            16,
            "all D08 capabilities have operation specifications",
        ),
        _check(
            "case-count",
            len(fixture.cases) == 64,
            len(fixture.cases),
            64,
            "four cases are present for every operation",
        ),
        _check(
            "source-joins",
            all(
                set(item.source_ids) <= source_ids for item in (*fixture.operations, *fixture.cases)
            ),
            sum(
                set(item.source_ids) <= source_ids for item in (*fixture.operations, *fixture.cases)
            ),
            80,
            "source joins resolve for operations and cases",
        ),
        _check(
            "operation-uniqueness",
            len(operation_ids) == 16,
            len(operation_ids),
            16,
            "operation IDs are unique",
        ),
        _check(
            "case-uniqueness",
            len({item.case_id for item in fixture.cases}) == 64,
            len({item.case_id for item in fixture.cases}),
            64,
            "case IDs are unique",
        ),
        _check(
            "positive-control-balance",
            (len(fixture.positive_cases), len(fixture.control_cases)) == (16, 48),
            (len(fixture.positive_cases), len(fixture.control_cases)),
            (16, 48),
            "positive and control paths are explicit",
        ),
        _check(
            "scenario-balance",
            _scenario_counts(fixture)
            == {scenario.value: 16 for scenario in CellStateArchitectureScenario},
            _scenario_counts(fixture),
            {scenario.value: 16 for scenario in CellStateArchitectureScenario},
            "each operation has one positive and three controls",
        ),
        _check(
            "source-addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.sources),
            sum(item.content_address.startswith("sha256:") for item in fixture.sources),
            18,
            "public source receipts are addressed",
        ),
        _check(
            "operation-addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.operations),
            sum(item.content_address.startswith("sha256:") for item in fixture.operations),
            16,
            "operation contracts are addressed",
        ),
        _check(
            "case-addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.cases),
            sum(item.content_address.startswith("sha256:") for item in fixture.cases),
            64,
            "case contracts are addressed",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return CellStateArchitectureDataAudit(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "cell-state-audit"),
    )


__all__ = [
    "CELL_STATE_ARCHITECTURE_FIXTURE_FILE",
    "audit_cell_state_architecture_data",
    "cell_state_architecture_fixture_json",
    "default_cell_state_architecture_fixture",
    "load_cell_state_architecture_mapping",
]
