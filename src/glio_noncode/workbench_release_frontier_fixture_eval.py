"""Five-plane row evaluation for the workbench-release fixture."""

from __future__ import annotations

from typing import Any

from .serialization import content_hash
from .workbench_release_frontier_adapters import WorkbenchReleaseAdapterRegistry, build_workbench_release_adapters, execute_workbench_release_adapter
from .workbench_release_frontier_contracts import WorkbenchReleaseEvaluation, WorkbenchReleaseExecution, WorkbenchReleaseFixture, WorkbenchReleaseRecord, WorkbenchReleaseRole, make_workbench_release_check
from .workbench_release_frontier_public_data import default_workbench_release_frontier_fixture
from .workbench_release_frontier_support import contains_private_marker


def execute_workbench_release_record(record: WorkbenchReleaseRecord, registry: WorkbenchReleaseAdapterRegistry | None = None) -> WorkbenchReleaseExecution:
    registry = registry or build_workbench_release_adapters()
    result = execute_workbench_release_adapter(registry, record.operation, record.payload)
    body = {"record_id": record.record_id, "capability": record.capability, "operation": record.operation, "role": record.role, "expected_state": record.expected_state, "observed_state": result.state, "issue_codes": result.issue_codes, "output": result.output}
    return WorkbenchReleaseExecution(**body, content_address=content_hash(body))


def evaluate_workbench_release_fixture(fixture: WorkbenchReleaseFixture | None = None) -> WorkbenchReleaseEvaluation:
    fixture = fixture or default_workbench_release_frontier_fixture()
    registry = build_workbench_release_adapters()
    executions = tuple(execute_workbench_release_record(record, registry) for record in fixture.records)
    checks = []
    for execution, record in zip(executions, fixture.records, strict=True):
        checks.append(make_workbench_release_check(f"{record.record_id}:state", record.record_id, "state", execution.observed_state == record.expected_state, execution.observed_state.value, record.expected_state.value, "observed state matches the fixture boundary"))
        checks.append(make_workbench_release_check(f"{record.record_id}:issues", record.record_id, "issue", set(record.expected_issue_codes) <= set(execution.issue_codes), execution.issue_codes, record.expected_issue_codes, "control reasons remain visible"))
        checks.append(make_workbench_release_check(f"{record.record_id}:role", record.record_id, "role", record.role == WorkbenchReleaseRole.CONTROL or not record.expected_issue_codes, record.role.value, "positive has no issue" if record.role == WorkbenchReleaseRole.POSITIVE else "control", "positive and control roles remain explicit"))
        checks.append(make_workbench_release_check(f"{record.record_id}:address", record.record_id, "integrity", execution.content_address.startswith("sha256:"), execution.content_address[:7], "sha256:", "execution is content addressed"))
        checks.append(make_workbench_release_check(f"{record.record_id}:safe-output", record.record_id, "safety", not contains_private_marker(execution.output), "safe" if not contains_private_marker(execution.output) else "private", "safe", "output projection excludes private markers"))
    passed = sum(check.passed for check in checks)
    body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": tuple(checks), "accepted": passed == len(checks), "passed_checks": passed, "failed_checks": len(checks) - passed}
    return WorkbenchReleaseEvaluation(**body, content_address=content_hash(body))


def audit_workbench_release_context(fixture: WorkbenchReleaseFixture) -> tuple[str, ...]:
    return tuple(sorted({record.context_key for record in fixture.records if record.context_key != fixture.context_key}))


def replay_workbench_release_fixture(fixture: WorkbenchReleaseFixture | None = None) -> tuple[WorkbenchReleaseExecution, ...]:
    return evaluate_workbench_release_fixture(fixture).executions


__all__ = ["audit_workbench_release_context", "evaluate_workbench_release_fixture", "execute_workbench_release_record", "replay_workbench_release_fixture"]
