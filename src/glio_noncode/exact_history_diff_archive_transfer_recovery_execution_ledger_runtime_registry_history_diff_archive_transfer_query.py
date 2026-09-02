"""Bounded query projections for execution-ledger history-diff archive transfers."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer as transfer_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = transfer_model.VERSION + "-query-v1"
BOUNDARY = transfer_model.BOUNDARY + "_query"
QUERY_PREFIX = transfer_model.TRANSFER_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = "execution-ledger-runtime-registry-history-diff-archive-transfer-query"
RESOURCES = ("summary", "chunks", "addresses", "bounds", "progress", "received", "missing", "receipts", "latest")
MAX_LIMIT = 256
MAX_QUERY_ITEMS = transfer_model.MAX_CHUNKS * 5 + 64
ROW_FIELDS = ("ordinal", "resource", "key", "value", "address", "row_address")
QUERY_FIELDS = ("version", "boundary", "query_id", "transfer_id", "archive_id", "transfer_address", "archive_address", "resources", "key", "text", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return transfer_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, key: str, value: Any, address: str, row_address: str) -> None:
        self.ordinal = _count(ordinal, "transfer query row ordinal", MAX_QUERY_ITEMS)
        self.resource = _label(resource, "transfer query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("transfer query row resource is unsupported")
        self.key = _label(key, "transfer query row key")
        self.value = value
        if len(canonical_bytes(value)) > 32768 or not _public(value):
            raise ValidationError("transfer query row value crosses its public bound")
        self.address = _text(address, "transfer query row address", 8192)
        self.row_address = _address(row_address, "transfer query row address", ROW_PREFIX, allow_pending=True)
        if not _public(self.to_dict()):
            raise ValidationError("transfer query row crosses its public boundary")
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("transfer query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "transfer query row")
        _strict(value, set(cls.FIELDS), "transfer query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value):
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, version: str, boundary: str, query_id: str, transfer_id: str, archive_id: str, transfer_address: str, archive_address: str, resources: Sequence[str], key: str, text: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryRow], content_address: str) -> None:
        self.version = _text(version, "transfer query version")
        self.boundary = _text(boundary, "transfer query boundary")
        self.query_id = _label(query_id, "transfer query ID")
        self.transfer_id = _label(transfer_id, "transfer query transfer ID")
        self.archive_id = _label(archive_id, "transfer query archive ID")
        self.transfer_address = _address(transfer_address, "transfer query transfer address", transfer_model.TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "transfer query archive address", transfer_model.archive_model.ARCHIVE_PREFIX)
        selected = tuple(_label(item, "transfer query resource") for item in _sequence(resources, "transfer query resources", len(RESOURCES)))
        if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected) or selected != tuple(item for item in RESOURCES if item in selected):
            raise ValidationError("transfer query resources must preserve contract order")
        self.resources = selected
        self.key = _label(key, "transfer query key", required=False)
        self.text = _text(text, "transfer query text", required=False)
        self.offset = _count(offset, "transfer query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "transfer query limit", MAX_LIMIT)
        if self.limit < 1:
            raise ValidationError("transfer query limit must be positive")
        self.total_count = _count(total_count, "transfer query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "transfer query returned count", MAX_QUERY_ITEMS)
        if not isinstance(truncated, bool):
            raise ValidationError("transfer query truncated must be boolean")
        self.truncated = truncated
        self.rows = tuple(row if isinstance(row, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryRow) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryRow.from_mapping(row) for row in _sequence(rows, "transfer query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "transfer query content address", QUERY_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.truncated != (self.offset + self.returned_count < self.total_count) or tuple(row.ordinal for row in self.rows) != tuple(range(self.offset, self.offset + self.returned_count)):
            raise ValidationError("transfer query does not replay its page")
        if not _public(self.to_dict()):
            raise ValidationError("transfer query crosses its public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("transfer query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "query_id": self.query_id, "transfer_id": self.transfer_id, "archive_id": self.archive_id, "transfer_address": self.transfer_address, "archive_address": self.archive_address, "resources": self.resources, "key": self.key, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [row.to_dict() for row in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "transfer query")
        _strict(value, set(cls.FIELDS), "transfer query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value):
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, key: str, value: Any, address: str):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryRow(ordinal, resource, key, value, address, ROW_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryRow(ordinal, resource, key, value, address, address_row(provisional))


def _progress(value):
    try:
        return transfer_model._progress_from_parts(value, value.payload_bytes())
    except ValidationError:
        return transfer_model._progress_from_parts(value, {})


def _all_rows(value):
    rows: list[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryRow] = []
    progress = _progress(value)
    for field, item in value.summary().items():
        rows.append(_row("summary", len(rows), field, item, value.content_address))
    for chunk in value.chunks:
        rows.append(_row("chunks", len(rows), str(chunk.index), chunk.to_dict(), chunk.content_address))
    for key, address in (("transfer", value.content_address), ("archive", value.archive_address)):
        rows.append(_row("addresses", len(rows), key, address, address))
    for key, item in (("archive-size", value.archive_size), ("chunk-size", value.chunk_size), ("chunk-count", value.chunk_count), ("max-chunks", transfer_model.MAX_CHUNKS), ("max-transfer-bytes", transfer_model.MAX_TRANSFER_BYTES)):
        rows.append(_row("bounds", len(rows), key, item, value.content_address))
    for key, item in progress.to_dict().items():
        rows.append(_row("progress", len(rows), key, item, progress.content_address))
    for index in progress.received_indices:
        chunk = value.chunks[index]
        rows.append(_row("received", len(rows), str(index), {"index": index, "offset": chunk.offset, "size": chunk.size, "address": chunk.content_address}, chunk.content_address))
    for index in progress.missing_indices:
        chunk = value.chunks[index]
        rows.append(_row("missing", len(rows), str(index), {"index": index, "offset": chunk.offset, "size": chunk.size}, value.content_address))
    for chunk in value.chunks:
        rows.append(_row("receipts", len(rows), str(chunk.index), chunk.to_dict(), chunk.content_address))
    latest = value.chunks[-1]
    for key, item in (("index", latest.index), ("offset", latest.offset), ("size", latest.size), ("address", latest.content_address)):
        rows.append(_row("latest", len(rows), key, item, latest.content_address))
    return tuple(rows)


def _matches(row, *, key: str, text: str) -> bool:
    return (not key or row.key == key) and (not text or text.casefold() in canonical_json(row.to_dict()).casefold())


def query_transfer(value: transfer_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransfer, *, resources: Sequence[str] | None = None, key: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT, query_id: str = DEFAULT_QUERY_ID):
    value = transfer_model.verify_transfer(value)
    if resources is None:
        selected = RESOURCES
    else:
        requested = tuple(resources)
        if len(set(requested)) != len(requested) or any(item not in RESOURCES for item in requested):
            raise ValidationError("transfer query resources are unsupported")
        selected = tuple(item for item in RESOURCES if item in requested)
    if not selected:
        raise ValidationError("transfer query requires at least one resource")
    key = _label(key, "transfer query key", required=False)
    text = _text(text, "transfer query text", required=False)
    offset = _count(offset, "transfer query offset", MAX_QUERY_ITEMS)
    limit = _count(limit, "transfer query limit", MAX_LIMIT)
    if limit < 1:
        raise ValidationError("transfer query limit must be positive")
    selected_rows = tuple(row for row in _all_rows(value) if row.resource in selected and _matches(row, key=key, text=text))
    page = selected_rows[offset:offset + limit]
    rows = tuple(_row(row.resource, index, row.key, row.value, row.address) for index, row in enumerate(page, offset))
    body = {"version": VERSION, "boundary": BOUNDARY, "query_id": query_id, "transfer_id": value.transfer_id, "archive_id": value.archive_id, "transfer_address": value.content_address, "archive_address": value.archive_address, "resources": selected, "key": key, "text": text, "offset": offset, "limit": limit, "total_count": len(selected_rows), "returned_count": len(rows), "truncated": offset + len(rows) < len(selected_rows), "rows": rows, "content_address": QUERY_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQuery(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQuery(**(body | {"content_address": address_query(provisional)}))


def verify_query(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQuery):
        raise ValidationError("transfer query verification requires a typed query")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQuery.from_mapping(value.to_dict())


def query_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQuery.from_mapping(value)


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
    lines = ["# Execution-ledger history-diff archive transfer query", "", f"- Transfer: `{value.transfer_id}`", f"- Resources: {', '.join(value.resources)}", f"- Rows: `{value.returned_count}/{value.total_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | key |", "| ---: | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.key}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 0}, "resource": {"enum": list(RESOURCES)}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "row_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "query_id": {"type": "string"}, "transfer_id": {"type": "string"}, "archive_id": {"type": "string"}, "transfer_address": {"type": "string", "pattern": "^" + transfer_model.TRANSFER_PREFIX + ":"}, "archive_address": {"type": "string", "pattern": "^" + transfer_model.archive_model.ARCHIVE_PREFIX + ":"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "key": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "operations": ["query_transfer", "verify_query", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"], "public_boundary": {"source_paths": False, "source_records": False, "chunk_bytes": False}}


__all__ = ["BOUNDARY", "DEFAULT_QUERY_ID", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQuery", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_schema", "query_transfer", "render_query_markdown", "row_schema", "verify_query"]
