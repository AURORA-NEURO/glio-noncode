"""D15 public aggregate normalization over four workbench delegate families."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .workbench_architecture_contracts import (
    WORKBENCH_ARCHITECTURE_BOUNDARY,
    WORKBENCH_ARCHITECTURE_CASE_COUNT,
    WORKBENCH_ARCHITECTURE_CASES_PER_OPERATION,
    WORKBENCH_ARCHITECTURE_CONTEXT,
    WORKBENCH_ARCHITECTURE_FOREIGN_CONTEXT,
    WORKBENCH_ARCHITECTURE_OPERATION_COUNT,
    WORKBENCH_ARCHITECTURE_SOURCE_COUNT,
    WORKBENCH_ARCHITECTURE_VERSION,
    WorkbenchArchitectureCase,
    WorkbenchArchitectureCheck,
    WorkbenchArchitectureCheckKind,
    WorkbenchArchitectureDataAudit,
    WorkbenchArchitectureFamily,
    WorkbenchArchitectureFixture,
    WorkbenchArchitectureOperation,
    WorkbenchArchitectureOperationSpec,
    WorkbenchArchitecturePlane,
    WorkbenchArchitectureScenario,
    WorkbenchArchitectureSource,
    WorkbenchArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class _FamilySpec:
    family: WorkbenchArchitectureFamily
    plane: WorkbenchArchitecturePlane
    data_module: str
    fixture_function: str
    eval_module: str
    eval_function: str
    fixture_version: str


_FAMILIES = (
    _FamilySpec(
        WorkbenchArchitectureFamily.WORKSPACE_FOUNDATION,
        WorkbenchArchitecturePlane.WORKSPACE_FOUNDATION,
        "workspace_frontier_public_data",
        "default_workspace_frontier_fixture",
        "workspace_frontier_fixture_eval",
        "evaluate_workspace_frontier_fixture",
        "2026.08.d15-c01-c04.v1",
    ),
    _FamilySpec(
        WorkbenchArchitectureFamily.WORKSPACE_BETA,
        WorkbenchArchitecturePlane.WORKSPACE_BETA,
        "workspace_beta_frontier_public_data",
        "default_beta_frontier_fixture",
        "workspace_beta_frontier_fixture_eval",
        "evaluate_beta_frontier_fixture",
        "2026.08.d15-c05-c08.v1",
    ),
    _FamilySpec(
        WorkbenchArchitectureFamily.WORKSPACE_GAMMA,
        WorkbenchArchitecturePlane.WORKSPACE_COLLABORATION,
        "workspace_gamma_frontier_public_data",
        "default_gamma_frontier_fixture",
        "workspace_gamma_frontier_fixture_eval",
        "evaluate_gamma_frontier_fixture",
        "2026.08.d15-c09-c12.v1",
    ),
    _FamilySpec(
        WorkbenchArchitectureFamily.WORKBENCH_RELEASE,
        WorkbenchArchitecturePlane.WORKBENCH_RELEASE,
        "workbench_release_frontier_public_data",
        "default_workbench_release_frontier_fixture",
        "workbench_release_frontier_fixture_eval",
        "evaluate_workbench_release_fixture",
        "2026.08.d15-c13-c16.v1",
    ),
)

_OPERATIONS = (
    (
        "D15-C01",
        "case_workspace",
        WorkbenchArchitectureOperation.CASE_WORKSPACE,
        WorkbenchArchitectureFamily.WORKSPACE_FOUNDATION,
        WorkbenchArchitecturePlane.WORKSPACE_FOUNDATION,
        "case manifest and dossier fields",
        "case workspace view",
        (),
    ),
    (
        "D15-C02",
        "cohort_workspace",
        WorkbenchArchitectureOperation.COHORT_WORKSPACE,
        WorkbenchArchitectureFamily.WORKSPACE_FOUNDATION,
        WorkbenchArchitecturePlane.WORKSPACE_FOUNDATION,
        "cohort query and record fields",
        "cohort workspace view",
        ("D15-C01",),
    ),
    (
        "D15-C03",
        "variant_explorer",
        WorkbenchArchitectureOperation.VARIANT_EXPLORER,
        WorkbenchArchitectureFamily.WORKSPACE_FOUNDATION,
        WorkbenchArchitecturePlane.WORKSPACE_FOUNDATION,
        "variant identity and workspace fields",
        "variant explorer view",
        ("D15-C01",),
    ),
    (
        "D15-C04",
        "regulatory_track_browser",
        WorkbenchArchitectureOperation.REGULATORY_TRACK_BROWSER,
        WorkbenchArchitectureFamily.WORKSPACE_FOUNDATION,
        WorkbenchArchitecturePlane.WORKSPACE_FOUNDATION,
        "track records and intervals",
        "regulatory track view",
        ("D15-C01",),
    ),
    (
        "D15-C05",
        "topology_viewport",
        WorkbenchArchitectureOperation.TOPOLOGY_VIEWER,
        WorkbenchArchitectureFamily.WORKSPACE_BETA,
        WorkbenchArchitecturePlane.WORKSPACE_BETA,
        "topology observations and focus",
        "topology viewport",
        ("D15-C03",),
    ),
    (
        "D15-C06",
        "causal_chain",
        WorkbenchArchitectureOperation.CAUSAL_CHAIN_EXPLORER,
        WorkbenchArchitectureFamily.WORKSPACE_BETA,
        WorkbenchArchitecturePlane.WORKSPACE_BETA,
        "mediator and chain records",
        "causal chain view",
        ("D15-C05",),
    ),
    (
        "D15-C07",
        "posterior_decomposition",
        WorkbenchArchitectureOperation.POSTERIOR_DECOMPOSITION,
        WorkbenchArchitectureFamily.WORKSPACE_BETA,
        WorkbenchArchitecturePlane.WORKSPACE_BETA,
        "component and support records",
        "posterior decomposition",
        ("D15-C06",),
    ),
    (
        "D15-C08",
        "evidence_table",
        WorkbenchArchitectureOperation.EVIDENCE_TABLE,
        WorkbenchArchitectureFamily.WORKSPACE_BETA,
        WorkbenchArchitecturePlane.WORKSPACE_BETA,
        "evidence rows and filters",
        "evidence table view",
        ("D15-C07",),
    ),
    (
        "D15-C09",
        "experiment_board",
        WorkbenchArchitectureOperation.VALIDATION_EXPERIMENT_BOARD,
        WorkbenchArchitectureFamily.WORKSPACE_GAMMA,
        WorkbenchArchitecturePlane.WORKSPACE_COLLABORATION,
        "experiment cards and dependencies",
        "validation experiment board",
        ("D15-C08",),
    ),
    (
        "D15-C10",
        "launch_plan",
        WorkbenchArchitectureOperation.NOTEBOOK_SDK_LAUNCHER,
        WorkbenchArchitectureFamily.WORKSPACE_GAMMA,
        WorkbenchArchitecturePlane.WORKSPACE_COLLABORATION,
        "launch request and resource profile",
        "notebook SDK launch plan",
        ("D15-C09",),
    ),
    (
        "D15-C11",
        "shareable_snapshot",
        WorkbenchArchitectureOperation.SIGNED_SNAPSHOT,
        WorkbenchArchitectureFamily.WORKSPACE_GAMMA,
        WorkbenchArchitecturePlane.WORKSPACE_COLLABORATION,
        "signed snapshot and expiry",
        "shareable snapshot",
        ("D15-C10",),
    ),
    (
        "D15-C12",
        "collaboration_access",
        WorkbenchArchitectureOperation.ROLE_COLLABORATION,
        WorkbenchArchitectureFamily.WORKSPACE_GAMMA,
        WorkbenchArchitecturePlane.WORKSPACE_COLLABORATION,
        "member, role, and workspace policy",
        "collaboration access report",
        ("D15-C11",),
    ),
    (
        "D15-C13",
        "review_form",
        WorkbenchArchitectureOperation.STRUCTURED_REVIEW,
        WorkbenchArchitectureFamily.WORKBENCH_RELEASE,
        WorkbenchArchitecturePlane.WORKBENCH_RELEASE,
        "review field declarations",
        "structured review projection",
        ("D15-C12",),
    ),
    (
        "D15-C14",
        "report_export",
        WorkbenchArchitectureOperation.REPORT_EXPORT,
        WorkbenchArchitectureFamily.WORKBENCH_RELEASE,
        WorkbenchArchitecturePlane.WORKBENCH_RELEASE,
        "report sections and formats",
        "report export artifact",
        ("D15-C13",),
    ),
    (
        "D15-C15",
        "search_palette",
        WorkbenchArchitectureOperation.SEARCH_PALETTE,
        WorkbenchArchitectureFamily.WORKBENCH_RELEASE,
        WorkbenchArchitecturePlane.WORKBENCH_RELEASE,
        "search query and records",
        "search result view",
        ("D15-C14",),
    ),
    (
        "D15-C16",
        "accessibility",
        WorkbenchArchitectureOperation.ACCESSIBILITY_HUMAN_FACTORS,
        WorkbenchArchitectureFamily.WORKBENCH_RELEASE,
        WorkbenchArchitecturePlane.WORKBENCH_RELEASE,
        "declared interface criteria",
        "accessibility assessment",
        ("D15-C15",),
    ),
)

_SOURCE_ALIASES = {
    WorkbenchArchitectureFamily.WORKSPACE_BETA.value: {
        "topology-public": "sequence-public",
    },
}


def _canonical_source_id(family: WorkbenchArchitectureFamily, source_id: str) -> str:
    return _SOURCE_ALIASES.get(family.value, {}).get(source_id, source_id)


_RESTRICTED_PAYLOAD_KEYS = frozenset(
    {
        "patient_id",
        "participant_id",
        "subject_id",
        "individual_id",
        "clinical_decision",
        "treatment_recommendation",
    }
)


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _safe_payload(child)
            for key, child in value.items()
            if str(key) not in _RESTRICTED_PAYLOAD_KEYS
        }
    if isinstance(value, list):
        return [_safe_payload(child) for child in value]
    if isinstance(value, tuple):
        return tuple(_safe_payload(child) for child in value)
    return value


def _load_family(spec: _FamilySpec) -> tuple[Any, tuple[Any, ...]]:
    import importlib

    fixture = getattr(
        importlib.import_module(f"glio_noncode.{spec.data_module}"), spec.fixture_function
    )()
    evaluation = getattr(
        importlib.import_module(f"glio_noncode.{spec.eval_module}"), spec.eval_function
    )(fixture)
    return fixture, tuple(evaluation.executions)


@lru_cache(maxsize=1)
def _family_objects() -> tuple[tuple[_FamilySpec, Any, tuple[Any, ...]], ...]:
    return tuple((spec, *_load_family(spec)) for spec in _FAMILIES)


def _operation_meta(operation_id: str) -> tuple[Any, ...]:
    return next(item for item in _OPERATIONS if item[0] == operation_id)


def _state_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _issue_values(value: Any) -> tuple[str, ...]:
    return tuple(_state_value(item) for item in value)


def _execution_state(execution: Any) -> str:
    return _state_value(
        getattr(
            execution,
            "observed_state",
            getattr(execution, "state", getattr(execution, "expected_state", "invalid")),
        )
    )


def _execution_operation(execution: Any) -> str:
    return _state_value(getattr(execution, "operation", "unknown"))


@lru_cache(maxsize=1)
def _delegate_rows() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for spec, fixture, executions in _family_objects():
        records = {record.record_id: record for record in fixture.records}
        for execution in executions:
            record = records[execution.record_id]
            output = execution.output if isinstance(execution.output, dict) else {}
            rows.append(
                {
                    "family": spec.family,
                    "plane": spec.plane,
                    "fixture": fixture,
                    "record": record,
                    "execution": execution,
                    "output": output,
                    "observed_state": _execution_state(execution),
                    "issue_codes": _issue_values(execution.issue_codes),
                    "output_address": execution.content_address,
                    "delegate_context_key": str(
                        getattr(record, "context_key", output.get("context_key", ""))
                    ),
                    "expected_record_state": _state_value(record.expected_state),
                    "expected_record_issue_codes": _issue_values(record.expected_issue_codes),
                }
            )
    return tuple(rows)


def _source_ids_for_family(family: WorkbenchArchitectureFamily) -> tuple[str, ...]:
    return tuple(
        source_id
        for source_id, _ in ((row["source_id"], row) for row in _source_rows())
        if source_id.startswith(f"D15-{family.value}:")
    )


def _source_rows() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for spec, fixture, _executions in _family_objects():
        for source in fixture.sources:
            source_id = f"D15-{spec.family.value}:{source.source_id}"
            body = {
                "source_id": source_id,
                "family": spec.family,
                "source_kind": type(source).__name__,
                "source_version": spec.fixture_version,
                "uri": source.uri,
                "source_context_key": fixture.context_key,
                "delegate_source_id": source.source_id,
                "delegate_fixture_id": fixture.fixture_id,
                "public_aggregate": True,
                "delegate_content_address": source.content_address,
            }
            rows.append(
                body | {"content_address": addressed(body, "workbench-architecture-source")}
            )
    return tuple(rows)


def default_workbench_architecture_fixture() -> WorkbenchArchitectureFixture:
    source_rows = _source_rows()
    sources = tuple(WorkbenchArchitectureSource(**row) for row in source_rows)
    source_map = {
        (row["family"].value, row["delegate_source_id"]): row["source_id"] for row in source_rows
    }
    operations: list[WorkbenchArchitectureOperationSpec] = []
    cases: list[WorkbenchArchitectureCase] = []
    family_contexts = {
        spec.family.value: fixture.context_key for spec, fixture, _ in _family_objects()
    }
    for ordinal, meta in enumerate(_OPERATIONS, start=1):
        (
            operation_id,
            delegate_operation,
            operation,
            family,
            plane,
            input_contract,
            output_contract,
            dependencies,
        ) = meta
        family_rows = [
            row
            for row in _delegate_rows()
            if row["family"] is family
            and _execution_operation(row["execution"]) == delegate_operation
        ]
        if len(family_rows) != WORKBENCH_ARCHITECTURE_CASES_PER_OPERATION:
            family_rows = [
                row
                for row in _delegate_rows()
                if row["family"] is family
                and row["record"].record_id.startswith(operation_id.replace("D15-", "C"))
            ]
        operation_sources = tuple(
            sorted(
                {
                    source_map[(family.value, _canonical_source_id(family, source_id))]
                    for row in family_rows
                    for source_id in row["record"].source_ids
                }
            )
        )
        op_body = {
            "operation_id": operation_id,
            "capability_id": operation_id,
            "ordinal": ordinal,
            "operation": operation,
            "delegate_operation": delegate_operation,
            "family": family,
            "plane": plane,
            "input_contract": input_contract,
            "output_contract": output_contract,
            "dependencies": dependencies,
            "source_ids": operation_sources,
            "control_policy": (
                "retain positive and control states; require explicit context mismatch evidence"
            ),
        }
        operations.append(
            WorkbenchArchitectureOperationSpec(
                **op_body, content_address=addressed(op_body, "workbench-architecture-operation")
            )
        )
        for index, row in enumerate(family_rows):
            record = row["record"]
            scenario = (
                WorkbenchArchitectureScenario.POSITIVE
                if index == 0
                else WorkbenchArchitectureScenario(
                    ("control_a", "control_b", "control_c")[index - 1]
                )
            )
            case_id = f"{operation_id}-{scenario.value.upper().replace('_', '-')}-001"
            case_source_ids = tuple(
                sorted(
                    {
                        source_map[(family.value, _canonical_source_id(family, source_id))]
                        for source_id in record.source_ids
                    }
                )
            )
            payload = _safe_payload(record.payload) if isinstance(record.payload, dict) else {}
            counts = {
                "source_count": len(record.source_ids),
                "payload_field_count": len(payload),
                "output_field_count": len(row["output"]),
                "issue_count": len(row["issue_codes"]),
            }
            case_body = {
                "case_id": case_id,
                "operation_id": operation_id,
                "operation": operation,
                "family": family,
                "plane": plane,
                "scenario": scenario,
                "aggregate_context_key": WORKBENCH_ARCHITECTURE_CONTEXT,
                "delegate_context_key": row["delegate_context_key"],
                "delegate_fixture_id": row["fixture"].fixture_id,
                "delegate_record_id": record.record_id,
                "delegate_class": type(record).__name__,
                "source_ids": case_source_ids,
                "payload": payload,
                "expected_state": WorkbenchArchitectureState(row["observed_state"]),
                "expected_issue_codes": row["issue_codes"],
                "expected_counts": counts,
                "description": (
                    f"{operation_id} {scenario.value} retains {record.record_id} "
                    f"from {family.value}"
                ),
            }
            cases.append(
                WorkbenchArchitectureCase(
                    **case_body, content_address=addressed(case_body, "workbench-architecture-case")
                )
            )
    fixture_body = {
        "fixture_id": "workbench-architecture-public-aggregate-001",
        "version": WORKBENCH_ARCHITECTURE_VERSION,
        "boundary": WORKBENCH_ARCHITECTURE_BOUNDARY,
        "context_key": WORKBENCH_ARCHITECTURE_CONTEXT,
        "foreign_context_key": WORKBENCH_ARCHITECTURE_FOREIGN_CONTEXT,
        "family_contexts": family_contexts,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return WorkbenchArchitectureFixture(
        **fixture_body, content_address=addressed(fixture_body, "workbench-architecture-fixture")
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: WorkbenchArchitectureCheckKind,
) -> WorkbenchArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return WorkbenchArchitectureCheck(
        **body, content_address=addressed(body, "workbench-architecture-audit-check")
    )


def audit_workbench_architecture_data(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> WorkbenchArchitectureDataAudit:
    selected = fixture or default_workbench_architecture_fixture()
    source_ids = {item.source_id for item in selected.sources}
    operation_ids = {item.operation_id for item in selected.operations}
    counts = {
        operation.operation_id: sum(
            case.operation_id == operation.operation_id for case in selected.cases
        )
        for operation in selected.operations
    }
    checks = (
        _check(
            "audit:source-count",
            len(selected.sources) == WORKBENCH_ARCHITECTURE_SOURCE_COUNT,
            len(selected.sources),
            WORKBENCH_ARCHITECTURE_SOURCE_COUNT,
            "four delegate source registries are retained",
            WorkbenchArchitectureCheckKind.SOURCE,
        ),
        _check(
            "audit:operation-count",
            len(selected.operations) == WORKBENCH_ARCHITECTURE_OPERATION_COUNT,
            len(selected.operations),
            WORKBENCH_ARCHITECTURE_OPERATION_COUNT,
            "all D15 capability operations are declared",
            WorkbenchArchitectureCheckKind.OPERATION,
        ),
        _check(
            "audit:case-count",
            len(selected.cases) == WORKBENCH_ARCHITECTURE_CASE_COUNT,
            len(selected.cases),
            WORKBENCH_ARCHITECTURE_CASE_COUNT,
            "four scenarios are retained per operation",
            WorkbenchArchitectureCheckKind.CASE,
        ),
        _check(
            "audit:family-contexts",
            len(selected.family_contexts) == 4 and all(selected.family_contexts.values()),
            selected.family_contexts,
            "four exact delegate contexts",
            "family contexts remain visible",
            WorkbenchArchitectureCheckKind.SOURCE,
        ),
        _check(
            "audit:all-public",
            all(item.public_aggregate for item in selected.sources),
            True,
            True,
            "all source receipts are public aggregate",
            WorkbenchArchitectureCheckKind.SAFETY,
        ),
        _check(
            "audit:ordinals",
            tuple(item.ordinal for item in selected.operations)
            == tuple(range(1, WORKBENCH_ARCHITECTURE_OPERATION_COUNT + 1)),
            tuple(item.ordinal for item in selected.operations),
            tuple(range(1, WORKBENCH_ARCHITECTURE_OPERATION_COUNT + 1)),
            "operation order is contiguous",
            WorkbenchArchitectureCheckKind.OPERATION,
        ),
        _check(
            "audit:source-joins",
            all(
                set(item.source_ids) <= source_ids
                for item in (*selected.operations, *selected.cases)
            ),
            True,
            True,
            "case and operation source joins resolve",
            WorkbenchArchitectureCheckKind.SOURCE,
        ),
        _check(
            "audit:operation-joins",
            all(item.operation_id in operation_ids for item in selected.cases),
            True,
            True,
            "every case resolves to an operation",
            WorkbenchArchitectureCheckKind.OPERATION,
        ),
        _check(
            "audit:operation-balance",
            set(counts.values()) == {WORKBENCH_ARCHITECTURE_CASES_PER_OPERATION},
            counts,
            WORKBENCH_ARCHITECTURE_CASES_PER_OPERATION,
            "every capability contributes four cases",
            WorkbenchArchitectureCheckKind.CONTROL,
        ),
        _check(
            "audit:foreign-control",
            selected.foreign_context_key == WORKBENCH_ARCHITECTURE_FOREIGN_CONTEXT,
            selected.foreign_context_key,
            WORKBENCH_ARCHITECTURE_FOREIGN_CONTEXT,
            "foreign context is a reserved control label",
            WorkbenchArchitectureCheckKind.SAFETY,
        ),
    )
    body = {"fixture_id": selected.fixture_id, "checks": checks}
    return WorkbenchArchitectureDataAudit(
        selected.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "workbench-architecture-audit"),
    )


def load_workbench_architecture_fixture(path: str) -> WorkbenchArchitectureFixture:
    return WorkbenchArchitectureFixture.from_file(path)


def workbench_architecture_fixture_json(fixture: WorkbenchArchitectureFixture | None = None) -> str:
    return (
        json.dumps(
            (fixture or default_workbench_architecture_fixture()).to_dict(),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def workbench_architecture_delegate_rows() -> tuple[dict[str, Any], ...]:
    return _delegate_rows()


__all__ = [
    "audit_workbench_architecture_data",
    "default_workbench_architecture_fixture",
    "load_workbench_architecture_fixture",
    "workbench_architecture_delegate_rows",
    "workbench_architecture_fixture_json",
]
