"""Read-only integrity and reachability audit for the local run store.

Individual run inspection proves that one run can be reopened.  A local data
root also needs a store-wide answer: are every JSON object and index canonical,
do every persisted pointer resolve, and are there objects that no run or batch
can reach?  This module answers those questions without repairing or deleting
anything.  It reports malformed files, non-canonical bytes, address drift,
missing references, orphan objects, and replay failures as explicit public
metadata.

The audit understands the core run and batch roots and follows only typed
object-reference fields.  Embedded content addresses used for lineage are not
mistaken for object-store pointers.  Object payloads are never returned, so an
audit remains safe for research-use operational handoff.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .batch_runtime import BatchRuntime
from .errors import GlioError, StoreError
from .module_fabric_support import contains_private_key
from .run_catalog import inspect_run
from .run_workspace import _has_forbidden_key
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash

STORAGE_AUDIT_VERSION = "storage-audit-v1"

_SHA256_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_OBJECT_REFERENCE_KEYS = frozenset(
    {
        "input_address",
        "input_addresses",
        "event_address",
        "event_history",
        "dossier_address",
        "dossier_addresses",
        "dossier_history",
        "source_bundle_addresses",
        "result_address",
        "result_addresses",
        "item_input_address",
        "item_input_addresses",
    }
)


def _valid_address(value: Any) -> bool:
    return bool(_SHA256_ADDRESS.fullmatch(str(value)))


def _unique(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _reference_values(value: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return valid object references and malformed sha references."""

    valid: list[str] = []
    malformed: list[str] = []

    def collect(item: Any) -> None:
        if isinstance(item, str):
            if _valid_address(item):
                valid.append(item)
            elif item.startswith("sha256:"):
                malformed.append(item)
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                collect(child)
            return
        if isinstance(item, dict):
            for child in item.values():
                collect(child)

    collect(value)
    return _unique(valid), _unique(malformed)


