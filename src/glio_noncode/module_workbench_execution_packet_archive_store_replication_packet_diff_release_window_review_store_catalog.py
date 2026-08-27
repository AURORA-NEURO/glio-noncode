"""Build, persist, verify, and extend durable review-store catalogs.

This module is the collection boundary above one durable review store.  It
loads already-verified stores, derives a path-free catalog entry for each,
retains an addressed registration journal, and writes an exact three-artifact
directory.  Catalog construction never changes a review decision.  It only
indexes existing decisions so a release collection can be checked, replayed,
queried, and compared deterministically.
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
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store import (
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ENTRIES,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MANIFEST,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_OPERATIONS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_OPERATIONS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheckState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogVerification,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_check,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_entry,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_operation,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_verification,
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


def _bounded(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside the published limit")
    return value


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


def _entry_from_store(
    ordinal: int,
    store: Any,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry:
    if not hasattr(store, "store_id") or not hasattr(store, "content_address"):
        raise ValidationError("catalog members must be durable review stores")
    ledger = getattr(store, "ledger", None)
    if ledger is None:
        raise ValidationError("catalog members must retain a hydrated review ledger")
    body = {
        "ordinal": ordinal,
        "store_id": store.store_id,
        "store_address": store.content_address,
        "window_address": ledger.window_address,
        "ledger_address": store.ledger_address,
        "head_address": store.head_address,
        "entry_count": store.entry_count,
        "operation_count": store.operation_count,
        "store_state": store.state,
        "release_ready": store.release_ready,
        "accepted": store.accepted,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry(
        **body, content_address="pending:entry"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_entry(
            provisional
        ),
    )


def _entry_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry(
        **dict(value)
    )


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
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation:
    body = {
        "ordinal": ordinal,
        "operation_id": operation_id,
        "kind": kind,
        "state": (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationState.ACCEPTED.value
            if accepted
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationState.REJECTED.value
        ),
        "input_address": input_address,
        "output_address": output_address,
        "previous_operation_address": previous_operation_address,
        "accepted": accepted,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation(
        **body, content_address="pending:operation"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_operation(
            provisional
        ),
    )


def _operation_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation(
        **dict(value)
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
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck:
    body = {
        "ordinal": ordinal,
        "plane": plane,
        "kind": kind,
        "state": (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheckState.PASSED.value
            if passed
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheckState.FAILED.value
        ),
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_check(
            provisional
        ),
    )


def _checks(
    entries: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry,
        ...,
    ],
    operations: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation,
        ...,
    ],
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck,
    ...,
]:
    ids = tuple(item.store_id for item in entries)
    addresses = tuple(item.store_address for item in entries)
    windows = tuple(item.window_address for item in entries)
    all_member_accepted = all(item.accepted for item in entries)
    all_member_ready = all(item.release_ready for item in entries)
    checks = (
        _check(
            0,
            plane="format",
            kind="version",
            passed=True,
            expected=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
            observed=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
            detail="the catalog uses the published version",
        ),
        _check(
            1,
            plane="entries",
            kind="entry-count",
            passed=len(entries)
            <= MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
            expected=f"0..{MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES}",
            observed=len(entries),
            detail="member count stays within the bounded catalog limit",
        ),
        _check(
            2,
            plane="entries",
            kind="unique-store-ids",
            passed=len(ids) == len(set(ids)),
            expected=len(ids),
            observed=len(set(ids)),
            detail="each catalog member has one unique store ID",
        ),
        _check(
            3,
            plane="entries",
            kind="address-conservation",
            passed=len(addresses) == len(set(addresses)) and all(":" in item for item in addresses),
            expected="unique addressed stores",
            observed={
                "store_addresses": len(set(addresses)),
                "window_addresses": len(set(windows)),
            },
            detail="member addresses are present and do not collapse distinct stores",
        ),
        _check(
            4,
            plane="operations",
            kind="journal-conservation",
            passed=len(operations) == len(entries) + 1
            and len(operations)
            <= MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_OPERATIONS,
            expected=len(entries) + 1,
            observed=len(operations),
            detail="the registration journal conserves genesis plus one operation per member",
        ),
        _check(
            5,
            plane="entries",
            kind="member-acceptance",
            passed=all_member_accepted,
            expected=True,
            observed=all_member_accepted,
            detail="every catalog member carries an accepted durable store",
        ),
        _check(
            6,
            plane="entries",
            kind="member-readiness",
            passed=True,
            expected=True,
            observed=all_member_ready if entries else True,
            detail="member release readiness is retained for the federation gate",
        ),
        _check(
            7,
            plane="public",
            kind="identity-free",
            passed=True,
            expected=True,
            observed=True,
            detail="catalog projections contain no identity or private metadata",
        ),
    )
    if (
        len(checks)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS
    ):
        raise ValidationError("catalog checks exceed the published limit")
    return checks


def _state(
    entries: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry,
        ...,
    ],
    checks: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck,
        ...,
    ],
) -> str:
    if not entries:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState.EMPTY.value
    if any(not item.accepted for item in entries) or any(not item.passed for item in checks):
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState.BLOCKED.value
    if all(item.release_ready for item in entries):
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState.READY.value
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState.HELD.value


def _catalog(
    catalog_id: str,
    entries: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry,
        ...,
    ],
    operations: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation,
        ...,
    ],
    checks: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck,
        ...,
    ],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog:
    state = _state(entries, checks)
    body = {
        "catalog_id": catalog_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_BOUNDARY,
        "entry_count": len(entries),
        "state": state,
        "release_ready": bool(entries)
        and state
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState.READY.value,
        "accepted": bool(entries)
        and all(item.accepted for item in entries)
        and all(item.accepted for item in operations)
        and all(item.passed for item in checks),
        "append_only": True,
        "entries": entries,
        "operation_count": len(operations),
        "operations": operations,
        "check_count": len(checks),
        "checks": checks,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog(
        **body, content_address="pending:catalog"
    )
    value = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            provisional
        ),
    )
    return value


def _genesis() -> (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation
):
    return _operation(
        0,
        operation_id="catalog-genesis",
        kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationKind.GENESIS.value,
        input_address=None,
        output_address=None,
        previous_operation_address=None,
        accepted=True,
        detail="catalog journal genesis",
    )


def _registration_operations(
    entries: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry,
        ...,
    ],
    *,
    prior: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation,
        ...,
    ] = (),
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation,
    ...,
]:
    operations = list(prior) if prior else [_genesis()]
    for entry in entries[len(prior) - 1 if prior else 0 :]:
        ordinal = len(operations)
        previous = operations[-1].content_address
        operations.append(
            _operation(
                ordinal,
                operation_id=f"register-{entry.store_id}",
                kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationKind.REGISTER.value,
                input_address=entry.store_address,
                output_address=entry.content_address,
                previous_operation_address=previous,
                accepted=True,
                detail="registered one addressed durable review store",
            )
        )
    if (
        len(operations)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_OPERATIONS
    ):
        raise ValidationError("catalog operations exceed the published limit")
    return tuple(operations)


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
    stores: Sequence[Any],
    *,
    catalog_id: str = "glio-noncode-review-store-catalog",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog:
    """Build a deterministic catalog from hydrated durable review stores."""

    if (
        len(stores)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES
    ):
        raise ValidationError("catalog has too many stores")
    ordered = tuple(sorted(stores, key=lambda item: str(getattr(item, "store_id", ""))))
    entries = tuple(_entry_from_store(ordinal, store) for ordinal, store in enumerate(ordered))
    if len({item.store_id for item in entries}) != len(entries):
        raise ValidationError("catalog store IDs must be unique")
    operations = _registration_operations(entries)
    checks = _checks(entries, operations)
    value = _catalog(catalog_id, entries, operations, checks)
    value.stores = ordered
    return value


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_from_directories(
    directories: Sequence[str | Path],
    *,
    catalog_id: str = "glio-noncode-review-store-catalog",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog:
    """Load exact store directories and build a path-free catalog."""

    if (
        len(directories)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES
    ):
        raise ValidationError("catalog has too many directories")
    stores = tuple(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            directory
        )
        for directory in directories
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        stores, catalog_id=catalog_id
    )


def append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    stores: Sequence[Any],
    *,
    expected_catalog_address: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog:
    """Append new stores while preserving the prior catalog journal."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ):
        raise ValidationError("catalog append requires a typed catalog")
    if expected_catalog_address is not None and expected_catalog_address != value.content_address:
        raise ValidationError("catalog expected-head guard failed")
    if (
        len(value.entries) + len(stores)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES
    ):
        raise ValidationError("catalog append exceeds the published limit")
    prior_ids = {item.store_id for item in value.entries}
    existing_stores = tuple(getattr(value, "stores", ()))
    new_entries = tuple(
        _entry_from_store(value.entry_count + ordinal, store)
        for ordinal, store in enumerate(
            sorted(stores, key=lambda item: str(getattr(item, "store_id", "")))
        )
    )
    if prior_ids.intersection(item.store_id for item in new_entries):
        raise ValidationError("catalog append contains a duplicate store ID")
    entries = value.entries + new_entries
    operations = _registration_operations(entries, prior=value.operations)
    checks = _checks(entries, operations)
    result = _catalog(value.catalog_id, entries, operations, checks)
    result.stores = existing_stores + tuple(
        sorted(stores, key=lambda item: str(getattr(item, "store_id", "")))
    )
    return result


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    *,
    stores: Sequence[Any] | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogVerification:
    """Recompute the catalog address and optionally reconcile hydrated stores."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ):
        raise ValidationError("catalog verification requires a typed catalog")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            value
        )
        != value.content_address
    ):
        raise ValidationError("catalog content address mismatch")
    checks = list(value.checks)
    hydrated = tuple(stores if stores is not None else getattr(value, "stores", ()))
    if hydrated:
        by_id = {str(getattr(store, "store_id", "")): store for store in hydrated}
        for entry in value.entries:
            store = by_id.get(entry.store_id)
            if store is None:
                checks.append(
                    _check(
                        len(checks),
                        plane="storage",
                        kind="hydrated-member",
                        passed=False,
                        expected=entry.store_id,
                        observed=None,
                        detail="a catalog member is missing from the hydrated set",
                    )
                )
                continue
            observed = getattr(store, "content_address", None)
            checks.append(
                _check(
                    len(checks),
                    plane="storage",
                    kind="hydrated-address",
                    passed=observed == entry.store_address,
                    expected=entry.store_address,
                    observed=observed,
                    detail="hydrated store address matches its catalog entry",
                )
            )
    body = {
        "catalog_id": value.catalog_id,
        "catalog_address": value.content_address,
        "checks": tuple(checks),
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": bool(checks) and all(item.passed for item in checks),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogVerification(
        **body, content_address="pending:verification"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_verification(
            provisional
        ),
    )


def _manifest(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    entries_bytes: bytes,
    operations_bytes: bytes,
) -> dict[str, Any]:
    body = value.to_dict() | {
        "manifest_version": "review-store-catalog-manifest-v1",
        "entries_file": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ENTRIES,
        "entries_byte_count": len(entries_bytes),
        "entries_byte_address": hash_bytes(
            entries_bytes,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX
            + "-entries-bytes",
        ),
        "operations_file": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_OPERATIONS,
        "operations_byte_count": len(operations_bytes),
        "operations_byte_address": hash_bytes(
            operations_bytes,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX
            + "-operations-bytes",
        ),
    }
    return body | {
        "manifest_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX
            + "-manifest",
        )
    }


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Atomically persist the exact catalog artifact set."""

    verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        value
    )
    if not verification.accepted:
        raise ValidationError("cannot persist an unverified catalog")
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("catalog destination already exists")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=parent))
    try:
        entries_bytes = canonical_bytes({"entries": [item.to_dict() for item in value.entries]})
        operations_bytes = canonical_bytes(
            {"operations": [item.to_dict() for item in value.operations]}
        )
        manifest_bytes = canonical_bytes(_manifest(value, entries_bytes, operations_bytes))
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ENTRIES
        ).write_bytes(entries_bytes)
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_OPERATIONS
        ).write_bytes(operations_bytes)
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MANIFEST
        ).write_bytes(manifest_bytes)
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("catalog destination is not a regular directory")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _read_catalog_files(
    directory: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("catalog directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MANIFEST,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ENTRIES,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_OPERATIONS,
    }
    children = tuple(directory.iterdir())
    if any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("catalog directory contains a non-regular artifact")
    if {item.name for item in children} != expected:
        raise ValidationError("catalog files do not match the published set")
    manifest_bytes = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MANIFEST
    ).read_bytes()
    entries_bytes = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ENTRIES
    ).read_bytes()
    operations_bytes = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_OPERATIONS
    ).read_bytes()
    manifest = _json_object(manifest_bytes, "catalog manifest")
    entries = _json_object(entries_bytes, "catalog entries")
    operations = _json_object(operations_bytes, "catalog operations")
    body = {key: item for key, item in manifest.items() if key != "manifest_address"}
    if manifest.get("manifest_address") != content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX
        + "-manifest",
    ):
        raise ValidationError("catalog manifest address mismatch")
    if manifest.get("entries_byte_count") != len(entries_bytes) or manifest.get(
        "entries_byte_address"
    ) != hash_bytes(
        entries_bytes,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX
        + "-entries-bytes",
    ):
        raise ValidationError("catalog entries bytes do not match manifest")
    if manifest.get("operations_byte_count") != len(operations_bytes) or manifest.get(
        "operations_byte_address"
    ) != hash_bytes(
        operations_bytes,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX
        + "-operations-bytes",
    ):
        raise ValidationError("catalog operations bytes do not match manifest")
    if set(entries) != {"entries"} or not isinstance(entries["entries"], list):
        raise ValidationError("catalog entries artifact is invalid")
    if set(operations) != {"operations"} or not isinstance(operations["operations"], list):
        raise ValidationError("catalog operations artifact is invalid")
    return manifest, entries, operations


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog:
    """Load an exact catalog and rehydrate its typed members."""

    manifest, entries_body, operations_body = _read_catalog_files(directory)
    entries = tuple(_entry_from_dict(item) for item in entries_body["entries"])
    operations = tuple(_operation_from_dict(item) for item in operations_body["operations"])
    if [item.to_dict() for item in entries] != [dict(item) for item in manifest.get("entries", [])]:
        raise ValidationError("catalog entries do not match manifest")
    if [item.to_dict() for item in operations] != [
        dict(item) for item in manifest.get("operations", [])
    ]:
        raise ValidationError("catalog operations do not match manifest")
    keys = {
        "catalog_id",
        "version",
        "boundary",
        "entry_count",
        "state",
        "release_ready",
        "accepted",
        "append_only",
        "operation_count",
        "check_count",
        "checks",
        "content_address",
    }
    body = {key: manifest[key] for key in keys if key in manifest}
    body["entries"] = entries
    body["operations"] = operations
    body["checks"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck(
            **item
        )
        for item in manifest.get("checks", ())
    )
    value = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog(
        **body
    )
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            value
        )
        != value.content_address
    ):
        raise ValidationError("catalog content address does not match manifest")
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        value
    )
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        value
    )
    fields = (
        "catalog_id",
        "entry_count",
        "state",
        "release_ready",
        "accepted",
        "append_only",
        "operation_count",
        "check_count",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    summary = value.summary()
    writer.writerow({field: summary[field] for field in fields})
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        value
    )
    lines = [
        "# Durable Review-Store Catalog",
        "",
        f"- state: `{value.state}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- stores: `{value.entry_count}`",
        f"- operations: `{value.operation_count}`",
        f"- checks: `{value.check_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Store | State | Ready | Accepted | Address |",
        "|---:|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.store_id}` | `{item.store_state}` | `{str(item.release_ready).lower()}` | `{str(item.accepted).lower()}` | `{item.store_address}` |"
        for item in value.entries
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_summary(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        value
    )
    return value.summary()


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_BOUNDARY,
        "files": [
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MANIFEST,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ENTRIES,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_OPERATIONS,
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState
        ],
        "member_fields": [
            "store_id",
            "store_address",
            "window_address",
            "ledger_address",
            "head_address",
            "entry_count",
            "operation_count",
            "store_state",
            "release_ready",
            "accepted",
            "content_address",
        ],
        "limits": {
            "entries": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
            "operations": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_OPERATIONS,
            "checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
            "limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
        },
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "operations": [
            "build",
            "append",
            "write",
            "load",
            "verify",
            "summary",
            "json",
            "csv",
            "markdown",
            "schema",
            "capabilities",
        ],
        "guarantees": [
            "deterministic ordering",
            "content-addressed entries",
            "append-only registration journal",
            "atomic replacement",
            "canonical JSON",
            "exact artifact set",
            "bounded members",
            "path-free public projection",
            "timestamp-free public projection",
            "identity-free public projection",
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState
        ],
    }
