"""Bounded inspection queries for runtime-registry federation archives."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation as federation_model
from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = archive_model.VERSION + "-query-v1"
BOUNDARY = archive_model.BOUNDARY + "_query"
QUERY_PREFIX = archive_model.ARCHIVE_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = "comparison-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive-query"
RESOURCES = ("summary", "manifest", "artifacts", "federation", "members", "entries", "states", "readiness", "addresses", "bounds")
STATES = federation_model.STATES
MAX_LIMIT = 256
MAX_TEXT = 4096
ROW_FIELDS = ("ordinal", "resource", "key", "value", "address", "state", "accepted", "row_address")
QUERY_FIELDS = ("query_id", "archive_id", "archive_address", "resources", "state_filter", "key_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 2048, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValidationError(f"{field} must be a string-keyed object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return archive_model._public(value)


class RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, key: str, value: Any, address: str, state: str, accepted: bool, row_address: str) -> None:
        self.ordinal = _count(ordinal, "archive query row ordinal", MAX_LIMIT, lower=1)
        if resource not in RESOURCES:
            raise ValidationError("archive query row resource is unsupported")
        self.resource = resource
        self.key = _label(key, "archive query row key")
        if isinstance(value, (bytes, bytearray)):
            raise ValidationError("archive query row value cannot be binary")
        self.value = value
        self.address = _address(address, "archive query row source address")
        if state not in STATES:
            raise ValidationError("archive query row state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "archive query row acceptance")
        self.row_address = _address(row_address, "archive query row address", ROW_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("archive query row crosses the public boundary")
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("archive query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow":
        value = _mapping(value, "archive query row")
        _strict(value, set(cls.FIELDS), "archive query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow):
        raise ValidationError("archive query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


def _compact_member(value: federation_model.RecoveryExecutionRuntimeRegistryFederationMember) -> dict[str, Any]:
    return {"ordinal": value.ordinal, "registry_id": value.registry_id, "registry_address": value.registry_address, "entry_count": value.entry_count, "accepted_count": value.accepted_count, "ready_count": value.ready_count, "blocked_count": value.blocked_count, "state": value.state, "accepted": value.accepted, "content_address": value.content_address}


def _compact_entry(value: federation_model.RecoveryExecutionRuntimeRegistryFederationEntry) -> dict[str, Any]:
    return {"ordinal": value.ordinal, "member_ordinal": value.member_ordinal, "registry_id": value.registry_id, "registry_address": value.registry_address, "runtime_id": value.runtime_id, "runtime_address": value.runtime_address, "execution_id": value.execution_id, "execution_address": value.execution_address, "execution_audit_address": value.execution_audit_address, "query_address": value.query_address, "query_audit_address": value.query_audit_address, "state": value.state, "accepted": value.accepted, "content_address": value.content_address}


def _all_rows(value: archive_model.RecoveryExecutionRuntimeRegistryFederationArchive) -> tuple[RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow, ...]:
    federation = value.federation
    if federation is None:
        raise ValidationError("archive query requires a loaded federation")
    rows: list[RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow] = []
    ordinal = 1

    def add(resource: str, key: str, item: Any, address: str, state: str, accepted: bool) -> None:
        nonlocal ordinal
        rows.append(_row(resource, key, item, address, state, accepted, ordinal))
        ordinal += 1

    for field in ("archive_id", "version", "boundary", "federation_id", "federation_address", "artifact_count", "archive_size", "content_address"):
        add("summary", field, value.summary()[field], value.content_address, federation.state, federation.accepted)
    manifest = archive_model.manifest_document(value)
    for field in ("version", "boundary", "archive_id", "federation_id", "federation_address", "artifact_count", "archive_address", "manifest_address"):
        add("manifest", field, manifest[field], manifest["manifest_address"], federation.state, federation.accepted)
    for item in value.artifacts:
        add("artifacts", f"artifact:{item.index}", item.to_dict(), item.hash, federation.state, True)
    add("federation", "summary", federation.summary.to_dict(), federation.content_address, federation.state, federation.accepted)
    for item in federation.members:
        add("members", f"member:{item.ordinal}", _compact_member(item), item.content_address, item.state, item.accepted)
    for item in federation.entries:
        add("entries", f"entry:{item.ordinal}", _compact_entry(item), item.content_address, item.state, item.accepted)
    for state in federation_model.STATES:
        add("states", f"member:{state}", sum(item.state == state for item in federation.members), federation.summary.content_address, state, state != "blocked")
    add("states", "federation", federation.state, federation.content_address, federation.state, federation.accepted)
    for field in ("accepted_member_count", "ready_member_count", "empty_member_count", "blocked_member_count", "accepted_runtime_entry_count", "ready_runtime_entry_count", "blocked_runtime_entry_count"):
        add("readiness", field, getattr(federation, field), federation.summary.content_address, federation.state, federation.accepted)
    addresses = (("archive", value.content_address), ("federation", value.federation_address), ("manifest", manifest["manifest_address"]), ("members", federation.manifest.artifact_addresses[0]), ("entries", federation.manifest.artifact_addresses[1]), ("summary", federation.summary.content_address))
    for key, address in addresses:
        add("addresses", key, address, address, federation.state, federation.accepted)
    for key, item in (("artifact_count", value.artifact_count), ("max_artifacts", len(archive_model.EMBEDDED_FILES)), ("archive_size", value.archive_size), ("max_archive_bytes", archive_model.MAX_ARCHIVE_BYTES), ("federation_member_count", federation.member_count), ("federation_runtime_entry_count", federation.runtime_entry_count), ("file_count", len(archive_model.FILES)), ("files", list(archive_model.FILES))):
        add("bounds", key, item, value.content_address, federation.state, federation.accepted)
    return tuple(rows)


class RecoveryExecutionRuntimeRegistryFederationArchiveQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, archive_id: str, archive_address: str, resources: Sequence[str], state_filter: str, key_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "archive query ID")
        self.archive_id = _label(archive_id, "archive query archive ID")
        self.archive_address = _address(archive_address, "archive query archive address", archive_model.ARCHIVE_PREFIX)
        self.resources = tuple(_label(item, "archive query resource") for item in _sequence(resources, "archive query resources", len(RESOURCES)))
        if len(self.resources) != len(set(self.resources)) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(item for item in RESOURCES if item in self.resources):
            raise ValidationError("archive query resources are not canonical")
        self.state_filter = _text(state_filter, "archive query state filter", 64)
        if self.state_filter not in ("",) + STATES:
            raise ValidationError("archive query state filter is unsupported")
        self.key_filter = _text(key_filter, "archive query key filter")
        self.text_filter = _text(text_filter, "archive query text filter")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValidationError("archive query offset is invalid")
        self.offset = offset
        self.limit = _count(limit, "archive query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "archive query total count", len(RESOURCES) * (federation_model.MAX_ENTRIES + federation_model.MAX_MEMBERS + len(archive_model.FILES) + 64))
        self.returned_count = _count(returned_count, "archive query returned count", MAX_LIMIT)
        self.truncated = _bool(truncated, "archive query truncation")
        self.rows = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow) else RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow.from_mapping(item) for item in _sequence(rows, "archive query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "archive query address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.offset > self.total_count or self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("archive query counts do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("archive query rows are not re-ordinalized")
        if not _public(self.to_dict()):
            raise ValidationError("archive query crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("archive query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "archive_id": self.archive_id, "archive_address": self.archive_address, "resources": list(self.resources), "state_filter": self.state_filter, "key_filter": self.key_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationArchiveQuery":
        value = _mapping(value, "archive query")
        _strict(value, set(cls.FIELDS), "archive query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RecoveryExecutionRuntimeRegistryFederationArchiveQuery) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationArchiveQuery):
        raise ValidationError("archive query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, key: str, value: Any, address: str, state: str, accepted: bool, ordinal: int) -> RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow:
    provisional = RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow(ordinal, resource, key, value, address, state, accepted, ROW_PREFIX + ":pending")
    return RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow(ordinal, resource, key, value, address, state, accepted, address_row(provisional))


def query_archive(value: archive_model.RecoveryExecutionRuntimeRegistryFederationArchive, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, state: str = "", key: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> RecoveryExecutionRuntimeRegistryFederationArchiveQuery:
    if not isinstance(value, archive_model.RecoveryExecutionRuntimeRegistryFederationArchive):
        raise ValidationError("archive query requires a typed archive")
    selected = tuple(item for item in RESOURCES if item in tuple(resources))
    if not selected:
        raise ValidationError("archive query requires at least one resource")
    if state not in ("",) + STATES:
        raise ValidationError("archive query state is unsupported")
    key = _text(key, "archive query key filter")
    text = _text(text, "archive query text filter")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("archive query offset is invalid")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("archive query limit is invalid")
    all_rows = tuple(item for item in _all_rows(value) if item.resource in selected and (not state or item.state == state) and (not key or key.casefold() in item.key.casefold()) and (not text or text.casefold() in canonical_json(item.to_dict()).casefold()))
    page = all_rows[offset:offset + limit]
    rows = tuple(RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow(index, item.resource, item.key, item.value, item.address, item.state, item.accepted, ROW_PREFIX + ":pending") for index, item in enumerate(page, 1))
    rows = tuple(RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow(item.ordinal, item.resource, item.key, item.value, item.address, item.state, item.accepted, address_row(item)) for item in rows)
    provisional = RecoveryExecutionRuntimeRegistryFederationArchiveQuery(query_id, value.archive_id, value.content_address, selected, state, key, text, offset, limit, len(all_rows), len(rows), offset + len(rows) < len(all_rows), rows, QUERY_PREFIX + ":pending")
    return RecoveryExecutionRuntimeRegistryFederationArchiveQuery(provisional.query_id, provisional.archive_id, provisional.archive_address, provisional.resources, provisional.state_filter, provisional.key_filter, provisional.text_filter, provisional.offset, provisional.limit, provisional.total_count, provisional.returned_count, provisional.truncated, provisional.rows, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryFederationArchiveQuery:
    return RecoveryExecutionRuntimeRegistryFederationArchiveQuery.from_mapping(value)


def query_json(value: RecoveryExecutionRuntimeRegistryFederationArchiveQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: RecoveryExecutionRuntimeRegistryFederationArchiveQuery) -> str:
    value = query_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "resource", "key", "state", "accepted", "address", "row_address"))
    for item in value.rows:
        writer.writerow((item.ordinal, item.resource, item.key, item.state, item.accepted, item.address, item.row_address))
    return output.getvalue()


def render_query_markdown(value: RecoveryExecutionRuntimeRegistryFederationArchiveQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Runtime Registry Federation Archive Query", "", f"- Archive: `{value.archive_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.total_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | resource | key | state | accepted | address |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.key}` | `{item.state}` | `{item.accepted}` | `{item.address}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime registry federation archive query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "resource": {"enum": list(RESOURCES)}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "row_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime registry federation archive query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "archive_id": {"type": "string"}, "archive_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "state_filter": {"enum": ["", *STATES]}, "key_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_LIMIT}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "states": list(STATES), "max_limit": MAX_LIMIT, "operations": ["query_archive", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"], "filters": ["resource", "state", "key", "text", "offset", "limit"], "privacy": {"values": False, "source_paths": False, "embedded_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "RecoveryExecutionRuntimeRegistryFederationArchiveQueryRow", "RecoveryExecutionRuntimeRegistryFederationArchiveQuery", "address_row", "address_query", "query_archive", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
