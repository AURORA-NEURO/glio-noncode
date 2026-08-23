"""Fixture execution and named checks for the module fabric."""

from __future__ import annotations

from .capability_registry import CapabilityRegistry, default_capability_registry
from .module_fabric_contracts import (
    FabricCheckPlane,
    FabricEvaluation,
    FabricExecution,
    FabricFixture,
    FabricRecord,
    FabricRole,
    FabricState,
    make_fabric_check,
)
from .module_fabric_operations import evaluate_module_fabric_record
from .module_fabric_public_data import default_module_fabric_fixture
from .module_fabric_support import contains_private_key, all_resolved
from .serialization import content_hash


def execute_module_fabric_record(
    record: FabricRecord,
    registry: CapabilityRegistry | None = None,
) -> FabricExecution:
    result = evaluate_module_fabric_record(record, registry)
    body = {
        "record_id": record.record_id,
        "domain_id": record.domain_id,
        "capability_id": record.capability_id,
        "role": record.role,
        "expected_state": record.expected_state,
        "observed_state": result.state,
        "issue_codes": result.issue_codes,
        "output": result.output,
        "implementation_receipts": result.implementation_receipts,
        "test_receipts": result.test_receipts,
    }
    return FabricExecution(**body, content_address=content_hash(body))


def evaluate_module_fabric_fixture(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
) -> FabricEvaluation:
    value = fixture or default_module_fabric_fixture(registry)
    catalog = registry or default_capability_registry()
    executions = tuple(execute_module_fabric_record(record, catalog) for record in value.records)
    checks = []
    for execution, record in zip(executions, value.records, strict=True):
        checks.append(
            make_fabric_check(
                f"{record.record_id}:state",
                record.record_id,
                FabricCheckPlane.IDENTITY,
                execution.observed_state is record.expected_state,
                execution.observed_state.value,
                record.expected_state.value,
                "observed state matches the declared positive/control scenario",
            )
        )
        checks.append(
            make_fabric_check(
                f"{record.record_id}:issue-floor",
                record.record_id,
                FabricCheckPlane.CONTROL,
                set(record.expected_issue_codes).issubset(set(execution.issue_codes)),
                execution.issue_codes,
                record.expected_issue_codes,
                "declared control issues remain visible",
            )
        )
        checks.append(
            make_fabric_check(
                f"{record.record_id}:role",
                record.record_id,
                FabricCheckPlane.CONTROL,
                (record.role is FabricRole.POSITIVE and execution.observed_state is FabricState.ACCEPTED)
                or (record.role is FabricRole.CONTROL and execution.observed_state is not FabricState.ACCEPTED),
                record.role.value,
                "positive=accepted/control=held",
                "role cannot promote a control row",
            )
        )
        checks.append(
            make_fabric_check(
                f"{record.record_id}:domain",
                record.record_id,
                FabricCheckPlane.DOMAIN_CLOSURE,
                execution.domain_id == record.domain_id and execution.output.get("domain_id") == record.domain_id,
                execution.output.get("domain_id"),
                record.domain_id,
                "execution retains owning domain identity",
            )
        )
        checks.append(
            make_fabric_check(
                f"{record.record_id}:implementation",
                record.record_id,
                FabricCheckPlane.REFERENCE_RESOLUTION,
                bool(execution.implementation_receipts) and all_resolved(execution.implementation_receipts),
                [item.state.value for item in execution.implementation_receipts],
                "all resolved",
                "declared implementation references are importable",
            )
        )
        checks.append(
            make_fabric_check(
                f"{record.record_id}:tests",
                record.record_id,
                FabricCheckPlane.TEST_SURFACE,
                bool(execution.test_receipts) and all_resolved(execution.test_receipts),
                [item.state.value for item in execution.test_receipts],
                "all resolved",
                "declared test modules are importable",
            )
        )
        checks.append(
            make_fabric_check(
                f"{record.record_id}:output",
                record.record_id,
                FabricCheckPlane.PUBLIC_BOUNDARY,
                not contains_private_key(execution.output),
                execution.output,
                "no private keys",
                "projection contains only aggregate reference metadata",
            )
        )
        checks.append(
            make_fabric_check(
                f"{record.record_id}:address",
                record.record_id,
                FabricCheckPlane.INTEGRITY,
                execution.content_address.startswith("sha256:"),
                execution.content_address[:7],
                "sha256:",
                "execution receipt is content addressed",
            )
        )
    passed = sum(item.passed for item in checks)
    body = {
        "fixture_id": value.fixture_id,
        "executions": executions,
        "checks": tuple(checks),
        "accepted": passed == len(checks),
        "passed_checks": passed,
        "failed_checks": len(checks) - passed,
    }
    return FabricEvaluation(
        value.fixture_id,
        executions,
        tuple(checks),
        passed == len(checks),
        passed,
        len(checks) - passed,
        content_hash(body, prefix="module-fabric-evaluation"),
    )


def replay_module_fabric_fixture(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
) -> FabricEvaluation:
    return evaluate_module_fabric_fixture(fixture, registry)


__all__ = [
    "evaluate_module_fabric_fixture",
    "execute_module_fabric_record",
    "replay_module_fabric_fixture",
]
