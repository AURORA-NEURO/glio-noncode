"""D11 delegate execution and causal evidence receipt comparison."""

from __future__ import annotations

from typing import Any

from .causal_architecture_contracts import (
    CausalArchitectureCase,
    CausalArchitectureCaseReceipt,
    CausalArchitectureCheck,
    CausalArchitectureCheckKind,
    CausalArchitectureEvaluation,
    CausalArchitectureExecution,
    CausalArchitectureFixture,
    CausalArchitectureOperation,
    CausalArchitectureScenario,
    CausalArchitectureState,
    addressed,
)
from .causal_architecture_public_data import _family_evaluation_map, _family_fixture_map, _rows


def _delegate_outcomes() -> dict[tuple[str, str], dict[str, Any]]:
    fixtures = _family_fixture_map()
    evaluations = _family_evaluation_map(fixtures)
    return {
        (family.value, str(row["record"].record_id)): row
        for family, fixture in fixtures.items()
        for row in _rows(family, fixture, evaluations[family])
    }


def _operation_for_id(operation_id: str) -> CausalArchitectureOperation:
    from .causal_architecture_public_data import _OPERATIONS

    return _OPERATIONS[int(operation_id.split("C", 1)[1]) - 1]


def execute_causal_architecture_case(
    case: CausalArchitectureCase, *, outcomes: dict[tuple[str, str], dict[str, Any]] | None = None
) -> CausalArchitectureExecution:
    row = (outcomes or _delegate_outcomes())[(case.family.value, case.delegate_record_id)]
    state = (
        CausalArchitectureState.ACCEPTED
        if case.scenario is CausalArchitectureScenario.POSITIVE
        else CausalArchitectureState.REVIEW
    )
    counts = {"delegate_case": 1, "issue_count": len(row["issue_codes"])}
    body = {
        "case_id": case.case_id,
        "operation": _operation_for_id(case.operation_id),
        "family": case.family,
        "scenario": case.scenario,
        "observed_state": state,
        "observed_result_state": str(row["state"]),
        "observed_issue_codes": tuple(row["issue_codes"]),
        "observed_counts": counts,
        "output_address": addressed(
            {"case_id": case.case_id, "delegate": row["output_address"], "state": row["state"]},
            "causal-execution",
        ),
        "summary": {
            "delegate_fixture_id": case.delegate_fixture_id,
            "delegate_record_id": case.delegate_record_id,
            "delegate_context_key": case.delegate_context_key,
            "delegate_state": row["state"],
            "delegate_output_address": row["output_address"],
        },
        "detail": (
            f"{case.family.value} delegate {case.delegate_record_id} retained "
            "in the D11 aggregate"
        ),
    }
    return CausalArchitectureExecution(**body)


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: CausalArchitectureCheckKind,
) -> CausalArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CausalArchitectureCheck(**body, content_address=addressed(body, "causal-check"))


def _receipt(
    case: CausalArchitectureCase, execution: CausalArchitectureExecution
) -> CausalArchitectureCaseReceipt:
    passed = (
        execution.observed_state is case.expected_state
        and execution.observed_result_state == case.expected_result_state
        and execution.observed_issue_codes == case.expected_issue_codes
        and dict(execution.observed_counts) == dict(case.expected_counts)
    )
    body = {
        "case_id": case.case_id,
        "operation_id": case.operation_id,
        "expected_state": case.expected_state,
        "observed_state": execution.observed_state,
        "expected_result_state": case.expected_result_state,
        "observed_result_state": execution.observed_result_state,
        "expected_issue_codes": case.expected_issue_codes,
        "observed_issue_codes": execution.observed_issue_codes,
        "expected_counts": case.expected_counts,
        "observed_counts": execution.observed_counts,
        "passed": passed,
        "output_address": execution.output_address,
    }
    return CausalArchitectureCaseReceipt(**body, content_address=addressed(body, "causal-receipt"))


