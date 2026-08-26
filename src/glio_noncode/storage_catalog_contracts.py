"""Strict contracts for the normalized, address-only storage catalog.

The storage audit is the integrity authority. The catalog is its query-oriented
read model: it normalizes object, run, batch, missing, and unexpected entries
and closes deterministic lookup indexes over stable keys. It intentionally
contains no stored object payloads and never owns a mutation operation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

STORAGE_CATALOG_VERSION = "storage-catalog-v1"
STORAGE_CATALOG_SCHEMA_VERSION = "storage-catalog-schema-v1"
STORAGE_CATALOG_BOUNDARY = "public_storage_catalog"
STORAGE_CATALOG_MAX_ENTRIES = 500_000
STORAGE_CATALOG_MAX_INDEX_ROWS = 500_000
STORAGE_CATALOG_DEFAULT_LIMIT = 50
STORAGE_CATALOG_MAX_LIMIT = 500
STORAGE_CATALOG_ENTRY_KINDS = ("object", "missing", "run", "batch", "unexpected")
STORAGE_CATALOG_STATES = ("accepted", "rejected", "orphan", "missing", "unexpected")
STORAGE_CATALOG_RESOURCES = ("entries", "objects", "runs", "batches", "missing", "unexpected")
STORAGE_CATALOG_INDEXES = ("address", "path", "kind", "state")


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


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


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


def _tuple_text(value: Any, field: str, *, maximum: int = 500) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_text(item, f"{field}[]", maximum=maximum) for item in value)
    if result != tuple(sorted(set(result))):
        raise ValidationError(f"{field} must be sorted and unique")
    return result


class StorageCatalogEntryKind(StrEnum):
    OBJECT = "object"
    MISSING = "missing"
    RUN = "run"
    BATCH = "batch"
    UNEXPECTED = "unexpected"


class StorageCatalogState(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ORPHAN = "orphan"
    MISSING = "missing"
    UNEXPECTED = "unexpected"


@dataclass(frozen=True, slots=True)
class StorageCatalogEntry:
    """One normalized filesystem or referenced-address catalog row."""

    entry_id: str
    kind: StorageCatalogEntryKind
    state: StorageCatalogState
    resource_key: str
    path: str | None
    target_address: str | None
    audit_address: str
    byte_count: int
    warning_count: int
    referenced: bool
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "kind": self.kind.value,
            "state": self.state.value,
            "resource_key": self.resource_key,
            "path": self.path,
            "target_address": self.target_address,
            "audit_address": self.audit_address,
            "byte_count": self.byte_count,
            "warning_count": self.warning_count,
            "referenced": self.referenced,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.entry_id, "storage_catalog_entry.entry_id", maximum=360)
        if not isinstance(self.kind, StorageCatalogEntryKind):
            raise ValidationError("storage catalog entry kind is invalid")
        if not isinstance(self.state, StorageCatalogState):
            raise ValidationError("storage catalog entry state is invalid")
        _text(self.resource_key, "storage_catalog_entry.resource_key", maximum=500)
        _optional_text(self.path, "storage_catalog_entry.path", maximum=500)
        _optional_text(self.target_address, "storage_catalog_entry.target_address", maximum=180)
        _text(self.audit_address, "storage_catalog_entry.audit_address", maximum=180)
        _int(self.byte_count, "storage_catalog_entry.byte_count", minimum=0)
        _int(self.warning_count, "storage_catalog_entry.warning_count", minimum=0)
        _bool(self.referenced, "storage_catalog_entry.referenced")
        _bool(self.accepted, "storage_catalog_entry.accepted")
        expected = content_hash(self._body(), prefix="storage-catalog-entry")
        if self.content_address != expected:
            raise ValidationError("storage catalog entry address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageCatalogEntry:
        body = _mapping(value, "storage catalog entry")
        allowed = {
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
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"storage catalog entry contains unsupported fields: {sorted(unknown)}"
            )
        try:
            kind = StorageCatalogEntryKind(
                _text(body.get("kind"), "storage_catalog_entry.kind", maximum=40)
            )
            state = StorageCatalogState(
                _text(body.get("state"), "storage_catalog_entry.state", maximum=40)
            )
        except ValueError as exc:
            raise ValidationError("storage catalog entry enum value is invalid") from exc
        return cls(
            entry_id=_text(body.get("entry_id"), "storage_catalog_entry.entry_id", maximum=360),
            kind=kind,
            state=state,
            resource_key=_text(
                body.get("resource_key"), "storage_catalog_entry.resource_key", maximum=500
            ),
            path=_optional_text(body.get("path"), "storage_catalog_entry.path", maximum=500),
            target_address=_optional_text(
                body.get("target_address"), "storage_catalog_entry.target_address", maximum=180
            ),
            audit_address=_text(
                body.get("audit_address"), "storage_catalog_entry.audit_address", maximum=180
            ),
            byte_count=_int(body.get("byte_count"), "storage_catalog_entry.byte_count", minimum=0),
            warning_count=_int(
                body.get("warning_count"), "storage_catalog_entry.warning_count", minimum=0
            ),
            referenced=_bool(body.get("referenced"), "storage_catalog_entry.referenced"),
            accepted=_bool(body.get("accepted"), "storage_catalog_entry.accepted"),
            content_address=_text(
                body.get("content_address"), "storage_catalog_entry.content_address", maximum=180
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageCatalogIndexRow:
    """One immutable key-to-entry-id row in a catalog index."""

    key: str
    entry_ids: tuple[str, ...]
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {"key": self.key, "entry_ids": self.entry_ids}

    def __post_init__(self) -> None:
        _text(self.key, "storage_catalog_index_row.key", maximum=500)
        if not self.entry_ids or self.entry_ids != tuple(sorted(set(self.entry_ids))):
            raise ValidationError("storage catalog index row entry IDs must be sorted and unique")
        for entry_id in self.entry_ids:
            _text(entry_id, "storage_catalog_index_row.entry_id", maximum=360)
        expected = content_hash(self._body(), prefix="storage-catalog-index-row")
        if self.content_address != expected:
            raise ValidationError("storage catalog index row address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageCatalogIndexRow:
        body = _mapping(value, "storage catalog index row")
        allowed = {"key", "entry_ids", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"storage catalog index row contains unsupported fields: {sorted(unknown)}"
            )
        return cls(
            key=_text(body.get("key"), "storage_catalog_index_row.key", maximum=500),
            entry_ids=_tuple_text(
                body.get("entry_ids"), "storage_catalog_index_row.entry_ids", maximum=360
            ),
            content_address=_text(
                body.get("content_address"),
                "storage_catalog_index_row.content_address",
                maximum=180,
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageCatalog:
    """Closed normalized storage catalog with deterministic lookup indexes."""

    root: str
    audit_address: str
    entries: tuple[StorageCatalogEntry, ...]
    address_index: tuple[StorageCatalogIndexRow, ...]
    path_index: tuple[StorageCatalogIndexRow, ...]
    kind_index: tuple[StorageCatalogIndexRow, ...]
    state_index: tuple[StorageCatalogIndexRow, ...]
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "storage_catalog_version": STORAGE_CATALOG_VERSION,
            "root": self.root,
            "audit_address": self.audit_address,
            "entries": tuple(item.to_dict() for item in self.entries),
            "address_index": tuple(item.to_dict() for item in self.address_index),
            "path_index": tuple(item.to_dict() for item in self.path_index),
            "kind_index": tuple(item.to_dict() for item in self.kind_index),
            "state_index": tuple(item.to_dict() for item in self.state_index),
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.root, "storage_catalog.root", maximum=500)
        _text(self.audit_address, "storage_catalog.audit_address", maximum=180)
        if len(self.entries) > STORAGE_CATALOG_MAX_ENTRIES:
            raise ValidationError("storage catalog entry count exceeds its contract")
        if tuple(item.entry_id for item in self.entries) != tuple(
            sorted(item.entry_id for item in self.entries)
        ):
            raise ValidationError("storage catalog entries must be sorted by entry ID")
        entry_ids = {item.entry_id for item in self.entries}
        if len(entry_ids) != len(self.entries):
            raise ValidationError("storage catalog entry IDs must be unique")
        for item in self.entries:
            if item.audit_address != self.audit_address:
                raise ValidationError("storage catalog entry audit identity does not reconcile")
        for name in ("address_index", "path_index", "kind_index", "state_index"):
            rows = tuple(getattr(self, name))
            if len(rows) > STORAGE_CATALOG_MAX_INDEX_ROWS:
                raise ValidationError(f"storage catalog {name} exceeds its contract")
            if tuple(row.key for row in rows) != tuple(sorted(row.key for row in rows)):
                raise ValidationError(f"storage catalog {name} keys must be sorted")
            if len({row.key for row in rows}) != len(rows):
                raise ValidationError(f"storage catalog {name} keys must be unique")
            if any(not set(row.entry_ids).issubset(entry_ids) for row in rows):
                raise ValidationError(f"storage catalog {name} references an unknown entry")
        _bool(self.accepted, "storage_catalog.accepted")
        expected = content_hash(self._body(), prefix="storage-catalog")
        if self.content_address != expected:
            raise ValidationError("storage catalog address does not reconcile")

    @property
    def boundary(self) -> str:
        return STORAGE_CATALOG_BOUNDARY

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def object_count(self) -> int:
        return sum(item.kind is StorageCatalogEntryKind.OBJECT for item in self.entries)

    @property
    def missing_count(self) -> int:
        return sum(item.kind is StorageCatalogEntryKind.MISSING for item in self.entries)

    @property
    def run_count(self) -> int:
        return sum(item.kind is StorageCatalogEntryKind.RUN for item in self.entries)

    @property
    def batch_count(self) -> int:
        return sum(item.kind is StorageCatalogEntryKind.BATCH for item in self.entries)

    @property
    def unexpected_count(self) -> int:
        return sum(item.kind is StorageCatalogEntryKind.UNEXPECTED for item in self.entries)

    @property
    def index_row_count(self) -> int:
        return sum(
            len(getattr(self, name))
            for name in ("address_index", "path_index", "kind_index", "state_index")
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": self.boundary,
                "entry_count": self.entry_count,
                "object_count": self.object_count,
                "missing_count": self.missing_count,
                "run_count": self.run_count,
                "batch_count": self.batch_count,
                "unexpected_count": self.unexpected_count,
                "index_row_count": self.index_row_count,
                "content_address": self.content_address,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageCatalog:
        body = _mapping(value, "storage catalog")
        allowed = {
            "storage_catalog_version",
            "root",
            "audit_address",
            "entries",
            "address_index",
            "path_index",
            "kind_index",
            "state_index",
            "accepted",
            "boundary",
            "entry_count",
            "object_count",
            "missing_count",
            "run_count",
            "batch_count",
            "unexpected_count",
            "index_row_count",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"storage catalog contains unsupported fields: {sorted(unknown)}")
        if body.get("storage_catalog_version") != STORAGE_CATALOG_VERSION:
            raise ValidationError("storage catalog version is invalid")
        raw_entries = body.get("entries")
        if not isinstance(raw_entries, (list, tuple)):
            raise ValidationError("storage catalog entries must be an array")
        arrays: dict[str, tuple[StorageCatalogIndexRow, ...]] = {}
        for name in ("address_index", "path_index", "kind_index", "state_index"):
            raw_rows = body.get(name)
            if not isinstance(raw_rows, (list, tuple)):
                raise ValidationError(f"storage catalog {name} must be an array")
            arrays[name] = tuple(StorageCatalogIndexRow.from_mapping(item) for item in raw_rows)
        result = cls(
            root=_text(body.get("root"), "storage_catalog.root", maximum=500),
            audit_address=_text(
                body.get("audit_address"), "storage_catalog.audit_address", maximum=180
            ),
            entries=tuple(StorageCatalogEntry.from_mapping(item) for item in raw_entries),
            address_index=arrays["address_index"],
            path_index=arrays["path_index"],
            kind_index=arrays["kind_index"],
            state_index=arrays["state_index"],
            accepted=_bool(body.get("accepted"), "storage_catalog.accepted"),
            content_address=_text(
                body.get("content_address"), "storage_catalog.content_address", maximum=180
            ),
        )
        if body.get("boundary") not in (None, STORAGE_CATALOG_BOUNDARY):
            raise ValidationError("storage catalog boundary is invalid")
        derived = {
            "entry_count": result.entry_count,
            "object_count": result.object_count,
            "missing_count": result.missing_count,
            "run_count": result.run_count,
            "batch_count": result.batch_count,
            "unexpected_count": result.unexpected_count,
            "index_row_count": result.index_row_count,
        }
        for field, expected in derived.items():
            if body.get(field) != expected:
                raise ValidationError(f"storage catalog {field} does not reconcile")
        return result


@dataclass(frozen=True, slots=True)
class StorageCatalogQueryResult:
    """Bounded catalog query page and index-selection receipt."""

    resource: str
    filters: dict[str, Any]
    total: int
    offset: int
    limit: int
    index_used: str | None
    items: tuple[dict[str, Any], ...]
    catalog_address: str
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "filters": self.filters,
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "index_used": self.index_used,
            "items": self.items,
            "catalog_address": self.catalog_address,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.resource, "storage_catalog_query.resource", maximum=40)
        if self.resource not in STORAGE_CATALOG_RESOURCES:
            raise ValidationError("storage catalog query resource is invalid")
        if not isinstance(self.filters, dict):
            raise ValidationError("storage catalog query filters must be an object")
        _int(self.total, "storage_catalog_query.total", minimum=0)
        _int(self.offset, "storage_catalog_query.offset", minimum=0)
        _int(
            self.limit, "storage_catalog_query.limit", minimum=1, maximum=STORAGE_CATALOG_MAX_LIMIT
        )
        _optional_text(self.index_used, "storage_catalog_query.index_used", maximum=160)
        if not isinstance(self.items, tuple):
            raise ValidationError("storage catalog query items must be a tuple")
        if len(self.items) > self.limit or len(self.items) > self.total:
            raise ValidationError("storage catalog query page does not reconcile")
        if not all(isinstance(item, dict) for item in self.items):
            raise ValidationError("storage catalog query items must be objects")
        _text(self.catalog_address, "storage_catalog_query.catalog_address", maximum=180)
        _bool(self.accepted, "storage_catalog_query.accepted")
        if self.content_address != content_hash(self._body(), prefix="storage-catalog-query"):
            raise ValidationError("storage catalog query address does not reconcile")

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body() | {"content_address": self.content_address, "has_more": self.has_more}
        )


@dataclass(frozen=True, slots=True)
class StorageCatalogDiff:
    """Structural diff between two normalized catalog snapshots."""

    baseline_address: str
    candidate_address: str
    added_entry_ids: tuple[str, ...]
    removed_entry_ids: tuple[str, ...]
    changed_entry_ids: tuple[str, ...]
    added_index_keys: tuple[str, ...]
    removed_index_keys: tuple[str, ...]
    changed_index_names: tuple[str, ...]
    counts_changed: bool
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "storage_catalog_diff_version": "storage-catalog-diff-v1",
            "baseline_address": self.baseline_address,
            "candidate_address": self.candidate_address,
            "added_entry_ids": self.added_entry_ids,
            "removed_entry_ids": self.removed_entry_ids,
            "changed_entry_ids": self.changed_entry_ids,
            "added_index_keys": self.added_index_keys,
            "removed_index_keys": self.removed_index_keys,
            "changed_index_names": self.changed_index_names,
            "counts_changed": self.counts_changed,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.baseline_address, "storage_catalog_diff.baseline_address", maximum=180)
        _text(self.candidate_address, "storage_catalog_diff.candidate_address", maximum=180)
        for field in (
            "added_entry_ids",
            "removed_entry_ids",
            "changed_entry_ids",
            "added_index_keys",
            "removed_index_keys",
            "changed_index_names",
        ):
            values = tuple(getattr(self, field))
            if values != tuple(sorted(set(values))):
                raise ValidationError(f"storage catalog diff {field} must be sorted and unique")
        _bool(self.counts_changed, "storage_catalog_diff.counts_changed")
        _bool(self.accepted, "storage_catalog_diff.accepted")
        expected = content_hash(self._body(), prefix="storage-catalog-diff")
        if self.content_address != expected:
            raise ValidationError("storage catalog diff address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageCatalogDiff:
        body = _mapping(value, "storage catalog diff")
        allowed = {
            "storage_catalog_diff_version",
            "baseline_address",
            "candidate_address",
            "added_entry_ids",
            "removed_entry_ids",
            "changed_entry_ids",
            "added_index_keys",
            "removed_index_keys",
            "changed_index_names",
            "counts_changed",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"storage catalog diff contains unsupported fields: {sorted(unknown)}"
            )
        if body.get("storage_catalog_diff_version") != "storage-catalog-diff-v1":
            raise ValidationError("storage catalog diff version is invalid")
        return cls(
            baseline_address=_text(
                body.get("baseline_address"), "storage_catalog_diff.baseline_address", maximum=180
            ),
            candidate_address=_text(
                body.get("candidate_address"), "storage_catalog_diff.candidate_address", maximum=180
            ),
            added_entry_ids=_tuple_text(
                body.get("added_entry_ids"), "storage_catalog_diff.added_entry_ids", maximum=360
            ),
            removed_entry_ids=_tuple_text(
                body.get("removed_entry_ids"), "storage_catalog_diff.removed_entry_ids", maximum=360
            ),
            changed_entry_ids=_tuple_text(
                body.get("changed_entry_ids"), "storage_catalog_diff.changed_entry_ids", maximum=360
            ),
            added_index_keys=_tuple_text(
                body.get("added_index_keys"), "storage_catalog_diff.added_index_keys", maximum=500
            ),
            removed_index_keys=_tuple_text(
                body.get("removed_index_keys"),
                "storage_catalog_diff.removed_index_keys",
                maximum=500,
            ),
            changed_index_names=_tuple_text(
                body.get("changed_index_names"),
                "storage_catalog_diff.changed_index_names",
                maximum=80,
            ),
            counts_changed=_bool(body.get("counts_changed"), "storage_catalog_diff.counts_changed"),
            accepted=_bool(body.get("accepted"), "storage_catalog_diff.accepted"),
            content_address=_text(
                body.get("content_address"), "storage_catalog_diff.content_address", maximum=180
            ),
        )


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_CATALOG") or name.startswith("StorageCatalog")
]
