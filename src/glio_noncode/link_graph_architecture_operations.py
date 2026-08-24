"""D10 delegate execution, receipt comparison, and control accounting."""

from __future__ import annotations

from typing import Any

from .link_graph_architecture_contracts import (
    LinkGraphArchitectureCase,
    LinkGraphArchitectureCaseReceipt,
    LinkGraphArchitectureCheck,
    LinkGraphArchitectureCheckKind,
    LinkGraphArchitectureEvaluation,
    LinkGraphArchitectureExecution,
    LinkGraphArchitectureFixture,
    LinkGraphArchitectureOperation,
    LinkGraphArchitectureScenario,
    LinkGraphArchitectureState,
    addressed,
)
from .link_graph_architecture_public_data import (
    _family_evaluation_map,
    _family_fixture_map,
    _rows,
)


def _delegate_outcomes() -> dict[tuple[str, str], dict[str, Any]]:
    fixtures = _family_fixture_map()
    evaluations = _family_evaluation_map(fixtures)
    outcomes: dict[tuple[str, str], dict[str, Any]] = {}
    for family, fixture in fixtures.items():
        for row in _rows(family, fixture, evaluations[family]):
            record = row["record"]
            outcomes[(family.value, str(record.record_id))] = row
    return outcomes


def execute_link_graph_architecture_case(
    case: LinkGraphArchitectureCase,
    *,
    outcomes: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> LinkGraphArchitectureExecution:
    selected = outcomes or _delegate_outcomes()
    row = selected[(case.family.value, case.delegate_record_id)]
    aggregate_state = (
        LinkGraphArchitectureState.ACCEPTED
        if case.scenario is LinkGraphArchitectureScenario.POSITIVE
        else LinkGraphArchitectureState.REVIEW
    )
    counts = {"delegate_case": 1, "issue_count": len(row["issue_codes"])}
    operation = _operation_for_id(case.operation_id)
    body = {
        "case_id": case.case_id,
        "operation": operation,
        "family": case.family,
        "scenario": case.scenario,
        "observed_state": aggregate_state,
        "observed_result_state": str(row["state"]),
        "observed_issue_codes": tuple(row["issue_codes"]),
        "observed_counts": counts,
        "output_address": addressed(
            {"case_id": case.case_id, "delegate": row["output_address"], "state": row["state"]},
            "link-execution",
        ),
        "summary": {
            "delegate_fixture_id": case.delegate_fixture_id,
            "delegate_record_id": case.delegate_record_id,
            "delegate_context_key": case.delegate_context_key,
            "delegate_state": row["state"],
            "delegate_output_address": row["output_address"],
        },
        "detail": (
            f"{case.family.value} delegate {case.delegate_record_id} retained in the D10 aggregate"
        ),
    }
    return LinkGraphArchitectureExecution(**body)


def _operation_for_id(operation_id: str) -> LinkGraphArchitectureOperation:
    from .link_graph_architecture_public_data import _OPERATIONS

    ordinal = int(operation_id.split("C", 1)[1])
    return _OPERATIONS[ordinal - 1]


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: LinkGraphArchitectureCheckKind,
) -> LinkGraphArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return LinkGraphArchitectureCheck(**body, content_address=addressed(body, "link-check"))


def _receipt(
    case: LinkGraphArchitectureCase, execution: LinkGraphArchitectureExecution
) -> LinkGraphArchitectureCaseReceipt:
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
    return LinkGraphArchitectureCaseReceipt(**body, content_address=addressed(body, "link-receipt"))


