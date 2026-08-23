"""Executable module-fabric operations over the capability ledger."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .capability_registry import CapabilityRecord, CapabilityRegistry, default_capability_registry
from .errors import ValidationError
from .module_fabric_contracts import (
    FabricOperationResult,
    FabricRecord,
    FabricReferenceKind,
    FabricReferenceReceipt,
    FabricReferenceState,
    FabricRole,
    FabricState,
    MODULE_FABRIC_CONTEXT_KEY,
)
from .module_fabric_support import (
    contains_private_key,
    exact_context,
    parse_capability_id,
    reference_failures,
    reference_set_receipts,
    safe_json,
    sorted_issue_codes,
)
from .serialization import content_hash


def _catalog_record(registry: CapabilityRegistry, capability_id: str) -> CapabilityRecord | None:
    try:
        return registry.record(capability_id)
    except ValidationError:
        return None


def _reference_output(
    implementation: tuple[FabricReferenceReceipt, ...],
    tests: tuple[FabricReferenceReceipt, ...],
) -> dict[str, Any]:
    return {
        "implementation_reference_count": len(implementation),
        "test_reference_count": len(tests),
        "resolved_implementation_count": sum(item.state is FabricReferenceState.RESOLVED for item in implementation),
        "resolved_test_count": sum(item.state is FabricReferenceState.RESOLVED for item in tests),
        "failed_reference_count": sum(item.state is FabricReferenceState.FAILED for item in (*implementation, *tests)),
        "implementation_references": [item.reference for item in implementation],
        "test_references": [item.reference for item in tests],
    }


def evaluate_module_fabric_record(
    record: FabricRecord,
    registry: CapabilityRegistry | None = None,
) -> FabricOperationResult:
    """Resolve the declared ledger row and preserve any control failures."""

    catalog = registry or default_capability_registry()
    issues: list[str] = []
    implementation: tuple[FabricReferenceReceipt, ...] = ()
    tests: tuple[FabricReferenceReceipt, ...] = ()
    ledger_record = _catalog_record(catalog, record.capability_id)
    if ledger_record is None:
        issues.append("unknown_capability")
    else:
        try:
            declared_domain, declared_order = parse_capability_id(record.capability_id)
        except ValidationError:
            declared_domain, declared_order = "", -1
            issues.append("invalid_capability_id")
        if ledger_record.spec.domain_id != record.domain_id or declared_domain != record.domain_id:
            issues.append("domain_mismatch")
        if record.payload.get("declared_domain_id") != record.domain_id:
            issues.append("foreign_domain")
        if record.payload.get("declared_capability_id") != record.capability_id:
            issues.append("capability_mismatch")
        if record.payload.get("required_capability_order") != declared_order:
            issues.append("capability_order_mismatch")
        implementation = reference_set_receipts(
            ledger_record.implementation_modules,
            FabricReferenceKind.IMPLEMENTATION,
        )
        tests = reference_set_receipts(ledger_record.test_modules, FabricReferenceKind.TEST)
        if not implementation:
            issues.append("missing_implementation_references")
        if not tests:
            issues.append("missing_test_references")
        issues.extend(reference_failures(implementation))
        issues.extend(reference_failures(tests))
    declared_context = record.payload.get("declared_context_key")
    if not exact_context(record.context_key):
        issues.append("record_context_mismatch")
    if not exact_context(declared_context):
        issues.append("context_mismatch")
    if record.role is FabricRole.POSITIVE and issues:
        issues.append("positive_reference_gap")
    if record.role is FabricRole.CONTROL and not issues:
        issues.append("control_boundary_missing")
    issues = list(sorted_issue_codes(issues))
    if record.role is FabricRole.POSITIVE:
        state = FabricState.ACCEPTED if not issues else FabricState.REVIEW
    else:
        state = FabricState.REVIEW if issues else FabricState.REJECTED
    output = {
        "record_id": record.record_id,
        "domain_id": record.domain_id,
        "capability_id": record.capability_id,
        "role": record.role.value,
        "context_supported": exact_context(record.context_key),
        "declared_context_supported": exact_context(declared_context),
        "ledger_state": ledger_record.state.value if ledger_record is not None else None,
        "issue_count": len(issues),
        **_reference_output(implementation, tests),
    }
    output = safe_json(output)
    if contains_private_key(output):
        raise ValidationError("module-fabric operation produced a private field")
    body = {
        "state": state,
        "issue_codes": tuple(issues),
        "output": output,
        "implementation_receipts": implementation,
        "test_receipts": tests,
    }
    return FabricOperationResult(**body, content_address=content_hash(body))


def run_module_fabric_operation(
    operation: str,
    record: FabricRecord,
    registry: CapabilityRegistry | None = None,
) -> FabricOperationResult:
    """Dispatch the single supported operation by name."""

    if operation not in {"resolve_capability_references", "module_fabric_audit"}:
        raise ValidationError(f"unknown module-fabric operation: {operation}")
    return evaluate_module_fabric_record(record, registry)


__all__ = [
    "evaluate_module_fabric_record",
    "run_module_fabric_operation",
]
