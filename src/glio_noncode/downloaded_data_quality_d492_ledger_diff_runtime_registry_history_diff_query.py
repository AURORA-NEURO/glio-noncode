"""Bounded projections and filters over D492 history comparisons."""
from __future__ import annotations

# ruff: noqa: E501, I001
import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any
from . import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "items", "changes", "direction", "addresses", "bounds")
CHANGES = diff_model.CHANGES
MAX_ROWS = diff_model.MAX_ITEMS * 8 + 64
MAX_LIMIT = 256
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "change", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "diff_id", "diff_address", "resources", "change_filter", "direction_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")

def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(c) < 32 and c not in "\n\t" for c in value): raise ValidationError(f"{field} must be bounded text")
    return value
def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(c.isspace() for c in value) or "/" in value or "\\" in value or '"' in value: raise ValidationError(f"{field} must be a compact label")
    return value
def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"): return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix and not value.startswith(prefix + ":")): raise ValidationError(f"{field} has the wrong namespace")
    return value
def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= maximum: raise ValidationError(f"{field} is outside its bound")
    return value
def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool): raise ValidationError(f"{field} must be boolean")
    return value
def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)
def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ValidationError(f"{field} must be an object")
    return value
def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed: raise ValidationError(f"{field} contains unknown or missing fields")
def _public(value: Any) -> bool: return diff_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value

