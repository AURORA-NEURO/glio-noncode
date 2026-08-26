"""Deterministic query, export, and verification operations for storage catalogs.

The catalog is a read model over :mod:`storage_audit`.  It gives callers one
stable collection for objects, missing references, run indexes, batch indexes,
and unexpected filesystem entries.  Every row is address-only: object bytes,
arbitrary index JSON, and operational metadata stay behind the audit boundary.

The implementation deliberately keeps construction and querying separate.  A
catalog is built once from an audit, then exact or bounded queries can be
replayed from the serialized catalog without touching the filesystem.  This is
useful for offline review, release evidence, and clients that need stable
pagination rather than a fresh directory scan for every request.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_support import text_matches
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash
from .storage_audit import StorageAuditReport, build_storage_audit
from .storage_catalog_contracts import (
    STORAGE_CATALOG_BOUNDARY,
    STORAGE_CATALOG_DEFAULT_LIMIT,
    STORAGE_CATALOG_INDEXES,
    STORAGE_CATALOG_MAX_ENTRIES,
    STORAGE_CATALOG_MAX_INDEX_ROWS,
    STORAGE_CATALOG_MAX_LIMIT,
    STORAGE_CATALOG_RESOURCES,
    STORAGE_CATALOG_SCHEMA_VERSION,
    STORAGE_CATALOG_STATES,
    STORAGE_CATALOG_VERSION,
    StorageCatalog,
    StorageCatalogDiff,
    StorageCatalogEntry,
    StorageCatalogEntryKind,
    StorageCatalogIndexRow,
    StorageCatalogQueryResult,
    StorageCatalogState,
)


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _optional_text(value: Any, field: str, *, maximum: int = 500) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum=maximum)


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValidationError(f"{field} must be {bound}")
    return result


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _as_report(value: StorageAuditReport | CaseRuntime) -> StorageAuditReport:
    if isinstance(value, StorageAuditReport):
        return value
    if isinstance(value, CaseRuntime):
        return build_storage_audit(value)
    raise ValidationError("storage catalog requires a storage audit or case runtime")


def _as_catalog(value: StorageCatalog | Mapping[str, Any]) -> StorageCatalog:
    if isinstance(value, StorageCatalog):
        return value
    return StorageCatalog.from_mapping(value)


def _entry(
    *,
    entry_id: str,
    kind: StorageCatalogEntryKind,
    state: StorageCatalogState,
    resource_key: str,
    path: str | None,
    target_address: str | None,
    audit_address: str,
    byte_count: int,
    warning_count: int,
    referenced: bool,
    accepted: bool,
) -> StorageCatalogEntry:
    body = {
        "entry_id": entry_id,
        "kind": kind.value,
        "state": state.value,
        "resource_key": resource_key,
        "path": path,
        "target_address": target_address,
        "audit_address": audit_address,
        "byte_count": byte_count,
        "warning_count": warning_count,
        "referenced": referenced,
        "accepted": accepted,
    }
    return StorageCatalogEntry(
        entry_id=entry_id,
        kind=kind,
        state=state,
        resource_key=resource_key,
        path=path,
        target_address=target_address,
        audit_address=audit_address,
        byte_count=byte_count,
        warning_count=warning_count,
        referenced=referenced,
        accepted=accepted,
        content_address=content_hash(body, prefix="storage-catalog-entry"),
    )


def _entry_state(*, accepted: bool, orphan: bool = False) -> StorageCatalogState:
    if orphan:
        return StorageCatalogState.ORPHAN
    if accepted:
        return StorageCatalogState.ACCEPTED
    return StorageCatalogState.REJECTED


def _object_path(filename: str) -> str:
    return f"objects/{_text(filename, 'object filename', maximum=300)}"


def _run_path(filename: str) -> str:
    return f"runs/{_text(filename, 'run filename', maximum=300)}"


def _batch_path(filename: str) -> str:
    return f"batches/{_text(filename, 'batch filename', maximum=300)}"


def _missing_path(address: str) -> str | None:
    if address.startswith("sha256:") and len(address) == 71:
        return f"objects/{address.split(':', 1)[1]}.json"
    return None


def _build_index(
    entries: tuple[StorageCatalogEntry, ...],
    selector: str,
) -> tuple[StorageCatalogIndexRow, ...]:
    values: dict[str, list[str]] = defaultdict(list)
    for item in entries:
        if selector == "address":
            key = item.target_address
        elif selector == "path":
            key = item.path
        elif selector == "kind":
            key = item.kind.value
        elif selector == "state":
            key = item.state.value
        else:
            raise ValidationError(f"unsupported storage catalog index: {selector}")
        if key is not None:
            values[key].append(item.entry_id)
    rows: list[StorageCatalogIndexRow] = []
    for key in sorted(values):
        entry_ids = tuple(sorted(set(values[key])))
        body = {"key": key, "entry_ids": entry_ids}
        rows.append(
            StorageCatalogIndexRow(
                key=key,
                entry_ids=entry_ids,
                content_address=content_hash(body, prefix="storage-catalog-index-row"),
            )
        )
    return tuple(rows)


def build_storage_catalog(
    source: StorageAuditReport | CaseRuntime,
) -> StorageCatalog:
    """Build a closed, sorted catalog from one storage audit."""

    report = _as_report(source)
    audit_address = report.content_address
    orphan_addresses = set(report.orphan_addresses)
    entries: list[StorageCatalogEntry] = []
    for item in report.objects:
        orphan = item.address in orphan_addresses
        accepted = item.accepted and not orphan
        entries.append(
            _entry(
                entry_id=f"object:{item.address}",
                kind=StorageCatalogEntryKind.OBJECT,
                state=_entry_state(accepted=item.accepted, orphan=orphan),
                resource_key=item.address,
                path=_object_path(item.filename),
                target_address=item.address,
                audit_address=audit_address,
                byte_count=item.byte_count,
                warning_count=len(item.warnings),
                referenced=item.referenced,
                accepted=accepted,
            )
        )
    for address in report.missing_addresses:
        entries.append(
            _entry(
                entry_id=f"missing:{address}",
                kind=StorageCatalogEntryKind.MISSING,
                state=StorageCatalogState.MISSING,
                resource_key=address,
                path=_missing_path(address),
                target_address=address,
                audit_address=audit_address,
                byte_count=0,
                warning_count=1,
                referenced=True,
                accepted=False,
            )
        )
    for item in report.runs:
        entries.append(
            _entry(
                entry_id=f"run:{item.run_id}",
                kind=StorageCatalogEntryKind.RUN,
                state=_entry_state(accepted=item.accepted),
                resource_key=item.run_id,
                path=_run_path(item.filename),
                target_address=None,
                audit_address=audit_address,
                byte_count=0,
                warning_count=len(item.warnings),
                referenced=bool(item.pointer_addresses),
                accepted=item.accepted,
            )
        )
    for item in report.batches:
        entries.append(
            _entry(
                entry_id=f"batch:{item.batch_id}",
                kind=StorageCatalogEntryKind.BATCH,
                state=_entry_state(accepted=item.accepted),
                resource_key=item.batch_id,
                path=_batch_path(item.filename),
                target_address=None,
                audit_address=audit_address,
                byte_count=0,
                warning_count=len(item.warnings),
                referenced=bool(item.input_address or item.result_address),
                accepted=item.accepted,
            )
        )
    for relative_path in report.unexpected_entries:
        normalized_path = _text(relative_path, "unexpected path", maximum=500).replace("\\", "/")
        entries.append(
            _entry(
                entry_id=f"unexpected:{normalized_path}",
                kind=StorageCatalogEntryKind.UNEXPECTED,
                state=StorageCatalogState.UNEXPECTED,
                resource_key=normalized_path,
                path=normalized_path,
                target_address=None,
                audit_address=audit_address,
                byte_count=0,
                warning_count=1,
                referenced=False,
                accepted=False,
            )
        )
    if len(entries) > STORAGE_CATALOG_MAX_ENTRIES:
        raise ValidationError("storage catalog entry count exceeds its contract")
    ordered = tuple(sorted(entries, key=lambda item: item.entry_id))
    indexes = {name: _build_index(ordered, name) for name in STORAGE_CATALOG_INDEXES}
    index_rows = sum(len(rows) for rows in indexes.values())
    if index_rows > STORAGE_CATALOG_MAX_INDEX_ROWS:
        raise ValidationError("storage catalog index row count exceeds its contract")
    accepted = report.accepted and all(item.accepted for item in ordered)
    body = {
        "storage_catalog_version": STORAGE_CATALOG_VERSION,
        "root": str(report.root),
        "audit_address": audit_address,
        "entries": tuple(item.to_dict() for item in ordered),
        "address_index": tuple(item.to_dict() for item in indexes["address"]),
        "path_index": tuple(item.to_dict() for item in indexes["path"]),
        "kind_index": tuple(item.to_dict() for item in indexes["kind"]),
        "state_index": tuple(item.to_dict() for item in indexes["state"]),
        "accepted": accepted,
    }
    return StorageCatalog(
        root=str(report.root),
        audit_address=audit_address,
        entries=ordered,
        address_index=indexes["address"],
        path_index=indexes["path"],
        kind_index=indexes["kind"],
        state_index=indexes["state"],
        accepted=accepted,
        content_address=content_hash(body, prefix="storage-catalog"),
    )


def verify_storage_catalog(
    value: StorageCatalog | Mapping[str, Any],
) -> StorageCatalog:
    """Parse and strictly verify a serialized catalog."""

    selected = _as_catalog(value)
    if selected.boundary != STORAGE_CATALOG_BOUNDARY:
        raise ValidationError("storage catalog boundary is invalid")
    return selected


def _index_rows(selected: StorageCatalog, name: str) -> tuple[StorageCatalogIndexRow, ...]:
    if name not in STORAGE_CATALOG_INDEXES:
        raise ValidationError(f"unsupported storage catalog index: {name}")
    return tuple(getattr(selected, f"{name}_index"))


def _index_entry_ids(
    selected: StorageCatalog,
    name: str,
    key: str,
) -> set[str]:
    for row in _index_rows(selected, name):
        if row.key == key:
            return set(row.entry_ids)
    return set()


def _filter_value(value: Any, field: str, allowed: tuple[str, ...]) -> str | None:
    if value is None:
        return None
    result = _text(value, field, maximum=80).lower()
    if result not in allowed:
        raise ValidationError(f"unsupported {field}: {result}")
    return result


def query_storage_catalog(
    catalog: StorageCatalog | Mapping[str, Any],
    *,
    resource: str = "entries",
    kind: str | None = None,
    state: str | None = None,
    prefix: str | None = None,
    text: str | None = None,
    accepted: bool | None = None,
    referenced: bool | None = None,
    offset: int = 0,
    limit: int = STORAGE_CATALOG_DEFAULT_LIMIT,
) -> StorageCatalogQueryResult:
    """Return a deterministic bounded page and identify the index used."""

    selected = _as_catalog(catalog)
    resource = _text(resource, "resource", maximum=40).lower()
    if resource not in STORAGE_CATALOG_RESOURCES:
        raise ValidationError(f"unsupported storage catalog resource: {resource}")
    kind = _filter_value(kind, "kind", ("object", "missing", "run", "batch", "unexpected"))
    state = _filter_value(state, "state", STORAGE_CATALOG_STATES)
    prefix = _optional_text(prefix, "prefix", maximum=500)
    text = _optional_text(text, "text", maximum=240)
    if accepted is not None:
        accepted = _bool(accepted, "accepted")
    if referenced is not None:
        referenced = _bool(referenced, "referenced")
    offset = _int(offset, "offset", minimum=0)
    limit = _int(limit, "limit", minimum=1, maximum=STORAGE_CATALOG_MAX_LIMIT)
    entries = selected.entries
    candidate_ids: set[str] | None = None
    index_used: str | None = None
    if kind is not None:
        candidate_ids = _index_entry_ids(selected, "kind", kind)
        index_used = "kind"
    if state is not None:
        state_ids = _index_entry_ids(selected, "state", state)
        candidate_ids = state_ids if candidate_ids is None else candidate_ids & state_ids
        index_used = "state" if index_used is None else f"{index_used}+state"
    if prefix is not None:
        prefix_folded = prefix.casefold()
        path_ids = {
            entry_id
            for row in _index_rows(selected, "path")
            if row.key.casefold().startswith(prefix_folded)
            for entry_id in row.entry_ids
        }
        address_ids = {
            entry_id
            for row in _index_rows(selected, "address")
            if row.key.casefold().startswith(prefix_folded)
            for entry_id in row.entry_ids
        }
        prefix_ids = path_ids | address_ids
        candidate_ids = prefix_ids if candidate_ids is None else candidate_ids & prefix_ids
        index_used = "path+address" if index_used is None else f"{index_used}+path+address"
    if candidate_ids is not None:
        entries = tuple(item for item in entries if item.entry_id in candidate_ids)
    if resource != "entries":
        wanted_kind = {
            "objects": StorageCatalogEntryKind.OBJECT.value,
            "missing": StorageCatalogEntryKind.MISSING.value,
            "runs": StorageCatalogEntryKind.RUN.value,
            "batches": StorageCatalogEntryKind.BATCH.value,
            "unexpected": StorageCatalogEntryKind.UNEXPECTED.value,
        }[resource]
        entries = tuple(item for item in entries if item.kind.value == wanted_kind)
        if index_used is None:
            index_used = "kind"
    if accepted is not None:
        entries = tuple(item for item in entries if item.accepted is accepted)
    if referenced is not None:
        entries = tuple(item for item in entries if item.referenced is referenced)
    if text is not None:
        entries = tuple(item for item in entries if text_matches(item.to_dict(), text))
    total = len(entries)
    page = entries[offset : offset + limit]
    filters = {
        "resource": resource,
        "kind": kind,
        "state": state,
        "prefix": prefix,
        "text": text,
        "accepted": accepted,
        "referenced": referenced,
    }
    items = tuple(item.to_dict() for item in page)
    body = {
        "resource": resource,
        "filters": filters,
        "total": total,
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "items": items,
        "catalog_address": selected.content_address,
        "accepted": selected.accepted,
    }
    return StorageCatalogQueryResult(
        resource=resource,
        filters=filters,
        total=total,
        offset=offset,
        limit=limit,
        index_used=index_used,
        items=items,
        catalog_address=selected.content_address,
        accepted=selected.accepted,
        content_address=content_hash(body, prefix="storage-catalog-query"),
    )


def _index_key_set(selected: StorageCatalog, name: str) -> set[str]:
    return {row.key for row in _index_rows(selected, name)}


def diff_storage_catalog(
    baseline: StorageCatalog | Mapping[str, Any],
    candidate: StorageCatalog | Mapping[str, Any],
) -> StorageCatalogDiff:
    """Compare catalog rows and index key sets by stable content addresses."""

    left = _as_catalog(baseline)
    right = _as_catalog(candidate)
    left_entries = {item.entry_id: item for item in left.entries}
    right_entries = {item.entry_id: item for item in right.entries}
    common = set(left_entries) & set(right_entries)
    changed = tuple(
        sorted(
            entry_id
            for entry_id in common
            if left_entries[entry_id].content_address != right_entries[entry_id].content_address
        )
    )
    added = tuple(sorted(set(right_entries) - set(left_entries)))
    removed = tuple(sorted(set(left_entries) - set(right_entries)))
    added_index_keys: list[str] = []
    removed_index_keys: list[str] = []
    changed_index_names: list[str] = []
    for name in STORAGE_CATALOG_INDEXES:
        left_rows = {row.key: row for row in _index_rows(left, name)}
        right_rows = {row.key: row for row in _index_rows(right, name)}
        added_index_keys.extend(f"{name}:{key}" for key in sorted(set(right_rows) - set(left_rows)))
        removed_index_keys.extend(
            f"{name}:{key}" for key in sorted(set(left_rows) - set(right_rows))
        )
        if set(left_rows) & set(right_rows) and any(
            left_rows[key].content_address != right_rows[key].content_address
            for key in set(left_rows) & set(right_rows)
        ):
            changed_index_names.append(name)
    counts_changed = (
        left.entry_count != right.entry_count
        or left.object_count != right.object_count
        or left.missing_count != right.missing_count
        or left.run_count != right.run_count
        or left.batch_count != right.batch_count
        or left.unexpected_count != right.unexpected_count
        or left.index_row_count != right.index_row_count
    )
    body = {
        "storage_catalog_diff_version": "storage-catalog-diff-v1",
        "baseline_address": left.content_address,
        "candidate_address": right.content_address,
        "added_entry_ids": added,
        "removed_entry_ids": removed,
        "changed_entry_ids": changed,
        "added_index_keys": tuple(sorted(added_index_keys)),
        "removed_index_keys": tuple(sorted(removed_index_keys)),
        "changed_index_names": tuple(sorted(set(changed_index_names))),
        "counts_changed": counts_changed,
        "accepted": True,
    }
    return StorageCatalogDiff(
        baseline_address=left.content_address,
        candidate_address=right.content_address,
        added_entry_ids=added,
        removed_entry_ids=removed,
        changed_entry_ids=changed,
        added_index_keys=body["added_index_keys"],
        removed_index_keys=body["removed_index_keys"],
        changed_index_names=body["changed_index_names"],
        counts_changed=counts_changed,
        accepted=True,
        content_address=content_hash(body, prefix="storage-catalog-diff"),
    )


def storage_catalog_json(catalog: StorageCatalog | Mapping[str, Any]) -> str:
    """Serialize one strict catalog as canonical JSON."""

    return canonical_json(_as_catalog(catalog).to_dict())


def storage_catalog_entries_csv(catalog: StorageCatalog | Mapping[str, Any]) -> str:
    """Export normalized entries with a stable, payload-free column order."""

    selected = _as_catalog(catalog)
    fields = (
        "entry_id",
        "kind",
        "state",
        "resource_key",
        "path",
        "target_address",
        "audit_address",
        "byte_count",
        "warning_count",
        "referenced",
        "accepted",
        "content_address",
    )
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in selected.entries:
        writer.writerow({field: item.to_dict().get(field, "") for field in fields})
    return output.getvalue()


def storage_catalog_indexes_csv(catalog: StorageCatalog | Mapping[str, Any]) -> str:
    """Export all four indexes as one deterministic tabular document."""

    selected = _as_catalog(catalog)
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=("index_name", "key", "entry_ids", "content_address"),
        lineterminator="\n",
    )
    writer.writeheader()
    for name in STORAGE_CATALOG_INDEXES:
        for row in _index_rows(selected, name):
            writer.writerow(
                {
                    "index_name": name,
                    "key": row.key,
                    "entry_ids": json.dumps(row.entry_ids, separators=(",", ":")),
                    "content_address": row.content_address,
                }
            )
    return output.getvalue()


def storage_catalog_markdown(catalog: StorageCatalog | Mapping[str, Any]) -> str:
    """Export a human-readable summary and entry table."""

    selected = _as_catalog(catalog)
    lines = [
        "# Storage catalog",
        "",
        f"- Root: `{selected.root}`",
        f"- Audit: `{selected.audit_address}`",
        f"- Catalog: `{selected.content_address}`",
        f"- Boundary: `{selected.boundary}`",
        f"- Accepted: `{str(selected.accepted).lower()}`",
        f"- Entries: {selected.entry_count}",
        f"- Objects: {selected.object_count}",
        f"- Missing: {selected.missing_count}",
        f"- Runs: {selected.run_count}",
        f"- Batches: {selected.batch_count}",
        f"- Unexpected: {selected.unexpected_count}",
        f"- Index rows: {selected.index_row_count}",
        "",
        "| Entry | Kind | State | Resource key | Path | Accepted |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in selected.entries:
        path = item.path or ""
        lines.append(
            f"| `{item.entry_id}` | `{item.kind.value}` | `{item.state.value}` | "
            f"`{item.resource_key}` | `{path}` | `{str(item.accepted).lower()}` |"
        )
    return "\n".join(lines) + "\n"


def storage_catalog_capabilities() -> dict[str, Any]:
    """Describe the catalog's stable public boundary."""

    return {
        "version": STORAGE_CATALOG_VERSION,
        "schema_version": STORAGE_CATALOG_SCHEMA_VERSION,
        "boundary": STORAGE_CATALOG_BOUNDARY,
        "address_only": True,
        "payload_exposure": False,
        "object_entries": True,
        "missing_entries": True,
        "run_entries": True,
        "batch_entries": True,
        "unexpected_entries": True,
        "address_index": True,
        "path_index": True,
        "kind_index": True,
        "state_index": True,
        "bounded_query": True,
        "prefix_filter": True,
        "text_filter": True,
        "structural_diff": True,
        "json_export": True,
        "entries_csv": True,
        "indexes_csv": True,
        "markdown_export": True,
        "timestamp_free": True,
        "mutation": False,
        "entry_kinds": ("object", "missing", "run", "batch", "unexpected"),
        "states": STORAGE_CATALOG_STATES,
        "resources": STORAGE_CATALOG_RESOURCES,
        "indexes": STORAGE_CATALOG_INDEXES,
        "max_entries": STORAGE_CATALOG_MAX_ENTRIES,
        "max_index_rows": STORAGE_CATALOG_MAX_INDEX_ROWS,
        "max_limit": STORAGE_CATALOG_MAX_LIMIT,
    }