def _case_checks(
    case: LinkGraphArchitectureCase,
    execution: LinkGraphArchitectureExecution,
    receipt: LinkGraphArchitectureCaseReceipt,
) -> tuple[LinkGraphArchitectureCheck, ...]:
    return (
        _check(
            f"{case.case_id}:state",
            execution.observed_state is case.expected_state,
            execution.observed_state.value,
            case.expected_state.value,
            "aggregate state matches scenario",
            LinkGraphArchitectureCheckKind.CASE,
        ),
        _check(
            f"{case.case_id}:result",
            execution.observed_result_state == case.expected_result_state,
            execution.observed_result_state,
            case.expected_result_state,
            "delegate result state is retained",
            LinkGraphArchitectureCheckKind.RESULT,
        ),
        _check(
            f"{case.case_id}:issues",
            execution.observed_issue_codes == case.expected_issue_codes,
            execution.observed_issue_codes,
            case.expected_issue_codes,
            "delegate issue vocabulary is retained",
            LinkGraphArchitectureCheckKind.CONTROL,
        ),
        _check(
            f"{case.case_id}:counts",
            dict(execution.observed_counts) == dict(case.expected_counts),
            execution.observed_counts,
            case.expected_counts,
            "delegate count summary is retained",
            LinkGraphArchitectureCheckKind.RESULT,
        ),
        _check(
            f"{case.case_id}:sources",
            bool(case.source_ids),
            len(case.source_ids),
            1,
            "case retains public source receipts",
            LinkGraphArchitectureCheckKind.SOURCE,
        ),
        _check(
            f"{case.case_id}:context",
            case.delegate_context_key == case.context_key
            or "context_mismatch" in execution.observed_issue_codes,
            case.delegate_context_key,
            case.context_key,
            "delegate context is exact or mismatch is explicit",
            LinkGraphArchitectureCheckKind.CONTROL,
        ),
        _check(
            f"{case.case_id}:receipt",
            receipt.passed and execution.output_address.startswith("sha256:"),
            receipt.passed,
            True,
            "case receipt and output address are closed",
            LinkGraphArchitectureCheckKind.CASE,
        ),
    )


def _global_checks(
    fixture: LinkGraphArchitectureFixture, receipts: tuple[LinkGraphArchitectureCaseReceipt, ...]
) -> tuple[LinkGraphArchitectureCheck, ...]:
    return (
        _check(
            "global:source-count",
            len(fixture.sources) == 19,
            len(fixture.sources),
            19,
            "source registry is complete",
            LinkGraphArchitectureCheckKind.SOURCE,
        ),
        _check(
            "global:operation-count",
            len(fixture.operations) == 16,
            len(fixture.operations),
            16,
            "operation registry is complete",
            LinkGraphArchitectureCheckKind.OPERATION,
        ),
        _check(
            "global:case-count",
            len(fixture.cases) == 64,
            len(fixture.cases),
            64,
            "case registry is complete",
            LinkGraphArchitectureCheckKind.CASE,
        ),
        _check(
            "global:positive-count",
            sum(item.expected_state is LinkGraphArchitectureState.ACCEPTED for item in receipts)
            == 16,
            sum(item.expected_state is LinkGraphArchitectureState.ACCEPTED for item in receipts),
            16,
            "positive paths are complete",
            LinkGraphArchitectureCheckKind.CONTROL,
        ),
        _check(
            "global:control-count",
            sum(item.expected_state is LinkGraphArchitectureState.REVIEW for item in receipts)
            == 48,
            sum(item.expected_state is LinkGraphArchitectureState.REVIEW for item in receipts),
            48,
            "control paths are complete",
            LinkGraphArchitectureCheckKind.CONTROL,
        ),
        _check(
            "global:receipt-count",
            len(receipts) == 64,
            len(receipts),
            64,
            "every case has a receipt",
            LinkGraphArchitectureCheckKind.CASE,
        ),
        _check(
            "global:receipt-pass",
            all(item.passed for item in receipts),
            all(item.passed for item in receipts),
            True,
            "every receipt passes",
            LinkGraphArchitectureCheckKind.RESULT,
        ),
        _check(
            "global:family-count",
            len({item.family for item in fixture.operations}) == 4,
            len({item.family for item in fixture.operations}),
            4,
            "all four family planes execute",
            LinkGraphArchitectureCheckKind.INVARIANT,
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
            "each link operation owns four cases",
            LinkGraphArchitectureCheckKind.OPERATION,
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
            "foreign link contexts are explicit controls",
            LinkGraphArchitectureCheckKind.CONTROL,
        ),
    )


def evaluate_link_graph_architecture_fixture(
    fixture: LinkGraphArchitectureFixture,
) -> LinkGraphArchitectureEvaluation:
    outcomes = _delegate_outcomes()
    executions = tuple(
        execute_link_graph_architecture_case(case, outcomes=outcomes) for case in fixture.cases
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
        "state": LinkGraphArchitectureState.ACCEPTED,
        "executions": executions,
        "receipts": receipts,
        "checks": checks,
    }
    return LinkGraphArchitectureEvaluation(
        **body, content_address=addressed(body, "link-evaluation")
    )


__all__ = [
    "evaluate_link_graph_architecture_fixture",
    "execute_link_graph_architecture_case",
]
