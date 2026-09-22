"""Bounded query projections over runtime registry history diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d371_history_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "items", "added", "removed", "changed", "unchanged", "addresses", "bounds")
CHANGES = diff_model.CHANGES
MAX_ROWS = diff_model.MAX_ITEMS * 8
MAX_LIMIT = 128
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "change", "value", "text", "left_address", "right_address", "content_address")
QUERY_FIELDS = ("query_id", "diff_id", "registry_id", "diff_address", "resources", "change_filter", "key_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if not value:
        return value
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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
    return diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class DiffQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, change: str, value: str, text: str, left_address: str, right_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history diff query row ordinal", MAX_ROWS, lower=1)
        self.resource = _label(resource, "runtime registry history diff query resource")
        self.item_id = _label(item_id, "runtime registry history diff query row item ID")
        self.key = _label(key, "runtime registry history diff query row key")
        if change and change not in CHANGES:
            raise ValidationError("runtime registry history diff query row change is unsupported")
        self.change = change
        self.value = _text(value, "runtime registry history diff query row value", 32768)
        self.text = _text(text, "runtime registry history diff query row text", 32768)
        self.left_address = _address(left_address, "runtime registry history diff query row left address", required=False)
        self.right_address = _address(right_address, "runtime registry history diff query row right address", required=False)
        self.content_address = _address(content_address, "runtime registry history diff query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES:
            raise ValidationError("runtime registry history diff query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history diff query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffQueryRow":
        value = _mapping(value, "runtime registry history diff query row")
        _strict(value, set(cls.FIELDS), "runtime registry history diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DiffQueryRow) -> str:
    if not isinstance(value, DiffQueryRow):
        raise ValidationError("runtime registry history diff query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class DiffQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, diff_id: str, registry_id: str, diff_address: str, resources: Sequence[str], change_filter: str, key_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[DiffQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "runtime registry history diff query ID")
        self.diff_id = _label(diff_id, "runtime registry history diff query diff ID")
        self.registry_id = _label(registry_id, "runtime registry history diff query registry ID")
        self.diff_address = _address(diff_address, "runtime registry history diff query diff address", diff_model.DIFF_PREFIX)
        self.resources = tuple(_label(item, "runtime registry history diff query resource") for item in _sequence(resources, "runtime registry history diff query resources", len(RESOURCES)))
        self.change_filter = _text(change_filter, "runtime registry history diff query change filter", 64, required=False)
        self.key_filter = _text(key_filter, "runtime registry history diff query key filter", 512, required=False)
        self.text_filter = _text(text_filter, "runtime registry history diff query text filter", 512, required=False)
        self.offset = _count(offset, "runtime registry history diff query offset", MAX_ROWS)
        self.limit = _count(limit, "runtime registry history diff query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "runtime registry history diff query total count", MAX_ROWS)
        self.returned_count = _count(returned_count, "runtime registry history diff query returned count", MAX_ROWS)
        self.truncated = _bool(truncated, "runtime registry history diff query truncation")
        self.rows = tuple(item if isinstance(item, DiffQueryRow) else DiffQueryRow.from_mapping(_mapping(item, "runtime registry history diff query row")) for item in _sequence(rows, "runtime registry history diff query rows", MAX_ROWS))
        self.content_address = _address(content_address, "runtime registry history diff query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources):
            raise ValidationError("runtime registry history diff query resources are unsupported or duplicated")
        if self.change_filter and self.change_filter not in CHANGES:
            raise ValidationError("runtime registry history diff query change filter is unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count:
            raise ValidationError("runtime registry history diff query counters do not replay")
        if self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("runtime registry history diff query truncation does not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("runtime registry history diff query row ordinals do not replay")
        if any(item.content_address != address_row(item) for item in self.rows):
            raise ValidationError("runtime registry history diff query row addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history diff query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffQuery":
        value = _mapping(value, "runtime registry history diff query")
        _strict(value, set(cls.FIELDS), "runtime registry history diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DiffQuery) -> str:
    if not isinstance(value, DiffQuery):
        raise ValidationError("runtime registry history diff query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)


def _row(ordinal: int, resource: str, key: str, value: Any, *, change: str = "", left_address: str = "", right_address: str = "") -> DiffQueryRow:
    rendered = canonical_json(value)
    return DiffQueryRow(ordinal, resource, f"{resource}:{key}", key, change, rendered, f"{resource} {key}={rendered}", left_address, right_address, f"pending:{ROW_PREFIX}")


def _rows(value: diff_model.HistoryDiff) -> tuple[DiffQueryRow, ...]:
    raw: list[tuple[str, str, Any, str, str, str]] = []
    def add(resource: str, key: str, item: Any, change: str = "", left: str = "", right: str = "") -> None:
        raw.append((resource, key, item, change, left, right))
    for key in ("diff_id", "registry_id", "left_history_id", "right_history_id", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "state_transition", "accepted"):
        add("summary", key, getattr(value, key))
    for item in value.items:
        add("items", item.identity, item.to_dict(), item.change, item.left_entry_address, item.right_entry_address)
    for change in CHANGES:
        add(change, "count", getattr(value, f"{change}_count"), change)
    for key, item in (("diff_address", value.content_address), ("manifest_address", value.manifest.content_address), ("items_address", value.manifest.artifact_addresses[0]), ("summary_address", value.summary.content_address), ("left_history_address", value.left_history_address), ("right_history_address", value.right_history_address)):
        add("addresses", key, item)
    for key, item in (("max_items", diff_model.MAX_ITEMS), ("max_rows", MAX_ROWS), ("item_count", value.item_count)):
        add("bounds", key, item)
    return tuple(_row(index, resource, key, item, change=change, left_address=left, right_address=right) for index, (resource, key, item, change, left, right) in enumerate(raw, 1))


def query_diff(value: diff_model.HistoryDiff, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, change_filter: str = "", key_filter: str = "", text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DiffQuery:
    diff_model.verify_diff(value)
    selected = tuple(resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected):
        raise ValidationError("runtime registry history diff query resources are unsupported or duplicated")
    if change_filter and change_filter not in CHANGES:
        raise ValidationError("runtime registry history diff query change filter is unsupported")
    rows = _rows(value)
    needle = text_filter.casefold(); key_needle = key_filter.casefold()
    filtered = tuple(item for item in rows if item.resource in selected and (not change_filter or item.change == change_filter) and (not key_needle or key_needle in item.key.casefold()) and (not needle or needle in item.text.casefold()))
    offset = _count(offset, "runtime registry history diff query offset", MAX_ROWS)
    limit = _count(limit, "runtime registry history diff query limit", MAX_LIMIT, lower=1)
    page = filtered[offset:offset + limit]
    page = tuple(_seal(DiffQueryRow(index, item.resource, item.item_id, item.key, item.change, item.value, item.text, item.left_address, item.right_address, f"pending:{ROW_PREFIX}"), address_row) for index, item in enumerate(page, offset + 1))
    return _seal(DiffQuery(query_id, value.diff_id, value.registry_id, value.content_address, selected, change_filter, key_filter, text_filter, offset, limit, len(filtered), len(page), offset + len(page) < len(filtered), page, f"pending:{QUERY_PREFIX}"), address_query)


def query_from_mapping(value: Mapping[str, Any]) -> DiffQuery:
    return DiffQuery.from_mapping(value)


def verify_query(value: DiffQuery) -> DiffQuery:
    if not isinstance(value, DiffQuery):
        raise ValidationError("runtime registry history diff query verification requires a typed query")
    value._validate()
    return value


def query_json(value: DiffQuery) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: DiffQuery) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_query(value).rows); return output.getvalue()


def render_query_markdown(value: DiffQuery) -> str:
    value = verify_query(value)
    lines = [f"# Runtime registry history diff query {value.query_id}", "", f"- Diff: {value.diff_id}", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Ordinal | Resource | Key | Change | Value |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.resource} | {item.key} | {item.change or '—'} | {item.value.replace('|', chr(92) + '|')} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "string"} for field in ROW_FIELDS}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {field: {"type": "array" if field in ("resources", "rows") else "integer" if field.endswith("count") or field in ("offset", "limit") else "boolean" if field == "truncated" else "string"} for field in QUERY_FIELDS}, "$defs": {"row": row_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "changes": CHANGES, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("summary and item projections", "change and text filtering", "bounded pagination", "canonical row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "CHANGES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "DiffQueryRow", "DiffQuery", "address_row", "address_query", "query_diff", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
