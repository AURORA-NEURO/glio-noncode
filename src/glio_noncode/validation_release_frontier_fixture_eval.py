"""Five-check evaluation of every validation-release fixture row."""

from __future__ import annotations

from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_adapters import ValidationReleaseAdapterRegistry, build_validation_release_adapters, execute_validation_release_adapter
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseExecution, ValidationReleaseFixture, ValidationReleaseOperation, ValidationReleaseRecord, make_validation_release_check
from .validation_release_frontier_public_data import audit_validation_release_frontier_data
from .validation_release_frontier_support import contains_forbidden_marker, normalized_issue_codes


def execute_validation_release_record(record: ValidationReleaseRecord, registry: ValidationReleaseAdapterRegistry | None = None) -> ValidationReleaseExecution:
    registry = registry or build_validation_release_adapters()
    result = execute_validation_release_adapter(registry, record.operation, record.payload)
    body = {"record_id": record.record_id, "operation": record.operation, "role": record.role, "expected_state": record.expected_state, "observed_state": result.state, "issue_codes": result.issue_codes, "output": result.output}
    return ValidationReleaseExecution(**body, content_address=content_hash(body))


def evaluate_validation_release_fixture(fixture: ValidationReleaseFixture | None = None) -> ValidationReleaseEvaluation:
    fixture = fixture or __import__("glio_noncode.validation_release_frontier_public_data", fromlist=["default_validation_release_frontier_fixture"]).default_validation_release_frontier_fixture()
    registry = build_validation_release_adapters()
    executions = tuple(execute_validation_release_record(record, registry) for record in fixture.records)
    checks = []
    for execution, record in zip(executions, fixture.records, strict=True):
        checks.append(make_validation_release_check(f"{record.record_id}:state", record.record_id, execution.observed_state == record.expected_state, execution.observed_state.value, record.expected_state.value, "observed state matches the declared boundary"))
        checks.append(make_validation_release_check(f"{record.record_id}:issues", record.record_id, set(record.expected_issue_codes) <= set(execution.issue_codes), execution.issue_codes, record.expected_issue_codes, "declared control reasons remain visible"))
        role_pass = record.role.value != "positive" or not record.expected_issue_codes
        checks.append(make_validation_release_check(f"{record.record_id}:role", record.record_id, role_pass, record.role.value, "positive rows have no expected issue" if record.role.value == "positive" else "control role remains explicit", "positive and control roles remain explicit"))
        checks.append(make_validation_release_check(f"{record.record_id}:address", record.record_id, execution.content_address.startswith("sha256:"), execution.content_address[:7], "sha256:", "execution is content addressed"))
        checks.append(make_validation_release_check(f"{record.record_id}:safe-output", record.record_id, not contains_forbidden_marker(execution.output), "safe" if not contains_forbidden_marker(execution.output) else "forbidden", "safe", "output projection excludes secret markers"))
    passed = sum(1 for item in checks if item.passed)
    body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": tuple(checks), "accepted": passed == len(checks), "passed_checks": passed, "failed_checks": len(checks) - passed}
    return ValidationReleaseEvaluation(**body, content_address=content_hash(body))


def audit_validation_release_context(fixture: ValidationReleaseFixture) -> tuple[str, ...]:
    return tuple(sorted({record.context_key for record in fixture.records if record.context_key != fixture.context_key}))


__all__ = ["audit_validation_release_context", "evaluate_validation_release_fixture", "execute_validation_release_record"]
