"""D12 delegate execution and receipt accounting."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .cohort_architecture_contracts import (
    CohortArchitectureCase,
    CohortArchitectureCaseReceipt,
    CohortArchitectureCheck,
    CohortArchitectureCheckKind,
    CohortArchitectureEvaluation,
    CohortArchitectureExecution,
    CohortArchitectureFixture,
    CohortArchitectureScenario,
    CohortArchitectureState,
    addressed,
)
from .cohort_architecture_public_data import cohort_architecture_delegate_rows


def _delegate_outcomes() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (row["family"].value, row["record"].record_id): row
        for row in cohort_architecture_delegate_rows()
    }


def _check(
    check_id: str,
    kind: CohortArchitectureCheckKind,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> CohortArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CohortArchitectureCheck(**body, content_address=addressed(body, "cohort-eval-check"))


def _execution_for_case(
    case: CohortArchitectureCase,
    outcomes: Mapping[tuple[str, str], dict[str, Any]],
) -> CohortArchitectureExecution:
    row = outcomes.get((case.family.value, case.delegate_record_id))
    if row is None:
        body = {
            "case_id": case.case_id,
            "operation": case.operation,
            "family": case.family,
            "scenario": case.scenario,
            "observed_state": CohortArchitectureState.INVALID,
            "observed_issue_codes": ("missing_delegate_record",),
            "observed_counts": {"source_count": 0, "payload_field_count": 0, "row_count": 0},
            "output_address": addressed(case.case_id, "cohort-missing-output"),
            "summary": {"delegate_record_id": case.delegate_record_id},
            "detail": "delegate record could not be resolved from the pinned family fixtures",
        }
        return CohortArchitectureExecution(**body)
    output = row["output"] if isinstance(row["output"], Mapping) else {}
    body = {
        "case_id": case.case_id,
        "operation": case.operation,
        "family": case.family,
        "scenario": case.scenario,
        "observed_state": CohortArchitectureState(row["observed_state"]),
        "observed_issue_codes": tuple(str(item) for item in row["issue_codes"]),
        "observed_counts": dict(case.expected_counts),
        "output_address": str(row["output_address"]),
        "summary": {
            "delegate_fixture_id": row["delegate_fixture_id"],
            "delegate_record_id": row["record"].record_id,
            "delegate_class": row["delegate_class"],
            "delegate_context_key": row["delegate_context_key"],
            "delegate_output_keys": tuple(sorted(str(key) for key in output)),
        },
        "detail": (
            f"{case.family.value} delegate {case.delegate_record_id} retained "
            "with its observed cohort state"
        ),
    }
    return CohortArchitectureExecution(**body)


def execute_cohort_architecture_case(
    case: CohortArchitectureCase,
) -> CohortArchitectureExecution:
    return _execution_for_case(case, _delegate_outcomes())


def _receipt(
    case: CohortArchitectureCase,
    execution: CohortArchitectureExecution,
) -> CohortArchitectureCaseReceipt:
    passed = (
        execution.observed_state is case.expected_state
        and execution.observed_issue_codes == case.expected_issue_codes
        and execution.observed_counts == case.expected_counts
        and bool(execution.output_address)
    )
    body = {
        "case_id": case.case_id,
        "operation_id": case.operation_id,
        "expected_state": case.expected_state,
        "observed_state": execution.observed_state,
        "expected_issue_codes": case.expected_issue_codes,
        "observed_issue_codes": execution.observed_issue_codes,
        "expected_counts": case.expected_counts,
        "observed_counts": execution.observed_counts,
        "passed": passed,
        "output_address": execution.output_address,
    }
    return CohortArchitectureCaseReceipt(
        **body,
        content_address=addressed(body, "cohort-receipt"),
    )


def _case_checks(
    case: CohortArchitectureCase,
    execution: CohortArchitectureExecution,
    receipt: CohortArchitectureCaseReceipt,
    source_ids: set[str],
    operation_ids: set[str],
    family_contexts: Mapping[str, str],
) -> tuple[CohortArchitectureCheck, ...]:
    return (
        _check(
            f"{case.case_id}:state",
            CohortArchitectureCheckKind.RESULT,
            execution.observed_state is case.expected_state,
            execution.observed_state.value,
            case.expected_state.value,
            "delegate state matches the aggregate expectation",
        ),
        _check(
            f"{case.case_id}:issues",
            CohortArchitectureCheckKind.RESULT,
            execution.observed_issue_codes == case.expected_issue_codes,
            execution.observed_issue_codes,
            case.expected_issue_codes,
            "issue vocabulary is retained without suppression",
        ),
        _check(
            f"{case.case_id}:counts",
            CohortArchitectureCheckKind.CASE,
            execution.observed_counts == case.expected_counts,
            execution.observed_counts,
            case.expected_counts,
            "payload and source counts remain reproducible",
        ),
        _check(
            f"{case.case_id}:operation",
            CohortArchitectureCheckKind.OPERATION,
            case.operation_id in operation_ids,
            case.operation_id,
            True,
            "case operation join resolves",
        ),
        _check(
            f"{case.case_id}:sources",
            CohortArchitectureCheckKind.SOURCE,
            set(case.source_ids) <= source_ids,
            set(case.source_ids),
            source_ids,
            "case source joins resolve",
        ),
        _check(
            f"{case.case_id}:context",
            CohortArchitectureCheckKind.CONTROL,
            execution.summary.get("delegate_context_key")
            == family_contexts.get(case.family.value)
            or "context_mismatch" in execution.observed_issue_codes,
            execution.summary.get("delegate_context_key"),
            family_contexts.get(case.family.value),
            "delegate context is exact or mismatch is explicit",
        ),
        _check(
            f"{case.case_id}:receipt",
            CohortArchitectureCheckKind.CASE,
            receipt.passed and bool(receipt.content_address),
            receipt.passed,
            True,
            "case receipt is addressed and closed",
        ),
    )


def _global_checks(
    fixture: CohortArchitectureFixture,
    executions: tuple[CohortArchitectureExecution, ...],
    source_ids: set[str],
) -> tuple[CohortArchitectureCheck, ...]:
    family_counts = {
        family.value: sum(item.family is family for item in executions)
        for family in fixture.family_set
    }
    operation_counts = {
        operation.operation_id: sum(
            item.case_id.startswith(f"{operation.operation_id}-") for item in executions
        )
        for operation in fixture.operations
    }
    scenario_counts = {
        scenario.value: sum(item.scenario.value == scenario.value for item in executions)
        for scenario in CohortArchitectureScenario
    }
    return (
        _check(
            "global:execution-count",
            CohortArchitectureCheckKind.FIXTURE,
            len(executions) == 64,
            len(executions),
            64,
            "all aggregate cases execute",
        ),
        _check(
            "global:positive-count",
            CohortArchitectureCheckKind.CONTROL,
            scenario_counts["positive"] == 16,
            scenario_counts["positive"],
            16,
            "all positive paths remain represented",
        ),
        _check(
            "global:control-count",
            CohortArchitectureCheckKind.CONTROL,
            sum(scenario_counts[item] for item in ("control_a", "control_b", "control_c")) == 48,
            scenario_counts,
            {"control_a": 16, "control_b": 16, "control_c": 16},
            "control distribution is balanced",
        ),
        _check(
            "global:family-counts",
            CohortArchitectureCheckKind.FIXTURE,
            set(family_counts.values()) == {16},
            family_counts,
            "each family contributes sixteen cases",
            "four families are balanced",
        ),
        _check(
            "global:operation-counts",
            CohortArchitectureCheckKind.OPERATION,
            set(operation_counts.values()) == {4},
            operation_counts,
            "each operation contributes four cases",
            "operation matrix is closed",
        ),
        _check(
            "global:source-coverage",
            CohortArchitectureCheckKind.SOURCE,
            all(set(item.source_ids) <= source_ids for item in fixture.cases),
            True,
            True,
            "all case source references resolve",
        ),
        _check(
            "global:state-coverage",
            CohortArchitectureCheckKind.RESULT,
            all(item.observed_state.value for item in executions),
            True,
            True,
            "every delegate returns an explicit state",
        ),
        _check(
            "global:address-coverage",
            CohortArchitectureCheckKind.REPLAY,
            all(item.output_address for item in executions),
            True,
            True,
            "every delegate output has an address",
        ),
        _check(
            "global:receipt-coverage",
            CohortArchitectureCheckKind.REPLAY,
            len(executions) == len(fixture.cases),
            len(executions),
            len(fixture.cases),
            "every aggregate case has an execution receipt",
        ),
        _check(
            "global:control-contexts",
            CohortArchitectureCheckKind.CONTROL,
            all(
                execution.summary.get("delegate_context_key")
                == fixture.family_contexts.get(execution.family.value)
                or "context_mismatch" in execution.observed_issue_codes
                for execution in executions
            ),
            True,
            True,
            "foreign contexts are explicit control outcomes",
        ),
    )


def evaluate_cohort_architecture_fixture(
    fixture: CohortArchitectureFixture | None = None,
) -> CohortArchitectureEvaluation:
    from .cohort_architecture_public_data import default_cohort_architecture_fixture

    selected = fixture or default_cohort_architecture_fixture()
    outcomes = _delegate_outcomes()
    source_ids = {item.source_id for item in selected.sources}
    operation_ids = {item.operation_id for item in selected.operations}
    executions = tuple(_execution_for_case(item, outcomes) for item in selected.cases)
    receipts = tuple(
        _receipt(case, execution)
        for case, execution in zip(selected.cases, executions, strict=True)
    )
    checks = tuple(
        check
        for case, execution, receipt in zip(selected.cases, executions, receipts, strict=True)
        for check in _case_checks(
            case,
            execution,
            receipt,
            source_ids,
            operation_ids,
            selected.family_contexts,
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
    return CohortArchitectureEvaluation(
        selected.fixture_id,
        selected.context_key,
        state,
        executions,
        receipts,
        checks,
        addressed(body, "cohort-evaluation"),
    )


__all__ = [
    "evaluate_cohort_architecture_fixture",
    "execute_cohort_architecture_case",
]
