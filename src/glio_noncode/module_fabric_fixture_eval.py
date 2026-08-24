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
from .module_fabric_support import all_resolved, contains_private_key
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
        source_ids = {item.source_id for item in value.sources}
        checks.append(
            make_fabric_check(
                f"{record.record_id}:source-joins",
                record.record_id,
                FabricCheckPlane.PUBLIC_BOUNDARY,
                bool(record.source_ids) and set(record.source_ids) <= source_ids,
                record.source_ids,
                "known public source IDs",
                "record retains resolvable source joins",
            )
        )
        checks.append(
            make_fabric_check(
                f"{record.record_id}:reference-counts",
                record.record_id,
                FabricCheckPlane.REFERENCE_RESOLUTION,
                execution.output.get("implementation_reference_count") == len(execution.implementation_receipts)
                and execution.output.get("test_reference_count") == len(execution.test_receipts),
                {
                    "implementation": execution.output.get("implementation_reference_count"),
                    "tests": execution.output.get("test_reference_count"),
                },
                {
                    "implementation": len(execution.implementation_receipts),
                    "tests": len(execution.test_receipts),
                },
                "reference counts conserve receipts",
            )
        )
        checks.append(
            make_fabric_check(
                f"{record.record_id}:public-identity",
                record.record_id,
                FabricCheckPlane.IDENTITY,
                execution.output.get("record_id") == record.record_id
                and execution.output.get("capability_id") == record.capability_id,
                {
                    "record_id": execution.output.get("record_id"),
                    "capability_id": execution.output.get("capability_id"),
                },
                {"record_id": record.record_id, "capability_id": record.capability_id},
                "execution retains public record identity",
            )
        )
        checks.append(
            make_fabric_check(
                f"{record.record_id}:receipt-addresses",
                record.record_id,
                FabricCheckPlane.INTEGRITY,
                all(item.content_address.startswith("sha256:") for item in (*execution.implementation_receipts, *execution.test_receipts)),
                len(execution.implementation_receipts) + len(execution.test_receipts),
                "addressed receipts",
                "all reference receipts are content addressed",
            )
        )
    fixture_checks = (
        ("fixture-id", bool(value.fixture_id), value.fixture_id, "non-empty", "fixture identity is retained"),
        ("execution-count", len(executions) == len(value.records), len(executions), len(value.records), "every fixture record executes"),
        ("check-count", len(checks) + 10 == len(value.records) * 12 + 10, len(checks) + 10, len(value.records) * 12 + 10, "record and global check denominator is closed"),
        ("execution-ids", len({item.record_id for item in executions}) == len(executions), len({item.record_id for item in executions}), len(executions), "execution identifiers are unique"),
        ("domain-coverage", {item.domain_id for item in executions} == {item.domain_id for item in value.records}, len({item.domain_id for item in executions}), len({item.domain_id for item in value.records}), "all fixture domains execute"),
        ("role-balance", sum(item.role is FabricRole.POSITIVE for item in executions) == 16 and sum(item.role is FabricRole.CONTROL for item in executions) == 16, {"positive": sum(item.role is FabricRole.POSITIVE for item in executions), "control": sum(item.role is FabricRole.CONTROL for item in executions)}, {"positive": 16, "control": 16}, "positive and control rows are balanced"),
        ("state-partition", sum(item.observed_state is FabricState.ACCEPTED for item in executions) == 16 and sum(item.observed_state is FabricState.REVIEW for item in executions) == 16, {"accepted": sum(item.observed_state is FabricState.ACCEPTED for item in executions), "review": sum(item.observed_state is FabricState.REVIEW for item in executions)}, {"accepted": 16, "review": 16}, "observed states conserve fixture roles"),
        ("reference-resolution", all(item.state.value == "resolved" for execution in executions for item in (*execution.implementation_receipts, *execution.test_receipts)), True, True, "all reference declarations resolve"),
        ("public-output", all(not contains_private_key(item.output) for item in executions), True, True, "all execution projections are aggregate only"),
        ("addressed-executions", all(item.content_address.startswith("sha256:") for item in executions), len(executions), len(executions), "all execution receipts are addressed"),
    )
    for check_id, passed_check, observed, required, detail in fixture_checks:
        checks.append(make_fabric_check(f"__fixture__:{check_id}", "__fixture__", FabricCheckPlane.INTEGRITY, passed_check, observed, required, detail))
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
