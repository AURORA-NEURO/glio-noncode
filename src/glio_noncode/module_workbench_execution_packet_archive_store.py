"""Persist, verify, append, and replay exact packet archive stores."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
    load_module_workbench_execution_packet_archive,
)
from .module_workbench_execution_packet_archive_contracts import (
    ModuleWorkbenchExecutionPacketArchive,
)
from .module_workbench_execution_packet_archive_store_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_FORMAT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MANIFEST,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_CHECKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECT_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECTS_DIRECTORY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStore,
    ModuleWorkbenchExecutionPacketArchiveStoreCheck,
    ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane,
    ModuleWorkbenchExecutionPacketArchiveStoreEntry,
    ModuleWorkbenchExecutionPacketArchiveStoreEntryState,
    ModuleWorkbenchExecutionPacketArchiveStoreOperation,
    ModuleWorkbenchExecutionPacketArchiveStoreOperationKind,
    ModuleWorkbenchExecutionPacketArchiveStoreOperationState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplay,
    ModuleWorkbenchExecutionPacketArchiveStoreReplayState,
    ModuleWorkbenchExecutionPacketArchiveStoreState,
    ModuleWorkbenchExecutionPacketArchiveStoreVerification,
    address_module_workbench_execution_packet_archive_store,
    address_module_workbench_execution_packet_archive_store_check,
    address_module_workbench_execution_packet_archive_store_entry,
    address_module_workbench_execution_packet_archive_store_operation,
    address_module_workbench_execution_packet_archive_store_replay,
    address_module_workbench_execution_packet_archive_store_verification,
)
from .run_workspace import _has_forbidden_key
from .serialization import canonical_bytes, hash_bytes


def _archive(
    value: ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path,
) -> ModuleWorkbenchExecutionPacketArchive:
    if isinstance(value, ModuleWorkbenchExecutionPacketArchive):
        return value
    return build_module_workbench_execution_packet_archive(
        load_module_workbench_execution_packet_archive(value)
    )


def _object_key(payload: bytes) -> str:
    address = hash_bytes(
        payload,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECT_PREFIX,
    )
    return address.replace(":", "-") + ".zip"


def _safe_object_token(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("archive store object key is required")
    if (
        "/" in value
        or "\\" in value
        or ":" in value
        or value in {".", ".."}
        or not value.endswith(".zip")
    ):
        raise ValidationError("archive store object key is unsafe")
    return value


def _entry(
    ordinal: int,
    archive: ModuleWorkbenchExecutionPacketArchive,
) -> ModuleWorkbenchExecutionPacketArchiveStoreEntry:
    body = {
        "ordinal": ordinal,
        "archive_id": archive.archive_id,
        "packet_id": archive.packet_id,
        "archive_address": archive.archive_address,
        "packet_address": archive.packet_address,
        "object_key": _object_key(archive.archive_bytes),
        "byte_count": len(archive.archive_bytes),
        "state": ModuleWorkbenchExecutionPacketArchiveStoreEntryState.STORED,
        "accepted": archive.accepted,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreEntry(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreEntry(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_entry(provisional),
    )


def _operation(
    ordinal: int,
    archive: ModuleWorkbenchExecutionPacketArchive,
    entry: ModuleWorkbenchExecutionPacketArchiveStoreEntry,
    *,
    kind: ModuleWorkbenchExecutionPacketArchiveStoreOperationKind,
    previous_address: str,
    operation_id: str,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreOperation:
    body = {
        "ordinal": ordinal,
        "operation_id": operation_id,
        "kind": kind,
        "state": ModuleWorkbenchExecutionPacketArchiveStoreOperationState.ACCEPTED,
        "archive_address": archive.archive_address,
        "object_key": entry.object_key,
        "previous_address": previous_address,
        "result_address": entry.content_address,
        "accepted": archive.accepted,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreOperation(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreOperation(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_operation(
            provisional
        ),
    )


def _make_store(
    store_id: str,
    entries: Iterable[ModuleWorkbenchExecutionPacketArchiveStoreEntry],
    operations: Iterable[ModuleWorkbenchExecutionPacketArchiveStoreOperation],
    payloads: Iterable[bytes],
) -> ModuleWorkbenchExecutionPacketArchiveStore:
    entry_rows = tuple(entries)
    operation_rows = tuple(operations)
    object_rows = tuple(payloads)
    body = {
        "store_id": store_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_BOUNDARY,
        "storage_format": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_FORMAT,
        "entries": entry_rows,
        "operations": operation_rows,
        "head_address": (
            operation_rows[-1].content_address
            if operation_rows
            else MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS
        ),
        "archive_count": len(entry_rows),
        "object_count": len(object_rows),
        "operation_count": len(operation_rows),
        "total_byte_count": sum(len(item) for item in object_rows),
        "unique_packet_count": len({item.packet_address for item in entry_rows}),
        "duplicate_registration_count": sum(
            item.kind is ModuleWorkbenchExecutionPacketArchiveStoreOperationKind.DEDUPLICATE
            for item in operation_rows
        ),
        "state": ModuleWorkbenchExecutionPacketArchiveStoreState.ACCEPTED,
        "accepted": all(item.accepted for item in entry_rows),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStore(
        **body,
        content_address="pending",
        object_payloads=object_rows,
    )
    return ModuleWorkbenchExecutionPacketArchiveStore(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store(provisional),
        object_payloads=object_rows,
    )


def build_module_workbench_execution_packet_archive_store(
    values: Iterable[ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path],
    *,
    store_id: str = "glio-noncode-module-workbench-execution-archive-store",
) -> ModuleWorkbenchExecutionPacketArchiveStore:
    """Build a deterministic store and deduplicate equal archive bytes."""

    archives = tuple(_archive(value) for value in values)
    if not archives:
        raise ValidationError("archive store requires at least one archive")
    if len(archives) > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS:
        raise ValidationError("archive store input exceeds operation limit")
    ordered = tuple(sorted(archives, key=lambda item: (item.archive_address, item.archive_id)))
    unique: dict[
        str,
        tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreEntry,
            ModuleWorkbenchExecutionPacketArchive,
        ],
    ] = {}
    for archive in ordered:
        if archive.archive_address not in unique:
            unique[archive.archive_address] = (
                _entry(len(unique), archive),
                archive,
            )
    entries = tuple(item[0] for item in unique.values())
    payloads = tuple(item[1].archive_bytes for item in unique.values())
    entry_by_address = {item.archive_address: item for item in entries}
    operations: list[ModuleWorkbenchExecutionPacketArchiveStoreOperation] = []
    previous = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS
    seen_addresses: set[str] = set()
    for ordinal, archive in enumerate(ordered):
        entry = entry_by_address[archive.archive_address]
        kind = (
            ModuleWorkbenchExecutionPacketArchiveStoreOperationKind.REGISTER
            if archive.archive_address not in seen_addresses
            else ModuleWorkbenchExecutionPacketArchiveStoreOperationKind.DEDUPLICATE
        )
        seen_addresses.add(archive.archive_address)
        operation = _operation(
            ordinal,
            archive,
            entry,
            kind=kind,
            previous_address=previous,
            operation_id=f"archive-store-operation-{ordinal}",
            detail=(
                "archive object registered"
                if kind is ModuleWorkbenchExecutionPacketArchiveStoreOperationKind.REGISTER
                else "archive bytes already present; registration deduplicated"
            ),
        )
        operations.append(operation)
        previous = operation.content_address
    return _make_store(store_id, entries, operations, payloads)


def _check(
    check_id: str,
    plane: ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreCheck(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_check(provisional),
    )


def _verification(
    store: ModuleWorkbenchExecutionPacketArchiveStore,
    checks: Iterable[ModuleWorkbenchExecutionPacketArchiveStoreCheck],
) -> ModuleWorkbenchExecutionPacketArchiveStoreVerification:
    rows = tuple(checks)
    body = {
        "store_id": store.store_id,
        "store_address": store.content_address,
        "head_address": store.head_address,
        "entry_count": store.archive_count,
        "object_count": store.object_count,
        "operation_count": store.operation_count,
        "check_count": len(rows),
        "passed_count": sum(item.passed for item in rows),
        "failed_count": sum(not item.passed for item in rows),
        "checks": rows,
        "accepted": bool(rows) and all(item.passed for item in rows),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreVerification(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_verification(
            provisional
        ),
    )


def _store_from_mapping(
    mapping: Mapping[str, Any],
    object_payloads: tuple[bytes, ...],
) -> ModuleWorkbenchExecutionPacketArchiveStore:
    """Hydrate a typed store from a canonical manifest and object bytes."""

    entries = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreEntry(
            ordinal=int(item["ordinal"]),
            archive_id=str(item["archive_id"]),
            packet_id=str(item["packet_id"]),
            archive_address=str(item["archive_address"]),
            packet_address=str(item["packet_address"]),
            object_key=str(item["object_key"]),
            byte_count=int(item["byte_count"]),
            state=ModuleWorkbenchExecutionPacketArchiveStoreEntryState(item["state"]),
            accepted=bool(item["accepted"]),
            content_address=str(item["content_address"]),
        )
        for item in mapping.get("entries", ())
    )
    operations = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreOperation(
            ordinal=int(item["ordinal"]),
            operation_id=str(item["operation_id"]),
            kind=ModuleWorkbenchExecutionPacketArchiveStoreOperationKind(item["kind"]),
            state=ModuleWorkbenchExecutionPacketArchiveStoreOperationState(item["state"]),
            archive_address=str(item["archive_address"]),
            object_key=str(item["object_key"]),
            previous_address=str(item["previous_address"]),
            result_address=str(item["result_address"]),
            accepted=bool(item["accepted"]),
            detail=str(item["detail"]),
            content_address=str(item["content_address"]),
        )
        for item in mapping.get("operations", ())
    )
    return ModuleWorkbenchExecutionPacketArchiveStore(
        store_id=str(mapping["store_id"]),
        version=str(mapping["version"]),
        boundary=str(mapping["boundary"]),
        storage_format=str(mapping["storage_format"]),
        entries=entries,
        operations=operations,
        head_address=str(mapping["head_address"]),
        archive_count=int(mapping["archive_count"]),
        object_count=int(mapping["object_count"]),
        operation_count=int(mapping["operation_count"]),
        total_byte_count=int(mapping["total_byte_count"]),
        unique_packet_count=int(mapping["unique_packet_count"]),
        duplicate_registration_count=int(mapping["duplicate_registration_count"]),
        state=ModuleWorkbenchExecutionPacketArchiveStoreState(mapping["state"]),
        accepted=bool(mapping["accepted"]),
        content_address=str(mapping["content_address"]),
        object_payloads=object_payloads,
    )


def _read_store(path: str | Path) -> ModuleWorkbenchExecutionPacketArchiveStore:
    root = Path(path)
    if not root.is_dir():
        raise ValidationError("archive store destination is not a directory")
    manifest_path = root / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MANIFEST
    if not manifest_path.is_file():
        raise ValidationError("archive store manifest is missing")
    raw = manifest_path.read_bytes()
    try:
        mapping = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("archive store manifest is not valid UTF-8 JSON") from exc
    if not isinstance(mapping, Mapping):
        raise ValidationError("archive store manifest must be a JSON object")
    if canonical_bytes(mapping) != raw:
        raise ValidationError("archive store manifest is not canonical")
    entry_mappings = tuple(mapping.get("entries", ()))
    objects_root = root / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECTS_DIRECTORY
    if not objects_root.is_dir() or objects_root.is_symlink():
        raise ValidationError("archive store objects directory is missing or unsafe")
    object_keys = tuple(_safe_object_token(item["object_key"]) for item in entry_mappings)
    actual_names = tuple(sorted(item.name for item in objects_root.iterdir()))
    if actual_names != tuple(sorted(object_keys)):
        raise ValidationError("archive store object set does not match the manifest")
    payloads = []
    for object_key in object_keys:
        object_path = objects_root / object_key
        if object_path.is_symlink() or not object_path.is_file():
            raise ValidationError("archive store object is not a regular file")
        payloads.append(object_path.read_bytes())
    return _store_from_mapping(mapping, tuple(payloads))


def verify_module_workbench_execution_packet_archive_store(
    value: ModuleWorkbenchExecutionPacketArchiveStore | str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreVerification:
    """Return a multi-plane, fail-closed verification receipt."""

    try:
        store = (
            value
            if isinstance(value, ModuleWorkbenchExecutionPacketArchiveStore)
            else _read_store(value)
        )
    except (OSError, TypeError, KeyError, ValueError, AttributeError, ValidationError) as exc:
        return _verification_fallback(str(exc))
    checks: list[ModuleWorkbenchExecutionPacketArchiveStoreCheck] = []
    checks.append(
        _check(
            "store-format",
            ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane.MANIFEST,
            store.version == MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERSION
            and store.boundary == MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_BOUNDARY
            and store.storage_format == MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_FORMAT,
            {
                "version": store.version,
                "boundary": store.boundary,
                "storage_format": store.storage_format,
            },
            {
                "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERSION,
                "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_BOUNDARY,
                "storage_format": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_FORMAT,
            },
            "store format fields match the published contract",
        )
    )
    checks.append(
        _check(
            "store-entry-addresses",
            ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane.ADDRESS,
            all(
                address_module_workbench_execution_packet_archive_store_entry(item)
                == item.content_address
                for item in store.entries
            ),
            tuple(item.content_address for item in store.entries),
            "recomputed entry addresses",
            "every store entry address is reproducible",
        )
    )
    checks.append(
        _check(
            "store-operation-addresses",
            ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane.ADDRESS,
            all(
                address_module_workbench_execution_packet_archive_store_operation(item)
                == item.content_address
                for item in store.operations
            ),
            tuple(item.content_address for item in store.operations),
            "recomputed operation addresses",
            "every journal operation address is reproducible",
        )
    )
    previous = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS
    chain_passed = True
    for operation in store.operations:
        chain_passed = chain_passed and operation.previous_address == previous
        previous = operation.content_address
    chain_passed = chain_passed and store.head_address == previous
    checks.append(
        _check(
            "store-journal-chain",
            ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane.INDEX,
            chain_passed,
            store.head_address,
            previous,
            "operation predecessor links and head address are contiguous",
        )
    )
    object_passed = all(
        hash_bytes(payload, prefix="module-workbench-execution-packet-archive")
        == entry.archive_address
        and _object_key(payload) == entry.object_key
        and len(payload) == entry.byte_count
        for entry, payload in zip(store.entries, store.object_payloads, strict=True)
    )
    checks.append(
        _check(
            "store-object-integrity",
            ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane.OBJECT,
            object_passed,
            store.total_byte_count,
            sum(item.byte_count for item in store.entries),
            "stored object bytes match archive addresses, keys, and counts",
        )
    )
    checks.append(
        _check(
            "store-manifest-address",
            ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane.MANIFEST,
            address_module_workbench_execution_packet_archive_store(store) == store.content_address,
            store.content_address,
            "recomputed store manifest address",
            "store content address is reproducible",
        )
    )
    public_body = store.to_dict()
    checks.append(
        _check(
            "store-public-boundary",
            ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane.PUBLIC,
            not _has_forbidden_key(public_body),
            "forbidden-key scan",
            "no private or attribution keys",
            "store projections remain identity-free",
        )
    )
    checks.append(
        _check(
            "store-count-conservation",
            ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane.INDEX,
            store.archive_count == store.object_count == len(store.entries)
            and store.operation_count == len(store.operations),
            {
                "archive_count": store.archive_count,
                "object_count": store.object_count,
                "operation_count": store.operation_count,
            },
            "entry/object/operation counts conserve",
            "store counts are conserved",
        )
    )
    checks.append(
        _check(
            "store-storage-policy",
            ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane.STORAGE,
            all(_object_key(payload).endswith(".zip") for payload in store.object_payloads),
            tuple(item.object_key for item in store.entries),
            "safe object tokens",
            "object names are deterministic safe tokens",
        )
    )
    checks = checks[:MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_CHECKS]
    return _verification(store, checks)


def _verification_fallback(detail: str) -> ModuleWorkbenchExecutionPacketArchiveStoreVerification:
    class _Fallback:
        store_id = "unavailable"
        content_address = "unavailable"
        head_address = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS
        archive_count = 0
        object_count = 0
        operation_count = 0

    store = _Fallback()
    check = _check(
        "store-invalid-input",
        ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane.STORAGE,
        False,
        detail,
        "readable canonical store",
        "store input could not be loaded",
    )
    body = {
        "store_id": store.store_id,
        "store_address": store.content_address,
        "head_address": store.head_address,
        "entry_count": store.archive_count,
        "object_count": store.object_count,
        "operation_count": store.operation_count,
        "check_count": 1,
        "passed_count": 0,
        "failed_count": 1,
        "checks": (check,),
        "accepted": False,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreVerification(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_verification(
            provisional
        ),
    )


def load_module_workbench_execution_packet_archive_store(
    path: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStore:
    """Load a store only after its manifest and objects verify."""

    store = _read_store(path)
    verification = verify_module_workbench_execution_packet_archive_store(store)
    if not verification.accepted:
        raise ValidationError("archive store verification is blocked")
    return store


def write_module_workbench_execution_packet_archive_store(
    value: ModuleWorkbenchExecutionPacketArchiveStore,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write manifest and objects through an atomic directory replacement."""

    verification = verify_module_workbench_execution_packet_archive_store(value)
    if not verification.accepted:
        raise ValidationError("cannot write a blocked archive store")
    target = Path(destination)
    if target.exists() and not allow_existing:
        raise ValidationError("archive store destination already exists")
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".archive-store-", dir=parent))
    try:
        objects_root = temporary / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECTS_DIRECTORY
        objects_root.mkdir()
        for entry, payload in zip(value.entries, value.object_payloads, strict=True):
            (objects_root / entry.object_key).write_bytes(payload)
        manifest = canonical_bytes(value.to_dict())
        manifest_path = temporary / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MANIFEST
        with manifest_path.open("wb") as handle:
            handle.write(manifest)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return target


