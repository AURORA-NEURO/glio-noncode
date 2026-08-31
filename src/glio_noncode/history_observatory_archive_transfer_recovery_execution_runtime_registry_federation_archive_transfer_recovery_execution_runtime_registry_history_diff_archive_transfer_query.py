"""Bounded manifest-only inspection queries for history-diff archive transfers."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer as transfer_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = transfer_model.VERSION + "-query-v1"
BOUNDARY = transfer_model.BOUNDARY + "_query"
QUERY_PREFIX = transfer_model.TRANSFER_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "archive", "chunks", "received", "missing", "progress", "bounds")
MAX_LIMIT = 128
MAX_QUERY_ITEMS = 4 + (3 * transfer_model.MAX_CHUNKS)
ROW_FIELDS = ("resource", "ordinal", "transfer_id", "transfer_address", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunk_index", "chunk_offset", "chunk_size_value", "chunk_address", "received", "missing", "received_bytes", "complete", "content_address")
QUERY_FIELDS = ("transfer_address", "transfer_id", "resources", "index_filter", "offset_filter", "size_filter", "chunk_address_filter", "received_filter", "text_filter", "received_indices", "received_bytes", "offset", "limit", "total_count", "matched_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 2048, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _optional_count(value: Any, field: str, maximum: int) -> int | None:
    if value is None:
        return None
    return _count(value, field, maximum)


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192, required=True)
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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


def _bool_or_none(value: Any, field: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise ValidationError(f"{field} must be boolean or null")


class HistoryDiffArchiveTransferQueryRow:
    """One public row from a transfer or receiver-state projection."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, transfer_id: str, transfer_address: str, archive_address: str, archive_size: int, chunk_size: int, chunk_count: int, chunk_index: int | None, chunk_offset: int | None, chunk_size_value: int | None, chunk_address: str, received: bool | None, missing: bool | None, received_bytes: int, complete: bool | None, content_address: str) -> None:
        if resource not in RESOURCES:
            raise ValidationError("query row resource is invalid")
        self.resource = resource
        self.ordinal = _count(ordinal, "query row ordinal", MAX_QUERY_ITEMS, positive=True)
        self.transfer_id = _label(transfer_id, "query row transfer ID")
        self.transfer_address = _address(transfer_address, "query row transfer address", transfer_model.TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "query row archive address", transfer_model.archive_model.ARCHIVE_PREFIX)
        self.archive_size = _count(archive_size, "query row archive size", transfer_model.MAX_TRANSFER_BYTES, positive=True)
        self.chunk_size = _count(chunk_size, "query row chunk size", transfer_model.MAX_CHUNK_SIZE, positive=True)
        self.chunk_count = _count(chunk_count, "query row chunk count", transfer_model.MAX_CHUNKS, positive=True)
        self.chunk_index = _optional_count(chunk_index, "query row chunk index", self.chunk_count - 1)
        self.chunk_offset = _optional_count(chunk_offset, "query row chunk offset", transfer_model.MAX_TRANSFER_BYTES)
        self.chunk_size_value = _optional_count(chunk_size_value, "query row chunk bytes", transfer_model.MAX_CHUNK_SIZE)
        self.chunk_address = _text(chunk_address, "query row chunk address", 8192)
        self.received = _bool_or_none(received, "query row received")
        self.missing = _bool_or_none(missing, "query row missing")
        self.received_bytes = _count(received_bytes, "query row received bytes", self.archive_size)
        self.complete = _bool_or_none(complete, "query row complete")
        self.content_address = _text(content_address, "query row content address", 8192, required=True) if content_address.startswith("pending:") else _address(content_address, "query row content address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.chunk_index is None and (self.chunk_offset is not None or self.chunk_size_value is not None):
            raise ValidationError("query row chunk geometry must be all-null or complete")
        if self.chunk_index is not None and (self.chunk_offset is None or self.chunk_size_value is None or not self.chunk_address):
            raise ValidationError("query row chunk geometry is incomplete")
        if not transfer_model._public(self.to_dict()):
            raise ValidationError("query row crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_row(self) != self.content_address:
            raise ValidationError("query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferQueryRow:
        value = _mapping(value, "history diff archive transfer query row")
        _strict(value, set(cls.FIELDS), "history diff archive transfer query row")
        return cls(*(value[field] for field in cls.FIELDS))


class HistoryDiffArchiveTransferQuery:
    """A deterministic bounded query result over a transfer manifest."""

    FIELDS = QUERY_FIELDS

    def __init__(self, transfer_address: str, transfer_id: str, resources: Sequence[str], index_filter: int | None, offset_filter: int | None, size_filter: int | None, chunk_address_filter: str, received_filter: bool | None, text_filter: str, received_indices: Sequence[int], received_bytes: int, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, truncated: bool, rows: Sequence[HistoryDiffArchiveTransferQueryRow], content_address: str) -> None:
        self.transfer_address = _address(transfer_address, "query transfer address", transfer_model.TRANSFER_PREFIX)
        self.transfer_id = _label(transfer_id, "query transfer ID")
        self.resources = tuple(resources)
        if not self.resources or any(resource not in RESOURCES for resource in self.resources) or len(set(self.resources)) != len(self.resources) or tuple(sorted(self.resources, key=RESOURCES.index)) != self.resources:
            raise ValidationError("query resources are invalid or not canonical")
        self.index_filter = _optional_count(index_filter, "query index filter", transfer_model.MAX_CHUNKS - 1)
        self.offset_filter = _optional_count(offset_filter, "query offset filter", transfer_model.MAX_TRANSFER_BYTES)
        self.size_filter = _optional_count(size_filter, "query size filter", transfer_model.MAX_CHUNK_SIZE)
        self.chunk_address_filter = _text(chunk_address_filter, "query chunk address filter", 8192)
        self.received_filter = _bool_or_none(received_filter, "query received filter")
        self.text_filter = _text(text_filter, "query text filter", 512)
        self.received_indices = tuple(received_indices)
        self.received_bytes = _count(received_bytes, "query received bytes", transfer_model.MAX_TRANSFER_BYTES)
        self.offset = _count(offset, "query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "query total count", MAX_QUERY_ITEMS)
        self.matched_count = _count(matched_count, "query matched count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "query returned count", MAX_LIMIT)
        if not isinstance(truncated, bool):
            raise ValidationError("query truncation must be boolean")
        self.truncated = truncated
        self.rows = tuple(item if isinstance(item, HistoryDiffArchiveTransferQueryRow) else HistoryDiffArchiveTransferQueryRow.from_mapping(item) for item in _sequence(rows, "query rows", MAX_LIMIT))
        self.content_address = _text(content_address, "query address", 8192, required=True) if content_address.startswith("pending:") else _address(content_address, "query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if any(isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= transfer_model.MAX_CHUNKS for index in self.received_indices) or tuple(sorted(set(self.received_indices))) != self.received_indices:
            raise ValidationError("query received indices are invalid")
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.matched_count or self.truncated != (self.offset + self.returned_count < self.matched_count):
            raise ValidationError("query counts or truncation do not replay")
        if tuple(row.ordinal for row in self.rows) != tuple(range(1, self.returned_count + 1)) or any(row.transfer_address != self.transfer_address or row.transfer_id != self.transfer_id for row in self.rows):
            raise ValidationError("query row order or linkage is invalid")
        if not transfer_model._public(self.to_dict()):
            raise ValidationError("query crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_query(self) != self.content_address:
            raise ValidationError("query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_address": self.transfer_address, "transfer_id": self.transfer_id, "resources": self.resources, "index_filter": self.index_filter, "offset_filter": self.offset_filter, "size_filter": self.size_filter, "chunk_address_filter": self.chunk_address_filter, "received_filter": self.received_filter, "text_filter": self.text_filter, "received_indices": self.received_indices, "received_bytes": self.received_bytes, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": tuple(row.to_dict() for row in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"rows", "received_indices"}}


def address_row(value: HistoryDiffArchiveTransferQueryRow) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferQueryRow):
        raise ValidationError("query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


def address_query(value: HistoryDiffArchiveTransferQuery) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferQuery):
        raise ValidationError("query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(value: transfer_model.HistoryDiffArchiveTransfer, resource: str, ordinal: int, *, index: int | None = None, received: bool | None = None, missing: bool | None = None, received_bytes: int = 0, complete: bool | None = None) -> HistoryDiffArchiveTransferQueryRow:
    chunk = value.chunks[index] if index is not None else None
    provisional = HistoryDiffArchiveTransferQueryRow(resource, ordinal, value.transfer_id, value.content_address, value.archive_address, value.archive_size, value.chunk_size, value.chunk_count, None if chunk is None else chunk.index, None if chunk is None else chunk.offset, None if chunk is None else chunk.size, "" if chunk is None else chunk.content_address, received, missing, received_bytes, complete, "pending:row")
    return HistoryDiffArchiveTransferQueryRow(provisional.resource, provisional.ordinal, provisional.transfer_id, provisional.transfer_address, provisional.archive_address, provisional.archive_size, provisional.chunk_size, provisional.chunk_count, provisional.chunk_index, provisional.chunk_offset, provisional.chunk_size_value, provisional.chunk_address, provisional.received, provisional.missing, provisional.received_bytes, provisional.complete, address_row(provisional))


def _rows(value: transfer_model.HistoryDiffArchiveTransfer, resources: Sequence[str], received_indices: tuple[int, ...], received_bytes: int) -> tuple[HistoryDiffArchiveTransferQueryRow, ...]:
    received = set(received_indices)
    complete = len(received) == value.chunk_count
    rows: list[HistoryDiffArchiveTransferQueryRow] = []
    for resource in resources:
        if resource in {"summary", "archive", "progress", "bounds"}:
            rows.append(_row(value, resource, len(rows) + 1, received_bytes=received_bytes, complete=complete))
        elif resource == "chunks":
            rows.extend(_row(value, resource, len(rows) + 1, index=index, received=index in received, missing=index not in received, received_bytes=received_bytes, complete=complete) for index in range(value.chunk_count))
        elif resource == "received":
            rows.extend(_row(value, resource, len(rows) + 1, index=index, received=True, missing=False, received_bytes=received_bytes, complete=complete) for index in received_indices)
        elif resource == "missing":
            rows.extend(_row(value, resource, len(rows) + 1, index=index, received=False, missing=True, received_bytes=received_bytes, complete=complete) for index in range(value.chunk_count) if index not in received)
    return tuple(rows)


def _matches(row: HistoryDiffArchiveTransferQueryRow, *, index: int | None, offset: int | None, size: int | None, chunk_address: str, received: bool | None, text: str) -> bool:
    if index is not None and row.chunk_index != index:
        return False
    if offset is not None and row.chunk_offset != offset:
        return False
    if size is not None and row.chunk_size_value != size:
        return False
    if chunk_address and chunk_address not in row.chunk_address:
        return False
    if received is not None and row.received != received:
        return False
    if text:
        haystack = " ".join(str(row.to_dict()[field]) for field in ("resource", "transfer_id", "transfer_address", "archive_address", "chunk_address", "content_address"))
        if text.casefold() not in haystack.casefold():
            return False
    return True


def query_transfer(value: transfer_model.HistoryDiffArchiveTransfer, *, resources: Sequence[str] | None = None, received_indices: Sequence[int] | None = None, index: int | None = None, chunk_offset: int | None = None, size: int | None = None, chunk_address: str = "", received: bool | None = None, text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> HistoryDiffArchiveTransferQuery:
    if not isinstance(value, transfer_model.HistoryDiffArchiveTransfer):
        raise ValidationError("transfer query requires a typed history diff archive transfer")
    transfer_model.verify_transfer(value)
    resources = tuple(resources or RESOURCES)
    if not resources or any(resource not in RESOURCES for resource in resources) or len(set(resources)) != len(resources) or tuple(sorted(resources, key=RESOURCES.index)) != resources:
        raise ValidationError("query resources must be unique and in canonical order")
    indices = tuple(sorted(value._payload)) if received_indices is None and value._payload else tuple(received_indices or ())
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 or item >= value.chunk_count for item in indices) or tuple(sorted(set(indices))) != indices:
        raise ValidationError("query received indices are outside the transfer")
    received_bytes = sum(value.chunks[item].size for item in indices)
    all_rows = _rows(value, resources, indices, received_bytes)
    filtered = tuple(row for row in all_rows if _matches(row, index=index, offset=chunk_offset, size=size, chunk_address=chunk_address, received=received, text=text))
    offset = _count(offset, "query offset", len(filtered) + len(all_rows))
    limit = _count(limit, "query limit", MAX_LIMIT, positive=True)
    page = filtered[offset:offset + limit]
    normalized = tuple(HistoryDiffArchiveTransferQueryRow(row.resource, ordinal + 1, row.transfer_id, row.transfer_address, row.archive_address, row.archive_size, row.chunk_size, row.chunk_count, row.chunk_index, row.chunk_offset, row.chunk_size_value, row.chunk_address, row.received, row.missing, row.received_bytes, row.complete, "pending:row") for ordinal, row in enumerate(page))
    rows = tuple(HistoryDiffArchiveTransferQueryRow(row.resource, row.ordinal, row.transfer_id, row.transfer_address, row.archive_address, row.archive_size, row.chunk_size, row.chunk_count, row.chunk_index, row.chunk_offset, row.chunk_size_value, row.chunk_address, row.received, row.missing, row.received_bytes, row.complete, address_row(row)) for row in normalized)
    total_count = len(all_rows)
    matched_count = len(filtered)
    provisional = HistoryDiffArchiveTransferQuery(value.content_address, value.transfer_id, resources, index, chunk_offset, size, chunk_address, received, text, indices, received_bytes, offset, limit, total_count, matched_count, len(rows), offset + len(rows) < matched_count, rows, "pending:query")
    return HistoryDiffArchiveTransferQuery(provisional.transfer_address, provisional.transfer_id, provisional.resources, provisional.index_filter, provisional.offset_filter, provisional.size_filter, provisional.chunk_address_filter, provisional.received_filter, provisional.text_filter, provisional.received_indices, provisional.received_bytes, provisional.offset, provisional.limit, provisional.total_count, provisional.matched_count, provisional.returned_count, provisional.truncated, provisional.rows, address_query(provisional))


def query_assembler(assembler: transfer_model.HistoryDiffArchiveTransferAssembler, **kwargs: Any) -> HistoryDiffArchiveTransferQuery:
    if not isinstance(assembler, transfer_model.HistoryDiffArchiveTransferAssembler):
        raise ValidationError("assembler query requires a typed history diff archive transfer assembler")
    return query_transfer(assembler.value, received_indices=assembler.received_indices(), **kwargs)


def query_from_mapping(value: Mapping[str, Any]) -> HistoryDiffArchiveTransferQuery:
    value = _mapping(value, "history diff archive transfer query")
    _strict(value, set(QUERY_FIELDS), "history diff archive transfer query")
    return HistoryDiffArchiveTransferQuery(value["transfer_address"], value["transfer_id"], value["resources"], value["index_filter"], value["offset_filter"], value["size_filter"], value["chunk_address_filter"], value["received_filter"], value["text_filter"], value["received_indices"], value["received_bytes"], value["offset"], value["limit"], value["total_count"], value["matched_count"], value["returned_count"], value["truncated"], tuple(HistoryDiffArchiveTransferQueryRow.from_mapping(row) for row in _sequence(value["rows"], "query rows", MAX_LIMIT)), value["content_address"])


def query_json(value: HistoryDiffArchiveTransferQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: HistoryDiffArchiveTransferQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow(row.to_dict())
    return stream.getvalue()


def render_query_markdown(value: HistoryDiffArchiveTransferQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Federation History-Diff Archive Transfer Query", "", f"- Transfer: `{value.transfer_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.matched_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | chunk | received | missing | address |", "| ---: | --- | ---: | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.chunk_index if row.chunk_index is not None else ''}` | `{row.received if row.received is not None else ''}` | `{row.missing if row.missing is not None else ''}` | `{row.content_address}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation history-diff archive transfer query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}, "transfer_id": {"type": "string"}, "transfer_address": {"type": "string", "pattern": "^" + transfer_model.TRANSFER_PREFIX + ":"}, "archive_address": {"type": "string", "pattern": "^" + transfer_model.archive_model.ARCHIVE_PREFIX + ":"}, "archive_size": {"type": "integer", "minimum": 1}, "chunk_size": {"type": "integer", "minimum": 1}, "chunk_count": {"type": "integer", "minimum": 1}, "chunk_index": {"type": ["integer", "null"], "minimum": 0}, "chunk_offset": {"type": ["integer", "null"], "minimum": 0}, "chunk_size_value": {"type": ["integer", "null"], "minimum": 0}, "chunk_address": {"type": "string"}, "received": {"type": ["boolean", "null"]}, "missing": {"type": ["boolean", "null"]}, "received_bytes": {"type": "integer", "minimum": 0}, "complete": {"type": ["boolean", "null"]}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation history-diff archive transfer query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"transfer_address": {"type": "string", "pattern": "^" + transfer_model.TRANSFER_PREFIX + ":"}, "transfer_id": {"type": "string"}, "resources": {"type": "array", "items": {"type": "string", "enum": list(RESOURCES)}, "minItems": 1, "maxItems": len(RESOURCES)}, "index_filter": {"type": ["integer", "null"], "minimum": 0}, "offset_filter": {"type": ["integer", "null"], "minimum": 0}, "size_filter": {"type": ["integer", "null"], "minimum": 0}, "chunk_address_filter": {"type": "string"}, "received_filter": {"type": ["boolean", "null"]}, "text_filter": {"type": "string"}, "received_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "received_bytes": {"type": "integer", "minimum": 0}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "matched_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_LIMIT}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "filters": ["chunk index", "chunk offset", "chunk size", "chunk address", "received state", "text", "offset", "limit"], "features": ["manifest-only inspection", "received and missing partitions", "progress projection", "deterministic row addresses", "stable pagination", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "HistoryDiffArchiveTransferQuery", "HistoryDiffArchiveTransferQueryRow", "VERSION", "address_query", "address_row", "capabilities", "query_assembler", "query_csv", "query_from_mapping", "query_json", "query_schema", "query_transfer", "render_query_markdown", "row_schema"]
