"""Five-plane evaluation of every editing-design fixture scenario."""
from __future__ import annotations
from typing import Any
from .serialization import content_hash
from .editing_design_frontier_adapters import EditingDesignAdapterRegistry, build_editing_design_adapters, execute_editing_design_adapter
from .editing_design_frontier_contracts import EditingDesignEvaluation, EditingDesignExecution, EditingDesignFixture, EditingDesignRecord, EditingDesignRole, make_editing_design_check
from .editing_design_frontier_public_data import default_editing_design_frontier_fixture
from .editing_design_frontier_support import contains_private_marker

def execute_editing_design_record(record: EditingDesignRecord, registry: EditingDesignAdapterRegistry | None = None) -> EditingDesignExecution:
    registry = registry or build_editing_design_adapters(); result = execute_editing_design_adapter(registry, record.operation, record.payload); body = {"record_id": record.record_id, "capability": record.capability, "operation": record.operation, "role": record.role, "expected_state": record.expected_state, "observed_state": result.state, "issue_codes": result.issue_codes, "output": result.output}; return EditingDesignExecution(**body, content_address=content_hash(body))

def evaluate_editing_design_fixture(fixture: EditingDesignFixture | None = None) -> EditingDesignEvaluation:
    fixture = fixture or default_editing_design_frontier_fixture(); executions = tuple(execute_editing_design_record(record) for record in fixture.records); checks = []
    for execution, record in zip(executions, fixture.records, strict=True):
        checks.append(make_editing_design_check(f"{record.record_id}:state", record.record_id, "state", execution.observed_state == record.expected_state, execution.observed_state.value, record.expected_state.value, "observed state matches scenario"))
        checks.append(make_editing_design_check(f"{record.record_id}:issue", record.record_id, "issue", set(record.expected_issue_codes) <= set(execution.issue_codes), execution.issue_codes, record.expected_issue_codes, "control issue codes remain visible"))
        checks.append(make_editing_design_check(f"{record.record_id}:role", record.record_id, "role", record.role == EditingDesignRole.CONTROL or not record.expected_issue_codes, record.role.value, "positive" if record.role == EditingDesignRole.POSITIVE else "control", "roles remain explicit"))
        checks.append(make_editing_design_check(f"{record.record_id}:address", record.record_id, "integrity", execution.content_address.startswith("sha256:"), execution.content_address[:7], "sha256:", "execution is content addressed"))
        checks.append(make_editing_design_check(f"{record.record_id}:safe", record.record_id, "safety", not contains_private_marker(execution.output), "safe", "safe", "output contains no private marker"))
    passed = sum(item.passed for item in checks); body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": tuple(checks), "accepted": passed == len(checks), "passed_checks": passed, "failed_checks": len(checks) - passed}; return EditingDesignEvaluation(**body, content_address=content_hash(body))

def replay_editing_design_fixture(fixture: EditingDesignFixture | None = None) -> tuple[EditingDesignExecution, ...]: return evaluate_editing_design_fixture(fixture).executions

__all__ = ["evaluate_editing_design_fixture", "execute_editing_design_record", "replay_editing_design_fixture"]
