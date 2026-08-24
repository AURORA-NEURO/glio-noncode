"""D12 public aggregate projection over the four cohort evidence families."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .cohort_alpha_frontier_fixture_eval import evaluate_cohort_alpha_frontier_fixture
from .cohort_alpha_frontier_public_data import default_cohort_alpha_frontier_fixture
from .cohort_architecture_contracts import (
    COHORT_ARCHITECTURE_BOUNDARY,
    COHORT_ARCHITECTURE_CASE_COUNT,
    COHORT_ARCHITECTURE_CASES_PER_OPERATION,
    COHORT_ARCHITECTURE_CONTEXT,
    COHORT_ARCHITECTURE_FOREIGN_CONTEXT,
    COHORT_ARCHITECTURE_OPERATION_COUNT,
    COHORT_ARCHITECTURE_SOURCE_COUNT,
    COHORT_ARCHITECTURE_VERSION,
    CohortArchitectureCase,
    CohortArchitectureCheck,
    CohortArchitectureCheckKind,
    CohortArchitectureFamily,
    CohortArchitectureFixture,
    CohortArchitectureOperation,
    CohortArchitectureOperationSpec,
    CohortArchitecturePlane,
    CohortArchitectureScenario,
    CohortArchitectureSource,
    CohortArchitectureState,
    addressed,
)
from .cohort_beta_frontier_fixture_eval import evaluate_cohort_beta_frontier_fixture
from .cohort_beta_frontier_public_data import default_cohort_beta_frontier_fixture
from .cohort_foundation_frontier_fixture_eval import (
    evaluate_cohort_foundation_frontier_fixture,
)
from .cohort_foundation_frontier_public_data import default_cohort_foundation_frontier_fixture
from .cohort_frontier_fixture_eval import evaluate_cohort_frontier_fixture
from .cohort_frontier_public_data import default_cohort_frontier_fixture
from .serialization import jsonable

_FAMILY_ORDER = (
    CohortArchitectureFamily.FOUNDATION,
    CohortArchitectureFamily.BETA,
    CohortArchitectureFamily.ALPHA,
    CohortArchitectureFamily.FRONTIER,
)

_OPERATIONS = (
    (
        CohortArchitectureFamily.FOUNDATION,
        "cohort_query",
        CohortArchitectureOperation.COHORT_QUERY,
        CohortArchitecturePlane.FOUNDATION,
    ),
    (
        CohortArchitectureFamily.FOUNDATION,
        "background_rate",
        CohortArchitectureOperation.BACKGROUND_RATE,
        CohortArchitecturePlane.FOUNDATION,
    ),
    (
        CohortArchitectureFamily.FOUNDATION,
        "sequence_control",
        CohortArchitectureOperation.SEQUENCE_CONTROL,
        CohortArchitecturePlane.FOUNDATION,
    ),
    (
        CohortArchitectureFamily.FOUNDATION,
        "chromatin_control",
        CohortArchitectureOperation.CHROMATIN_CONTROL,
        CohortArchitecturePlane.FOUNDATION,
    ),
    (
        CohortArchitectureFamily.BETA,
        "C05",
        CohortArchitectureOperation.REGULATORY_RECURRENCE,
        CohortArchitecturePlane.BETA,
    ),
    (
        CohortArchitectureFamily.BETA,
        "C06",
        CohortArchitectureOperation.REGIONAL_BURDEN,
        CohortArchitecturePlane.BETA,
    ),
    (
        CohortArchitectureFamily.BETA,
        "C07",
        CohortArchitectureOperation.FUNCTIONAL_CONVERGENCE,
        CohortArchitecturePlane.BETA,
    ),
    (
        CohortArchitectureFamily.BETA,
        "C08",
        CohortArchitectureOperation.PATHWAY_REGULON_CONVERGENCE,
        CohortArchitecturePlane.BETA,
    ),
    (
        CohortArchitectureFamily.ALPHA,
        "C09",
        CohortArchitectureOperation.CLONALITY_TIMING,
        CohortArchitecturePlane.ALPHA,
    ),
    (
        CohortArchitectureFamily.ALPHA,
        "C10",
        CohortArchitectureOperation.PRIMARY_RECURRENCE,
        CohortArchitecturePlane.ALPHA,
    ),
    (
        CohortArchitectureFamily.ALPHA,
        "C11",
        CohortArchitectureOperation.TREATMENT_SELECTION,
        CohortArchitecturePlane.ALPHA,
    ),
    (
        CohortArchitectureFamily.ALPHA,
        "C12",
        CohortArchitectureOperation.CROSS_COHORT_REPLICATION,
        CohortArchitecturePlane.ALPHA,
    ),
    (
        CohortArchitectureFamily.FRONTIER,
        "subgroup_fairness",
        CohortArchitectureOperation.SUBGROUP_FAIRNESS,
        CohortArchitecturePlane.FRONTIER,
    ),
    (
        CohortArchitectureFamily.FRONTIER,
        "transportability",
        CohortArchitectureOperation.TRANSPORTABILITY,
        CohortArchitecturePlane.FRONTIER,
    ),
    (
        CohortArchitectureFamily.FRONTIER,
        "federated_summary",
        CohortArchitectureOperation.FEDERATED_SUMMARY,
        CohortArchitecturePlane.FRONTIER,
    ),
    (
        CohortArchitectureFamily.FRONTIER,
        "cohort_discovery",
        CohortArchitectureOperation.COHORT_DISCOVERY,
        CohortArchitecturePlane.FRONTIER,
    ),
)

_CONTROL_ISSUES = {
    "negative_control": ("negative_control",),
    "incomplete_control": ("incomplete_control",),
    "foreign_context": ("context_mismatch",),
    "empty_control": ("empty_control",),
    "contradictory_control": ("contradictory_control",),
}


def _family_fixtures() -> dict[CohortArchitectureFamily, Any]:
    return {
        CohortArchitectureFamily.FOUNDATION: default_cohort_foundation_frontier_fixture(),
        CohortArchitectureFamily.BETA: default_cohort_beta_frontier_fixture(),
        CohortArchitectureFamily.ALPHA: default_cohort_alpha_frontier_fixture(),
        CohortArchitectureFamily.FRONTIER: default_cohort_frontier_fixture(),
    }


def _family_evaluations(
    fixtures: Mapping[CohortArchitectureFamily, Any],
) -> dict[CohortArchitectureFamily, Any]:
    return {
        CohortArchitectureFamily.FOUNDATION: evaluate_cohort_foundation_frontier_fixture(
            fixtures[CohortArchitectureFamily.FOUNDATION]
        ),
        CohortArchitectureFamily.BETA: evaluate_cohort_beta_frontier_fixture(
            fixtures[CohortArchitectureFamily.BETA]
        ),
        CohortArchitectureFamily.ALPHA: evaluate_cohort_alpha_frontier_fixture(
            fixtures[CohortArchitectureFamily.ALPHA]
        ),
        CohortArchitectureFamily.FRONTIER: evaluate_cohort_frontier_fixture(
            fixtures[CohortArchitectureFamily.FRONTIER]
        ),
    }


def _family_context(fixture: Any) -> str:
    return str(getattr(fixture, "context_key", COHORT_ARCHITECTURE_CONTEXT))


def _family_boundary(fixture: Any) -> str:
    return str(
        getattr(
            fixture,
            "boundary",
            getattr(fixture, "evidence_boundary", "public_aggregate_non_patient"),
        )
    )


def _record_dict(record: Any) -> dict[str, Any]:
    value = record.to_dict() if hasattr(record, "to_dict") else jsonable(record)
    return dict(value)


def _source_dict(source: Any) -> dict[str, Any]:
    value = source.to_dict() if hasattr(source, "to_dict") else jsonable(source)
    return dict(value)


def _state_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _row_count(payload: Mapping[str, Any]) -> int:
    preferred = ("rows", "observations", "input_records", "records", "candidates")
    for key in preferred:
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    for value in payload.values():
        if isinstance(value, list):
            return len(value)
    return 0


def _scenario_for(
    family: CohortArchitectureFamily, record: Any, index: int
) -> CohortArchitectureScenario:
    role = getattr(getattr(record, "role", None), "value", None)
    control_class = str(getattr(record, "control_class", ""))
    if role == "positive" or control_class == "positive":
        return CohortArchitectureScenario.POSITIVE
    return (
        CohortArchitectureScenario.CONTROL_A,
        CohortArchitectureScenario.CONTROL_B,
        CohortArchitectureScenario.CONTROL_C,
    )[index]


def _delegate_rows(
    fixtures: Mapping[CohortArchitectureFamily, Any],
    evaluations: Mapping[CohortArchitectureFamily, Any],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for family in _FAMILY_ORDER:
        fixture = fixtures[family]
        evaluation = evaluations[family]
        records = tuple(fixture.records)
        if family is CohortArchitectureFamily.FOUNDATION:
            execution_map = evaluation.execution_map()
            for index, record in enumerate(records):
                execution = execution_map[record.record_id]
                row = {
                    "family": family,
                    "delegate_operation": record.operation.value,
                    "record": record,
                    "record_dict": _record_dict(record),
                    "delegate_fixture_id": fixture.fixture_id,
                    "delegate_context_key": record.context_key,
                    "delegate_class": record.role.value,
                    "expected_state": record.expected_state,
                    "observed_state": execution.actual_state,
                    "issue_codes": tuple(execution.issues),
                    "output": execution.output,
                    "output_address": execution.content_address,
                    "source_ids": tuple(record.source_ids),
                    "source_index": index,
                }
                rows.append(row)
            continue
        if family is CohortArchitectureFamily.BETA:
            row_map = {item.record_id: item for item in evaluation.rows}
            for index, record in enumerate(records):
                result = row_map[record.record_id]
                control = record.control_class
                rows.append(
                    {
                        "family": family,
                        "delegate_operation": record.operation,
                        "record": record,
                        "record_dict": _record_dict(record),
                        "delegate_fixture_id": fixture.fixture_id,
                        "delegate_context_key": fixture.context_key,
                        "delegate_class": control,
                        "expected_state": record.expected_state,
                        "observed_state": result.observed_state.value,
                        "issue_codes": _CONTROL_ISSUES.get(control, ()),
                        "output": result.result,
                        "output_address": result.content_address,
                        "source_ids": tuple(record.source_ids),
                        "source_index": index,
                    }
                )
            continue
        if family is CohortArchitectureFamily.ALPHA:
            row_map = {item.record_id: item for item in evaluation.rows}
            for index, record in enumerate(records):
                result = row_map[record.record_id]
                control = record.control_class
                result_issues = tuple(
                    str(item)
                    for item in result.result.get("issues", ())
                    if isinstance(item, (str, int, float))
                )
                rows.append(
                    {
                        "family": family,
                        "delegate_operation": record.operation,
                        "record": record,
                        "record_dict": _record_dict(record),
                        "delegate_fixture_id": fixture.fixture_id,
                        "delegate_context_key": fixture.context_key,
                        "delegate_class": control,
                        "expected_state": record.expected_state,
                        "observed_state": result.observed_state.value,
                        "issue_codes": result_issues or _CONTROL_ISSUES.get(control, ()),
                        "output": result.result,
                        "output_address": result.content_address,
                        "source_ids": tuple(record.source_ids),
                        "source_index": index,
                    }
                )
            continue
        execution_map = evaluation.execution_map()
        for index, record in enumerate(records):
            execution = execution_map[record.record_id]
            rows.append(
                {
                    "family": family,
                    "delegate_operation": record.operation.value,
                    "record": record,
                    "record_dict": _record_dict(record),
                    "delegate_fixture_id": fixture.fixture_id,
                    "delegate_context_key": record.context_key,
                    "delegate_class": record.role.value,
                    "expected_state": record.expected_state,
                    "observed_state": execution.state,
                    "issue_codes": tuple(execution.issue_codes),
                    "output": execution.output,
                    "output_address": execution.content_address,
                    "source_ids": tuple(record.source_ids),
                    "source_index": index,
                }
            )
    return tuple(rows)


def cohort_architecture_delegate_rows() -> tuple[dict[str, Any], ...]:
    """Return normalized rows backed by each D12 family evaluator."""

    fixtures = _family_fixtures()
    return _delegate_rows(fixtures, _family_evaluations(fixtures))


def _source_records(
    fixtures: Mapping[CohortArchitectureFamily, Any],
) -> tuple[CohortArchitectureSource, ...]:
    sources: list[CohortArchitectureSource] = []
    for family in _FAMILY_ORDER:
        fixture = fixtures[family]
        for source in fixture.sources:
            raw = _source_dict(source)
            delegate_id = str(raw["source_id"])
            source_id = f"D12-{family.value}-{delegate_id}"
            body = {
                "source_id": source_id,
                "family": family,
                "source_kind": str(
                    raw.get(
                        "source_kind", raw.get("title", raw.get("label", "public aggregate source"))
                    )
                ),
                "source_version": str(
                    raw.get("source_version", raw.get("version", raw.get("release", "unspecified")))
                ),
                "uri": str(raw.get("uri", raw.get("url", ""))),
                "source_context_key": _family_context(fixture),
                "delegate_source_id": delegate_id,
                "delegate_fixture_id": fixture.fixture_id,
                "public_aggregate": bool(raw.get("aggregate_only", True)),
                "delegate_content_address": str(raw.get("content_address", "")),
            }
            sources.append(
                CohortArchitectureSource(**body, content_address=addressed(body, "cohort-source"))
            )
    return tuple(sources)


def _operation_specs(
    sources: tuple[CohortArchitectureSource, ...],
) -> tuple[CohortArchitectureOperationSpec, ...]:
    specs: list[CohortArchitectureOperationSpec] = []
    for ordinal, (family, delegate_operation, operation, plane) in enumerate(_OPERATIONS, start=1):
        body = {
            "operation_id": f"D12-C{ordinal:02d}",
            "capability_id": f"GNC-D12-C{ordinal:02d}",
            "ordinal": ordinal,
            "operation": operation,
            "delegate_operation": delegate_operation,
            "family": family,
            "plane": plane,
            "input_contract": f"cohort.{operation.value}.public_record.v1",
            "output_contract": f"cohort.{operation.value}.receipt.v1",
            "dependencies": (f"D12-C{ordinal - 1:02d}",) if ordinal > 1 else (),
            "source_ids": tuple(item.source_id for item in sources if item.family is family),
            "control_policy": (
                "retain exact cohort context, callable or phase coverage, source dependence, "
                "review state, and claim ceiling"
            ),
        }
        specs.append(
            CohortArchitectureOperationSpec(
                **body, content_address=addressed(body, "cohort-operation")
            )
        )
    return tuple(specs)


def _cases(
    fixtures: Mapping[CohortArchitectureFamily, Any],
    sources: tuple[CohortArchitectureSource, ...],
    operations: tuple[CohortArchitectureOperationSpec, ...],
) -> tuple[CohortArchitectureCase, ...]:
    evaluations = _family_evaluations(fixtures)
    rows = _delegate_rows(fixtures, evaluations)
    cases: list[CohortArchitectureCase] = []
    family_source_map = {
        family: tuple(item.source_id for item in sources if item.family is family)
        for family in _FAMILY_ORDER
    }
    for operation in operations:
        selected = [
            row
            for row in rows
            if row["family"] is operation.family
            and row["delegate_operation"] == operation.delegate_operation
        ]
        mapped: dict[CohortArchitectureScenario, dict[str, Any]] = {}
        controls = [row for row in selected if row["delegate_class"] != "positive"]
        positive = [row for row in selected if row["delegate_class"] == "positive"]
        if positive:
            mapped[CohortArchitectureScenario.POSITIVE] = positive[0]
        for index, row in enumerate(controls):
            scenario = _scenario_for(operation.family, row["record"], index)
            mapped[scenario] = row
        if set(mapped) != set(CohortArchitectureScenario):
            raise ValueError(f"D12 scenario balance failed for {operation.operation_id}")
        for scenario in CohortArchitectureScenario:
            row = mapped[scenario]
            record = row["record"]
            payload = row["record_dict"].get("payload", {})
            counts = {
                "source_count": len(row["source_ids"]),
                "payload_field_count": len(payload),
                "row_count": _row_count(payload),
            }
            body = {
                "case_id": f"{operation.operation_id}-{scenario.value}",
                "operation_id": operation.operation_id,
                "operation": operation.operation,
                "family": operation.family,
                "plane": operation.plane,
                "scenario": scenario,
                "aggregate_context_key": COHORT_ARCHITECTURE_CONTEXT,
                "delegate_context_key": str(row["delegate_context_key"]),
                "delegate_fixture_id": row["delegate_fixture_id"],
                "delegate_record_id": record.record_id,
                "delegate_class": row["delegate_class"],
                "source_ids": family_source_map[operation.family],
                "payload": {
                    "delegate_operation": row["delegate_operation"],
                    "delegate_class": row["delegate_class"],
                    "delegate_payload": jsonable(payload),
                    "delegate_output": jsonable(row["output"]),
                    "delegate_output_address": row["output_address"],
                    "delegate_context_key": row["delegate_context_key"],
                    "delegate_fixture_id": row["delegate_fixture_id"],
                },
                "expected_state": CohortArchitectureState(
                    row["expected_state"]
                    if isinstance(row["expected_state"], str)
                    else row["expected_state"].value
                ),
                "expected_issue_codes": tuple(row["issue_codes"]),
                "expected_counts": counts,
                "description": (
                    f"{operation.operation.value} public aggregate record {record.record_id} "
                    f"retained as D12 {scenario.value}"
                ),
            }
            cases.append(
                CohortArchitectureCase(**body, content_address=addressed(body, "cohort-case"))
            )
    return tuple(cases)


def default_cohort_architecture_fixture() -> CohortArchitectureFixture:
    fixtures = _family_fixtures()
    sources = _source_records(fixtures)
    operations = _operation_specs(sources)
    cases = _cases(fixtures, sources, operations)
    family_contexts = {family.value: _family_context(fixtures[family]) for family in _FAMILY_ORDER}
    body = {
        "fixture_id": "cohort-architecture-public-aggregate",
        "version": COHORT_ARCHITECTURE_VERSION,
        "boundary": COHORT_ARCHITECTURE_BOUNDARY,
        "context_key": COHORT_ARCHITECTURE_CONTEXT,
        "foreign_context_key": COHORT_ARCHITECTURE_FOREIGN_CONTEXT,
        "family_contexts": family_contexts,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return CohortArchitectureFixture(**body, content_address=addressed(body, "cohort-fixture"))


def cohort_architecture_fixture_json(fixture: CohortArchitectureFixture | None = None) -> str:
    selected = fixture or default_cohort_architecture_fixture()
    return json.dumps(selected.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_cohort_architecture_mapping(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("D12 aggregate JSON must be an object")
    return dict(raw)


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: CohortArchitectureCheckKind = CohortArchitectureCheckKind.FIXTURE,
) -> CohortArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CohortArchitectureCheck(**body, content_address=addressed(body, "cohort-audit-check"))


def audit_cohort_architecture_data(
    fixture: CohortArchitectureFixture | None = None,
) -> Any:
    selected = fixture or default_cohort_architecture_fixture()
    source_ids = {item.source_id for item in selected.sources}
    operation_ids = {item.operation_id for item in selected.operations}
    checks = (
        _check(
            "source-count",
            len(selected.sources) == COHORT_ARCHITECTURE_SOURCE_COUNT,
            len(selected.sources),
            COHORT_ARCHITECTURE_SOURCE_COUNT,
            "all four family source registries are joined",
            CohortArchitectureCheckKind.SOURCE,
        ),
        _check(
            "operation-count",
            len(selected.operations) == COHORT_ARCHITECTURE_OPERATION_COUNT,
            len(selected.operations),
            COHORT_ARCHITECTURE_OPERATION_COUNT,
            "sixteen semantic operations are declared",
            CohortArchitectureCheckKind.OPERATION,
        ),
        _check(
            "case-count",
            len(selected.cases) == COHORT_ARCHITECTURE_CASE_COUNT,
            len(selected.cases),
            COHORT_ARCHITECTURE_CASE_COUNT,
            "four scenarios are retained per operation",
            CohortArchitectureCheckKind.CASE,
        ),
        _check(
            "family-count",
            len({item.family for item in selected.operations}) == 4,
            len({item.family for item in selected.operations}),
            4,
            "foundation, beta, alpha, and frontier families are present",
        ),
        _check(
            "source-joins",
            all(set(item.source_ids) <= source_ids for item in selected.operations),
            True,
            True,
            "operation source references resolve",
            CohortArchitectureCheckKind.SOURCE,
        ),
        _check(
            "case-operation-joins",
            all(item.operation_id in operation_ids for item in selected.cases),
            True,
            True,
            "case operation references resolve",
            CohortArchitectureCheckKind.CASE,
        ),
        _check(
            "scenario-balance",
            all(
                sum(item.operation_id == operation.operation_id for item in selected.cases)
                == COHORT_ARCHITECTURE_CASES_PER_OPERATION
                for operation in selected.operations
            ),
            True,
            True,
            "each operation owns four cases",
            CohortArchitectureCheckKind.CONTROL,
        ),
        _check(
            "aggregate-boundary",
            selected.boundary == COHORT_ARCHITECTURE_BOUNDARY,
            selected.boundary,
            COHORT_ARCHITECTURE_BOUNDARY,
            "release boundary is public aggregate only",
        ),
        _check(
            "family-contexts",
            len(selected.family_contexts) == 4 and all(selected.family_contexts.values()),
            len(selected.family_contexts),
            4,
            "family context keys are retained",
        ),
        _check(
            "addresses",
            all(
                item.content_address.startswith("sha256:")
                for item in (*selected.sources, *selected.operations, *selected.cases)
            ),
            True,
            True,
            "all aggregate records are addressed",
        ),
    )
    body = {"fixture_id": selected.fixture_id, "checks": checks}
    from .cohort_architecture_contracts import CohortArchitectureDataAudit

    return CohortArchitectureDataAudit(
        selected.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "cohort-data-audit"),
    )


__all__ = [
    "COHORT_ARCHITECTURE_BOUNDARY",
    "COHORT_ARCHITECTURE_CONTEXT",
    "COHORT_ARCHITECTURE_FOREIGN_CONTEXT",
    "COHORT_ARCHITECTURE_VERSION",
    "audit_cohort_architecture_data",
    "cohort_architecture_delegate_rows",
    "cohort_architecture_fixture_json",
    "default_cohort_architecture_fixture",
    "load_cohort_architecture_mapping",
]