def append_module_workbench_execution_packet_archive_store(
    value: ModuleWorkbenchExecutionPacketArchiveStore,
    archive: ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path,
    *,
    operation_id: str | None = None,
    expected_head_address: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStore:
    """Return a new store with one idempotent registration operation."""

    verification = verify_module_workbench_execution_packet_archive_store(value)
    if not verification.accepted:
        raise ValidationError("cannot append to a blocked archive store")
    if expected_head_address is not None and expected_head_address != value.head_address:
        raise ValidationError("archive store head is stale")
    candidate = _archive(archive)
    requested_id = operation_id or f"archive-store-operation-{value.operation_count}"
    existing_operation = next(
        (item for item in value.operations if item.operation_id == requested_id),
        None,
    )
    if existing_operation is not None:
        if existing_operation.archive_address != candidate.archive_address:
            raise ValidationError("operation ID already names a different archive")
        return value
    entries = list(value.entries)
    payloads = list(value.object_payloads)
    existing_entry = next(
        (item for item in entries if item.archive_address == candidate.archive_address),
        None,
    )
    if existing_entry is None:
        existing_entry = _entry(len(entries), candidate)
        entries.append(existing_entry)
        payloads.append(candidate.archive_bytes)
        kind = ModuleWorkbenchExecutionPacketArchiveStoreOperationKind.REGISTER
        detail = "archive object registered"
    else:
        kind = ModuleWorkbenchExecutionPacketArchiveStoreOperationKind.DEDUPLICATE
        detail = "archive bytes already present; registration deduplicated"
    operation = _operation(
        value.operation_count,
        candidate,
        existing_entry,
        kind=kind,
        previous_address=value.head_address,
        operation_id=requested_id,
        detail=detail,
    )
    return _make_store(value.store_id, entries, (*value.operations, operation), payloads)


def append_module_workbench_execution_packet_archive_store_batch(
    value: ModuleWorkbenchExecutionPacketArchiveStore,
    archives: Iterable[ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path],
    *,
    expected_head_address: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStore:
    """Append a batch in caller order with one final immutable result."""

    result = value
    for archive in archives:
        result = append_module_workbench_execution_packet_archive_store(
            result,
            archive,
            expected_head_address=expected_head_address if result is value else None,
        )
    return result


def replay_module_workbench_execution_packet_archive_store(
    value: ModuleWorkbenchExecutionPacketArchiveStore,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplay:
    """Reload every stored archive object and replay its address chain."""

    verification = verify_module_workbench_execution_packet_archive_store(value)
    matched = verification.accepted
    detail = "all stored archive objects replayed and matched their manifest records"
    if matched:
        for entry, payload in zip(value.entries, value.object_payloads, strict=True):
            try:
                packet = load_module_workbench_execution_packet_archive(payload)
                archive = build_module_workbench_execution_packet_archive(
                    packet,
                    archive_id=entry.archive_id,
                )
                matched = matched and archive.archive_address == entry.archive_address
                matched = matched and archive.packet_address == entry.packet_address
            except (OSError, TypeError, ValueError, ValidationError):
                matched = False
                break
    state = (
        ModuleWorkbenchExecutionPacketArchiveStoreReplayState.MATCHED
        if matched
        else ModuleWorkbenchExecutionPacketArchiveStoreReplayState.MISMATCHED
    )
    body = {
        "store_id": value.store_id,
        "store_address": value.content_address,
        "replayed_store_address": value.content_address if matched else "unavailable",
        "entry_count": value.archive_count,
        "operation_count": value.operation_count,
        "state": state,
        "accepted": matched,
        "detail": detail if matched else "one or more stored archive objects failed replay",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplay(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplay(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replay(provisional),
    )


__all__ = [
    "append_module_workbench_execution_packet_archive_store",
    "append_module_workbench_execution_packet_archive_store_batch",
    "build_module_workbench_execution_packet_archive_store",
    "load_module_workbench_execution_packet_archive_store",
    "replay_module_workbench_execution_packet_archive_store",
    "verify_module_workbench_execution_packet_archive_store",
    "write_module_workbench_execution_packet_archive_store",
]
