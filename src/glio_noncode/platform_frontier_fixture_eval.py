"""Evaluation harness for Domain 16 C01-C04 platform rows."""

from __future__ import annotations

from typing import Any

from .platform_frontier_contracts import (
    PLATFORM_FRONTIER_CONTEXT_KEY,
    PlatformFrontierCheck,
    PlatformFrontierEvaluation,
    PlatformFrontierExecution,
    PlatformFrontierFixture,
    PlatformFrontierRecord,
    PlatformFrontierRole,
    addressed_platform_check,
)
from .platform_frontier_operations import run_platform_frontier_operation
from .serialization import content_hash


def execute_platform_frontier_record(record: PlatformFrontierRecord) -> PlatformFrontierExecution:
    """Run one fixture row and retain positive/control separation."""

    result = run_platform_frontier_operation(record.operation, record.payload)
    accepted = record.role is PlatformFrontierRole.POSITIVE and result.state is record.expected_state and not result.issue_codes
    body = {
        "record_id": record.record_id,
        "operation": record.operation,
        "role": record.role,
        "state": result.state,
        "accepted": accepted,
        "issue_codes": result.issue_codes,
        "output": result.output,
    }
    return PlatformFrontierExecution(**body, content_address=content_hash(body))


def _checks_for_record(record: PlatformFrontierRecord, execution: PlatformFrontierExecution) -> tuple[PlatformFrontierCheck, ...]:
    return (
        addressed_platform_check(
            f"{record.record_id}:state",
            record.record_id,
            execution.state is record.expected_state,
            execution.state.value,
            record.expected_state.value,
            "observed platform state equals the declared row boundary",
        ),
        addressed_platform_check(
            f"{record.record_id}:issues",
            record.record_id,
            execution.issue_codes == record.expected_issue_codes,
            list(execution.issue_codes),
            list(record.expected_issue_codes),
            "issue vocabulary remains explicit and ordered",
        ),
        addressed_platform_check(
            f"{record.record_id}:role",
            record.record_id,
            execution.accepted == (record.role is PlatformFrontierRole.POSITIVE and not record.expected_issue_codes),
            execution.accepted,
            record.role is PlatformFrontierRole.POSITIVE and not record.expected_issue_codes,
            "positive and control roles are not conflated",
        ),
        addressed_platform_check(
            f"{record.record_id}:address",
            record.record_id,
            execution.content_address.startswith("sha256:"),
            execution.content_address.startswith("sha256:"),
            True,
            "execution receipt is content-addressed",
        ),
        addressed_platform_check(
            f"{record.record_id}:output",
            record.record_id,
            bool(execution.output) and isinstance(execution.output, dict),
            bool(execution.output),
            True,
            "operation output retains a structured safe projection",
        ),
    )


def evaluate_platform_frontier_fixture(fixture: PlatformFrontierFixture) -> PlatformFrontierEvaluation:
    """Execute all rows and retain five checks per row."""

    executions = tuple(execute_platform_frontier_record(item) for item in fixture.records)
    checks = tuple(check for record, execution in zip(fixture.records, executions, strict=True) for check in _checks_for_record(record, execution))
    positive_ok = all(item.accepted for item in executions if item.role is PlatformFrontierRole.POSITIVE)
    controls_visible = all(not item.accepted for item in executions if item.role is PlatformFrontierRole.CONTROL)
    expected_count = len(fixture.records) * 5
    accepted = positive_ok and controls_visible and len(checks) == expected_count and all(item.passed for item in checks)
    body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": checks, "accepted": accepted}
    return PlatformFrontierEvaluation(**body, content_address=content_hash(body))


def audit_platform_frontier_context(fixture: PlatformFrontierFixture) -> tuple[str, ...]:
    """Return exact-context violations without modifying the fixture."""

    issues = []
    if fixture.context_key != PLATFORM_FRONTIER_CONTEXT_KEY:
        issues.append("fixture_context_mismatch")
    issues.extend(item.record_id for item in fixture.records if item.context_key != PLATFORM_FRONTIER_CONTEXT_KEY)
    return tuple(issues)


__all__ = ["audit_platform_frontier_context", "evaluate_platform_frontier_fixture", "execute_platform_frontier_record"]
