"""Fixture evaluation for the D16 C13-C16 deployment frontier."""

from __future__ import annotations

from typing import Any

from .deployment_frontier_contracts import (
    DeploymentFrontierCheck,
    DeploymentFrontierEvaluation,
    DeploymentFrontierExecution,
    DeploymentFrontierFixture,
    DeploymentFrontierRole,
    addressed_deployment_check,
)
from .deployment_frontier_operations import run_deployment_frontier_operation
from .serialization import content_hash, jsonable


def execute_deployment_frontier_record(record: Any) -> DeploymentFrontierExecution:
    result = run_deployment_frontier_operation(record.operation, record.payload)
    output = dict(result.output)
    body = {
        "record_id": record.record_id,
        "operation": record.operation,
        "role": record.role,
        "state": result.state,
        "accepted": not result.issue_codes,
        "issue_codes": result.issue_codes,
        "output": output,
    }
    return DeploymentFrontierExecution(**body, content_address=content_hash(body))


def _row_checks(record: Any, execution: DeploymentFrontierExecution) -> tuple[DeploymentFrontierCheck, ...]:
    expected_issues = tuple(record.expected_issue_codes)
    observed_issues = tuple(execution.issue_codes)
    state_check = addressed_deployment_check(
        f"{record.record_id}:state",
        record.record_id,
        execution.state.value == record.expected_state.value,
        execution.state.value,
        record.expected_state.value,
        "observed state matches the declared positive or control boundary",
    )
    issues_check = addressed_deployment_check(
        f"{record.record_id}:issues",
        record.record_id,
        set(expected_issues) <= set(observed_issues),
        observed_issues,
        expected_issues,
        "all expected denial reasons remain visible",
    )
    role_check = addressed_deployment_check(
        f"{record.record_id}:role",
        record.record_id,
        (record.role is DeploymentFrontierRole.POSITIVE) == (not expected_issues),
        record.role.value,
        "positive" if not expected_issues else "control",
        "positive and control rows are not conflated",
    )
    address_check = addressed_deployment_check(
        f"{record.record_id}:address",
        record.record_id,
        execution.content_address.startswith("sha256:"),
        execution.content_address[:7],
        "sha256:",
        "execution receipt is content addressed",
    )
    serialized = str(jsonable(execution.output)).lower()
    secret_check = addressed_deployment_check(
        f"{record.record_id}:safe-output",
        record.record_id,
        not any(marker in serialized for marker in ("password", "token", "api_key", "signing_secret")),
        "safe" if not any(marker in serialized for marker in ("password", "token", "api_key", "signing_secret")) else "unsafe",
        "safe",
        "operation output excludes secret-like fields",
    )
    return (state_check, issues_check, role_check, address_check, secret_check)


def evaluate_deployment_frontier_fixture(fixture: DeploymentFrontierFixture) -> DeploymentFrontierEvaluation:
    executions = []
    checks = []
    for record in fixture.records:
        execution = execute_deployment_frontier_record(record)
        executions.append(execution)
        checks.extend(_row_checks(record, execution))
    values = tuple(executions)
    check_values = tuple(checks)
    return DeploymentFrontierEvaluation(
        fixture.fixture_id,
        values,
        check_values,
        all(item.passed for item in check_values),
        content_hash({"fixture_id": fixture.fixture_id, "executions": values, "checks": check_values}),
    )


def audit_deployment_frontier_context(fixture: DeploymentFrontierFixture) -> tuple[str, ...]:
    issues = []
    if any(record.context_key != fixture.context_key for record in fixture.records):
        issues.append("record_context_mismatch")
    known = {source.source_id for source in fixture.sources}
    if any(set(record.source_ids) - known for record in fixture.records):
        issues.append("unknown_source")
    if len({record.operation for record in fixture.records}) != 4:
        issues.append("operation_family_missing")
    return tuple(issues)


__all__ = [
    "audit_deployment_frontier_context",
    "evaluate_deployment_frontier_fixture",
    "execute_deployment_frontier_record",
]
