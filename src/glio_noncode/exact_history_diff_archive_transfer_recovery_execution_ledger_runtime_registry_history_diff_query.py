"""Bounded inspection queries for execution-ledger runtime registry history diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = "execution-ledger-runtime-registry-history-diff-query"
RESOURCES = ("summary", "items", "added", "removed", "changed", "unchanged", "addresses", "bounds", "latest")
CHANGES = diff_model.CHANGES
MAX_LIMIT = 256
MAX_QUERY_ITEMS = diff_model.MAX_ITEMS * 6 + 64
ROW_FIELDS = ("ordinal", "resource", "key", "value", "address", "change", "left_entry_address", "right_entry_address", "row_address")
QUERY_FIELDS = ("version", "boundary", "query_id", "diff_id", "diff_address", "resources", "change", "key", "text", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 4096, required=True)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, key: str, value: Any, address: str, change: str, left_entry_address: str, right_entry_address: str, row_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history diff query row ordinal", MAX_QUERY_ITEMS,)
        self.resource = _label(resource, "registry history diff query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("registry history diff query row resource is unsupported")
        self.key = _label(key, "registry history diff query row key")
        self.value = value
        if len(canonical_bytes(value)) > 32768 or not _public(value):
            raise ValidationError("registry history diff query row value crosses its public bound")
        self.address = _address(address, "registry history diff query row address")
        self.change = _label(change, "registry history diff query row change")
        self.left_entry_address = _text(left_entry_address, "registry history diff query row baseline address", required=False)
        self.right_entry_address = _text(right_entry_address, "registry history diff query row candidate address", required=False)
        self.row_address = _address(row_address, "registry history diff query row content address", ROW_PREFIX, allow_pending=True)
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff query row crosses the public boundary")
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("registry history diff query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff query row")
        _strict(value, set(cls.FIELDS), "registry history diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow) -> str:
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, version: str, boundary: str, query_id: str, diff_id: str, diff_address: str, resources: Sequence[str], change: str, key: str, text: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow], content_address: str) -> None:
        self.version = _text(version, "registry history diff query version", 1024, required=True)
        self.boundary = _text(boundary, "registry history diff query boundary", 1024, required=True)
        self.query_id = _label(query_id, "registry history diff query ID")
        self.diff_id = _label(diff_id, "registry history diff query diff ID")
        self.diff_address = _address(diff_address, "registry history diff query diff address", diff_model.DIFF_PREFIX)
        selected = tuple(_label(item, "registry history diff query resource") for item in _sequence(resources, "registry history diff query resources", len(RESOURCES)))
        if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected) or selected != tuple(item for item in RESOURCES if item in selected):
            raise ValidationError("registry history diff query resources must be unique and preserve resource order")
        self.resources = selected
        self.change = _label(change, "registry history diff query change", required=False)
        if self.change and self.change not in CHANGES:
            raise ValidationError("registry history diff query change is unsupported")
        self.key = _label(key, "registry history diff query key", required=False)
        self.text = _text(text, "registry history diff query text", required=False)
        self.offset = _count(offset, "registry history diff query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "registry history diff query limit", MAX_LIMIT,)
        if self.limit < 1:
            raise ValidationError("registry history diff query limit must be positive")
        self.total_count = _count(total_count, "registry history diff query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "registry history diff query returned count", MAX_QUERY_ITEMS)
        self.truncated = _bool(truncated, "registry history diff query truncated")
        self.rows = tuple(row if isinstance(row, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow.from_mapping(row) for row in _sequence(rows, "registry history diff query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "registry history diff query address", QUERY_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.truncated != (self.offset + self.returned_count < self.total_count) or tuple(row.ordinal for row in self.rows) != tuple(range(self.offset, self.offset + self.returned_count)):
            raise ValidationError("registry history diff query does not replay its page")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff query crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("registry history diff query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "query_id": self.query_id, "diff_id": self.diff_id, "diff_address": self.diff_address, "resources": self.resources, "change": self.change, "key": self.key, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [row.to_dict() for row in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff query")
        _strict(value, set(cls.FIELDS), "registry history diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, key: str, value: Any, address: str, change: str, left_entry_address: str = "", right_entry_address: str = ""):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow(ordinal, resource, key, value, address, change, left_entry_address, right_entry_address, ROW_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow(ordinal, resource, key, value, address, change, left_entry_address, right_entry_address, address_row(provisional))


def _all_rows(value: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff) -> tuple[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow, ...]:
    rows: list[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow] = []
    summary = value.summary.to_dict()
    for field in diff_model.SUMMARY_FIELDS:
        rows.append(_row("summary", len(rows), field, summary[field], value.summary.content_address, "summary", value.left_history_address, value.right_history_address))
    for item in value.items:
        rows.append(_row("items", len(rows), item.identity, item.to_dict(), item.content_address, item.change, item.left_entry_address, item.right_entry_address))
    for change in diff_model.CHANGES:
        for item in value.items:
            if item.change == change:
                rows.append(_row(change, len(rows), item.identity, item.to_dict(), item.content_address, change, item.left_entry_address, item.right_entry_address))
    addresses = (("diff", value.content_address), ("baseline", value.left_history_address), ("candidate", value.right_history_address), ("items", diff_model.address_items(value.items)), ("summary", value.summary.content_address), ("manifest", value.manifest.manifest_address))
    for key, address in addresses:
        rows.append(_row("addresses", len(rows), key, address, address, "addresses"))
    bounds = (("item-count", value.item_count), ("max-items", diff_model.MAX_ITEMS), ("added-count", value.added_count), ("removed-count", value.removed_count), ("changed-count", value.changed_count), ("unchanged-count", value.unchanged_count))
    for key, item in bounds:
        rows.append(_row("bounds", len(rows), key, item, value.summary.content_address, "bounds"))
    latest = value.items[-1] if value.items else None
    latest_values = (("ordinal", latest.ordinal if latest else 0), ("change", latest.change if latest else ""), ("left-entry-address", latest.left_entry_address if latest else ""), ("right-entry-address", latest.right_entry_address if latest else ""), ("direction", value.direction))
    for key, item in latest_values:
        rows.append(_row("latest", len(rows), key, item, latest.content_address if latest else value.content_address, latest.change if latest else "latest", latest.left_entry_address if latest else "", latest.right_entry_address if latest else ""))
    return tuple(rows)


def _matches(row: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow, *, change: str, key: str, text: str) -> bool:
    if change and row.change != change:
        return False
    if key and row.key != key:
        return False
    return not text or text.casefold() in canonical_json(row.to_dict()).casefold()


def query_history_diff(value: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff, *, resources: Sequence[str] | None = None, change: str = "", key: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT, query_id: str = DEFAULT_QUERY_ID):
    value = diff_model.verify_diff(value)
    selected = tuple(item for item in RESOURCES if resources is None or item in tuple(resources))
    if not selected:
        raise ValidationError("registry history diff query requires at least one resource")
    if change and change not in CHANGES:
        raise ValidationError("registry history diff query change is unsupported")
    offset = _count(offset, "registry history diff query offset", MAX_QUERY_ITEMS)
    limit = _count(limit, "registry history diff query limit", MAX_LIMIT)
    if limit < 1:
        raise ValidationError("registry history diff query limit must be positive")
    selected_rows = tuple(row for row in _all_rows(value) if row.resource in selected and _matches(row, change=change, key=key, text=text))
    page = selected_rows[offset:offset + limit]
    rows = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow(index, row.resource, row.key, row.value, row.address, row.change, row.left_entry_address, row.right_entry_address, ROW_PREFIX + ":pending") for index, row in enumerate(page, offset))
    rows = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow(index, row.resource, row.key, row.value, row.address, row.change, row.left_entry_address, row.right_entry_address, address_row(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow(index, row.resource, row.key, row.value, row.address, row.change, row.left_entry_address, row.right_entry_address, ROW_PREFIX + ":pending"))) for index, row in enumerate(page, offset))
    body = {"version": VERSION, "boundary": BOUNDARY, "query_id": query_id, "diff_id": value.diff_id, "diff_address": value.content_address, "resources": selected, "change": change, "key": key, "text": text, "offset": offset, "limit": limit, "total_count": len(selected_rows), "returned_count": len(rows), "truncated": offset + len(rows) < len(selected_rows), "rows": rows, "content_address": QUERY_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQuery(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQuery(**(body | {"content_address": address_query(provisional)}))


def verify_query(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQuery):
        raise ValidationError("registry history diff query verification requires a typed query")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQuery.from_mapping(value.to_dict())


def query_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQuery.from_mapping(value)


def query_json(value) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value) -> str:
    value = verify_query(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(row.to_dict()[field] for field in ROW_FIELDS) for row in value.rows)
    return output.getvalue()


def render_query_markdown(value) -> str:
    value = verify_query(value)
    lines = ["# Execution-ledger runtime registry history diff query", "", f"- Diff: {value.diff_id}", f"- Resources: {', '.join(value.resources)}", f"- Change filter: {value.change or 'all'}", f"- Rows: {value.returned_count}/{value.total_count}", f"- Address: {value.content_address}", "", "| # | resource | key | change | baseline | candidate |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | {row.resource} | {row.key} | {row.change} | {row.left_entry_address or '—'} | {row.right_entry_address or '—'} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 0}, "resource": {"enum": list(RESOURCES)}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "change": {"type": "string"}, "left_entry_address": {"type": "string"}, "right_entry_address": {"type": "string"}, "row_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "query_id": {"type": "string"}, "diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "change": {"enum": [""] + list(CHANGES)}, "key": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "changes": CHANGES, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "operations": ("query_history_diff", "verify_query", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "CHANGES", "MAX_LIMIT", "MAX_QUERY_ITEMS", "ROW_FIELDS", "QUERY_FIELDS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryRow", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQuery", "address_row", "address_query", "query_history_diff", "verify_query", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
