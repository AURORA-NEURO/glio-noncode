"""Persist, replay, append, and export durable release-window review stores.

The store is an addressed transport boundary around a review ledger.  It
keeps the typed ledger as a canonical JSON artifact, an operation journal, and
an addressed manifest.  Writes are atomic and replacement is explicit; reads
reject missing, extra, non-canonical, or tampered files before returning a
typed object.  The public projections contain no filesystem paths, timestamps,
credentials, or attribution metadata.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review import (
    append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_decision,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_from_directories,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_LEDGER,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MANIFEST,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_CHECKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_OPERATIONS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_OPERATIONS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheckState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplay,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplayState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreVerification,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_check,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_operation,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_replay,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_verification,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _optional_address(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _address(value, field)


def _json_object(payload: bytes, field: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{field} must be a JSON object")
    if canonical_bytes(value) != payload:
        raise ValidationError(f"{field} is not canonical JSON")
    return value


def _operation(
    ordinal: int,
    *,
    operation_id: str,
    kind: str,
    input_address: str | None,
    output_address: str | None,
    previous_operation_address: str | None,
    accepted: bool,
    detail: str,
) -> (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation
):
    body = {
        "ordinal": ordinal,
        "operation_id": operation_id,
        "kind": kind,
        "state": (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationState.ACCEPTED.value
            if accepted
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationState.REJECTED.value
        ),
        "input_address": input_address,
        "output_address": output_address,
        "previous_operation_address": previous_operation_address,
        "accepted": accepted,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation(
        **body, content_address="pending:operation"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_operation(
            provisional
        ),
    )


def _check(
    ordinal: int,
    *,
    plane: str,
    kind: str,
    passed: bool,
    expected: Any,
    observed: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck:
    body = {
        "ordinal": ordinal,
        "plane": plane,
        "kind": kind,
        "state": (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheckState.PASSED.value
            if passed
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheckState.FAILED.value
        ),
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_check(
            provisional
        ),
    )


def _state(ledger: Any) -> str:
    if not ledger.entries:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.EMPTY.value
    if ledger.release_ready:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.READY.value
    if ledger.state in {"hold", "superseded"}:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.HELD.value
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.BLOCKED.value


def _checks(
    ledger: Any,
    operations: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation,
        ...,
    ],
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck,
    ...,
]:
    return (
        _check(
            0,
            plane="format",
            kind="version",
            passed=True,
            expected=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_VERSION,
            observed=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_VERSION,
            detail="the durable review store uses the published version",
        ),
        _check(
            1,
            plane="ledger",
            kind="ledger-link",
            passed=ledger.content_address.startswith(
                "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review:"
            ),
            expected="addressed review ledger",
            observed=ledger.content_address,
            detail="the store retains one addressed review ledger",
        ),
        _check(
            2,
            plane="chain",
            kind="operation-chain",
            passed=all(item.accepted for item in operations)
            and tuple(item.ordinal for item in operations) == tuple(range(len(operations))),
            expected="contiguous accepted operations",
            observed={
                "count": len(operations),
                "accepted": all(item.accepted for item in operations),
            },
            detail="the journal is contiguous and accepted",
        ),
        _check(
            3,
            plane="chain",
            kind="head-conservation",
            passed=(
                not ledger.entries or ledger.head_address == ledger.entries[-1].content_address
            ),
            expected=ledger.head_address,
            observed=ledger.entries[-1].content_address if ledger.entries else None,
            detail="the persisted store head agrees with the ledger head",
        ),
        _check(
            4,
            plane="ledger",
            kind="readiness",
            passed=ledger.release_ready == (ledger.state == "promoted"),
            expected=ledger.release_ready,
            observed=ledger.state == "promoted",
            detail="store readiness follows the ledger decision",
        ),
        _check(
            5,
            plane="storage",
            kind="append-only",
            passed=True,
            expected=True,
            observed=True,
            detail="store operations are retained as an append-only history",
        ),
        _check(
            6,
            plane="public",
            kind="boundary",
            passed=True,
            expected=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_BOUNDARY,
            observed=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_BOUNDARY,
            detail="the store projection contains only public deterministic fields",
        ),
    )


def _store(
    ledger: Any,
    operations: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation,
        ...,
    ],
    *,
    store_id: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore:
    checks = _checks(ledger, operations)
    body = {
        "store_id": store_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_BOUNDARY,
        "ledger_address": ledger.content_address,
        "head_address": ledger.head_address,
        "entry_count": ledger.entry_count,
        "state": _state(ledger),
        "release_ready": ledger.release_ready,
        "accepted": ledger.entry_count > 0
        and bool(operations)
        and all(item.accepted for item in operations)
        and all(item.passed for item in checks),
        "append_only": True,
        "operations": operations,
        "operation_count": len(operations),
        "checks": checks,
        "check_count": len(checks),
    }
    provisional = (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore(
            **body, content_address="pending:store"
        )
    )
    value = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            provisional
        ),
    )
    value.ledger = ledger
    return value


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
    ledger: Any,
    *,
    store_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-store",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore:
    """Build a durable store with a genesis operation for one review ledger."""

    operation = _operation(
        0,
        operation_id=f"{store_id}:genesis",
        kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationKind.GENESIS.value,
        input_address=None,
        output_address=ledger.content_address,
        previous_operation_address=None,
        accepted=True,
        detail="genesis operation records the addressed review ledger",
    )
    return _store(ledger, (operation,), store_id=store_id)


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_from_directories(
    pairs: Sequence[tuple[str, str | Path, str | Path]],
    *,
    decisions: Sequence[Mapping[str, Any]] = (),
    policy: Any | None = None,
    batch_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-batch",
    window_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window",
    ledger_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review",
    store_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-store",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore:
    """Build a store directly from persisted packet directories."""

    ledger = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_from_directories(
        pairs,
        decisions=decisions,
        policy=policy,
        batch_id=batch_id,
        window_id=window_id,
        ledger_id=ledger_id,
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        ledger, store_id=store_id
    )


def append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_decision(
    store: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    ledger: Any,
    window: Any,
    assurance: Any,
    *,
    entry_id: str,
    decision: str,
    rationale: str,
    required_actions: Sequence[str] = (),
    expected_head_address: str | None = None,
    operation_id: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore:
    """Append one decision with an optional optimistic head guard."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        store, ledger=ledger
    )
    if expected_head_address is not None and expected_head_address != store.head_address:
        raise ValidationError("review store expected head address does not match")
    next_ledger = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_decision(
        ledger,
        window,
        assurance,
        entry_id=entry_id,
        decision=decision,
        rationale=rationale,
        required_actions=required_actions,
    )
    operation = _operation(
        store.operation_count,
        operation_id=operation_id or f"{store.store_id}:append:{store.operation_count}",
        kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationKind.APPEND.value,
        input_address=ledger.content_address,
        output_address=next_ledger.content_address,
        previous_operation_address=store.operations[-1].content_address
        if store.operations
        else None,
        accepted=True,
        detail="append operation records one new verified review ledger revision",
    )
    return _store(next_ledger, store.operations + (operation,), store_id=store.store_id)


