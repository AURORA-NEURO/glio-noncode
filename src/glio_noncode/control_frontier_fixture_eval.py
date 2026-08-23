"""Evaluation harness for positive and control rows in the control frontier."""

from __future__ import annotations

from typing import Any

from .control_frontier_contracts import (
    CONTROL_FRONTIER_CONTEXT_KEY,
    ControlFrontierExecution,
    ControlFrontierEvaluation,
    ControlFrontierFixture,
    ControlFrontierRecord,
    ControlFrontierRole,
    ControlFrontierState,
    addressed_control_frontier_check,
)
from .control_frontier_operations import run_control_frontier_operation
from .serialization import content_hash


def execute_control_frontier_record(record: ControlFrontierRecord) -> ControlFrontierExecution:
    """Execute a row from its payload and compare only against its role."""

    result = run_control_frontier_operation(record.operation, record.payload)
    accepted = record.role is ControlFrontierRole.POSITIVE and result.state is record.expected_state and not result.issue_codes
    body = {
        "record_id": record.record_id,
        "operation": record.operation,
        "role": record.role,
        "state": result.state,
        "accepted": accepted,
        "issue_codes": result.issue_codes,
        "output": result.output,
    }
    return ControlFrontierExecution(**body, content_address=content_hash(body))


def _checks_for_record(record: ControlFrontierRecord, execution: ControlFrontierExecution) -> tuple[Any, ...]:
    observed_output = execution.output
    return (
        addressed_control_frontier_check(
            f"{record.record_id}:state",
            execution.state is record.expected_state,
            execution.state.value,
            record.expected_state.value,
            "observed state equals the declared row boundary",
            record.record_id,
        ),
        addressed_control_frontier_check(
            f"{record.record_id}:issues",
            execution.issue_codes == record.expected_issue_codes,
            list(execution.issue_codes),
            list(record.expected_issue_codes),
            "issue vocabulary remains explicit and ordered",
            record.record_id,
        ),
        addressed_control_frontier_check(
            f"{record.record_id}:role",
            execution.accepted == (record.role is ControlFrontierRole.POSITIVE and not record.expected_issue_codes),
            execution.accepted,
            record.role is ControlFrontierRole.POSITIVE and not record.expected_issue_codes,
            "positive and control roles are not conflated",
            record.record_id,
        ),
        addressed_control_frontier_check(
            f"{record.record_id}:address",
            execution.content_address.startswith("sha256:"),
            execution.content_address.startswith("sha256:"),
            True,
            "execution receipt is content-addressed",
            record.record_id,
        ),
        addressed_control_frontier_check(
            f"{record.record_id}:output",
            bool(observed_output) and isinstance(observed_output, dict),
            bool(observed_output),
            True,
            "operation output retains a structured projection",
            record.record_id,
        ),
    )


def evaluate_control_frontier_fixture(fixture: ControlFrontierFixture) -> ControlFrontierEvaluation:
    """Execute all rows and retain five checks per row."""

    executions = tuple(execute_control_frontier_record(item) for item in fixture.records)
    checks = tuple(check for record, execution in zip(fixture.records, executions, strict=True) for check in _checks_for_record(record, execution))
    positive_ok = all(item.accepted for item in executions if item.role is ControlFrontierRole.POSITIVE)
    controls_visible = all(not item.accepted for item in executions if item.role is ControlFrontierRole.CONTROL)
    expected_count = len(fixture.records) * 5
    accepted = positive_ok and controls_visible and len(checks) == expected_count and all(item.passed for item in checks)
    body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": checks, "accepted": accepted}
    return ControlFrontierEvaluation(**body, content_address=content_hash(body))


def audit_control_frontier_context(fixture: ControlFrontierFixture) -> tuple[str, ...]:
    """Return context violations without changing any row or result."""

    issues: list[str] = []
    if fixture.context_key != CONTROL_FRONTIER_CONTEXT_KEY:
        issues.append("fixture_context_mismatch")
    issues.extend(item.record_id for item in fixture.records if item.context_key != CONTROL_FRONTIER_CONTEXT_KEY)
    return tuple(issues)


__all__ = [
    "audit_control_frontier_context",
    "evaluate_control_frontier_fixture",
    "execute_control_frontier_record",
]
