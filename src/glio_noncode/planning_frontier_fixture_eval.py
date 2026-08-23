"""Scenario evaluation across state, issue, role, integrity, and safety planes."""

from __future__ import annotations

from .planning_frontier_adapters import PlanningAdapterRegistry, build_planning_adapters, execute_planning_adapter
from .planning_frontier_contracts import PlanningEvaluation, PlanningExecution, PlanningFixture, PlanningRecord, PlanningRole, make_planning_check
from .planning_frontier_public_data import default_planning_frontier_fixture
from .planning_frontier_support import contains_private_marker
from .serialization import content_hash


def execute_planning_record(record: PlanningRecord, registry: PlanningAdapterRegistry | None = None) -> PlanningExecution:
    registry = registry or build_planning_adapters()
    result = execute_planning_adapter(registry, record.operation, record.payload)
    body = {
        "record_id": record.record_id,
        "capability": record.capability,
        "operation": record.operation,
        "role": record.role,
        "expected_state": record.expected_state,
        "observed_state": result.state,
        "issue_codes": result.issue_codes,
        "output": result.output,
    }
    return PlanningExecution(**body, content_address=content_hash(body))


def evaluate_planning_fixture(fixture: PlanningFixture | None = None) -> PlanningEvaluation:
    value = fixture or default_planning_frontier_fixture()
    executions = tuple(execute_planning_record(record) for record in value.records)
    checks = []
    for execution, record in zip(executions, value.records, strict=True):
        checks.append(make_planning_check(f"{record.record_id}:state", record.record_id, "state", execution.observed_state is record.expected_state, execution.observed_state.value, record.expected_state.value, "state matches declared scenario"))
        checks.append(make_planning_check(f"{record.record_id}:issue", record.record_id, "issue", set(record.expected_issue_codes) <= set(execution.issue_codes), execution.issue_codes, record.expected_issue_codes, "declared issue floor is visible"))
        checks.append(make_planning_check(f"{record.record_id}:role", record.record_id, "role", record.role is PlanningRole.CONTROL or not record.expected_issue_codes, record.role.value, "positive or control", "role boundary is explicit"))
        checks.append(make_planning_check(f"{record.record_id}:address", record.record_id, "integrity", execution.content_address.startswith("sha256:"), execution.content_address[:7], "sha256:", "execution is content addressed"))
        checks.append(make_planning_check(f"{record.record_id}:safe", record.record_id, "safety", not contains_private_marker(execution.output), "safe", "safe", "output excludes private markers"))
    passed = sum(item.passed for item in checks)
    body = {"fixture_id": value.fixture_id, "executions": executions, "checks": tuple(checks), "accepted": passed == len(checks), "passed_checks": passed, "failed_checks": len(checks) - passed}
    return PlanningEvaluation(value.fixture_id, executions, tuple(checks), passed == len(checks), passed, len(checks) - passed, content_hash(body, prefix="planning-evaluation"))


def replay_planning_fixture(fixture: PlanningFixture | None = None) -> tuple[PlanningExecution, ...]:
    return evaluate_planning_fixture(fixture).executions


__all__ = ["evaluate_planning_fixture", "execute_planning_record", "replay_planning_fixture"]