def _entry_from_dict(value: Mapping[str, Any]) -> Any:
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_contracts import (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry,
    )

    body = dict(value)
    body["required_actions"] = tuple(body.get("required_actions", ()))
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry(
        **body
    )


def _ledger_from_dict(value: Mapping[str, Any]) -> Any:
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_contracts import (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    )

    body = dict(value)
    body["entries"] = tuple(_entry_from_dict(item) for item in body.get("entries", ()))
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview(
        **body
    )


def _operation_from_dict(
    value: Mapping[str, Any],
) -> (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation
):
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation(
        **dict(value)
    )


def _check_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck(
        **dict(value)
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    *,
    ledger: Any | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreVerification:
    """Verify store contracts and optionally reconcile the hydrated ledger."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    ):
        raise ValidationError("review store verification requires a typed store")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            value
        )
        != value.content_address
    ):
        raise ValidationError("review store content address mismatch")
    checks = list(value.checks)
    if ledger is not None:
        if ledger.content_address != value.ledger_address:
            checks.append(
                _check(
                    len(checks),
                    plane="ledger",
                    kind="hydrated-ledger-link",
                    passed=False,
                    expected=value.ledger_address,
                    observed=ledger.content_address,
                    detail="hydrated ledger address differs from the store manifest",
                )
            )
        if ledger.head_address != value.head_address or ledger.entry_count != value.entry_count:
            checks.append(
                _check(
                    len(checks),
                    plane="ledger",
                    kind="hydrated-head",
                    passed=False,
                    expected={"head": value.head_address, "count": value.entry_count},
                    observed={"head": ledger.head_address, "count": ledger.entry_count},
                    detail="hydrated ledger head or entry count differs from the store manifest",
                )
            )
    provisional_checks = tuple(checks)
    body = {
        "store_id": value.store_id,
        "store_address": value.content_address,
        "checks": provisional_checks,
        "check_count": len(provisional_checks),
        "passed_count": sum(item.passed for item in provisional_checks),
        "failed_count": sum(not item.passed for item in provisional_checks),
        "accepted": bool(provisional_checks) and all(item.passed for item in provisional_checks),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreVerification(
        **body, content_address="pending:verification"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_verification(
            provisional
        ),
    )


def _manifest(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    ledger_bytes: bytes,
    operation_bytes: bytes,
) -> dict[str, Any]:
    body = value.to_dict() | {
        "manifest_version": "review-store-manifest-v1",
        "ledger_file": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_LEDGER,
        "ledger_byte_count": len(ledger_bytes),
        "ledger_byte_address": hash_bytes(
            ledger_bytes,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX
            + "-ledger-bytes",
        ),
        "operations_file": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_OPERATIONS,
        "operations_byte_count": len(operation_bytes),
        "operations_byte_address": hash_bytes(
            operation_bytes,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX
            + "-operations-bytes",
        ),
    }
    return body | {
        "manifest_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX
            + "-manifest",
        )
    }


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Atomically write manifest, ledger, and operation artifacts."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        value
    )
    ledger = getattr(value, "ledger", None)
    if ledger is None:
        raise ValidationError("review store writing requires a hydrated ledger")
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("review store destination already exists")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=parent))
    try:
        ledger_bytes = canonical_bytes(ledger.to_dict())
        operation_bytes = canonical_bytes(
            {"operations": [item.to_dict() for item in value.operations]}
        )
        manifest_bytes = canonical_bytes(_manifest(value, ledger_bytes, operation_bytes))
        (
            temp
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_LEDGER
        ).write_bytes(ledger_bytes)
        (
            temp
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_OPERATIONS
        ).write_bytes(operation_bytes)
        (
            temp
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MANIFEST
        ).write_bytes(manifest_bytes)
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("review store destination is not a regular directory")
            shutil.rmtree(destination)
        os.replace(temp, destination)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return destination


def _read_store_files(
    directory: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("review store directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MANIFEST,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_LEDGER,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_OPERATIONS,
    }
    children = tuple(directory.iterdir())
    if any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("review store directory contains a non-regular artifact")
    actual = {item.name for item in children}
    if actual != expected:
        raise ValidationError("review store files do not match the published set")
    manifest_bytes = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MANIFEST
    ).read_bytes()
    ledger_bytes = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_LEDGER
    ).read_bytes()
    operation_bytes = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_OPERATIONS
    ).read_bytes()
    manifest = _json_object(manifest_bytes, "review store manifest")
    ledger = _json_object(ledger_bytes, "review store ledger")
    operations = _json_object(operation_bytes, "review store operations")
    expected_manifest = {key: item for key, item in manifest.items() if key != "manifest_address"}
    if manifest.get("manifest_address") != content_hash(
        expected_manifest,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX
        + "-manifest",
    ):
        raise ValidationError("review store manifest address mismatch")
    if manifest.get("ledger_byte_count") != len(ledger_bytes) or manifest.get(
        "ledger_byte_address"
    ) != hash_bytes(
        ledger_bytes,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX
        + "-ledger-bytes",
    ):
        raise ValidationError("review store ledger bytes do not match manifest")
    if manifest.get("operations_byte_count") != len(operation_bytes) or manifest.get(
        "operations_byte_address"
    ) != hash_bytes(
        operation_bytes,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX
        + "-operations-bytes",
    ):
        raise ValidationError("review store operation bytes do not match manifest")
    if set(operations) != {"operations"} or not isinstance(operations["operations"], list):
        raise ValidationError("review store operations artifact is invalid")
    return manifest, ledger, operations


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore:
    """Load and verify an exact durable review store directory."""

    manifest, ledger_body, operation_body = _read_store_files(directory)
    ledger = _ledger_from_dict(ledger_body)
    if manifest.get("ledger_address") != ledger.content_address:
        raise ValidationError("review store ledger address does not match manifest")
    operations = tuple(_operation_from_dict(item) for item in operation_body["operations"])
    manifest_operations = tuple(
        _operation_from_dict(item) for item in manifest.get("operations", [])
    )
    if [item.to_dict() for item in operations] != [item.to_dict() for item in manifest_operations]:
        raise ValidationError("review store operations do not match manifest")
    body = {
        key: item
        for key, item in manifest.items()
        if key
        in {
            "store_id",
            "version",
            "boundary",
            "ledger_address",
            "head_address",
            "entry_count",
            "state",
            "release_ready",
            "accepted",
            "append_only",
            "operations",
            "operation_count",
            "checks",
            "check_count",
            "content_address",
        }
    }
    body["operations"] = operations
    body["checks"] = tuple(_check_from_dict(item) for item in body.get("checks", ()))
    value = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore(
        **body
    )
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            value
        )
        != value.content_address
    ):
        raise ValidationError("review store content address does not match manifest")
    value.ledger = ledger
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        value, ledger=ledger
    )
    return value


def replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplay:
    """Return an addressed replay receipt for a hydrated store."""

    ledger = getattr(value, "ledger", None)
    observed_head = ledger.head_address if ledger is not None else None
    matched = (
        ledger is not None
        and ledger.content_address == value.ledger_address
        and observed_head == value.head_address
        and ledger.entry_count == value.entry_count
    )
    state = (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplayState.MATCHED.value
        if matched
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplayState.BLOCKED.value
        if ledger is None
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplayState.DIVERGED.value
    )
    body = {
        "store_id": value.store_id,
        "store_address": value.content_address,
        "ledger_address": value.ledger_address,
        "expected_head_address": value.head_address,
        "observed_head_address": observed_head,
        "entry_count": value.entry_count,
        "operation_count": value.operation_count,
        "state": state,
        "accepted": matched,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplay(
        **body, content_address="pending:replay"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplay(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_replay(
            provisional
        ),
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "store_id",
        "ledger_address",
        "head_address",
        "entry_count",
        "state",
        "release_ready",
        "accepted",
        "append_only",
        "operation_count",
        "check_count",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow({key: value.summary().get(key) for key in fields})
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        value
    )
    lines = [
        "# Durable Release-Window Review Store",
        "",
        f"- state: `{value.state}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- entries: `{value.entry_count}`",
        f"- operations: `{value.operation_count}`",
        f"- checks: `{value.check_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Kind | Accepted | Detail |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | {item.kind} | {str(item.accepted).lower()} | {item.detail} |"
        for item in value.operations
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_BOUNDARY,
        "files": [
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MANIFEST,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_LEDGER,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_OPERATIONS,
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState
        ],
        "limits": {
            "operations": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_OPERATIONS,
            "checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_CHECKS,
            "limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT,
        },
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_VERSION,
        "operations": [
            "build",
            "append",
            "write",
            "load",
            "verify",
            "replay",
            "json",
            "csv",
            "markdown",
        ],
        "atomic_write": True,
        "append_only": True,
        "exact_byte_files": True,
        "identity_free": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
    or name.startswith(
        "append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
    or name.startswith(
        "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
    or name.startswith(
        "load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
    or name.startswith(
        "replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
    or name.startswith(
        "write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
]
