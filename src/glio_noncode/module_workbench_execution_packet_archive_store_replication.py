"""Plan, verify, apply, and promote archive-store replications.

The implementation keeps the transport decision separate from persistence. A
plan is a deterministic description of the source and target boundaries. An
apply call re-verifies both stores, re-builds the plan, enforces the expected
target head, and only then atomically writes the verified source boundary.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store import (
    load_module_workbench_execution_packet_archive_store,
    verify_module_workbench_execution_packet_archive_store,
    write_module_workbench_execution_packet_archive_store,
)
from .module_workbench_execution_packet_archive_store_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStore,
)
from .module_workbench_execution_packet_archive_store_replication_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_CHECK_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStorePromotion,
    ModuleWorkbenchExecutionPacketArchiveStorePromotionState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntry,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperation,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationState,
    address_module_workbench_execution_packet_archive_store_promotion,
    address_module_workbench_execution_packet_archive_store_replication,
    address_module_workbench_execution_packet_archive_store_replication_check,
    address_module_workbench_execution_packet_archive_store_replication_entry,
    address_module_workbench_execution_packet_archive_store_replication_operation,
    address_module_workbench_execution_packet_archive_store_replication_receipt,
)
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash


def _addressed_check(
    check_id: str,
    plane: ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck:
    normalized_check_id = (
        check_id
        if ":" in check_id
        else content_hash(
            {"check_id": check_id},
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_CHECK_PREFIX,
        )
    )
    body = {
        "check_id": normalized_check_id,
        "plane": plane,
        "state": (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckState.PASSED
            if passed
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckState.FAILED
        ),
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck(
        **body,
        content_address="pending:replication-check",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_check(
            provisional
        ),
    )


def _entry(
    ordinal: int,
    source: Any,
    target: Any | None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntry:
    target_address = target.content_address if target is not None else None
    if target is None:
        action = ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.COPY
        detail = "source archive object is absent from target; copy required"
    elif target.content_address == source.content_address:
        action = ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.REUSE
        detail = "target already contains the exact addressed archive object"
    else:
        action = ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.CONFLICT
        detail = "target contains the archive address with a different entry address"
    body = {
        "ordinal": ordinal,
        "archive_address": source.archive_address,
        "object_key": source.object_key,
        "source_entry_address": source.content_address,
        "target_entry_address": target_address,
        "action": action,
        "byte_count": source.byte_count,
        "required": action
        is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.REUSE,
        "accepted": action
        is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.CONFLICT,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntry(
        **body,
        content_address="pending:replication-entry",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntry(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_entry(
            provisional
        ),
    )


def _operation(
    ordinal: int,
    source: Any,
    target: Any | None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperation:
    target_address = target.content_address if target is not None else None
    if target is None:
        action = ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.COPY
        detail = "source journal operation is absent from target; append required"
    elif target.content_address == source.content_address:
        action = ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.REUSE
        detail = "target already contains the exact addressed journal operation"
    else:
        action = ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.CONFLICT
        detail = "target operation ID resolves to a different addressed operation"
    body = {
        "ordinal": ordinal,
        "operation_address": source.content_address,
        "operation_id": source.operation_id,
        "previous_address": source.previous_address,
        "source_result_address": source.result_address,
        "target_operation_address": target_address,
        "action": action,
        "required": action
        is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.REUSE,
        "accepted": action
        is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.CONFLICT,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperation(
        **body,
        content_address="pending:replication-operation",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperation(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_operation(
            provisional
        ),
    )


def _target_entry_map(store: ModuleWorkbenchExecutionPacketArchiveStore) -> dict[str, Any]:
    return {item.archive_address: item for item in store.entries}


def _target_operation_map(store: ModuleWorkbenchExecutionPacketArchiveStore) -> dict[str, Any]:
    return {item.operation_id: item for item in store.operations}


def _prefix(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    """Return whether ``left`` is an exact prefix of ``right``."""

    return len(left) <= len(right) and right[: len(left)] == left


def _public_replication_body(
    source: ModuleWorkbenchExecutionPacketArchiveStore,
    target: ModuleWorkbenchExecutionPacketArchiveStore,
    entries: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntry, ...],
    operations: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperation, ...],
    checks: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck, ...],
) -> dict[str, Any]:
    """Build the inspectable body used by the public-boundary check."""

    return {
        "source_store_id": source.store_id,
        "target_store_id": target.store_id,
        "source_store_address": source.content_address,
        "target_store_address": target.content_address,
        "source_head_address": source.head_address,
        "target_head_address": target.head_address,
        "entries": [item.to_dict() for item in entries],
        "operations": [item.to_dict() for item in operations],
        "checks": [item.to_dict() for item in checks],
    }


def _state(
    source: ModuleWorkbenchExecutionPacketArchiveStore,
    target: ModuleWorkbenchExecutionPacketArchiveStore,
    same_store: bool,
    operation_ancestor: bool,
    entry_ancestor: bool,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationState:
    if not same_store:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.DIVERGED
    if source.content_address == target.content_address:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.MATCHED
    if operation_ancestor and entry_ancestor:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.EXTENDED
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.DIVERGED


def build_module_workbench_execution_packet_archive_store_replication(
    source: ModuleWorkbenchExecutionPacketArchiveStore,
    target: ModuleWorkbenchExecutionPacketArchiveStore,
    *,
    replication_id: str = "glio-noncode-module-workbench-execution-archive-store-replication",
    expected_target_head_address: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan:
    """Plan an append-only source-to-target transfer.

    The source must be the same logical store as the target. A target that is
    not an exact prefix of the source is represented as ``diverged`` and is
    never applyable. A target with the same complete boundary is a successful
    noop plan.
    """

    source_verification = verify_module_workbench_execution_packet_archive_store(source)
    target_verification = verify_module_workbench_execution_packet_archive_store(target)
    source_operations = tuple(item.content_address for item in source.operations)
    target_operations = tuple(item.content_address for item in target.operations)
    source_entries = tuple(item.content_address for item in source.entries)
    target_entries = tuple(item.content_address for item in target.entries)
    operation_ancestor = _prefix(target_operations, source_operations)
    entry_ancestor = _prefix(target_entries, source_entries)
    same_store = source.store_id == target.store_id
    plan_state = _state(source, target, same_store, operation_ancestor, entry_ancestor)
    target_entries_by_archive = _target_entry_map(target)
    target_operations_by_id = _target_operation_map(target)
    entries = tuple(
        _entry(index, source_entry, target_entries_by_archive.get(source_entry.archive_address))
        for index, source_entry in enumerate(source.entries)
    )
    operations = tuple(
        _operation(
            index, source_operation, target_operations_by_id.get(source_operation.operation_id)
        )
        for index, source_operation in enumerate(source.operations)
    )
    checks_list = [
        _addressed_check(
            "replication-check-identity",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.IDENTITY,
            same_store,
            {"source_store_id": source.store_id, "target_store_id": target.store_id},
            "source_store_id == target_store_id",
            "source and target identify one logical append-only store"
            if same_store
            else "source and target store IDs differ",
        ),
        _addressed_check(
            "replication-check-source",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.SOURCE,
            source_verification.accepted,
            source_verification.passed_count,
            source_verification.check_count,
            "source store manifest and objects are accepted"
            if source_verification.accepted
            else "source store verification is blocked",
        ),
        _addressed_check(
            "replication-check-target",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.TARGET,
            target_verification.accepted,
            target_verification.passed_count,
            target_verification.check_count,
            "target store manifest and objects are accepted"
            if target_verification.accepted
            else "target store verification is blocked",
        ),
        _addressed_check(
            "replication-check-operation-ancestry",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.ANCESTRY,
            operation_ancestor,
            {"target": len(target_operations), "source": len(source_operations)},
            "target operation sequence is a source prefix",
            "journal ancestry is append-only"
            if operation_ancestor
            else "journal sequence diverges from source",
        ),
        _addressed_check(
            "replication-check-entry-ancestry",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.ANCESTRY,
            entry_ancestor,
            {"target": len(target_entries), "source": len(source_entries)},
            "target entry sequence is a source prefix",
            "entry ancestry is append-only"
            if entry_ancestor
            else "entry sequence diverges from source",
        ),
        _addressed_check(
            "replication-check-object-actions",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.OBJECT,
            not any(not item.accepted for item in entries),
            sum(item.required for item in entries),
            "no archive object address conflicts",
            "object reuse and copy actions are conflict-free"
            if not any(not item.accepted for item in entries)
            else "one or more archive object entries conflict",
        ),
        _addressed_check(
            "replication-check-operation-actions",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.OPERATION,
            not any(not item.accepted for item in operations),
            sum(item.required for item in operations),
            "no journal operation address conflicts",
            "operation reuse and copy actions are conflict-free"
            if not any(not item.accepted for item in operations)
            else "one or more journal operations conflict",
        ),
    ]
    if expected_target_head_address is None:
        head_passed = True
        head_detail = "no expected target head supplied; target head guard not requested"
        head_required: Any = "not_requested"
    else:
        head_passed = target.head_address == expected_target_head_address
        head_detail = (
            "target head matches caller-provided expected head"
            if head_passed
            else "target head changed since the caller's expected boundary"
        )
        head_required = expected_target_head_address
    checks_list.append(
        _addressed_check(
            "replication-check-expected-head",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.TARGET,
            head_passed,
            target.head_address,
            head_required,
            head_detail,
        )
    )
    checks = tuple(checks_list)
    public_body = _public_replication_body(source, target, entries, operations, checks)
    checks = checks + (
        _addressed_check(
            "replication-check-public",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.PUBLIC,
            not _has_forbidden_key(public_body),
            "path_free_content_addressed_boundary",
            "no_forbidden_public_keys",
            "replication plan contains no binary payloads, paths, timestamps, or identity metadata",
        ),
    )
    object_copy_count = sum(
        item.action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.COPY
        for item in entries
    )
    object_reuse_count = sum(
        item.action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.REUSE
        for item in entries
    )
    object_conflict_count = sum(
        item.action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.CONFLICT
        for item in entries
    )
    operation_copy_count = sum(
        item.action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.COPY
        for item in operations
    )
    operation_reuse_count = sum(
        item.action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.REUSE
        for item in operations
    )
    operation_conflict_count = sum(
        item.action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.CONFLICT
        for item in operations
    )
    required_byte_count = sum(item.byte_count for item in entries if item.required)
    source_byte_count = source.total_byte_count
    transfer_ratio = required_byte_count / source_byte_count if source_byte_count else 0
    accepted = (
        plan_state
        in {
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.MATCHED,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.EXTENDED,
        }
        and all(item.passed for item in checks)
        and all(item.accepted for item in entries)
        and all(item.accepted for item in operations)
    )
    body = {
        "replication_id": replication_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_BOUNDARY,
        "source_store_id": source.store_id,
        "target_store_id": target.store_id,
        "source_store_address": source.content_address,
        "target_store_address": target.content_address,
        "source_head_address": source.head_address,
        "target_head_address": target.head_address,
        "source_archive_count": source.archive_count,
        "target_archive_count": target.archive_count,
        "source_operation_count": source.operation_count,
        "target_operation_count": target.operation_count,
        "source_byte_count": source.total_byte_count,
        "target_byte_count": target.total_byte_count,
        "state": plan_state,
        "entries": entries,
        "operations": operations,
        "checks": checks,
        "object_count": len(entries),
        "object_copy_count": object_copy_count,
        "object_reuse_count": object_reuse_count,
        "object_conflict_count": object_conflict_count,
        "operation_count": len(operations),
        "operation_copy_count": operation_copy_count,
        "operation_reuse_count": operation_reuse_count,
        "operation_conflict_count": operation_conflict_count,
        "required_byte_count": required_byte_count,
        "transfer_ratio": transfer_ratio,
        "apply_allowed": accepted
        and plan_state is ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.EXTENDED,
        "accepted": accepted,
        "detail": (
            "source extends target through a conflict-free append-only boundary"
            if accepted
            and plan_state is ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.EXTENDED
            else "source and target already match exactly"
            if accepted
            else (
                "replication is blocked by identity, ancestry, verification, guard, "
                "or conflict checks"
            )
        ),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan(
        **body,
        content_address="pending:replication",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan:
    """Verify all nested addresses and the plan's deterministic address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan):
        raise ValidationError("replication verification requires a typed plan")
    for item in value.entries:
        if (
            address_module_workbench_execution_packet_archive_store_replication_entry(item)
            != item.content_address
        ):
            raise ValidationError("replication entry address mismatch")
    for item in value.operations:
        if (
            address_module_workbench_execution_packet_archive_store_replication_operation(item)
            != item.content_address
        ):
            raise ValidationError("replication operation address mismatch")
    for item in value.checks:
        if (
            address_module_workbench_execution_packet_archive_store_replication_check(item)
            != item.content_address
        ):
            raise ValidationError("replication check address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication(value)
        != value.content_address
    ):
        raise ValidationError("replication plan address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan:
    """Rehydrate and verify a plan from a public JSON mapping."""

    if not isinstance(value, Mapping):
        raise ValidationError("replication plan document must be an object")
    body = dict(value)
    body["state"] = ModuleWorkbenchExecutionPacketArchiveStoreReplicationState(body["state"])
    body["entries"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntry(
            **{
                **item,
                "action": ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction(
                    item["action"]
                ),
            }
        )
        for item in body.get("entries", ())
    )
    body["operations"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperation(
            **{
                **item,
                "action": ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction(
                    item["action"]
                ),
            }
        )
        for item in body.get("operations", ())
    )
    body["checks"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck(
            **{
                **item,
                "plane": ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane(
                    item["plane"]
                ),
                "state": ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckState(
                    item["state"]
                ),
            }
        )
        for item in body.get("checks", ())
    )
    return verify_module_workbench_execution_packet_archive_store_replication(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan(**body)
    )


def apply_module_workbench_execution_packet_archive_store_replication(
    plan: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
    source: ModuleWorkbenchExecutionPacketArchiveStore,
    target: ModuleWorkbenchExecutionPacketArchiveStore,
    *,
    destination: str | Path,
    expected_target_head_address: str | None = None,
    allow_existing: bool = False,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt:
    """Apply a fresh plan by atomically writing the verified source boundary."""

    verify_module_workbench_execution_packet_archive_store_replication(plan)
    source_verification = verify_module_workbench_execution_packet_archive_store(source)
    target_verification = verify_module_workbench_execution_packet_archive_store(target)
    if not source_verification.accepted or not target_verification.accepted:
        raise ValidationError("replication apply requires two accepted stores")
    current = build_module_workbench_execution_packet_archive_store_replication(
        source,
        target,
        replication_id=plan.replication_id,
        expected_target_head_address=expected_target_head_address,
    )
    if current.content_address != plan.content_address:
        raise ValidationError("replication plan is stale")
    if (
        expected_target_head_address is not None
        and target.head_address != expected_target_head_address
    ):
        raise ValidationError("replication target head is stale")
    if not current.accepted:
        raise ValidationError("replication plan is blocked")
    if current.state is ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.MATCHED:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState.NOOP
        after_address = target.content_address
        after_head = target.head_address
        detail = "target already matches source; no destination write was required"
    else:
        write_module_workbench_execution_packet_archive_store(
            source,
            destination,
            allow_existing=allow_existing,
        )
        written = load_module_workbench_execution_packet_archive_store(destination)
        if written.content_address != source.content_address:
            raise ValidationError("replication destination did not match source boundary")
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState.APPLIED
        after_address = written.content_address
        after_head = written.head_address
        detail = "source boundary atomically written and reloaded from destination"
    body = {
        "replication_id": plan.replication_id,
        "plan_address": plan.content_address,
        "source_store_id": source.store_id,
        "target_store_id": target.store_id,
        "before_target_address": target.content_address,
        "after_target_address": after_address,
        "before_target_head_address": target.head_address,
        "after_target_head_address": after_head,
        "state": state,
        "object_copy_count": plan.object_copy_count,
        "object_reuse_count": plan.object_reuse_count,
        "operation_copy_count": plan.operation_copy_count,
        "operation_reuse_count": plan.operation_reuse_count,
        "byte_count": plan.required_byte_count,
        "expected_head_address": expected_target_head_address,
        "accepted": True,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt(
        **body,
        content_address="pending:replication-receipt",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_receipt(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_receipt(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt:
    """Verify an apply receipt's deterministic address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt):
        raise ValidationError("replication receipt verification requires a typed receipt")
    if (
        address_module_workbench_execution_packet_archive_store_replication_receipt(value)
        != value.content_address
    ):
        raise ValidationError("replication receipt address mismatch")
    return value


def build_module_workbench_execution_packet_archive_store_promotion(
    plan: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
    receipt: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt | None = None,
    *,
    promotion_id: str = "glio-noncode-module-workbench-execution-archive-store-promotion",
) -> ModuleWorkbenchExecutionPacketArchiveStorePromotion:
    """Build a release-style decision for the source boundary."""

    verify_module_workbench_execution_packet_archive_store_replication(plan)
    if receipt is not None:
        verify_module_workbench_execution_packet_archive_store_replication_receipt(receipt)
    checks: list[ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck] = []
    checks.append(
        _addressed_check(
            "promotion-check-plan",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.SOURCE,
            plan.accepted,
            plan.state,
            "accepted replication plan",
            "replication plan is accepted" if plan.accepted else "replication plan is blocked",
        )
    )
    receipt_matches = (
        plan.state is ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.MATCHED
    )
    if receipt is not None:
        receipt_matches = (
            receipt.accepted and receipt.after_target_address == plan.source_store_address
        )
    checks.append(
        _addressed_check(
            "promotion-check-receipt",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.DESTINATION,
            receipt_matches,
            receipt.after_target_address if receipt is not None else "not_required_for_exact_match",
            plan.source_store_address,
            "target boundary is reconciled to the source boundary"
            if receipt_matches
            else "target boundary has not been reconciled to the source boundary",
        )
    )
    checks.append(
        _addressed_check(
            "promotion-check-identity",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.IDENTITY,
            plan.source_store_id == plan.target_store_id,
            {"source_store_id": plan.source_store_id, "target_store_id": plan.target_store_id},
            "same logical store",
            "promotion remains within one logical store"
            if plan.source_store_id == plan.target_store_id
            else "promotion crosses logical store identities",
        )
    )
    checks.append(
        _addressed_check(
            "promotion-check-public",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane.PUBLIC,
            not _has_forbidden_key({"checks": [item.to_dict() for item in checks]}),
            "path_free_content_addressed_boundary",
            "no_forbidden_public_keys",
            "promotion decision is safe for the public output boundary",
        )
    )
    checks_tuple = tuple(checks)
    promotable = plan.accepted and receipt_matches and all(item.passed for item in checks_tuple)
    state = (
        ModuleWorkbenchExecutionPacketArchiveStorePromotionState.PROMOTABLE
        if promotable
        else ModuleWorkbenchExecutionPacketArchiveStorePromotionState.HOLD
        if plan.accepted
        else ModuleWorkbenchExecutionPacketArchiveStorePromotionState.BLOCKED
    )
    body = {
        "promotion_id": promotion_id,
        "plan_address": plan.content_address,
        "receipt_address": receipt.content_address if receipt is not None else None,
        "source_store_id": plan.source_store_id,
        "target_store_id": plan.target_store_id,
        "source_store_address": plan.source_store_address,
        "target_store_address": plan.target_store_address,
        "state": state,
        "checks": checks_tuple,
        "required_check_count": len(checks_tuple),
        "passed_check_count": sum(item.passed for item in checks_tuple),
        "release_allowed": promotable,
        "accepted": promotable,
        "detail": (
            "replication boundary is reconciled and promotable"
            if promotable
            else "promotion is held until an accepted replication receipt reconciles the target"
            if plan.accepted
            else "promotion is blocked because the replication plan is not accepted"
        ),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStorePromotion(
        **body,
        content_address="pending:promotion",
    )
    return ModuleWorkbenchExecutionPacketArchiveStorePromotion(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_promotion(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_promotion(
    value: ModuleWorkbenchExecutionPacketArchiveStorePromotion,
) -> ModuleWorkbenchExecutionPacketArchiveStorePromotion:
    """Verify promotion checks and deterministic address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveStorePromotion):
        raise ValidationError("promotion verification requires a typed decision")
    for item in value.checks:
        if (
            address_module_workbench_execution_packet_archive_store_replication_check(item)
            != item.content_address
        ):
            raise ValidationError("promotion check address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_promotion(value)
        != value.content_address
    ):
        raise ValidationError("promotion address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_receipt_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_receipt(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_promotion_json(
    value: ModuleWorkbenchExecutionPacketArchiveStorePromotion,
) -> str:
    verify_module_workbench_execution_packet_archive_store_promotion(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
) -> str:
    """Export the plan as one row per source object and journal operation."""

    verify_module_workbench_execution_packet_archive_store_replication(value)
    fields = (
        "resource",
        "ordinal",
        "address",
        "key",
        "action",
        "required",
        "accepted",
        "detail",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.entries:
        writer.writerow(
            {
                "resource": "entry",
                "ordinal": item.ordinal,
                "address": item.archive_address,
                "key": item.object_key,
                "action": item.action,
                "required": item.required,
                "accepted": item.accepted,
                "detail": item.detail,
            }
        )
    for item in value.operations:
        writer.writerow(
            {
                "resource": "operation",
                "ordinal": item.ordinal,
                "address": item.operation_address,
                "key": item.operation_id,
                "action": item.action,
                "required": item.required,
                "accepted": item.accepted,
                "detail": item.detail,
            }
        )
    return output.getvalue()


def module_workbench_execution_packet_archive_store_replication_receipt_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_receipt(value)
    fields = tuple(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow(value.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication(value)
    lines = [
        "# Archive Store Replication Plan",
        "",
        f"- Replication: `{value.replication_id}`",
        f"- Address: `{value.content_address}`",
        f"- State: `{value.state}`",
        f"- Source / target: `{value.source_store_address}` / `{value.target_store_address}`",
        f"- Objects copied / reused: `{value.object_copy_count}` / `{value.object_reuse_count}`",
        f"- Operations copied / reused: `{value.operation_copy_count}` / "
        f"`{value.operation_reuse_count}`",
        f"- Required bytes: `{value.required_byte_count:,}` ({value.transfer_ratio:.3f} of source)",
        f"- Apply allowed: `{str(value.apply_allowed).lower()}`",
        "",
        "| Resource | Ordinal | Address | Action | Required | Accepted |",
        "|---|---:|---|---|---:|---:|",
    ]
    for item in value.entries:
        lines.append(
            f"| entry | {item.ordinal} | `{item.archive_address}` | `{item.action}` | "
            f"{str(item.required).lower()} | {str(item.accepted).lower()} |"
        )
    for item in value.operations:
        lines.append(
            f"| operation | {item.ordinal} | `{item.operation_address}` | `{item.action}` | "
            f"{str(item.required).lower()} | {str(item.accepted).lower()} |"
        )
    return "\n".join(lines) + "\n"


def load_module_workbench_execution_packet_archive_store_replication_inputs(
    source_directory: str | Path,
    target_directory: str | Path,
    *,
    replication_id: str = "glio-noncode-module-workbench-execution-archive-store-replication",
    expected_target_head_address: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan:
    """Load two verified directories and build a path-free plan."""

    source = load_module_workbench_execution_packet_archive_store(source_directory)
    target = load_module_workbench_execution_packet_archive_store(target_directory)
    return build_module_workbench_execution_packet_archive_store_replication(
        source,
        target,
        replication_id=replication_id,
        expected_target_head_address=expected_target_head_address,
    )


def apply_module_workbench_execution_packet_archive_store_replication_from_directories(
    source_directory: str | Path,
    target_directory: str | Path,
    *,
    destination: str | Path,
    replication_id: str = "glio-noncode-module-workbench-execution-archive-store-replication",
    expected_target_head_address: str | None = None,
    allow_existing: bool = False,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt:
    """Load, plan, and apply a directory replication with a fresh head guard."""

    source = load_module_workbench_execution_packet_archive_store(source_directory)
    target = load_module_workbench_execution_packet_archive_store(target_directory)
    plan = build_module_workbench_execution_packet_archive_store_replication(
        source,
        target,
        replication_id=replication_id,
        expected_target_head_address=expected_target_head_address,
    )
    return apply_module_workbench_execution_packet_archive_store_replication(
        plan,
        source,
        target,
        destination=destination,
        expected_target_head_address=expected_target_head_address,
        allow_existing=allow_existing,
    )
