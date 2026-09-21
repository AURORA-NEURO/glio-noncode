"""Bounded query projections over diff-runtime admission registries."""
from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d397_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-query-v1"
BOUNDARY = registry_model.BOUNDARY + "_query"
QUERY_PREFIX = registry_model.REGISTRY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "entries", "diffs", "state", "readiness", "addresses", "bounds")
STATES = registry_model.STATES[1:]
MAX_ROWS = registry_model.MAX_ENTRIES * 8
MAX_LIMIT = 128
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "release_ready", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "registry_id", "registry_address", "resources", "runtime_id_filter", "state_filter", "readiness_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value): raise ValidationError(f"{field} must be bounded public text")
    return value
def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value: raise ValidationError(f"{field} must be a compact label")
    return value
def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"): return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")): raise ValidationError(f"{field} has the wrong address namespace")
    return value
def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum: raise ValidationError(f"{field} is outside its bound")
    return value
def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool): raise ValidationError(f"{field} must be boolean")
    return value
def _optional_bool(value: Any, field: str) -> bool | None:
    if value is not None and not isinstance(value, bool): raise ValidationError(f"{field} must be boolean or null")
    return value
def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)
def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ValidationError(f"{field} must be an object")
    return value
def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed: raise ValidationError(f"{field} contains unknown or missing fields")
def _public(value: Any) -> bool: return registry_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any: value.content_address = address_function(value); value._validate(); return value