def _object_references(value: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    valid: list[str] = []
    malformed: list[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = str(key)
                if key_text in _OBJECT_REFERENCE_KEYS:
                    references, invalid = _reference_values(child)
                    valid.extend(references)
                    malformed.extend(invalid)
                elif key_text != "content_address":
                    walk(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child)

    walk(value)
    return _unique(valid), _unique(malformed)


def _canonical_hash_valid(value: Any, address: str) -> bool:
    if content_hash(value) == address:
        return True
    if isinstance(value, dict) and "content_address" in value:
        without_self = {key: item for key, item in value.items() if key != "content_address"}
        return content_hash(without_self) == address
    return False


@dataclass(frozen=True, slots=True)
class StorageObjectAudit:
    """Address, byte, and reachability observations for one object file."""

    address: str
    filename: str
    byte_count: int
    json_valid: bool
    canonical_bytes_valid: bool
    hash_valid: bool
    referenced: bool
    reference_count: int
    warnings: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "filename": self.filename,
            "byte_count": self.byte_count,
            "json_valid": self.json_valid,
            "canonical_bytes_valid": self.canonical_bytes_valid,
            "hash_valid": self.hash_valid,
            "referenced": self.referenced,
            "reference_count": self.reference_count,
            "warnings": list(self.warnings),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class StorageRunAudit:
    """Structural and replay observations for one run index file."""

    run_id: str
    filename: str
    pointer_addresses: tuple[str, ...]
    history_count: int
    event_history_count: int
    replay_accepted: bool
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "filename": self.filename,
            "pointer_addresses": list(self.pointer_addresses),
            "history_count": self.history_count,
            "event_history_count": self.event_history_count,
            "replay_accepted": self.replay_accepted,
            "accepted": self.accepted,
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class StorageBatchAudit:
    """Structural and reopen observations for one batch index file."""

    batch_id: str
    filename: str
    input_address: str | None
    result_address: str | None
    result_accepted: bool
    reopened: bool
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "filename": self.filename,
            "input_address": self.input_address,
            "result_address": self.result_address,
            "result_accepted": self.result_accepted,
            "reopened": self.reopened,
            "accepted": self.accepted,
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class StorageAuditReport:
    """Complete public audit of one local data root."""

    root: str
    object_count: int
    valid_object_count: int
    run_count: int
    batch_count: int
    referenced_object_count: int
    orphan_object_count: int
    missing_reference_count: int
    unexpected_entries: tuple[str, ...]
    objects: tuple[StorageObjectAudit, ...]
    runs: tuple[StorageRunAudit, ...]
    batches: tuple[StorageBatchAudit, ...]
    referenced_addresses: tuple[str, ...]
    orphan_addresses: tuple[str, ...]
    missing_addresses: tuple[str, ...]
    warnings: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "storage_audit_version": STORAGE_AUDIT_VERSION,
            "root": self.root,
            "object_count": self.object_count,
            "valid_object_count": self.valid_object_count,
            "run_count": self.run_count,
            "batch_count": self.batch_count,
            "referenced_object_count": self.referenced_object_count,
            "orphan_object_count": self.orphan_object_count,
            "missing_reference_count": self.missing_reference_count,
            "unexpected_entries": list(self.unexpected_entries),
            "objects": [item.to_dict() for item in self.objects],
            "runs": [item.to_dict() for item in self.runs],
            "batches": [item.to_dict() for item in self.batches],
            "referenced_addresses": list(self.referenced_addresses),
            "orphan_addresses": list(self.orphan_addresses),
            "missing_addresses": list(self.missing_addresses),
            "warnings": list(self.warnings),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _addressed(body: dict[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _object_audit(path: Path, address: str) -> tuple[StorageObjectAudit, Any | None]:
    warnings: list[str] = []
    try:
        payload = path.read_bytes()
    except OSError as exc:
        body = {
            "address": address,
            "filename": path.name,
            "byte_count": 0,
            "json_valid": False,
            "canonical_bytes_valid": False,
            "hash_valid": False,
            "referenced": False,
            "reference_count": 0,
            "warnings": (f"object read failed: {exc}",),
            "accepted": False,
        }
        return StorageObjectAudit(**body, content_address=_addressed(body, "storage-object-audit")), None
    byte_count = len(payload)
    value: Any | None = None
    json_valid = False
    canonical_valid = False
    hash_valid = False
    try:
        value = json.loads(payload.decode("utf-8"))
        json_valid = True
        canonical_valid = canonical_json(value).encode("utf-8") == payload
        hash_valid = _canonical_hash_valid(value, address)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        warnings.append(f"object JSON is invalid: {exc}")
    if json_valid and not canonical_valid:
        warnings.append("object bytes are not canonical UTF-8 JSON")
    if json_valid and not hash_valid:
        warnings.append("object content does not match its filename address")
    if json_valid and isinstance(value, dict):
        _, malformed = _object_references(value)
        warnings.extend(f"malformed object reference: {item}" for item in malformed)
    accepted = json_valid and canonical_valid and hash_valid and not warnings
    body = {
        "address": address,
        "filename": path.name,
        "byte_count": byte_count,
        "json_valid": json_valid,
        "canonical_bytes_valid": canonical_valid,
        "hash_valid": hash_valid,
        "referenced": False,
        "reference_count": 0,
        "warnings": tuple(dict.fromkeys(warnings)),
        "accepted": accepted,
    }
    return StorageObjectAudit(**body, content_address=_addressed(body, "storage-object-audit")), value


def _scan_objects(root: Path) -> tuple[tuple[StorageObjectAudit, ...], dict[str, Any], tuple[str, ...]]:
    objects_root = root / "objects"
    if not objects_root.is_dir():
        return (), {}, ()
    audits: list[StorageObjectAudit] = []
    parsed: dict[str, Any] = {}
    unexpected: list[str] = []
    for entry in sorted(objects_root.iterdir(), key=lambda item: item.name):
        relative = f"objects/{entry.name}"
        if entry.is_symlink() or not entry.is_file() or entry.suffix != ".json":
            unexpected.append(relative)
            continue
        stem = entry.stem
        if len(stem) != 64 or any(char not in "0123456789abcdef" for char in stem):
            unexpected.append(relative)
            continue
        address = f"sha256:{stem}"
        audit, value = _object_audit(entry, address)
        audits.append(audit)
        if value is not None:
            parsed[address] = value
    return tuple(audits), parsed, tuple(unexpected)


def _read_index(path: Path) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    warnings: list[str] = []
    try:
        payload = path.read_bytes()
        value = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        return None, (f"index JSON is invalid: {exc}",)
    if not isinstance(value, dict):
        return None, ("index root must be an object",)
    if canonical_json(value).encode("utf-8") != payload:
        warnings.append("index bytes are not canonical UTF-8 JSON")
    return value, tuple(warnings)


def _index_pointer(value: Any, field: str, warnings: list[str]) -> str | None:
    address = str(value or "")
    if not _valid_address(address):
        warnings.append(f"{field} is not a valid sha256 object address")
        return None
    return address


def _scan_runs(runtime: CaseRuntime) -> tuple[tuple[StorageRunAudit, ...], tuple[str, ...]]:
    root = Path(runtime.store.root) / "runs"
    if not root.is_dir():
        return (), ()
    audits: list[StorageRunAudit] = []
    unexpected: list[str] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_symlink() or not path.is_file() or path.suffix != ".json" or not path.name.startswith("run-"):
            unexpected.append(f"runs/{path.name}")
            continue
        raw, index_warnings = _read_index(path)
        warnings = list(index_warnings)
        run_id = str(raw.get("run_id", "")) if raw else f"run-{path.stem}"
        if raw is not None and run_id != path.stem:
            warnings.append("run index filename does not match run_id")
        pointers: list[str] = []
        if raw is not None:
            for field in ("input_address", "event_address", "dossier_address"):
                pointer = _index_pointer(raw.get(field), field, warnings)
                if pointer is not None:
                    pointers.append(pointer)
            history = raw.get("dossier_history")
            if not isinstance(history, list):
                warnings.append("dossier_history must be an array")
                history_values: list[Any] = []
            else:
                history_values = history
            for index, item in enumerate(history_values):
                pointer = _index_pointer(item, f"dossier_history[{index}]", warnings)
                if pointer is not None:
                    pointers.append(pointer)
            event_history = raw.get("event_history")
            if event_history is not None and not isinstance(event_history, list):
                warnings.append("event_history must be an array")
                event_history_values: list[Any] = []
            elif isinstance(event_history, list):
                event_history_values = event_history
            else:
                event_history_values = []
            for index, item in enumerate(event_history_values):
                pointer = _index_pointer(item, f"event_history[{index}]", warnings)
                if pointer is not None:
                    pointers.append(pointer)
            current = str(raw.get("dossier_address", ""))
            if current and current not in history_values:
                warnings.append("current dossier address is absent from dossier_history")
        replay_accepted = False
        if raw is not None and run_id:
            try:
                replay_accepted = inspect_run(runtime, run_id).accepted
            except (AttributeError, KeyError, StoreError, TypeError, ValueError) as exc:
                warnings.append(f"run replay inspection failed: {exc}")
        body = {
            "run_id": run_id,
            "filename": path.name,
            "pointer_addresses": tuple(dict.fromkeys(pointers)),
            "history_count": len(raw.get("dossier_history", ())) if raw and isinstance(raw.get("dossier_history"), list) else 0,
            "event_history_count": len(raw.get("event_history", ())) if raw and isinstance(raw.get("event_history"), list) else 0,
            "replay_accepted": replay_accepted,
            "accepted": raw is not None and not warnings and replay_accepted,
            "warnings": tuple(dict.fromkeys(warnings)),
        }
        audits.append(StorageRunAudit(**body, content_address=_addressed(body, "storage-run-audit")))
    return tuple(audits), tuple(unexpected)


def _scan_batches(runtime: CaseRuntime) -> tuple[tuple[StorageBatchAudit, ...], tuple[str, ...]]:
    root = Path(runtime.store.root) / "batches"
    if not root.is_dir():
        return (), ()
    audits: list[StorageBatchAudit] = []
    unexpected: list[str] = []
    batch_runtime = BatchRuntime(runtime=runtime)
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_symlink() or not path.is_file() or path.suffix != ".json" or len(path.stem) != 64:
            unexpected.append(f"batches/{path.name}")
            continue
        batch_id = f"batch-{path.stem}"
        raw, index_warnings = _read_index(path)
        warnings = list(index_warnings)
        if raw is not None and str(raw.get("batch_id", "")) != batch_id:
            warnings.append("batch index filename does not match batch_id")
        input_address = None
        result_address = None
        if raw is not None:
            input_address = _index_pointer(raw.get("input_address"), "input_address", warnings)
            result_address = _index_pointer(raw.get("result_address"), "result_address", warnings)
        reopened = False
        result_accepted = False
        try:
            result = batch_runtime.get(batch_id)
            reopened = True
            result_accepted = result.accepted
        except (GlioError, OSError, TypeError, ValueError, KeyError) as exc:
            warnings.append(f"batch reopen failed: {exc}")
        body = {
            "batch_id": batch_id,
            "filename": path.name,
            "input_address": input_address,
            "result_address": result_address,
            "result_accepted": result_accepted,
            "reopened": reopened,
            "accepted": raw is not None and not warnings and reopened,
            "warnings": tuple(dict.fromkeys(warnings)),
        }
        audits.append(StorageBatchAudit(**body, content_address=_addressed(body, "storage-batch-audit")))
    return tuple(audits), tuple(unexpected)


def _reachable(
    parsed: dict[str, Any],
    roots: tuple[str, ...],
) -> tuple[tuple[str, ...], dict[str, int], tuple[str, ...]]:
    queue: list[str] = []
    counts: dict[str, int] = {}
    missing: list[str] = []
    for root in roots:
        counts[root] = counts.get(root, 0) + 1
        if root in parsed:
            queue.append(root)
        elif root not in missing:
            missing.append(root)
    visited: set[str] = set()
    while queue:
        address = queue.pop(0)
        if address in visited:
            continue
        visited.add(address)
        references, _ = _object_references(parsed[address])
        for reference in references:
            counts[reference] = counts.get(reference, 0) + 1
            if reference in parsed:
                if reference not in visited:
                    queue.append(reference)
            elif reference not in missing:
                missing.append(reference)
    return tuple(sorted(visited)), counts, tuple(sorted(missing))


def build_storage_audit(runtime: CaseRuntime) -> StorageAuditReport:
    """Audit every core store object, run index, and batch index read-only."""

    root = Path(runtime.store.root)
    object_audits, parsed, object_unexpected = _scan_objects(root)
    run_audits, run_unexpected = _scan_runs(runtime)
    batch_audits, batch_unexpected = _scan_batches(runtime)
    roots = tuple(
        address
        for item in run_audits
        for address in item.pointer_addresses
    ) + tuple(
        address
        for item in batch_audits
        for address in (item.input_address, item.result_address)
        if address is not None
    )
    referenced, counts, missing = _reachable(parsed, roots)
    object_addresses = tuple(item.address for item in object_audits)
    orphan = tuple(sorted(set(object_addresses) - set(referenced)))
    updated_objects = tuple(
        replace(
            item,
            referenced=item.address in referenced,
            reference_count=counts.get(item.address, 0),
            accepted=item.accepted,
            content_address="",
        )
        for item in object_audits
    )
    updated_objects = tuple(
        replace(
            item,
            content_address=_addressed(
                {key: value for key, value in item.to_dict().items() if key != "content_address"},
                "storage-object-audit",
            ),
        )
        for item in updated_objects
    )
    unexpected = tuple(sorted((*object_unexpected, *run_unexpected, *batch_unexpected)))
    warnings: list[str] = []
    if unexpected:
        warnings.append(f"store contains {len(unexpected)} unexpected filesystem entries")
    if missing:
        warnings.append(f"store contains {len(missing)} missing object references")
    if orphan:
        warnings.append(f"store contains {len(orphan)} orphan objects")
    invalid_objects = sum(not item.accepted for item in updated_objects)
    if invalid_objects:
        warnings.append(f"store contains {invalid_objects} invalid object files")
    if any(not item.accepted for item in run_audits):
        warnings.append("one or more run indexes failed structural or replay checks")
    if any(not item.accepted for item in batch_audits):
        warnings.append("one or more batch indexes failed structural or reopen checks")
    public_body = {
        "storage_audit_version": STORAGE_AUDIT_VERSION,
        "root": str(root),
        "objects": [item.to_dict() for item in updated_objects],
        "runs": [item.to_dict() for item in run_audits],
        "batches": [item.to_dict() for item in batch_audits],
        "unexpected_entries": unexpected,
        "referenced_addresses": referenced,
        "orphan_addresses": orphan,
        "missing_addresses": missing,
        "warnings": tuple(warnings),
    }
    accepted = (
        not unexpected
        and not missing
        and not orphan
        and all(item.accepted for item in updated_objects)
        and all(item.accepted for item in run_audits)
        and all(item.accepted for item in batch_audits)
        and not _has_forbidden_key(public_body)
        and not contains_private_key(public_body)
    )
    body = {
        "root": str(root),
        "object_count": len(updated_objects),
        "valid_object_count": sum(item.accepted for item in updated_objects),
        "run_count": len(run_audits),
        "batch_count": len(batch_audits),
        "referenced_object_count": len(referenced),
        "orphan_object_count": len(orphan),
        "missing_reference_count": len(missing),
        "unexpected_entries": unexpected,
        "objects": updated_objects,
        "runs": run_audits,
        "batches": batch_audits,
        "referenced_addresses": referenced,
        "orphan_addresses": orphan,
        "missing_addresses": missing,
        "warnings": tuple(warnings),
        "accepted": accepted,
    }
    return StorageAuditReport(
        **body,
        content_address=content_hash(body, prefix="storage-audit"),
    )


__all__ = [
    "STORAGE_AUDIT_VERSION",
    "StorageAuditReport",
    "StorageBatchAudit",
    "StorageObjectAudit",
    "StorageRunAudit",
    "build_storage_audit",
]