def storage_catalog_schema() -> dict[str, Any]:
    """Return the closed catalog schema for clients and validation tooling."""

    return {
        "version": STORAGE_CATALOG_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_CATALOG_BOUNDARY,
        "required": (
            "storage_catalog_version",
            "root",
            "audit_address",
            "entries",
            "address_index",
            "path_index",
            "kind_index",
            "state_index",
            "accepted",
            "content_address",
        ),
        "entry_required": (
            "entry_id",
            "kind",
            "state",
            "resource_key",
            "path",
            "target_address",
            "audit_address",
            "byte_count",
            "warning_count",
            "referenced",
            "accepted",
            "content_address",
        ),
        "index_row_required": ("key", "entry_ids", "content_address"),
        "entry_kinds": ("object", "missing", "run", "batch", "unexpected"),
        "states": STORAGE_CATALOG_STATES,
        "resources": STORAGE_CATALOG_RESOURCES,
        "indexes": STORAGE_CATALOG_INDEXES,
        "derived": (
            "boundary",
            "entry_count",
            "object_count",
            "missing_count",
            "run_count",
            "batch_count",
            "unexpected_count",
            "index_row_count",
        ),
        "address_only": True,
        "payload_exposure": False,
        "timestamp_free": True,
        "strict_unknown_fields": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_CATALOG")
    or name.startswith("StorageCatalog")
    or name.startswith("build_storage_catalog")
    or name.startswith("verify_storage_catalog")
    or name.startswith("query_storage_catalog")
    or name.startswith("diff_storage_catalog")
    or name.startswith("storage_catalog")
]
