"""Bounded inspection query for execution-ledger history-diff archives."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = archive_model.VERSION + "-query-v1"
BOUNDARY = archive_model.BOUNDARY + "_query"
QUERY_PREFIX = archive_model.ARCHIVE_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = "execution-ledger-runtime-registry-history-diff-archive-query"
RESOURCES = ("summary", "artifacts", "members", "addresses", "bounds", "nested", "receipts", "latest")
MAX_LIMIT = 256
MAX_QUERY_ITEMS = len(archive_model.EMBEDDED_FILES) * 6 + 32
ROW_FIELDS = ("ordinal", "resource", "key", "value", "address", "row_address")
QUERY_FIELDS = ("version", "boundary", "query_id", "archive_id", "archive_address", "resources", "key", "text", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096, required=True)
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return archive_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, key: str, value: Any, address: str, row_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff archive query row ordinal", MAX_QUERY_ITEMS)
        self.resource = _label(resource, "history diff archive query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("history diff archive query row resource is unsupported")
        self.key = _label(key, "history diff archive query row key")
        self.value = value
        if len(canonical_bytes(value)) > 32768 or not _public(value):
            raise ValidationError("history diff archive query row value crosses its public bound")
        self.address = _text(address, "history diff archive query row address", 4096, required=True)
        self.row_address = _address(row_address, "history diff archive query row address", ROW_PREFIX)
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive query row crosses its public boundary")
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("history diff archive query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history diff archive query row")
        _strict(value, set(cls.FIELDS), "history diff archive query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value):
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, version: str, boundary: str, query_id: str, archive_id: str, archive_address: str, resources: Sequence[str], key: str, text: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryRow], content_address: str) -> None:
        self.version = _text(version, "history diff archive query version", 2048, required=True)
        self.boundary = _text(boundary, "history diff archive query boundary", 2048, required=True)
        self.query_id = _label(query_id, "history diff archive query ID")
        self.archive_id = _label(archive_id, "history diff archive query archive ID")
        self.archive_address = _address(archive_address, "history diff archive query archive address", archive_model.ARCHIVE_PREFIX)
        selected = tuple(_label(item, "history diff archive query resource") for item in _sequence(resources, "history diff archive query resources", len(RESOURCES)))
        if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected) or selected != tuple(item for item in RESOURCES if item in selected):
            raise ValidationError("history diff archive query resources must preserve contract order")
        self.resources = selected
        self.key = _label(key, "history diff archive query key", required=False)
        self.text = _text(text, "history diff archive query text", required=False)
        self.offset = _count(offset, "history diff archive query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "history diff archive query limit", MAX_LIMIT)
        if self.limit < 1:
            raise ValidationError("history diff archive query limit must be positive")
        self.total_count = _count(total_count, "history diff archive query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "history diff archive query returned count", MAX_QUERY_ITEMS)
        self.truncated = bool(truncated)
        self.rows = tuple(row if isinstance(row, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryRow) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryRow.from_mapping(row) for row in _sequence(rows, "history diff archive query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "history diff archive query content address", QUERY_PREFIX)
        if self.version != VERSION or self.boundary != BOUNDARY or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.truncated != (self.offset + self.returned_count < self.total_count) or tuple(row.ordinal for row in self.rows) != tuple(range(self.offset, self.offset + self.returned_count)):
            raise ValidationError("history diff archive query does not replay its page")
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive query crosses its public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("history diff archive query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "query_id": self.query_id, "archive_id": self.archive_id, "archive_address": self.archive_address, "resources": self.resources, "key": self.key, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [row.to_dict() for row in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history diff archive query")
        _strict(value, set(cls.FIELDS), "history diff archive query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value):
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, key: str, value: Any, address: str):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryRow(ordinal, resource, key, value, address, ROW_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryRow(ordinal, resource, key, value, address, address_row(provisional))


def _all_rows(value: archive_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive) -> tuple[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryRow, ...]:
    rows: list[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryRow] = []
    for field, item in value.summary().items():
        rows.append(_row("summary", len(rows), field, item, value.content_address))
    for item in value.artifacts:
        rows.append(_row("artifacts", len(rows), str(item.index), item.to_dict(), item.hash))
    for index, name in enumerate(value.files):
        rows.append(_row("members", len(rows), str(index), name, value.content_address))
    for key, address in (("archive", value.content_address), ("diff", value.diff_address)):
        rows.append(_row("addresses", len(rows), key, address, address))
    for key, item in (("artifact-count", value.artifact_count), ("archive-size", value.archive_size), ("max-archive-bytes", archive_model.MAX_ARCHIVE_BYTES), ("max-member-bytes", archive_model.MAX_MEMBER_BYTES)):
        rows.append(_row("bounds", len(rows), key, item, value.content_address))
    if value.diff is not None:
        nested = value.diff.compact()
        for key in ("diff_id", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "accepted"):
            rows.append(_row("nested", len(rows), key, nested[key], value.diff_address))
    for item in value.artifacts:
        rows.append(_row("receipts", len(rows), str(item.index), {"name": item.name, "size": item.size, "hash": item.hash}, item.hash))
    latest = value.artifacts[-1]
    for key, item in (("index", latest.index), ("name", latest.name), ("size", latest.size), ("hash", latest.hash)):
        rows.append(_row("latest", len(rows), key, item, latest.hash))
    return tuple(rows)


def _matches(row, *, key: str, text: str) -> bool:
    return (not key or row.key == key) and (not text or text.casefold() in canonical_json(row.to_dict()).casefold())


def query_archive(value: archive_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive, *, resources: Sequence[str] | None = None, key: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT, query_id: str = DEFAULT_QUERY_ID):
    value = archive_model.verify_archive(value)
    selected = tuple(item for item in RESOURCES if resources is None or item in tuple(resources))
    if not selected:
        raise ValidationError("history diff archive query requires at least one resource")
    offset = _count(offset, "history diff archive query offset", MAX_QUERY_ITEMS)
    limit = _count(limit, "history diff archive query limit", MAX_LIMIT)
    if limit < 1:
        raise ValidationError("history diff archive query limit must be positive")
    selected_rows = tuple(row for row in _all_rows(value) if row.resource in selected and _matches(row, key=key, text=text))
    page = selected_rows[offset:offset + limit]
    rows = tuple(_row(row.resource, index, row.key, row.value, row.address) for index, row in enumerate(page, offset))
    body = {"version": VERSION, "boundary": BOUNDARY, "query_id": query_id, "archive_id": value.archive_id, "archive_address": value.content_address, "resources": selected, "key": key, "text": text, "offset": offset, "limit": limit, "total_count": len(selected_rows), "returned_count": len(rows), "truncated": offset + len(rows) < len(selected_rows), "rows": rows, "content_address": QUERY_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQuery(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQuery(**(body | {"content_address": address_query(provisional)}))


def verify_query(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQuery):
        raise ValidationError("history diff archive query verification requires a typed query")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQuery.from_mapping(value.to_dict())


def query_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQuery.from_mapping(value)


def query_json(value) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value) -> str:
    value = verify_query(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(row.to_dict() for row in value.rows)
    return stream.getvalue()


def render_query_markdown(value) -> str:
    value = verify_query(value)
    lines = ["# Execution-ledger registry history diff archive query", "", f"- Archive: `{value.archive_id}`", f"- Resources: {', '.join(value.resources)}", f"- Rows: `{value.returned_count}/{value.total_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | key |", "| ---: | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.key}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 0}, "resource": {"enum": list(RESOURCES)}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "row_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffArchiveQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "query_id": {"type": "string"}, "archive_id": {"type": "string"}, "archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "key": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "operations": ["query_archive", "verify_query", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["BOUNDARY", "DEFAULT_QUERY_ID", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQuery", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryRow", "address_query", "address_row", "capabilities", "query_archive", "query_csv", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema", "verify_query"]