class RegistryQueryRow:
    FIELDS = ROW_FIELDS
    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, release_ready: bool | None, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff runtime registry query row ordinal", MAX_ROWS, lower=1); self.resource = _label(resource, "diff runtime registry query resource"); self.item_id = _label(item_id, "diff runtime registry query row item ID"); self.key = _label(key, "diff runtime registry query row key")
        if state not in STATES: raise ValidationError("diff runtime registry query row state is unsupported")
        self.state = state; self.release_ready = _optional_bool(release_ready, "diff runtime registry query row readiness"); self.value = _text(value, "diff runtime registry query row value", 32768); self.text = _text(text, "diff runtime registry query row text", 32768); self.content_address = _address(content_address, "diff runtime registry query row address", ROW_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.resource not in RESOURCES: raise ValidationError("diff runtime registry query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address: raise ValidationError("diff runtime registry query row address does not replay")
        if not _public(self.to_dict()): raise ValidationError("diff runtime registry query row crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryQueryRow": value = _mapping(value, "diff runtime registry query row"); _strict(value, set(cls.FIELDS), "diff runtime registry query row"); return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryQueryRow) -> str:
    if not isinstance(value, RegistryQueryRow): raise ValidationError("diff runtime registry query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class RegistryQuery:
    FIELDS = QUERY_FIELDS
    def __init__(self, query_id: str, registry_id: str, registry_address: str, resources: Sequence[str], runtime_id_filter: str, state_filter: str, readiness_filter: bool | None, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[RegistryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "diff runtime registry query ID"); self.registry_id = _label(registry_id, "diff runtime registry query registry ID"); self.registry_address = _address(registry_address, "diff runtime registry query registry address", registry_model.REGISTRY_PREFIX); self.resources = tuple(_label(item, "diff runtime registry query resource") for item in _sequence(resources, "diff runtime registry query resources", len(RESOURCES))); self.runtime_id_filter = _text(runtime_id_filter, "diff runtime registry runtime ID filter", 512, required=False); self.state_filter = _text(state_filter, "diff runtime registry state filter", 64, required=False); self.readiness_filter = _optional_bool(readiness_filter, "diff runtime registry readiness filter"); self.text_filter = _text(text_filter, "diff runtime registry text filter", 512, required=False); self.offset = _count(offset, "diff runtime registry query offset", MAX_ROWS); self.limit = _count(limit, "diff runtime registry query limit", MAX_LIMIT, lower=1); self.total_count = _count(total_count, "diff runtime registry query total count", MAX_ROWS); self.returned_count = _count(returned_count, "diff runtime registry query returned count", MAX_ROWS); self.truncated = _bool(truncated, "diff runtime registry query truncation"); self.rows = tuple(item if isinstance(item, RegistryQueryRow) else RegistryQueryRow.from_mapping(_mapping(item, "diff runtime registry query row")) for item in _sequence(rows, "diff runtime registry query rows", MAX_ROWS)); self.content_address = _address(content_address, "diff runtime registry query address", QUERY_PREFIX); self._validate()
    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources): raise ValidationError("diff runtime registry query resources are unsupported or duplicated")
        if self.state_filter and self.state_filter not in STATES: raise ValidationError("diff runtime registry state filter is unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count or self.truncated != (self.offset + self.returned_count < self.total_count): raise ValidationError("diff runtime registry query counters do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)) or any(item.content_address != address_row(item) for item in self.rows): raise ValidationError("diff runtime registry query row order or addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address: raise ValidationError("diff runtime registry query address does not replay")
        if not _public(self.to_dict()): raise ValidationError("diff runtime registry query crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryQuery": value = _mapping(value, "diff runtime registry query"); _strict(value, set(cls.FIELDS), "diff runtime registry query"); return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryQuery) -> str:
    if not isinstance(value, RegistryQuery): raise ValidationError("diff runtime registry query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)
def _row(ordinal: int, resource: str, key: str, value: Any, *, state: str, readiness: bool | None = None) -> RegistryQueryRow:
    rendered = canonical_json(value); return RegistryQueryRow(ordinal, resource, f"{resource}:{key}", key, state, readiness, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")


def _rows(value: registry_model.RuntimeRegistry) -> tuple[RegistryQueryRow, ...]:
    raw: list[tuple[str, str, Any, str, bool | None]] = []
    def add(resource: str, key: str, item: Any, state: str, readiness: bool | None = None) -> None: raw.append((resource, key, item, state, readiness))
    for key in ("registry_id", "entry_count", "ready_count", "blocked_count", "accepted", "release_ready", "state"): add("summary", key, getattr(value, key), value.state, getattr(value, key) if isinstance(getattr(value, key), bool) else None)
    for item in value.entries: add("entries", item.runtime_id, item.to_dict(), item.state, item.release_ready)
    for item in value.entries: add("diffs", item.diff_id, {"runtime_id": item.runtime_id, "diff_address": item.diff_address, "item_count": item.item_count}, item.state, item.release_ready)
    for key, item in (("state", value.state), ("accepted", value.accepted), ("release_ready", value.release_ready)): add("state", key, item, value.state, item if isinstance(item, bool) else None)
    for key, item in (("release_ready", value.release_ready), ("ready_count", value.ready_count), ("blocked_count", value.blocked_count)): add("readiness", key, item, value.state, item if isinstance(item, bool) else None)
    for key, item in (("registry_address", value.content_address), ("entries_address", value.manifest.artifact_addresses[0]), ("summary_address", value.summary.content_address), ("manifest_address", value.manifest.content_address)): add("addresses", key, item, value.state)
    for key, item in (("max_entries", registry_model.MAX_ENTRIES), ("max_rows", MAX_ROWS), ("entry_count", value.entry_count)): add("bounds", key, item, value.state)
    return tuple(_row(index, resource, key, item, state=state, readiness=readiness) for index, (resource, key, item, state, readiness) in enumerate(raw, 1))


def query_registry(value: registry_model.RuntimeRegistry, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, runtime_id_filter: str = "", state_filter: str = "", readiness_filter: bool | None = None, text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> RegistryQuery:
    registry_model.verify_registry(value); selected = tuple(resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected): raise ValidationError("diff runtime registry query resources are unsupported or duplicated")
    if state_filter and state_filter not in STATES: raise ValidationError("diff runtime registry state filter is unsupported")
    rows = _rows(value); text_needle = text_filter.casefold(); runtime_needle = runtime_id_filter.casefold()
    filtered = tuple(item for item in rows if item.resource in selected and (not runtime_needle or runtime_needle in item.item_id.casefold() or runtime_needle in item.text.casefold()) and (not state_filter or item.state == state_filter) and (readiness_filter is None or item.release_ready == readiness_filter) and (not text_needle or text_needle in item.text.casefold()))
    offset = _count(offset, "diff runtime registry query offset", MAX_ROWS); limit = _count(limit, "diff runtime registry query limit", MAX_LIMIT, lower=1); page = filtered[offset:offset + limit]
    page = tuple(_seal(RegistryQueryRow(index, item.resource, item.item_id, item.key, item.state, item.release_ready, item.value, item.text, f"pending:{ROW_PREFIX}"), address_row) for index, item in enumerate(page, offset + 1))
    return _seal(RegistryQuery(query_id, value.registry_id, value.content_address, selected, runtime_id_filter, state_filter, readiness_filter, text_filter, offset, limit, len(filtered), len(page), offset + len(page) < len(filtered), page, f"pending:{QUERY_PREFIX}"), address_query)


def query_from_mapping(value: Mapping[str, Any]) -> RegistryQuery: return RegistryQuery.from_mapping(value)
def verify_query(value: RegistryQuery) -> RegistryQuery:
    if not isinstance(value, RegistryQuery): raise ValidationError("diff runtime registry query verification requires a typed query")
    value._validate(); return value
def query_json(value: RegistryQuery) -> str: return canonical_json(verify_query(value).to_dict())
def query_csv(value: RegistryQuery) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_query(value).rows); return output.getvalue()
def render_query_markdown(value: RegistryQuery) -> str:
    value = verify_query(value); lines = [f"# Diff runtime registry query {value.query_id}", "", f"- Registry: {value.registry_id}", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Ordinal | Resource | Key | State | Ready | Value |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.resource} | {item.key} | {item.state} | {item.release_ready if item.release_ready is not None else '—'} | {item.value.replace('|', '\\|')} |" for item in value.rows); return "\n".join(lines) + "\n"
def row_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistryQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "release_ready" else "string"} for field in ROW_FIELDS}}
def query_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistryQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {field: {"type": "array" if field in ("resources", "rows") else "integer" if field.endswith("count") or field in ("offset", "limit") else "boolean" if field in ("readiness_filter", "truncated") else "string"} for field in QUERY_FIELDS}, "$defs": {"row": row_schema()}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("summary entry diff state readiness address and bounds projections", "runtime identity state readiness and text filters", "bounded pagination", "canonical row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "RegistryQueryRow", "RegistryQuery", "address_row", "address_query", "query_registry", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
