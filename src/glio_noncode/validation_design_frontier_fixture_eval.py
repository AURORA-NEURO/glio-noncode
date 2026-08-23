"""Five-plane evaluation of every public validation-design fixture row."""
from __future__ import annotations
from typing import Any
from .serialization import content_hash
from .validation_design_frontier_adapters import ValidationDesignAdapterRegistry, build_validation_design_adapters, execute_validation_design_adapter
from .validation_design_frontier_contracts import ValidationDesignCheck, ValidationDesignExecution, ValidationDesignFixture, ValidationDesignRecord, ValidationDesignRole, make_validation_design_check
from .validation_design_frontier_public_data import default_validation_design_frontier_fixture
from .validation_design_frontier_support import contains_private_marker

def execute_validation_design_record(record: ValidationDesignRecord, registry: ValidationDesignAdapterRegistry | None = None) -> ValidationDesignExecution:
    registry = registry or build_validation_design_adapters()
    result = execute_validation_design_adapter(registry, record.operation, record.payload)
    body = {"record_id": record.record_id, "capability": record.capability, "operation": record.operation, "role": record.role, "expected_state": record.expected_state, "observed_state": result.state, "issue_codes": result.issue_codes, "output": result.output}
    return ValidationDesignExecution(**body, content_address=content_hash(body))

def evaluate_validation_design_fixture(fixture: ValidationDesignFixture | None = None):
    fixture = fixture or default_validation_design_frontier_fixture()
    registry = build_validation_design_adapters()
    executions = tuple(execute_validation_design_record(record, registry) for record in fixture.records)
    checks: list[ValidationDesignCheck] = []
    for execution, record in zip(executions, fixture.records, strict=True):
        checks.append(make_validation_design_check(f"{record.record_id}:state", record.record_id, "state", execution.observed_state == record.expected_state, execution.observed_state.value, record.expected_state.value, "state agrees with the public scenario"))
        checks.append(make_validation_design_check(f"{record.record_id}:issues", record.record_id, "issue", set(record.expected_issue_codes) <= set(execution.issue_codes), execution.issue_codes, record.expected_issue_codes, "expected control reasons remain visible"))
        checks.append(make_validation_design_check(f"{record.record_id}:role", record.record_id, "role", record.role == ValidationDesignRole.CONTROL or not record.expected_issue_codes, record.role.value, "positive" if record.role == ValidationDesignRole.POSITIVE else "control", "positive and control roles are explicit"))
        checks.append(make_validation_design_check(f"{record.record_id}:address", record.record_id, "integrity", execution.content_address.startswith("sha256:"), execution.content_address[:7], "sha256:", "execution is content addressed"))
        checks.append(make_validation_design_check(f"{record.record_id}:safe-output", record.record_id, "safety", not contains_private_marker(execution.output), "safe", "safe", "output contains no private marker"))
    passed = sum(item.passed for item in checks)
    body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": tuple(checks), "accepted": passed == len(checks), "passed_checks": passed, "failed_checks": len(checks) - passed}
    from .validation_design_frontier_contracts import ValidationDesignEvaluation
    return ValidationDesignEvaluation(**body, content_address=content_hash(body))

def replay_validation_design_fixture(fixture: ValidationDesignFixture | None = None): return evaluate_validation_design_fixture(fixture).executions

__all__ = ["evaluate_validation_design_fixture", "execute_validation_design_record", "replay_validation_design_fixture"]