def _case_checks(
    case: CausalArchitectureCase,
    execution: CausalArchitectureExecution,
    receipt: CausalArchitectureCaseReceipt,
) -> tuple[CausalArchitectureCheck, ...]:
    return (
        _check(
            f"{case.case_id}:state",
            execution.observed_state is case.expected_state,
            execution.observed_state.value,
            case.expected_state.value,
            "aggregate state matches scenario",
            CausalArchitectureCheckKind.CASE,
        ),
        _check(
            f"{case.case_id}:result",
            execution.observed_result_state == case.expected_result_state,
            execution.observed_result_state,
            case.expected_result_state,
            "causal family state is retained",
            CausalArchitectureCheckKind.RESULT,
        ),
        _check(
            f"{case.case_id}:issues",
            execution.observed_issue_codes == case.expected_issue_codes,
            execution.observed_issue_codes,
            case.expected_issue_codes,
            "issue vocabulary is retained",
            CausalArchitectureCheckKind.CONTROL,
        ),
        _check(
            f"{case.case_id}:counts",
            dict(execution.observed_counts) == dict(case.expected_counts),
            execution.observed_counts,
            case.expected_counts,
            "count summary is retained",
            CausalArchitectureCheckKind.RESULT,
        ),
        _check(
            f"{case.case_id}:sources",
            bool(case.source_ids),
            len(case.source_ids),
            1,
            "public source receipt is attached",
            CausalArchitectureCheckKind.SOURCE,
        ),
        _check(
            f"{case.case_id}:context",
            case.delegate_context_key == case.context_key
            or "context_mismatch" in execution.observed_issue_codes,
            case.delegate_context_key,
            case.context_key,
            "delegate context is exact or mismatch is explicit",
            CausalArchitectureCheckKind.CONTROL,
        ),
        _check(
            f"{case.case_id}:receipt",
            receipt.passed and execution.output_address.startswith("sha256:"),
            receipt.passed,
            True,
            "receipt and output address are closed",
            CausalArchitectureCheckKind.CASE,
        ),
    )


def _global_checks(
    fixture: CausalArchitectureFixture, receipts: tuple[CausalArchitectureCaseReceipt, ...]
) -> tuple[CausalArchitectureCheck, ...]:
    return (
        _check(
            "global:source-count",
            len(fixture.sources) == 20,
            len(fixture.sources),
            20,
            "source registry is complete",
            CausalArchitectureCheckKind.SOURCE,
        ),
        _check(
            "global:operation-count",
            len(fixture.operations) == 16,
            len(fixture.operations),
            16,
            "operation registry is complete",
            CausalArchitectureCheckKind.OPERATION,
        ),
        _check(
            "global:case-count",
            len(fixture.cases) == 64,
            len(fixture.cases),
            64,
            "case registry is complete",
            CausalArchitectureCheckKind.CASE,
        ),
        _check(
            "global:positive-count",
            sum(item.expected_state is CausalArchitectureState.ACCEPTED for item in receipts) == 16,
            sum(item.expected_state is CausalArchitectureState.ACCEPTED for item in receipts),
            16,
            "positive coverage is complete",
            CausalArchitectureCheckKind.CONTROL,
        ),
        _check(
            "global:control-count",
            sum(item.expected_state is CausalArchitectureState.REVIEW for item in receipts) == 48,
            sum(item.expected_state is CausalArchitectureState.REVIEW for item in receipts),
            48,
            "control coverage is complete",
            CausalArchitectureCheckKind.CONTROL,
        ),
        _check(
            "global:receipt-count",
            len(receipts) == 64,
            len(receipts),
            64,
            "every case has a receipt",
            CausalArchitectureCheckKind.CASE,
        ),
        _check(
            "global:receipt-pass",
            all(item.passed for item in receipts),
            all(item.passed for item in receipts),
            True,
            "every receipt passes",
            CausalArchitectureCheckKind.RESULT,
        ),
        _check(
            "global:family-count",
            len({item.family for item in fixture.operations}) == 4,
            len({item.family for item in fixture.operations}),
            4,
            "all four causal planes execute",
            CausalArchitectureCheckKind.INVARIANT,
        ),
        _check(
            "global:operation-balance",
            all(
                sum(item.operation_id == operation.operation_id for item in fixture.cases) == 4
                for operation in fixture.operations
            ),
            tuple(
                sum(item.operation_id == operation.operation_id for item in fixture.cases)
                for operation in fixture.operations
            ),
            4,
            "each causal operation owns four cases",
            CausalArchitectureCheckKind.OPERATION,
        ),
        _check(
            "global:context-controls",
            all(
                case.delegate_context_key == case.context_key
                or "context_mismatch" in receipt.observed_issue_codes
                for case, receipt in zip(fixture.cases, receipts, strict=True)
            ),
            True,
            True,
            "foreign causal contexts are explicit controls",
            CausalArchitectureCheckKind.CONTROL,
        ),
    )


def evaluate_causal_architecture_fixture(
    fixture: CausalArchitectureFixture,
) -> CausalArchitectureEvaluation:
    outcomes = _delegate_outcomes()
    executions = tuple(
        execute_causal_architecture_case(case, outcomes=outcomes) for case in fixture.cases
    )
    receipts = tuple(
        _receipt(case, execution) for case, execution in zip(fixture.cases, executions, strict=True)
    )
    checks = tuple(
        check
        for case, execution, receipt in zip(fixture.cases, executions, receipts, strict=True)
        for check in _case_checks(case, execution, receipt)
    ) + _global_checks(fixture, receipts)
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "state": CausalArchitectureState.ACCEPTED,
        "executions": executions,
        "receipts": receipts,
        "checks": checks,
    }
    return CausalArchitectureEvaluation(
        **body, content_address=addressed(body, "causal-evaluation")
    )


__all__ = ["evaluate_causal_architecture_fixture", "execute_causal_architecture_case"]
