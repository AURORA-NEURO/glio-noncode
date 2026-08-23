"""Deterministic operation evaluation for the D16 coordination fixture."""

from __future__ import annotations

from typing import Any

from .coordination_architecture_contracts import (
    COORDINATION_CONTEXT,
    CoordinationCase,
    CoordinationEvaluation,
    CoordinationExecution,
    CoordinationFixture,
    CoordinationOperationSpec,
    CoordinationScenario,
    CoordinationState,
    addressed,
)
from .module_fabric_support import contains_private_key, sorted_issue_codes


def _issues(case: CoordinationCase, spec: CoordinationOperationSpec) -> list[str]:
    payload = case.payload
    issues: list[str] = []
    if case.operation_id != spec.operation_id or payload.get("declared_operation_id") != spec.operation_id:
        issues.append("operation_mismatch")
    if case.capability_id != spec.capability_id or payload.get("declared_capability_id") != spec.capability_id:
        issues.append("capability_mismatch")
    if case.context_key != COORDINATION_CONTEXT or payload.get("declared_context_key") != COORDINATION_CONTEXT:
        issues.append("foreign_context")
    if payload.get("declared_input_contract") != spec.input_contract or payload.get("declared_output_contract") != spec.output_contract:
        issues.append("contract_mismatch")
    if not isinstance(payload.get("available_budget_units"), int) or payload.get("available_budget_units", 0) < spec.budget_units:
        issues.append("budget_exceeded")
    if payload.get("network_requested") is not False:
        issues.append("network_not_allowed")
    if payload.get("public_aggregate_only") is not True:
        issues.append("scope_mismatch")
    if not case.source_ids or contains_private_key(payload):
        issues.append("unsafe_payload")
    return list(sorted_issue_codes(issues))


def execute_coordination_case(case: CoordinationCase, spec: CoordinationOperationSpec) -> CoordinationExecution:
    issue_codes = tuple(_issues(case, spec))
    observed_state = CoordinationState.ACCEPTED if not issue_codes else CoordinationState.REVIEW
    output = {
        "case_id": case.case_id,
        "operation_id": case.operation_id,
        "capability_id": case.capability_id,
        "scenario": case.scenario,
        "state": observed_state,
        "issue_codes": issue_codes,
        "reference_count": len(case.source_ids),
        "public_projection": True,
        "claim_boundary": "public aggregate coordination control only",
    }
    return CoordinationExecution(
        case_id=case.case_id,
        operation_id=case.operation_id,
        capability_id=case.capability_id,
        scenario=case.scenario,
        expected_state=case.expected_state,
        observed_state=observed_state,
        issue_codes=issue_codes,
        output=output,
        tool_id=f"coordination-tool:{spec.operation_id}",
        content_address=addressed(output, "coordination-execution"),
    )


def evaluate_coordination_case(case: CoordinationCase, spec: CoordinationOperationSpec) -> CoordinationExecution:
    return execute_coordination_case(case, spec)


def evaluate_coordination_fixture(fixture: CoordinationFixture) -> CoordinationEvaluation:
    specs = {item.operation_id: item for item in fixture.operations}
    executions = tuple(execute_coordination_case(case, specs[case.operation_id]) for case in fixture.cases)
    expected = {case.case_id: case for case in fixture.cases}
    passed = sum(
        execution.expected_state is execution.observed_state
        and execution.issue_codes == expected[execution.case_id].expected_issue_codes
        for execution in executions
    )
    failed = len(executions) - passed
    body: dict[str, Any] = {
        "fixture_id": fixture.fixture_id,
        "executions": executions,
        "passed_cases": passed,
        "failed_cases": failed,
        "accepted": failed == 0,
    }
    return CoordinationEvaluation(fixture.fixture_id, executions, passed, failed, failed == 0, addressed(body, "coordination-evaluation"))


__all__ = [
    "execute_coordination_case",
    "evaluate_coordination_case",
    "evaluate_coordination_fixture",
]
