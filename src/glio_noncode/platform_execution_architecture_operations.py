"""D16 delegate execution, receipts, and platform control checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .platform_execution_architecture_contracts import (
    PLATFORM_EXECUTION_ARCHITECTURE_CASE_COUNT,
    PLATFORM_EXECUTION_ARCHITECTURE_CASES_PER_OPERATION,
    PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT,
    PlatformExecutionCase,
    PlatformExecutionCheck,
    PlatformExecutionCheckKind,
    PlatformExecutionEvaluation,
    PlatformExecutionExecution,
    PlatformExecutionFixture,
    PlatformExecutionScenario,
    PlatformExecutionState,
    addressed,
)
from .platform_execution_architecture_public_data import (
    default_platform_execution_fixture,
    platform_execution_delegate_rows,
)


def _outcomes() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (row["family"].value, row["record"].record_id): row
        for row in platform_execution_delegate_rows()
    }


def _check(
    check_id: str,
    kind: PlatformExecutionCheckKind,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
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
        **body, content_address=addressed(body, "platform-execution-check")
    )


def _execute(
    case: PlatformExecutionCase, outcomes: Mapping[tuple[str, str], dict[str, Any]]
) -> PlatformExecutionExecution:
    row = outcomes.get((case.family.value, case.delegate_record_id))
    if row is None:
        return PlatformExecutionExecution(
            case.case_id,
            case.operation,
            case.family,
            case.scenario,
            PlatformExecutionState.REJECTED,
            ("missing_delegate_record",),
            {
                "source_count": 0,
                "payload_field_count": 0,
                "output_field_count": 0,
                "issue_count": 1,
            },
            addressed(case.case_id, "platform-execution-missing-output"),
            {"delegate_record_id": case.delegate_record_id},
            "delegate record is unresolved",
        )
    output = row["output"] if isinstance(row["output"], Mapping) else {}
    return PlatformExecutionExecution(
        case.case_id,
        case.operation,
        case.family,
        case.scenario,
        PlatformExecutionState(row["observed_state"]),
        tuple(row["issue_codes"]),
        dict(case.expected_counts),
        row["output_address"],
        {
            "delegate_fixture_id": row["fixture"].fixture_id,
            "delegate_record_id": row["record"].record_id,
            "delegate_class": type(row["record"]).__name__,
            "delegate_operation": row["record"].operation.value,
            "delegate_context_key": row["delegate_context_key"],
            "delegate_output_keys": tuple(sorted(str(key) for key in output)),
            "delegate_expected_state": row["expected_record_state"],
            "delegate_expected_issue_codes": row["expected_record_issue_codes"],
        },
        (
            f"{case.family.value} delegate {case.delegate_record_id} retained with state "
            f"{row['observed_state']}"
        ),
    )


def execute_platform_execution_case(case: PlatformExecutionCase) -> PlatformExecutionExecution:
    return _execute(case, _outcomes())


def _receipt(case: PlatformExecutionCase, execution: PlatformExecutionExecution) -> dict[str, Any]:
    body = {
        "case_id": case.case_id,
        "operation_id": case.operation_id,
        "expected_state": case.expected_state,
        "observed_state": execution.observed_state,
        "expected_issue_codes": case.expected_issue_codes,
        "observed_issue_codes": execution.observed_issue_codes,
        "expected_counts": case.expected_counts,
        "observed_counts": execution.observed_counts,
        "passed": execution.observed_state is case.expected_state
        and execution.observed_issue_codes == case.expected_issue_codes
        and execution.observed_counts == case.expected_counts
        and bool(execution.output_address),
        "output_address": execution.output_address,
    }
    return body | {"content_address": addressed(body, "platform-execution-receipt")}


def _case_checks(
    case: PlatformExecutionCase,
    execution: PlatformExecutionExecution,
    receipt: Mapping[str, Any],
    source_ids: set[str],
    operation_ids: set[str],
    contexts: Mapping[str, str],
) -> tuple[PlatformExecutionCheck, ...]:
    expected_context = contexts.get(case.family.value, "")
    return (
        _check(
            f"{case.case_id}:state",
            PlatformExecutionCheckKind.RESULT,
            execution.observed_state is case.expected_state,
            execution.observed_state.value,
            case.expected_state.value,
            "delegate state matches",
        ),
        _check(
            f"{case.case_id}:issues",
            PlatformExecutionCheckKind.RESULT,
            execution.observed_issue_codes == case.expected_issue_codes,
            execution.observed_issue_codes,
            case.expected_issue_codes,
            "issue codes match",
        ),
        _check(
            f"{case.case_id}:counts",
            PlatformExecutionCheckKind.CASE,
            execution.observed_counts == case.expected_counts,
            execution.observed_counts,
            case.expected_counts,
            "bounded counts match",
        ),
        _check(
            f"{case.case_id}:operation",
            PlatformExecutionCheckKind.OPERATION,
            case.operation_id in operation_ids,
            case.operation_id,
            True,
            "operation join resolves",
        ),
        _check(
            f"{case.case_id}:sources",
            PlatformExecutionCheckKind.SOURCE,
            set(case.source_ids) <= source_ids,
            set(case.source_ids),
            source_ids,
            "source joins resolve",
        ),
        _check(
            f"{case.case_id}:context",
            PlatformExecutionCheckKind.SAFETY,
            case.delegate_context_key == expected_context
            or "context_mismatch" in execution.observed_issue_codes,
            case.delegate_context_key,
            expected_context,
            "exact context or explicit mismatch",
        ),
        _check(
            f"{case.case_id}:receipt",
            PlatformExecutionCheckKind.CASE,
            bool(receipt["passed"] and receipt["content_address"]),
            receipt["passed"],
            True,
            "receipt closes",
        ),
    )


def _global_checks(
    fixture: PlatformExecutionFixture,
    executions: tuple[PlatformExecutionExecution, ...],
    source_ids: set[str],
) -> tuple[PlatformExecutionCheck, ...]:
    family_counts = {
        family.value: sum(item.family is family for item in executions)
        for family in fixture.family_set
    }
    operation_counts = {
        operation.operation_id: sum(
            item.operation.value == operation.operation.value for item in executions
        )
        for operation in fixture.operations
    }
    scenario_counts = {
        scenario.value: sum(item.scenario is scenario for item in executions)
        for scenario in PlatformExecutionScenario
    }
    case_by_id = {item.case_id: item for item in fixture.cases}
    return (
        _check(
            "global:execution-count",
            PlatformExecutionCheckKind.FIXTURE,
            len(executions) == PLATFORM_EXECUTION_ARCHITECTURE_CASE_COUNT,
            len(executions),
            PLATFORM_EXECUTION_ARCHITECTURE_CASE_COUNT,
            "all D16 cases execute",
        ),
        _check(
            "global:positive-count",
            PlatformExecutionCheckKind.CONTROL,
            scenario_counts["positive"] == PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT,
            scenario_counts["positive"],
            PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT,
            "one positive path per operation",
        ),
        _check(
            "global:control-count",
            PlatformExecutionCheckKind.CONTROL,
            all(
                scenario_counts[item] == PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT
                for item in ("control_a", "control_b", "control_c")
            ),
            scenario_counts,
            {item: 16 for item in ("control_a", "control_b", "control_c")},
            "controls are balanced",
        ),
        _check(
            "global:family-counts",
            PlatformExecutionCheckKind.FIXTURE,
            family_counts
            == {"platform_frontier": 16, "control_frontier": 32, "deployment_frontier": 16},
            family_counts,
            "platform, control, and deployment families close",
            "family counts close",
        ),
        _check(
            "global:operation-counts",
            PlatformExecutionCheckKind.OPERATION,
            set(operation_counts.values()) == {PLATFORM_EXECUTION_ARCHITECTURE_CASES_PER_OPERATION},
            operation_counts,
            4,
            "four cases per operation",
        ),
        _check(
            "global:source-coverage",
            PlatformExecutionCheckKind.SOURCE,
            all(set(item.source_ids) <= source_ids for item in fixture.cases),
            True,
            True,
            "source coverage closes",
        ),
        _check(
            "global:state-coverage",
            PlatformExecutionCheckKind.RESULT,
            all(item.observed_state.value for item in executions),
            True,
            True,
            "every result has a state",
        ),
        _check(
            "global:address-coverage",
            PlatformExecutionCheckKind.REPLAY,
            all(item.output_address for item in executions),
            True,
            True,
            "every output is addressed",
        ),
        _check(
            "global:control-contexts",
            PlatformExecutionCheckKind.SAFETY,
            all(
                case.delegate_context_key == fixture.family_contexts[case.family.value]
                or "context_mismatch" in execution.observed_issue_codes
                for execution in executions
                for case in (case_by_id[execution.case_id],)
            ),
            True,
            True,
            "foreign context is explicit",
        ),
        _check(
            "global:receipt-coverage",
            PlatformExecutionCheckKind.REPLAY,
            len(executions) == len(fixture.cases),
            len(executions),
            len(fixture.cases),
            "receipts cover cases",
        ),
    )


def evaluate_platform_execution_fixture(
    fixture: PlatformExecutionFixture | None = None,
) -> PlatformExecutionEvaluation:
    selected = fixture or default_platform_execution_fixture()
    source_ids = {item.source_id for item in selected.sources}
    operation_ids = {item.operation_id for item in selected.operations}
    executions = tuple(_execute(case, _outcomes()) for case in selected.cases)
    receipt_dicts = tuple(
        _receipt(case, execution)
        for case, execution in zip(selected.cases, executions, strict=True)
    )
    from .platform_execution_architecture_contracts import PlatformExecutionReceipt

    receipts = tuple(
        PlatformExecutionReceipt(
            case["case_id"],
            case["operation_id"],
            case["expected_state"],
            case["observed_state"],
            case["expected_issue_codes"],
            case["observed_issue_codes"],
            case["expected_counts"],
            case["observed_counts"],
            case["passed"],
            case["output_address"],
            case["content_address"],
        )
        for case in receipt_dicts
    )
    checks = tuple(
        check
        for case, execution, receipt in zip(selected.cases, executions, receipt_dicts, strict=True)
        for check in _case_checks(
            case, execution, receipt, source_ids, operation_ids, selected.family_contexts
        )
    ) + _global_checks(selected, executions, source_ids)
    state = "accepted" if all(item.passed for item in checks) else "review"
    body = {
        "fixture_id": selected.fixture_id,
        "context_key": selected.context_key,
        "state": state,
        "executions": executions,
        "receipts": receipts,
        "checks": checks,
    }
    return PlatformExecutionEvaluation(
        selected.fixture_id,
        selected.context_key,
        state,
        executions,
        receipts,
        checks,
        addressed(body, "platform-execution-evaluation"),
    )


__all__ = ["evaluate_platform_execution_fixture", "execute_platform_execution_case"]
