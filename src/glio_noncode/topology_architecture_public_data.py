"""Public aggregate fixture composing all D09 topology tranches."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .serialization import jsonable
from .topology_alpha_frontier_fixture_eval import evaluate_topology_alpha_frontier_fixture
from .topology_alpha_frontier_public_data import default_topology_alpha_frontier_fixture
from .topology_architecture_contracts import (
    TOPOLOGY_ARCHITECTURE_BOUNDARY,
    TOPOLOGY_ARCHITECTURE_CONTEXT,
    TOPOLOGY_ARCHITECTURE_FOREIGN_CONTEXT,
    TOPOLOGY_ARCHITECTURE_VERSION,
    TopologyArchitectureCase,
    TopologyArchitectureCheck,
    TopologyArchitectureCheckKind,
    TopologyArchitectureDataAudit,
    TopologyArchitectureFamily,
    TopologyArchitectureFixture,
    TopologyArchitectureOperation,
    TopologyArchitectureOperationSpec,
    TopologyArchitecturePlane,
    TopologyArchitectureScenario,
    TopologyArchitectureSource,
    TopologyArchitectureState,
    addressed,
)
from .topology_beta_frontier_fixture_eval import evaluate_topology_beta_frontier_fixture
from .topology_beta_frontier_public_data import default_topology_beta_frontier_fixture
from .topology_context_frontier_fixture_eval import evaluate_topology_context_frontier_fixture
from .topology_context_frontier_public_data import default_topology_context_frontier_fixture
from .topology_frontier_fixture_eval import evaluate_topology_frontier_fixture
from .topology_frontier_public_data import default_topology_frontier_fixture

TOPOLOGY_ARCHITECTURE_FIXTURE_FILE = "topology-architecture-public-aggregate.json"

_FAMILY_ORDER = (
    TopologyArchitectureFamily.CONTEXT,
    TopologyArchitectureFamily.BETA,
    TopologyArchitectureFamily.ALPHA,
    TopologyArchitectureFamily.FRONTIER,
)
_FAMILY_PLANES = {
    TopologyArchitectureFamily.CONTEXT: TopologyArchitecturePlane.CONTEXT_QC,
    TopologyArchitectureFamily.BETA: TopologyArchitecturePlane.CONTACT_INFERENCE,
    TopologyArchitectureFamily.ALPHA: TopologyArchitecturePlane.TOPOLOGY_ALPHA,
    TopologyArchitectureFamily.FRONTIER: TopologyArchitecturePlane.FRONTIER_RELEASE,
}
_FAMILY_OPERATIONS = {
    TopologyArchitectureFamily.CONTEXT: (
        TopologyArchitectureOperation.CONTACT_IMPORT,
        TopologyArchitectureOperation.MATRIX_QC,
        TopologyArchitectureOperation.BOUNDARY_ENSEMBLE,
        TopologyArchitectureOperation.INSULATION_DELTA,
    ),
    TopologyArchitectureFamily.BETA: (
        TopologyArchitectureOperation.LOOP_STRIPE,
        TopologyArchitectureOperation.PROMOTER_CAPTURE,
        TopologyArchitectureOperation.ENHANCER_PROMOTER_CONTACT,
        TopologyArchitectureOperation.ACTIVITY_BY_CONTACT,
    ),
    TopologyArchitectureFamily.ALPHA: (
        TopologyArchitectureOperation.BOUNDARY_MOTIF,
        TopologyArchitectureOperation.CTCF_COHESIN,
        TopologyArchitectureOperation.IDH_INSULATOR,
        TopologyArchitectureOperation.SV_REWIRE,
    ),
    TopologyArchitectureFamily.FRONTIER: (
        TopologyArchitectureOperation.ECDNA_CONTACT,
        TopologyArchitectureOperation.COMPARTMENT_SWITCH,
        TopologyArchitectureOperation.TOPOLOGY_TRANSPORT,
        TopologyArchitectureOperation.EVIDENCE_PUBLICATION,
    ),
}


def _family_fixture_map() -> dict[TopologyArchitectureFamily, Any]:
    return {
        TopologyArchitectureFamily.CONTEXT: default_topology_context_frontier_fixture(),
        TopologyArchitectureFamily.BETA: default_topology_beta_frontier_fixture(),
        TopologyArchitectureFamily.ALPHA: default_topology_alpha_frontier_fixture(),
        TopologyArchitectureFamily.FRONTIER: default_topology_frontier_fixture(),
    }


def _family_evaluation_map(
    fixtures: Mapping[TopologyArchitectureFamily, Any],
) -> dict[TopologyArchitectureFamily, Any]:
    return {
        TopologyArchitectureFamily.CONTEXT: evaluate_topology_context_frontier_fixture(
            fixtures[TopologyArchitectureFamily.CONTEXT]
        ),
        TopologyArchitectureFamily.BETA: evaluate_topology_beta_frontier_fixture(
            fixtures[TopologyArchitectureFamily.BETA]
        ),
        TopologyArchitectureFamily.ALPHA: evaluate_topology_alpha_frontier_fixture(
            fixtures[TopologyArchitectureFamily.ALPHA]
        ),
        TopologyArchitectureFamily.FRONTIER: evaluate_topology_frontier_fixture(
            fixtures[TopologyArchitectureFamily.FRONTIER]
        ),
    }


def _rows(evaluation: Any) -> tuple[Any, ...]:
    return tuple(
        getattr(evaluation, "rows", None)
        or getattr(evaluation, "receipts", None)
        or getattr(evaluation, "executions", None)
        or ()
    )


def _record_dict(record: Any) -> dict[str, Any]:
    try:
        return dict(record.to_dict(include_payload=True))
    except TypeError:
        return dict(record.to_dict())


def _sanitize(value: Any) -> Any:
    hidden = {"payload", "input_text", "track_text", "raw_text", "records_text"}
    if isinstance(value, Mapping):
        return {str(key): _sanitize(item) for key, item in value.items() if str(key) not in hidden}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def _positive_metadata(
    evaluations: Mapping[TopologyArchitectureFamily, Any],
) -> dict[tuple[TopologyArchitectureFamily, str], tuple[str, tuple[str, ...], dict[str, Any]]]:
    result: dict[
        tuple[TopologyArchitectureFamily, str], tuple[str, tuple[str, ...], dict[str, Any]]
    ] = {}
    for family in _FAMILY_ORDER:
        for row in _rows(evaluations[family]):
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


def _source_registry(
    fixtures: Mapping[TopologyArchitectureFamily, Any],
) -> tuple[
    tuple[TopologyArchitectureSource, ...], dict[tuple[TopologyArchitectureFamily, str], str]
]:
    sources: list[TopologyArchitectureSource] = []
    mapping: dict[tuple[TopologyArchitectureFamily, str], str] = {}
    for family in _FAMILY_ORDER:
        for source in fixtures[family].sources:
            raw = jsonable(source)
            original_id = str(raw.get("source_id", raw.get("id", "")))
            source_id = f"{family.value}:{original_id}"
            mapping[(family, original_id)] = source_id
            body = {
                "source_id": source_id,
                "family": family,
                "title": str(raw.get("title", raw.get("source_kind", original_id))),
                "uri": str(raw.get("uri", "https://example.org/public-source")),
                "version": str(
                    raw.get("release", raw.get("source_version", raw.get("version", "public")))
                ),
                "scope": "public_aggregate",
                "license": "public source receipt",
                "public_aggregate": True,
            }
            sources.append(
                TopologyArchitectureSource(
                    **body, content_address=addressed(body, "topology-source")
                )
            )
    return tuple(sources), mapping


def _operations(
    fixtures: Mapping[TopologyArchitectureFamily, Any],
    source_maps: Mapping[tuple[TopologyArchitectureFamily, str], str],
) -> tuple[TopologyArchitectureOperationSpec, ...]:
    operations: list[TopologyArchitectureOperationSpec] = []
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
                "operation_id": f"D09-C{ordinal:02d}",
                "capability_id": f"GNC-D09-C{ordinal:02d}",
                "ordinal": ordinal,
                "operation": operation,
                "family": family,
                "plane": _FAMILY_PLANES[family],
                "input_contract": f"topology.{operation.value}.public_record.v1",
                "output_contract": f"topology.{operation.value}.receipt.v1",
                "dependencies": (f"D09-C{ordinal - 1:02d}",) if ordinal > 1 else (),
                "source_ids": source_ids,
                "control_policy": (
                    "hold context mismatch, malformed input, and identity conflict "
                    "before topology delegation"
                ),
            }
            operations.append(
                TopologyArchitectureOperationSpec(
                    **body, content_address=addressed(body, "topology-operation")
                )
            )
    return tuple(operations)


def _case(
    operation: TopologyArchitectureOperationSpec,
    scenario: TopologyArchitectureScenario,
    context_key: str,
    source_ids: tuple[str, ...],
    delegate_context_key: str,
    payload: dict[str, Any],
    expected_state: TopologyArchitectureState,
    expected_result_state: str,
    expected_issue_codes: tuple[str, ...],
    expected_counts: dict[str, int],
    description: str,
) -> TopologyArchitectureCase:
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
    return TopologyArchitectureCase(**body, content_address=addressed(body, "topology-case"))


def _cases(
    fixtures: Mapping[TopologyArchitectureFamily, Any],
    operations: tuple[TopologyArchitectureOperationSpec, ...],
    source_maps: Mapping[tuple[TopologyArchitectureFamily, str], str],
    metadata: Mapping[
        tuple[TopologyArchitectureFamily, str], tuple[str, tuple[str, ...], dict[str, Any]]
    ],
) -> tuple[TopologyArchitectureCase, ...]:
    cases: list[TopologyArchitectureCase] = []
    for operation in operations:
        family = operation.family
        record = fixtures[family].positive_records[
            list(_FAMILY_OPERATIONS[family]).index(operation.operation)
        ]
        record_dict = _record_dict(record)
        source_ids = tuple(source_maps[(family, str(source_id))] for source_id in record.source_ids)
        result_state, issue_codes, summary = metadata.get(
            (family, str(record.record_id)), ("supported", (), {})
        )
        positive_payload = {
            "family_record_id": str(record.record_id),
            "family_context_key": str(
                getattr(record, "context_key", TOPOLOGY_ARCHITECTURE_CONTEXT)
            ),
            "family_record": record_dict,
            "family_summary": summary,
            "operation_payload": record_dict.get("payload", record_dict),
        }
        cases.append(
            _case(
                operation,
                TopologyArchitectureScenario.POSITIVE,
                TOPOLOGY_ARCHITECTURE_CONTEXT,
                source_ids,
                str(getattr(record, "context_key", TOPOLOGY_ARCHITECTURE_CONTEXT)),
                positive_payload,
                TopologyArchitectureState.ACCEPTED,
                result_state,
                issue_codes,
                {"primary": 1, "secondary": 1},
                f"public aggregate positive topology path for {operation.capability_id}",
            )
        )
        controls = (
            (
                TopologyArchitectureScenario.FOREIGN_CONTEXT,
                TOPOLOGY_ARCHITECTURE_FOREIGN_CONTEXT,
                "out_of_domain",
                ("context_mismatch",),
                "foreign context is held before topology delegation",
            ),
            (
                TopologyArchitectureScenario.MALFORMED_INPUT,
                TOPOLOGY_ARCHITECTURE_CONTEXT,
                "invalid",
                ("malformed_input",),
                "malformed topology input is held before delegation",
            ),
            (
                TopologyArchitectureScenario.IDENTITY_CONFLICT,
                TOPOLOGY_ARCHITECTURE_CONTEXT,
                "contradictory",
                ("identity_conflict",),
                "topology identity conflict is held before delegation",
            ),
        )
        for scenario, control_context, state, codes, detail in controls:
            control_payload = {
                "family_record_id": str(record.record_id),
                "operation_payload": positive_payload["operation_payload"],
                "control": scenario.value,
                "malformed": scenario is TopologyArchitectureScenario.MALFORMED_INPUT,
                "identity_conflict": scenario is TopologyArchitectureScenario.IDENTITY_CONFLICT,
            }
            cases.append(
                _case(
                    operation,
                    scenario,
                    control_context,
                    source_ids,
                    str(getattr(record, "context_key", TOPOLOGY_ARCHITECTURE_CONTEXT)),
                    control_payload,
                    TopologyArchitectureState.REVIEW,
                    state,
                    codes,
                    {"primary": 0, "secondary": 0},
                    detail,
                )
            )
    return tuple(cases)


def default_topology_architecture_fixture(
    path: str | Path | None = None,
) -> TopologyArchitectureFixture:
    if path is not None:
        return TopologyArchitectureFixture.from_file(path)
    fixtures = _family_fixture_map()
    evaluations = _family_evaluation_map(fixtures)
    sources, source_maps = _source_registry(fixtures)
    operations = _operations(fixtures, source_maps)
    cases = _cases(fixtures, operations, source_maps, _positive_metadata(evaluations))
    body = {
        "fixture_id": "d09-topology-architecture-public-aggregate",
        "version": TOPOLOGY_ARCHITECTURE_VERSION,
        "boundary": TOPOLOGY_ARCHITECTURE_BOUNDARY,
        "context_key": TOPOLOGY_ARCHITECTURE_CONTEXT,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return TopologyArchitectureFixture(**body, content_address=addressed(body, "topology-fixture"))


def topology_architecture_fixture_json(fixture: TopologyArchitectureFixture | None = None) -> str:
    return (
        json.dumps(
            (fixture or default_topology_architecture_fixture()).to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def load_topology_architecture_mapping(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("D09 topology architecture JSON must be an object")
    return dict(raw)


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> TopologyArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": TopologyArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return TopologyArchitectureCheck(**body, content_address=addressed(body, "topology-check"))


def _scenario_counts(fixture: TopologyArchitectureFixture) -> dict[str, int]:
    return {
        scenario.value: sum(item.scenario is scenario for item in fixture.cases)
        for scenario in TopologyArchitectureScenario
    }


def audit_topology_architecture_data(
    fixture: TopologyArchitectureFixture,
) -> TopologyArchitectureDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    checks = (
        _check(
            "fixture-version",
            fixture.version == TOPOLOGY_ARCHITECTURE_VERSION,
            fixture.version,
            TOPOLOGY_ARCHITECTURE_VERSION,
            "D09 version is pinned",
        ),
        _check(
            "fixture-boundary",
            fixture.boundary == TOPOLOGY_ARCHITECTURE_BOUNDARY,
            fixture.boundary,
            TOPOLOGY_ARCHITECTURE_BOUNDARY,
            "D09 is public aggregate topology data",
        ),
        _check(
            "fixture-context",
            fixture.context_key == TOPOLOGY_ARCHITECTURE_CONTEXT,
            fixture.context_key,
            TOPOLOGY_ARCHITECTURE_CONTEXT,
            "topology aggregate context is exact",
        ),
        _check(
            "source-count",
            len(fixture.sources) == 17,
            len(fixture.sources),
            17,
            "four topology registries conserve seventeen sources",
        ),
        _check(
            "operation-count",
            len(fixture.operations) == 16,
            len(fixture.operations),
            16,
            "all D09 capabilities have operation specifications",
        ),
        _check(
            "case-count",
            len(fixture.cases) == 64,
            len(fixture.cases),
            64,
            "four cases are present for every topology operation",
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
            "topology source joins resolve",
        ),
        _check(
            "operation-uniqueness",
            len(operation_ids) == 16,
            len(operation_ids),
            16,
            "topology operation IDs are unique",
        ),
        _check(
            "case-uniqueness",
            len({item.case_id for item in fixture.cases}) == 64,
            len({item.case_id for item in fixture.cases}),
            64,
            "topology case IDs are unique",
        ),
        _check(
            "positive-control-balance",
            (len(fixture.positive_cases), len(fixture.control_cases)) == (16, 48),
            (len(fixture.positive_cases), len(fixture.control_cases)),
            (16, 48),
            "topology positive and control paths are explicit",
        ),
        _check(
            "scenario-balance",
            _scenario_counts(fixture)
            == {scenario.value: 16 for scenario in TopologyArchitectureScenario},
            _scenario_counts(fixture),
            {scenario.value: 16 for scenario in TopologyArchitectureScenario},
            "each topology operation has one positive and three controls",
        ),
        _check(
            "source-addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.sources),
            sum(item.content_address.startswith("sha256:") for item in fixture.sources),
            17,
            "topology public source receipts are addressed",
        ),
        _check(
            "operation-addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.operations),
            sum(item.content_address.startswith("sha256:") for item in fixture.operations),
            16,
            "topology operation contracts are addressed",
        ),
        _check(
            "case-addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.cases),
            sum(item.content_address.startswith("sha256:") for item in fixture.cases),
            64,
            "topology case contracts are addressed",
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return TopologyArchitectureDataAudit(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "topology-audit"),
    )


__all__ = [
    "TOPOLOGY_ARCHITECTURE_FIXTURE_FILE",
    "audit_topology_architecture_data",
    "default_topology_architecture_fixture",
    "load_topology_architecture_mapping",
    "topology_architecture_fixture_json",
]
