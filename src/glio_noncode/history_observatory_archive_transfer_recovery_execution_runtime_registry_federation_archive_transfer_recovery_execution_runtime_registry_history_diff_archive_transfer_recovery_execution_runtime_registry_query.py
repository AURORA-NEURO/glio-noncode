"""Bounded inspection queries for history-diff recovery runtime registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-query-v1"
BOUNDARY = registry_model.BOUNDARY + "_query"
QUERY_PREFIX = registry_model.REGISTRY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = "history-diff-archive-transfer-recovery-execution-runtime-registry-query"
RESOURCES = ("summary", "entries", "runtimes", "states", "readiness", "addresses", "bounds")
STATES = registry_model.STATES
MAX_LIMIT = 512
MAX_TEXT = 4096
ROW_FIELDS = ("ordinal", "resource", "key", "value", "address", "state", "accepted", "row_address")
QUERY_FIELDS = ("query_id", "registry_id", "registry_address", "resources", "state_filter", "key_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, required=True)
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, key: str, value: Any, address: str, state: str, accepted: bool, row_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry query row ordinal", MAX_LIMIT, lower=1)
        if resource not in RESOURCES:
            raise ValidationError("runtime registry query row resource is unsupported")
        self.resource = resource
        self.key = _label(key, "runtime registry query row key")
        self.value = value
        if len(canonical_json(value).encode("utf-8")) > 8192:
            raise ValidationError("runtime registry query row value is too large")
        self.address = _address(address, "runtime registry query row address")
        if state not in STATES:
            raise ValidationError("runtime registry query row state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry query row acceptance")
        self.row_address = _address(row_address, "runtime registry query row address", ROW_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry query row crosses the public boundary")
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("runtime registry query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow:
        value = _mapping(value, "runtime registry query row")
        _strict(value, set(cls.FIELDS), "runtime registry query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow):
        raise ValidationError("runtime registry query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


def _row(resource: str, key: str, value: Any, address: str, state: str, accepted: bool, ordinal: int) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "key": key, "value": value, "address": address, "state": state, "accepted": accepted, "row_address": ROW_PREFIX + ":pending"}
    provisional = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow(**body)
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow(**(body | {"row_address": address_row(provisional)}))


def _all_rows(value: registry_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry) -> tuple[HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow, ...]:
    value = registry_model.verify_registry(value)
    rows: list[HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow] = []
    for field in registry_model.SUMMARY_FIELDS:
        rows.append(_row("summary", field, getattr(value.summary, field), value.summary.content_address, value.state, value.accepted, len(rows) + 1))
    for item in value.entries:
        rows.append(_row("entries", item.runtime_id, {"runtime_address": item.runtime_address, "runtime_version": item.runtime_version, "execution_id": item.execution_id, "execution_address": item.execution_address, "execution_audit_address": item.execution_audit_address, "query_address": item.query_address, "query_audit_address": item.query_audit_address, "state": item.state, "accepted": item.accepted}, item.content_address, item.state, item.accepted, len(rows) + 1))
    for item in value.entries:
        rows.append(_row("runtimes", item.runtime_id, {"runtime_id": item.runtime_id, "runtime_address": item.runtime_address, "execution_id": item.execution_id, "state": item.state, "accepted": item.accepted}, item.runtime_address, item.state, item.accepted, len(rows) + 1))
    for state in STATES:
        count = sum(item.state == state for item in value.entries)
        rows.append(_row("states", state, {"state": state, "count": count}, value.summary.content_address, state, state == "ready", len(rows) + 1))
    for key, count in (("accepted", value.accepted_count), ("ready", value.ready_count), ("blocked", value.blocked_count)):
        rows.append(_row("readiness", key, {"key": key, "count": count, "entry_count": value.entry_count}, value.summary.content_address, value.state, value.accepted, len(rows) + 1))
    for key, address in (("registry", value.content_address), ("manifest", value.manifest.content_address), ("entries", value.manifest.artifact_addresses[0]), ("summary", value.summary.content_address)):
        rows.append(_row("addresses", key, {"address": address}, address, value.state, value.accepted, len(rows) + 1))
    for key, bound in (("entry_count", value.entry_count), ("max_entries", registry_model.MAX_ENTRIES), ("file_count", len(registry_model.FILES)), ("files", list(registry_model.FILES))):
        rows.append(_row("bounds", key, bound, value.manifest.content_address, value.state, value.accepted, len(rows) + 1))
    return tuple(rows)


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, registry_id: str, registry_address: str, resources: Sequence[str], state_filter: str, key_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "runtime registry query ID")
        self.registry_id = _label(registry_id, "runtime registry query registry ID")
        self.registry_address = _address(registry_address, "runtime registry query registry address", registry_model.REGISTRY_PREFIX)
        self.resources = tuple(_label(item, "runtime registry query resource") for item in _sequence(resources, "runtime registry query resources", len(RESOURCES)))
        if len(self.resources) != len(set(self.resources)) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(item for item in RESOURCES if item in self.resources):
            raise ValidationError("runtime registry query resources are unsupported, duplicated, or unordered")
        self.state_filter = _text(state_filter, "runtime registry query state filter", required=False)
        if self.state_filter not in ("",) + STATES:
            raise ValidationError("runtime registry query state filter is unsupported")
        self.key_filter = _text(key_filter, "runtime registry query key filter", 512)
        self.text_filter = _text(text_filter, "runtime registry query text filter", MAX_TEXT)
        self.offset = _count(offset, "runtime registry query offset", 1_000_000)
        self.limit = _count(limit, "runtime registry query limit", MAX_LIMIT, lower=1)
        self.rows = tuple(item if isinstance(item, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow) else HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow.from_mapping(item) for item in _sequence(rows, "runtime registry query rows", MAX_LIMIT))
        self.total_count = _count(total_count, "runtime registry query total count", 1_000_000)
        self.returned_count = _count(returned_count, "runtime registry query returned count", MAX_LIMIT)
        self.truncated = _bool(truncated, "runtime registry query truncation")
        self.content_address = _address(content_address, "runtime registry query address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.returned_count or self.returned_count != len(self.rows) or self.truncated != (self.offset + self.returned_count < self.offset + self.total_count) or tuple(item.ordinal for item in self.rows) != tuple(range(1, len(self.rows) + 1)):
            raise ValidationError("runtime registry query counts or ordinals do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry query crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("runtime registry query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "registry_id": self.registry_id, "registry_address": self.registry_address, "resources": self.resources, "state_filter": self.state_filter, "key_filter": self.key_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        """Return the bounded query metadata used by compact CLI/API views."""
        return {field: self.to_dict()[field] for field in ("query_id", "registry_id", "registry_address", "resources", "state_filter", "key_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery:
        value = _mapping(value, "runtime registry query")
        _strict(value, set(cls.FIELDS), "runtime registry query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery):
        raise ValidationError("runtime registry query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def query_registry(value: registry_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry, *, resources: Sequence[str] | None = None, state: str = "", key: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT, query_id: str = DEFAULT_QUERY_ID) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery:
    value = registry_model.verify_registry(value)
    selected_resources = tuple(resources if resources is not None else RESOURCES)
    if len(selected_resources) != len(set(selected_resources)) or any(item not in RESOURCES for item in selected_resources) or selected_resources != tuple(item for item in RESOURCES if item in selected_resources):
        raise ValidationError("runtime registry query resources are unsupported, duplicated, or unordered")
    if state not in ("",) + STATES:
        raise ValidationError("runtime registry query state is unsupported")
    key = _text(key, "runtime registry query key", 512)
    text = _text(text, "runtime registry query text", MAX_TEXT)
    offset = _count(offset, "runtime registry query offset", 1_000_000)
    limit = _count(limit, "runtime registry query limit", MAX_LIMIT, lower=1)
    selected = []
    for row in _all_rows(value):
        if row.resource not in selected_resources or (state and row.state != state) or (key and row.key != key):
            continue
        if text and text.casefold() not in canonical_json(row.to_dict()).casefold():
            continue
        selected.append(row)
    total_count = len(selected)
    page = selected[offset:offset + limit]
    rows = tuple(_row(row.resource, row.key, row.value, row.address, row.state, row.accepted, ordinal) for ordinal, row in enumerate(page, 1))
    body = {"query_id": query_id, "registry_id": value.registry_id, "registry_address": value.content_address, "resources": selected_resources, "state_filter": state, "key_filter": key, "text_filter": text, "offset": offset, "limit": limit, "total_count": total_count, "returned_count": len(rows), "truncated": offset + len(rows) < total_count, "rows": rows, "content_address": QUERY_PREFIX + ":pending"}
    provisional = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery(**body)
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery:
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery.from_mapping(value)


def query_json(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery) -> str:
    return canonical_json(HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery) -> str:
    value = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery.from_mapping(value.to_dict())
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for row in value.rows:
        writer.writerow((row.ordinal, row.resource, row.key, json.dumps(row.value, ensure_ascii=False, sort_keys=True), row.address, row.state, row.accepted, row.row_address))
    return output.getvalue()


def render_query_markdown(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery) -> str:
    value = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery.from_mapping(value.to_dict())
    lines = ["# History-Diff Archive Transfer Recovery Execution Runtime Registry Query", "", f"- Registry: `{value.registry_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.total_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | key | state | accepted |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.key}` | `{row.state}` | `{row.accepted}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "row_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "registry_id": {"type": "string"}, "registry_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "state_filter": {"enum": ["", *STATES]}, "key_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "states": STATES, "max_limit": MAX_LIMIT, "features": ("summary entry runtime state readiness address and bounds resources", "state key and text filters", "deterministic pagination", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryRow", "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery", "address_row", "address_query", "query_registry", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