class DiffQueryRow:
    FIELDS = ROW_FIELDS
    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, change: str, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "D492 row ordinal", MAX_ROWS, lower=1); self.resource = _label(resource, "D492 row resource"); self.item_id = _label(item_id, "D492 row item ID"); self.key = _label(key, "D492 row key")
        if change not in CHANGES and change not in diff_model.DIRECTIONS and change != "": raise ValidationError("D492 row change or direction is unsupported")
        self.change = change; self.value = _text(value, "D492 row value", 32768); self.text = _text(text, "D492 row text", 32768); self.content_address = _address(content_address, "D492 row address", ROW_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.resource not in RESOURCES: raise ValidationError("D492 row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address: raise ValidationError("D492 row address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D492 row crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffQueryRow":
        value = _mapping(value, "D492 query row"); _strict(value, set(cls.FIELDS), "D492 query row"); return cls(*(value[f] for f in cls.FIELDS))

def address_row(value: DiffQueryRow) -> str:
    if not isinstance(value, DiffQueryRow): raise ValidationError("D492 row addressing requires a typed row")
    return _address_for(value, ROW_PREFIX)

class DiffQuery:
    FIELDS = QUERY_FIELDS
    def __init__(self, query_id: str, diff_id: str, diff_address: str, resources: Sequence[str], change_filter: str, direction_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[DiffQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "D492 query ID"); self.diff_id = _label(diff_id, "D492 diff ID"); self.diff_address = _address(diff_address, "D492 query diff address", diff_model.DIFF_PREFIX); self.resources = tuple(_label(x, "D492 resource") for x in _sequence(resources, "D492 resources", len(RESOURCES))); self.change_filter = _text(change_filter, "D492 change filter", 64, required=False); self.direction_filter = _text(direction_filter, "D492 direction filter", 64, required=False); self.text_filter = _text(text_filter, "D492 text filter", 512, required=False); self.offset = _count(offset, "D492 offset", MAX_ROWS); self.limit = _count(limit, "D492 limit", MAX_LIMIT, lower=1); self.total_count = _count(total_count, "D492 total count", MAX_ROWS); self.returned_count = _count(returned_count, "D492 returned count", MAX_ROWS); self.truncated = _bool(truncated, "D492 truncation"); self.rows = tuple(x if isinstance(x, DiffQueryRow) else DiffQueryRow.from_mapping(_mapping(x, "D492 query row")) for x in _sequence(rows, "D492 rows", MAX_ROWS)); self.content_address = _address(content_address, "D492 query address", QUERY_PREFIX); self._validate()
    def _validate(self) -> None:
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(x not in RESOURCES for x in self.resources): raise ValidationError("D492 resources are unsupported or duplicated")
        if self.change_filter and self.change_filter not in CHANGES: raise ValidationError("D492 change filter is unsupported")
        if self.direction_filter and self.direction_filter not in diff_model.DIRECTIONS: raise ValidationError("D492 direction filter is unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count or self.truncated != (self.offset + self.returned_count < self.total_count): raise ValidationError("D492 query counts do not replay")
        if tuple(x.ordinal for x in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)) or any(x.content_address != address_row(x) for x in self.rows): raise ValidationError("D492 row order or address does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address: raise ValidationError("D492 query address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D492 query crosses the public boundary")
    def to_dict(self) -> dict[str, Any]:
        result = {field: getattr(self, field) for field in self.FIELDS[:-1]}
        result["resources"] = list(self.resources); result["rows"] = [x.to_dict() for x in self.rows]
        return result | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffQuery":
        value = _mapping(value, "D492 query"); _strict(value, set(cls.FIELDS), "D492 query"); return cls(*(value[f] for f in cls.FIELDS))

def address_query(value: DiffQuery) -> str:
    if not isinstance(value, DiffQuery): raise ValidationError("D492 query addressing requires a typed query")
    return _address_for(value, QUERY_PREFIX)

def _row(ordinal: int, resource: str, key: str, value: Any, change: str = "") -> DiffQueryRow:
    rendered = canonical_json(value); return DiffQueryRow(ordinal, resource, f"{resource}:{key}", key, change, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")

def _rows(value: diff_model.HistoryDiff) -> tuple[DiffQueryRow, ...]:
    raw: list[tuple[str, str, Any, str]] = []
    def add(resource: str, key: str, item: Any, change: str = "") -> None: raw.append((resource, key, item, change))
    for key in ("diff_id", "left_history_id", "right_history_id", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "accepted"):
        add("summary", key, getattr(value, key))
    for x in value.items: add("items", x.identity, x.to_dict(), x.change)
    for x in value.items:
        for field in x.changed_fields: add("changes", f"{x.identity}.{field}", {"left": x.left_snapshot.get(field), "right": x.right_snapshot.get(field)}, x.change)
    add("direction", "direction", value.direction, value.direction); add("direction", "state_transition", value.state_transition, value.direction)
    for key, item in (("diff_address", value.content_address), ("left_history_address", value.left_history_address), ("right_history_address", value.right_history_address), ("manifest_address", value.manifest.content_address), ("summary_address", value.summary.content_address), ("items_address", diff_model.address_items(value.items))): add("addresses", key, item)
    for key, item in (("max_items", diff_model.MAX_ITEMS), ("max_rows", MAX_ROWS), ("item_count", value.item_count)): add("bounds", key, item)
    return tuple(_row(i, resource, key, item, change) for i, (resource, key, item, change) in enumerate(raw, 1))

def query_diff(value: diff_model.HistoryDiff, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, change_filter: str = "", direction_filter: str = "", text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DiffQuery:
    diff_model.verify_diff(value); selected = tuple(resources)
    if not selected or any(x not in RESOURCES for x in selected) or len(set(selected)) != len(selected): raise ValidationError("D492 resources are unsupported or duplicated")
    if change_filter and change_filter not in CHANGES: raise ValidationError("D492 change filter is unsupported")
    if direction_filter and direction_filter not in diff_model.DIRECTIONS: raise ValidationError("D492 direction filter is unsupported")
    offset = _count(offset, "D492 offset", MAX_ROWS); limit = _count(limit, "D492 limit", MAX_LIMIT, lower=1); needle = text_filter.casefold()
    rows = tuple(x for x in _rows(value) if x.resource in selected and (not change_filter or x.change == change_filter) and (not direction_filter or (x.change == direction_filter or (x.resource == "direction" and x.value.strip('"') == direction_filter))) and (not needle or needle in x.text.casefold()))
    page = rows[offset:offset + limit]; typed = tuple(_seal(DiffQueryRow(i + 1, x.resource, x.item_id, x.key, x.change, x.value, x.text, f"pending:{ROW_PREFIX}"), address_row) for i, x in enumerate(page, offset))
    return _seal(DiffQuery(query_id, value.diff_id, value.content_address, selected, change_filter, direction_filter, text_filter, offset, limit, len(rows), len(typed), offset + len(typed) < len(rows), typed, f"pending:{QUERY_PREFIX}"), address_query)

def query_from_mapping(value: Mapping[str, Any]) -> DiffQuery: return DiffQuery.from_mapping(value)
def verify_query(value: DiffQuery) -> DiffQuery:
    if not isinstance(value, DiffQuery): raise ValidationError("D492 verification requires a typed query")
    value._validate(); return value
def query_json(value: DiffQuery) -> str: return canonical_json(verify_query(value).to_dict())
def query_csv(value: DiffQuery) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(x.to_dict() for x in verify_query(value).rows); return output.getvalue()
def render_query_markdown(value: DiffQuery) -> str:
    value = verify_query(value); lines = [f"# D492 query {value.query_id}", "", f"- Diff: {value.diff_id}", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Resource | Key | Change/direction | Value |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {x.resource} | {x.key} | {x.change} | {x.value} |" for x in value.rows); return "\n".join(lines) + "\n"
def row_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryDiffQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {f: {"type": "integer" if f == "ordinal" else "string"} for f in ROW_FIELDS}}
def query_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryDiffQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {f: {"type": "array" if f in ("resources", "rows") else "integer" if f.endswith("count") or f in ("offset", "limit") else "boolean" if f == "truncated" else "string"} for f in QUERY_FIELDS}, "$defs": {"row": row_schema()}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "changes": CHANGES, "directions": diff_model.DIRECTIONS, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("summary item change direction address and bounds projections", "change direction and text filters", "bounded pagination", "canonical row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}

__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "CHANGES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "DiffQueryRow", "DiffQuery", "address_row", "address_query", "query_diff", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
