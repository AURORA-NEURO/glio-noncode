"""Bounded evidence queries for exact runtime-registry history diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history as history_model
from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "items", "added", "removed", "changed", "unchanged", "addresses", "bounds")
CHANGES = diff_model.CHANGES
MAX_LIMIT = 512
MAX_TEXT = 4096
ROW_FIELDS = ("ordinal", "resource", "key", "value", "address", "change", "left_address", "right_address", "row_address")
QUERY_FIELDS = ("query_id", "diff_id", "diff_address", "resources", "change_filter", "key_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True, allow_pending: bool = False) -> str:
    value = _text(value, field, required=required)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if value and (":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":"))):
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
    return diff_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow:
    """One addressed row in a bounded history-diff projection."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, key: str, value: Any, address: str, change: str, left_address: str, right_address: str, row_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history diff query row ordinal", MAX_LIMIT, lower=1)
        if resource not in RESOURCES:
            raise ValidationError("runtime registry history diff query row resource is unsupported")
        self.resource = resource
        self.key = _label(key, "runtime registry history diff query row key")
        if len(canonical_json(value).encode("utf-8")) > 16384:
            raise ValidationError("runtime registry history diff query row value is too large")
        self.value = json.loads(canonical_json(value))
        self.address = _address(address, "runtime registry history diff query row address")
        if change and change not in CHANGES:
            raise ValidationError("runtime registry history diff query row change is unsupported")
        self.change = _label(change, "runtime registry history diff query row change", required=False)
        self.left_address = _address(left_address, "runtime registry history diff query row left address", history_model.ENTRY_PREFIX, required=False)
        self.right_address = _address(right_address, "runtime registry history diff query row right address", history_model.ENTRY_PREFIX, required=False)
        self.row_address = _address(row_address, "runtime registry history diff query row address", ROW_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff query row crosses the public boundary")
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("runtime registry history diff query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow:
        value = _mapping(value, "runtime registry history diff query row")
        _strict(value, set(cls.FIELDS), "runtime registry history diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow):
        raise ValidationError("runtime registry history diff query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


def _row(resource: str, key: str, value: Any, address: str, change: str, left_address: str, right_address: str, ordinal: int) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "key": key, "value": value, "address": address, "change": change, "left_address": left_address, "right_address": right_address, "row_address": ROW_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow(**(body | {"row_address": address_row(provisional)}))


def _all_rows(value: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> tuple[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow, ...]:
    value = diff_model.verify_diff(value)
    rows: list[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow] = []
    for field in diff_model.SUMMARY_FIELDS:
        rows.append(_row("summary", field, getattr(value.summary, field), value.summary.content_address, "", "", "", len(rows) + 1))
    for item in value.items:
        rows.append(_row("items", item.identity, item.to_dict(), item.content_address, item.change, item.left_entry_address, item.right_entry_address, len(rows) + 1))
    for change in CHANGES:
        rows.append(_row(change, change, {"change": change, "count": sum(item.change == change for item in value.items)}, value.content_address, change, "", "", len(rows) + 1))
    addresses = (("diff", value.content_address), ("manifest", value.manifest.content_address), ("items", diff_model.address_items(value.items)), ("summary", value.summary.content_address), ("left", value.left_history_address), ("right", value.right_history_address))
    for key, address in addresses:
        rows.append(_row("addresses", key, {"address": address}, address or value.content_address, "", "", "", len(rows) + 1))
    for key, bound in (("item_count", value.item_count), ("max_items", diff_model.MAX_ITEMS), ("file_count", len(diff_model.FILES)), ("files", list(diff_model.FILES))):
        rows.append(_row("bounds", key, bound, value.manifest.content_address, "", "", "", len(rows) + 1))
    return tuple(rows)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery:
    """Deterministic, filterable, paginated history-diff query result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, diff_id: str, diff_address: str, resources: Sequence[str], change_filter: str, key_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "runtime registry history diff query ID")
        self.diff_id = _label(diff_id, "runtime registry history diff query diff ID")
        self.diff_address = _address(diff_address, "runtime registry history diff query diff address", diff_model.DIFF_PREFIX)
        self.resources = tuple(_label(item, "runtime registry history diff query resource") for item in _sequence(resources, "runtime registry history diff query resources", len(RESOURCES)))
        if len(self.resources) != len(set(self.resources)) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(item for item in RESOURCES if item in self.resources):
            raise ValidationError("runtime registry history diff query resources are unsupported, duplicated, or unordered")
        if change_filter not in ("",) + CHANGES:
            raise ValidationError("runtime registry history diff query change filter is unsupported")
        self.change_filter = change_filter
        self.key_filter = _text(key_filter, "runtime registry history diff query key filter", 512)
        self.text_filter = _text(text_filter, "runtime registry history diff query text filter")
        self.offset = _count(offset, "runtime registry history diff query offset", 1_000_000)
        self.limit = _count(limit, "runtime registry history diff query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "runtime registry history diff query total count", 1_000_000)
        self.returned_count = _count(returned_count, "runtime registry history diff query returned count", MAX_LIMIT)
        self.truncated = _bool(truncated, "runtime registry history diff query truncation")
        self.rows = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow.from_mapping(item) for item in _sequence(rows, "runtime registry history diff query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "runtime registry history diff query address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.returned_count or self.returned_count != len(self.rows) or self.truncated != (self.offset + self.returned_count < self.offset + self.total_count) or tuple(item.ordinal for item in self.rows) != tuple(range(1, len(self.rows) + 1)):
            raise ValidationError("runtime registry history diff query counts or ordinals do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff query crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("runtime registry history diff query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "diff_id": self.diff_id, "diff_address": self.diff_address, "resources": self.resources, "change_filter": self.change_filter, "key_filter": self.key_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery:
        value = _mapping(value, "runtime registry history diff query")
        _strict(value, set(cls.FIELDS), "runtime registry history diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery):
        raise ValidationError("runtime registry history diff query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def query_history_diff(value: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff, *, resources: Sequence[str] | None = None, change: str = "", key: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT, query_id: str = DEFAULT_QUERY_ID) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery:
    value = diff_model.verify_diff(value)
    selected = tuple(resources) if resources is not None else RESOURCES
    rows = _all_rows(value)
    if selected != RESOURCES:
        rows = tuple(row for row in rows if row.resource in selected)
    if change:
        rows = tuple(row for row in rows if row.change == change)
    if key:
        rows = tuple(row for row in rows if key in row.key)
    if text:
        rows = tuple(row for row in rows if text.casefold() in canonical_json(row.to_dict()).casefold())
    total_count = len(rows)
    page = rows[offset:offset + limit]
    projected = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow(item.ordinal, item.resource, item.key, item.value, item.address, item.change, item.left_address, item.right_address, item.row_address) for item in page)
    projected = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow(index, item.resource, item.key, item.value, item.address, item.change, item.left_address, item.right_address, ROW_PREFIX + ":pending") for index, item in enumerate(projected, 1))
    final_rows: list[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow] = []
    for item in projected:
        body = item.to_dict()
        final_rows.append(ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow(**(body | {"row_address": address_row(item)})))
    body = {"query_id": query_id, "diff_id": value.diff_id, "diff_address": value.content_address, "resources": selected, "change_filter": change, "key_filter": key, "text_filter": text, "offset": offset, "limit": limit, "total_count": total_count, "returned_count": len(final_rows), "truncated": offset + len(final_rows) < offset + total_count, "rows": tuple(final_rows), "content_address": QUERY_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery(**(body | {"content_address": address_query(provisional)}))


def verify_query(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery):
        raise ValidationError("runtime registry history diff query verification requires a typed query")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery.from_mapping(value.to_dict())


def query_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery.from_mapping(value)


def query_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery) -> str:
    value = verify_query(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in ROW_FIELDS) for item in value.rows)
    return output.getvalue()


def render_query_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery) -> str:
    value = verify_query(value)
    lines = ["# Federation runtime-registry history diff query", "", f"- Diff: {value.diff_id}", f"- Resources: {', '.join(value.resources)}", f"- Results: {value.returned_count}/{value.total_count}", f"- Address: {value.content_address}", "", "| # | resource | key | change | address |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.resource} | {item.key} | {item.change or '—'} | {item.address} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationRuntimeRegistryHistoryDiffQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "change": {"enum": [""] + list(CHANGES)}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "row_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationRuntimeRegistryHistoryDiffQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "change_filter": {"enum": [""] + list(CHANGES)}, "key_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "changes": list(CHANGES), "max_limit": MAX_LIMIT, "operations": ["query", "verify", "csv", "markdown", "schema", "capabilities"]}
