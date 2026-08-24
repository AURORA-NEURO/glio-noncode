"""D16 public aggregate normalization over platform, control, and deployment data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .platform_execution_architecture_contracts import (
    PLATFORM_EXECUTION_ARCHITECTURE_BOUNDARY,
    PLATFORM_EXECUTION_ARCHITECTURE_CASE_COUNT,
    PLATFORM_EXECUTION_ARCHITECTURE_CASES_PER_OPERATION,
    PLATFORM_EXECUTION_ARCHITECTURE_CONTEXT,
    PLATFORM_EXECUTION_ARCHITECTURE_FOREIGN_CONTEXT,
    PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT,
    PLATFORM_EXECUTION_ARCHITECTURE_SOURCE_COUNT,
    PLATFORM_EXECUTION_ARCHITECTURE_VERSION,
    PlatformExecutionCase,
    PlatformExecutionCheck,
    PlatformExecutionCheckKind,
    PlatformExecutionDataAudit,
    PlatformExecutionFamily,
    PlatformExecutionFixture,
    PlatformExecutionOperation,
    PlatformExecutionOperationSpec,
    PlatformExecutionPlane,
    PlatformExecutionScenario,
    PlatformExecutionSource,
    PlatformExecutionState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class _FamilySpec:
    family: PlatformExecutionFamily
    plane: PlatformExecutionPlane
    data_module: str
    fixture_function: str
    eval_module: str
    eval_function: str
    fixture_version: str


_FAMILIES = (
    _FamilySpec(
        PlatformExecutionFamily.PLATFORM,
        PlatformExecutionPlane.PLATFORM_CONTROL,
        "platform_frontier_public_data",
        "default_platform_frontier_fixture",
        "platform_frontier_fixture_eval",
        "evaluate_platform_frontier_fixture",
        "2026.08.d16-c01-c04.v1",
    ),
    _FamilySpec(
        PlatformExecutionFamily.CONTROL,
        PlatformExecutionPlane.QUALITY_CONTROL,
        "control_frontier_public_data",
        "default_control_frontier_fixture",
        "control_frontier_fixture_eval",
        "evaluate_control_frontier_fixture",
        "2026.08.d16-c05-c12.v1",
    ),
    _FamilySpec(
        PlatformExecutionFamily.DEPLOYMENT,
        PlatformExecutionPlane.DEPLOYMENT,
        "deployment_frontier_public_data",
        "default_deployment_frontier_fixture",
        "deployment_frontier_fixture_eval",
        "evaluate_deployment_frontier_fixture",
        "2026.08.d16-c13-c16.v1",
    ),
)

_OPERATIONS = (
    (
        "D16-C01",
        "mission_planner",
        PlatformExecutionOperation.MISSION_PLANNER,
        PlatformExecutionFamily.PLATFORM,
        PlatformExecutionPlane.PLATFORM_CONTROL,
        "mission request",
        "mission plan",
        (),
    ),
    (
        "D16-C02",
        "workflow_compiler",
        PlatformExecutionOperation.WORKFLOW_COMPILER,
        PlatformExecutionFamily.PLATFORM,
        PlatformExecutionPlane.PLATFORM_CONTROL,
        "mission plan",
        "workflow graph",
        ("D16-C01",),
    ),
    (
        "D16-C03",
        "typed_tool_registry",
        PlatformExecutionOperation.TYPED_TOOL_REGISTRY,
        PlatformExecutionFamily.PLATFORM,
        PlatformExecutionPlane.PLATFORM_CONTROL,
        "workflow tool references",
        "typed registry",
        ("D16-C02",),
    ),
    (
        "D16-C04",
        "execution_sandbox",
        PlatformExecutionOperation.EXECUTION_SANDBOX,
        PlatformExecutionFamily.PLATFORM,
        PlatformExecutionPlane.PLATFORM_CONTROL,
        "admitted tool call",
        "sandbox admission",
        ("D16-C03",),
    ),
    (
        "D16-C05",
        "policy_claim_gate",
        PlatformExecutionOperation.POLICY_CLAIM_GATE,
        PlatformExecutionFamily.CONTROL,
        PlatformExecutionPlane.QUALITY_CONTROL,
        "claim and source policy",
        "policy decision",
        ("D16-C04",),
    ),
    (
        "D16-C06",
        "budget_resource_scheduler",
        PlatformExecutionOperation.BUDGET_RESOURCE_SCHEDULER,
        PlatformExecutionFamily.CONTROL,
        PlatformExecutionPlane.QUALITY_CONTROL,
        "budget and resource request",
        "schedule decision",
        ("D16-C05",),
    ),
    (
        "D16-C07",
        "deterministic_fallback",
        PlatformExecutionOperation.DETERMINISTIC_FALLBACK,
        PlatformExecutionFamily.CONTROL,
        PlatformExecutionPlane.QUALITY_CONTROL,
        "failed execution candidates",
        "fallback selection",
        ("D16-C06",),
    ),
    (
        "D16-C08",
        "human_review_router",
        PlatformExecutionOperation.HUMAN_REVIEW_ROUTER,
        PlatformExecutionFamily.CONTROL,
        PlatformExecutionPlane.QUALITY_CONTROL,
        "review items",
        "review route",
        ("D16-C07",),
    ),
    (
        "D16-C09",
        "execution_ledger",
        PlatformExecutionOperation.EXECUTION_LEDGER,
        PlatformExecutionFamily.CONTROL,
        PlatformExecutionPlane.QUALITY_CONTROL,
        "execution events",
        "ledger transition",
        ("D16-C08",),
    ),
    (
        "D16-C10",
        "model_registry",
        PlatformExecutionOperation.MODEL_REGISTRY,
        PlatformExecutionFamily.CONTROL,
        PlatformExecutionPlane.QUALITY_CONTROL,
        "registry card",
        "compatibility result",
        ("D16-C09",),
    ),
    (
        "D16-C11",
        "data_reference_registry",
        PlatformExecutionOperation.DATA_REFERENCE_REGISTRY,
        PlatformExecutionFamily.CONTROL,
        PlatformExecutionPlane.QUALITY_CONTROL,
        "reference card",
        "reference compatibility",
        ("D16-C10",),
    ),
    (
        "D16-C12",
        "drift_ood_monitor",
        PlatformExecutionOperation.DRIFT_OOD_MONITOR,
        PlatformExecutionFamily.CONTROL,
        PlatformExecutionPlane.QUALITY_CONTROL,
        "monitoring metrics",
        "drift decision",
        ("D16-C11",),
    ),
    (
        "D16-C13",
        "privacy_security_policy",
        PlatformExecutionOperation.PRIVACY_SECURITY_POLICY,
        PlatformExecutionFamily.DEPLOYMENT,
        PlatformExecutionPlane.DEPLOYMENT,
        "deployment access request",
        "security decision",
        ("D16-C12",),
    ),
    (
        "D16-C14",
        "local_deployment_bundle",
        PlatformExecutionOperation.LOCAL_DEPLOYMENT_BUNDLE,
        PlatformExecutionFamily.DEPLOYMENT,
        PlatformExecutionPlane.DEPLOYMENT,
        "local bundle manifest",
        "deployment bundle",
        ("D16-C13",),
    ),
    (
        "D16-C15",
        "federated_execution",
        PlatformExecutionOperation.FEDERATED_EXECUTION,
        PlatformExecutionFamily.DEPLOYMENT,
        PlatformExecutionPlane.DEPLOYMENT,
        "site execution request",
        "federated result",
        ("D16-C14",),
    ),
    (
        "D16-C16",
        "release_rollback",
        PlatformExecutionOperation.RELEASE_ROLLBACK,
        PlatformExecutionFamily.DEPLOYMENT,
        PlatformExecutionPlane.DEPLOYMENT,
        "release checks",
        "release or rollback decision",
        ("D16-C15",),
    ),
)


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


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _safe_payload(value: Any) -> Any:
    restricted = {
        "patient_id",
        "participant_id",
        "subject_id",
        "individual_id",
        "clinical_decision",
        "treatment_recommendation",
    }
    if isinstance(value, dict):
        return {
            str(key): _safe_payload(child)
            for key, child in value.items()
            if str(key) not in restricted
        }
    if isinstance(value, list):
        return [_safe_payload(child) for child in value]
    if isinstance(value, tuple):
        return tuple(_safe_payload(child) for child in value)
    return value


@lru_cache(maxsize=1)
def _delegate_rows() -> tuple[dict[str, Any], ...]:
    rows = []
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
                    "observed_state": _enum_value(
                        getattr(execution, "observed_state", getattr(execution, "state", "invalid"))
                    ),
                    "issue_codes": tuple(str(item) for item in execution.issue_codes),
                    "output_address": execution.content_address,
                    "delegate_context_key": str(
                        getattr(record, "context_key", output.get("context_key", ""))
                    ),
                    "expected_record_state": _enum_value(record.expected_state),
                    "expected_record_issue_codes": tuple(
                        str(item) for item in record.expected_issue_codes
                    ),
                }
            )
    return tuple(rows)


def _source_rows() -> tuple[dict[str, Any], ...]:
    rows = []
    for spec, fixture, _executions in _family_objects():
        for source in fixture.sources:
            body = {
                "source_id": f"D16-{spec.family.value}:{source.source_id}",
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
            rows.append(body | {"content_address": addressed(body, "platform-execution-source")})
    return tuple(rows)


def default_platform_execution_fixture() -> PlatformExecutionFixture:
    source_rows = _source_rows()
    sources = tuple(PlatformExecutionSource(**row) for row in source_rows)
    source_map = {
        (row["family"].value, row["delegate_source_id"]): row["source_id"] for row in source_rows
    }
    family_contexts = {
        spec.family.value: fixture.context_key for spec, fixture, _ in _family_objects()
    }
    operations = []
    cases = []
    for ordinal, (
        operation_id,
        delegate_operation,
        operation,
        family,
        plane,
        input_contract,
        output_contract,
        dependencies,
    ) in enumerate(_OPERATIONS, start=1):
        family_rows = [
            row
            for row in _delegate_rows()
            if row["family"] is family
            and _enum_value(row["record"].operation) == delegate_operation
        ]
        operation_sources = tuple(
            sorted(
                {
                    source_map[(family.value, source_id)]
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
                "retain exact execution state and issue codes; hold unsafe or unsupported paths"
            ),
        }
        operations.append(
            PlatformExecutionOperationSpec(
                **op_body, content_address=addressed(op_body, "platform-execution-operation")
            )
        )
        for index, row in enumerate(family_rows):
            record = row["record"]
            scenario = (
                PlatformExecutionScenario.POSITIVE
                if index == 0
                else PlatformExecutionScenario(("control_a", "control_b", "control_c")[index - 1])
            )
            case_id = f"{operation_id}-{scenario.value.upper().replace('_', '-')}-001"
            payload = _safe_payload(record.payload) if isinstance(record.payload, dict) else {}
            source_ids = tuple(
                sorted({source_map[(family.value, source_id)] for source_id in record.source_ids})
            )
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
                "aggregate_context_key": PLATFORM_EXECUTION_ARCHITECTURE_CONTEXT,
                "delegate_context_key": row["delegate_context_key"],
                "delegate_fixture_id": row["fixture"].fixture_id,
                "delegate_record_id": record.record_id,
                "delegate_class": type(record).__name__,
                "source_ids": source_ids,
                "payload": payload,
                "expected_state": PlatformExecutionState(row["observed_state"]),
                "expected_issue_codes": row["issue_codes"],
                "expected_counts": counts,
                "description": (
                    f"{operation_id} {scenario.value} retains {record.record_id} "
                    f"from {family.value}"
                ),
            }
            cases.append(
                PlatformExecutionCase(
                    **case_body, content_address=addressed(case_body, "platform-execution-case")
                )
            )
    body = {
        "fixture_id": "platform-execution-architecture-public-aggregate-001",
        "version": PLATFORM_EXECUTION_ARCHITECTURE_VERSION,
        "boundary": PLATFORM_EXECUTION_ARCHITECTURE_BOUNDARY,
        "context_key": PLATFORM_EXECUTION_ARCHITECTURE_CONTEXT,
        "foreign_context_key": PLATFORM_EXECUTION_ARCHITECTURE_FOREIGN_CONTEXT,
        "family_contexts": family_contexts,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return PlatformExecutionFixture(
        **body, content_address=addressed(body, "platform-execution-fixture")
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: PlatformExecutionCheckKind,
) -> PlatformExecutionCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return PlatformExecutionCheck(
        **body, content_address=addressed(body, "platform-execution-audit-check")
    )


def audit_platform_execution_data(
    fixture: PlatformExecutionFixture | None = None,
) -> PlatformExecutionDataAudit:
    selected = fixture or default_platform_execution_fixture()
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
            len(selected.sources) == PLATFORM_EXECUTION_ARCHITECTURE_SOURCE_COUNT,
            len(selected.sources),
            PLATFORM_EXECUTION_ARCHITECTURE_SOURCE_COUNT,
            "three public source registries are retained",
            PlatformExecutionCheckKind.SOURCE,
        ),
        _check(
            "audit:operation-count",
            len(selected.operations) == PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT,
            len(selected.operations),
            PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT,
            "all D16 capability operations are declared",
            PlatformExecutionCheckKind.OPERATION,
        ),
        _check(
            "audit:case-count",
            len(selected.cases) == PLATFORM_EXECUTION_ARCHITECTURE_CASE_COUNT,
            len(selected.cases),
            PLATFORM_EXECUTION_ARCHITECTURE_CASE_COUNT,
            "four scenarios are retained per operation",
            PlatformExecutionCheckKind.CASE,
        ),
        _check(
            "audit:family-contexts",
            len(selected.family_contexts) == 3 and all(selected.family_contexts.values()),
            selected.family_contexts,
            "three exact delegate contexts",
            "family contexts remain visible",
            PlatformExecutionCheckKind.SOURCE,
        ),
        _check(
            "audit:all-public",
            all(item.public_aggregate for item in selected.sources),
            True,
            True,
            "all source receipts are public aggregate",
            PlatformExecutionCheckKind.SAFETY,
        ),
        _check(
            "audit:ordinals",
            tuple(item.ordinal for item in selected.operations)
            == tuple(range(1, PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT + 1)),
            tuple(item.ordinal for item in selected.operations),
            tuple(range(1, PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT + 1)),
            "operation order is contiguous",
            PlatformExecutionCheckKind.OPERATION,
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
            PlatformExecutionCheckKind.SOURCE,
        ),
        _check(
            "audit:operation-joins",
            all(item.operation_id in operation_ids for item in selected.cases),
            True,
            True,
            "every case resolves to an operation",
            PlatformExecutionCheckKind.OPERATION,
        ),
        _check(
            "audit:operation-balance",
            set(counts.values()) == {PLATFORM_EXECUTION_ARCHITECTURE_CASES_PER_OPERATION},
            counts,
            PLATFORM_EXECUTION_ARCHITECTURE_CASES_PER_OPERATION,
            "every capability contributes four cases",
            PlatformExecutionCheckKind.CONTROL,
        ),
        _check(
            "audit:foreign-control",
            selected.foreign_context_key == PLATFORM_EXECUTION_ARCHITECTURE_FOREIGN_CONTEXT,
            selected.foreign_context_key,
            PLATFORM_EXECUTION_ARCHITECTURE_FOREIGN_CONTEXT,
            "foreign context is a reserved control label",
            PlatformExecutionCheckKind.SAFETY,
        ),
    )
    body = {"fixture_id": selected.fixture_id, "checks": checks}
    return PlatformExecutionDataAudit(
        selected.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "platform-execution-audit"),
    )


def load_platform_execution_fixture(path: str) -> PlatformExecutionFixture:
    return PlatformExecutionFixture.from_file(path)


def platform_execution_fixture_json(fixture: PlatformExecutionFixture | None = None) -> str:
    return (
        json.dumps(
            (fixture or default_platform_execution_fixture()).to_dict(), indent=2, sort_keys=True
        )
        + "\n"
    )


def platform_execution_delegate_rows() -> tuple[dict[str, Any], ...]:
    return _delegate_rows()


__all__ = [
    "audit_platform_execution_data",
    "default_platform_execution_fixture",
    "load_platform_execution_fixture",
    "platform_execution_delegate_rows",
    "platform_execution_fixture_json",
]
