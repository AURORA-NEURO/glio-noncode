"""Bounded inspection queries for history-observatory archive transfers."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer as transfer_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = transfer_model.VERSION + "-query-v1"
BOUNDARY = transfer_model.BOUNDARY + "_query"
QUERY_PREFIX = transfer_model.TRANSFER_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "archive", "chunks", "received", "missing", "progress")
MAX_LIMIT = 128
MAX_QUERY_ITEMS = 3 + (3 * transfer_model.MAX_CHUNKS)
ROW_FIELDS = ("resource", "ordinal", "transfer_id", "transfer_address", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunk_index", "chunk_offset", "chunk_size_value", "chunk_address", "received", "missing", "received_bytes", "complete", "content_address")
QUERY_FIELDS = ("transfer_address", "resources", "index_filter", "offset_filter", "size_filter", "chunk_address_filter", "received_filter", "text_filter", "offset", "limit", "total_count", "matched_count", "returned_count", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 256)
    if required and not value:
        raise ValidationError(f"{field} must not be empty")
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = False, allow_pending: bool = False) -> str:
    value = _text(value, field, 4096)
    if required and not value:
        raise ValidationError(f"{field} must not be empty")
    if allow_pending and value.startswith("pending:"):
        return value
    if value and (":" not in value or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and value and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool_or_none(value: Any, field: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean or null")
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


def _resources(value: Any) -> tuple[str, ...]:
    values = tuple(_label(item, "query resource", required=True) for item in _sequence(value, "query resources", len(RESOURCES)))
    if not values or len(set(values)) != len(values) or any(item not in RESOURCES for item in values) or tuple(sorted(values, key=RESOURCES.index)) != values:
        raise ValidationError("query resources must be a unique canonical subsequence")
    return values


class TransferQueryRow:
    """One addressed transfer inspection row."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, transfer_id: str, transfer_address: str, archive_address: str, archive_size: int, chunk_size: int, chunk_count: int, chunk_index: int, chunk_offset: int, chunk_size_value: int, chunk_address: str, received: bool, missing: bool, received_bytes: int, complete: bool, content_address: str) -> None:
        self.resource = _label(resource, "row resource", required=True)
        if self.resource not in RESOURCES:
            raise ValidationError("row resource is unsupported")
        self.ordinal = _count(ordinal, "row ordinal", MAX_QUERY_ITEMS, positive=True)
        self.transfer_id = _label(transfer_id, "row transfer ID", required=True)
        self.transfer_address = _address(transfer_address, "row transfer address", transfer_model.TRANSFER_PREFIX, required=True)
        self.archive_address = _address(archive_address, "row archive address", transfer_model.archive_model.ARCHIVE_PREFIX, required=True)
        self.archive_size = _count(archive_size, "row archive size", transfer_model.MAX_TRANSFER_BYTES, positive=True)
        self.chunk_size = _count(chunk_size, "row chunk size", transfer_model.MAX_CHUNK_SIZE, positive=True)
        self.chunk_count = _count(chunk_count, "row chunk count", transfer_model.MAX_CHUNKS, positive=True)
        self.chunk_index = _count(chunk_index, "row chunk index", transfer_model.MAX_CHUNKS - 1)
        self.chunk_offset = _count(chunk_offset, "row chunk offset", transfer_model.MAX_TRANSFER_BYTES)
        self.chunk_size_value = _count(chunk_size_value, "row chunk size value", transfer_model.MAX_CHUNK_SIZE)
        self.chunk_address = _address(chunk_address, "row chunk address", transfer_model.CHUNK_PREFIX) if chunk_address else ""
        if not isinstance(received, bool) or not isinstance(missing, bool) or not isinstance(complete, bool):
            raise ValidationError("row state fields must be boolean")
        self.received = received
        self.missing = missing
        self.received_bytes = _count(received_bytes, "row received bytes", self.archive_size)
        self.complete = complete
        self.content_address = _address(content_address, "row content address", ROW_PREFIX, required=True, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.received and self.missing or self.received_bytes > self.archive_size or self.chunk_offset + self.chunk_size_value > self.archive_size and self.chunk_size_value:
            raise ValidationError("row state or range is inconsistent")
        if self.resource in {"chunks", "received", "missing"} and not self.chunk_address:
            raise ValidationError("chunk resource rows require a chunk address")
        if not transfer_model._public(self.to_dict()):
            raise ValidationError("query row crosses the public boundary")
        if not self.content_address.startswith("pending:") and content_hash(self.to_dict() | {"content_address": None}, prefix=ROW_PREFIX) != self.content_address:
            raise ValidationError("query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "ordinal": self.ordinal, "transfer_id": self.transfer_id, "transfer_address": self.transfer_address, "archive_address": self.archive_address, "archive_size": self.archive_size, "chunk_size": self.chunk_size, "chunk_count": self.chunk_count, "chunk_index": self.chunk_index, "chunk_offset": self.chunk_offset, "chunk_size_value": self.chunk_size_value, "chunk_address": self.chunk_address, "received": self.received, "missing": self.missing, "received_bytes": self.received_bytes, "complete": self.complete, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TransferQueryRow":
        value = _mapping(value, "transfer query row")
        _strict(value, set(cls.FIELDS), "transfer query row")
        return cls(*(value[field] for field in cls.FIELDS))


class TransferQuery:
    """A bounded, addressed transfer query result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, transfer_address: str, resources: Sequence[str], index_filter: int | None, offset_filter: int | None, size_filter: int | None, chunk_address_filter: str, received_filter: bool | None, text_filter: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, rows: Sequence[TransferQueryRow], content_address: str) -> None:
        self.transfer_address = _address(transfer_address, "query transfer address", transfer_model.TRANSFER_PREFIX, required=True)
        self.resources = _resources(resources)
        self.index_filter = None if index_filter is None else _count(index_filter, "index filter", transfer_model.MAX_CHUNKS - 1)
        self.offset_filter = None if offset_filter is None else _count(offset_filter, "offset filter", transfer_model.MAX_TRANSFER_BYTES)
        self.size_filter = None if size_filter is None else _count(size_filter, "size filter", transfer_model.MAX_CHUNK_SIZE)
        self.chunk_address_filter = _address(chunk_address_filter, "chunk address filter", transfer_model.CHUNK_PREFIX) if chunk_address_filter else ""
        self.received_filter = _bool_or_none(received_filter, "received filter")
        self.text_filter = _text(text_filter, "text filter")
        self.offset = _count(offset, "query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "query total count", MAX_QUERY_ITEMS)
        self.matched_count = _count(matched_count, "query matched count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "query returned count", MAX_LIMIT)
        self.rows = tuple(item if isinstance(item, TransferQueryRow) else TransferQueryRow.from_mapping(item) for item in _sequence(rows, "query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "query content address", QUERY_PREFIX, required=True, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.offset > self.total_count or tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("query counts or row order do not replay")
        if any(item.transfer_address != self.transfer_address or item.resource not in self.resources for item in self.rows):
            raise ValidationError("query rows do not belong to the query")
        if not transfer_model._public(self.to_dict()):
            raise ValidationError("query crosses the public boundary")
        if not self.content_address.startswith("pending:") and content_hash(self.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX) != self.content_address:
            raise ValidationError("query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_address": self.transfer_address, "resources": self.resources, "index_filter": self.index_filter, "offset_filter": self.offset_filter, "size_filter": self.size_filter, "chunk_address_filter": self.chunk_address_filter, "received_filter": self.received_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TransferQuery":
        value = _mapping(value, "transfer query")
        _strict(value, set(cls.FIELDS), "transfer query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: TransferQueryRow) -> str:
    if not isinstance(value, TransferQueryRow):
        raise ValidationError("row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


def address_query(value: TransferQuery) -> str:
    if not isinstance(value, TransferQuery):
        raise ValidationError("query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(value: transfer_model.ArchiveTransfer, resource: str, ordinal: int, *, chunk: transfer_model.ArchiveTransferChunk | None = None, received: bool = False, missing: bool = False) -> TransferQueryRow:
    parts = value._payload
    complete = bool(parts) and len(parts) == value.chunk_count
    received_bytes = sum(len(raw) for raw in parts.values()) if parts else 0
    body = {"resource": resource, "ordinal": ordinal, "transfer_id": value.transfer_id, "transfer_address": value.content_address, "archive_address": value.archive_address, "archive_size": value.archive_size, "chunk_size": value.chunk_size, "chunk_count": value.chunk_count, "chunk_index": 0 if chunk is None else chunk.index, "chunk_offset": 0 if chunk is None else chunk.offset, "chunk_size_value": 0 if chunk is None else chunk.size, "chunk_address": "" if chunk is None else chunk.content_address, "received": received, "missing": missing, "received_bytes": received_bytes, "complete": complete, "content_address": "pending:row"}
    provisional = TransferQueryRow(**body)
    return TransferQueryRow(**(body | {"content_address": address_row(provisional)}))


def _all_rows(value: transfer_model.ArchiveTransfer, resources: Sequence[str]) -> tuple[TransferQueryRow, ...]:
    parts = value._payload
    rows: list[TransferQueryRow] = []
    for resource in resources:
        if resource == "summary":
            rows.append(_row(value, resource, len(rows) + 1, received=bool(parts) and len(parts) == value.chunk_count, missing=not parts or len(parts) != value.chunk_count))
        elif resource == "archive":
            rows.append(_row(value, resource, len(rows) + 1, received=bool(parts) and len(parts) == value.chunk_count, missing=not parts or len(parts) != value.chunk_count))
        elif resource == "progress":
            progress = transfer_model.TransferAssembler(value).progress()
            rows.append(_row(value, resource, len(rows) + 1, received=progress.complete, missing=not progress.complete))
        elif resource in {"chunks", "received", "missing"}:
            for chunk in value.chunks:
                is_received = chunk.index in parts
                if resource == "received" and not is_received or resource == "missing" and is_received:
                    continue
                rows.append(_row(value, resource, len(rows) + 1, chunk=chunk, received=is_received, missing=not is_received))
    return tuple(rows)


def _matches(row: TransferQueryRow, *, index: int | None, offset: int | None, size: int | None, chunk_address: str, received: bool | None, text: str) -> bool:
    if index is not None and row.chunk_index != index:
        return False
    if offset is not None and row.chunk_offset != offset:
        return False
    if size is not None and row.chunk_size_value != size:
        return False
    if chunk_address and row.chunk_address != chunk_address:
        return False
    if received is not None and row.received != received:
        return False
    return not text or text.casefold() in canonical_json(row.to_dict()).casefold()


def _renumber(row: TransferQueryRow, ordinal: int) -> TransferQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": "pending:row"}
    provisional = TransferQueryRow(**body)
    return TransferQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_transfer(value: transfer_model.ArchiveTransfer, *, resources: Sequence[str] | None = None, index: int | None = None, chunk_offset: int | None = None, size: int | None = None, chunk_address: str = "", received: bool | None = None, text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> TransferQuery:
    if not isinstance(value, transfer_model.ArchiveTransfer):
        raise ValidationError("transfer query requires a typed transfer")
    transfer_model.verify_transfer(value)
    selected = _resources(RESOURCES if resources is None else resources)
    _text(text, "text filter")
    rows = _all_rows(value, selected)
    filtered = tuple(item for item in rows if _matches(item, index=index, offset=chunk_offset, size=size, chunk_address=chunk_address, received=received, text=text))
    page = tuple(_renumber(item, item_index + 1) for item_index, item in enumerate(filtered[offset:offset + limit]))
    body = {"transfer_address": value.content_address, "resources": selected, "index_filter": index, "offset_filter": chunk_offset, "size_filter": size, "chunk_address_filter": chunk_address, "received_filter": received, "text_filter": text, "offset": offset, "limit": limit, "total_count": len(rows), "matched_count": len(filtered), "returned_count": len(page), "rows": page}
    provisional = TransferQuery(**body, content_address="pending:query")
    return TransferQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> TransferQuery:
    return TransferQuery.from_mapping(value)


def query_json(value: TransferQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: TransferQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow(row.to_dict())
    return stream.getvalue()


def render_query_markdown(value: TransferQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Comparison-query history observatory archive transfer query", "", f"- Transfer: `{value.transfer_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.matched_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | chunk | offset | size | received | missing |", "| ---: | --- | ---: | ---: | ---: | --- | --- |"]
    lines.extend(f"| {row.ordinal} | {row.resource} | {row.chunk_index} | {row.chunk_offset} | {row.chunk_size_value} | {str(row.received).lower()} | {str(row.missing).lower()} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory archive transfer query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}, "transfer_id": {"type": "string"}, "transfer_address": {"type": "string", "pattern": "^" + transfer_model.TRANSFER_PREFIX + ":"}, "archive_address": {"type": "string", "pattern": "^" + transfer_model.archive_model.ARCHIVE_PREFIX + ":"}, "archive_size": {"type": "integer", "minimum": 1}, "chunk_size": {"type": "integer", "minimum": 1}, "chunk_count": {"type": "integer", "minimum": 1}, "chunk_index": {"type": "integer", "minimum": 0}, "chunk_offset": {"type": "integer", "minimum": 0}, "chunk_size_value": {"type": "integer", "minimum": 0}, "chunk_address": {"type": "string"}, "received": {"type": "boolean"}, "missing": {"type": "boolean"}, "received_bytes": {"type": "integer", "minimum": 0}, "complete": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory archive transfer query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"transfer_address": {"type": "string", "pattern": "^" + transfer_model.TRANSFER_PREFIX + ":"}, "resources": {"type": "array", "items": {"type": "string", "enum": list(RESOURCES)}, "minItems": 1, "maxItems": len(RESOURCES)}, "index_filter": {"type": ["integer", "null"], "minimum": 0}, "offset_filter": {"type": ["integer", "null"], "minimum": 0}, "size_filter": {"type": ["integer", "null"], "minimum": 0}, "chunk_address_filter": {"type": "string"}, "received_filter": {"type": ["boolean", "null"]}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "matched_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_LIMIT}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "filters": ["chunk index", "chunk offset", "chunk size", "chunk address", "received state", "text", "offset", "limit"], "features": ["manifest-only inspection", "received and missing partitions", "progress projection", "deterministic row addresses", "stable pagination", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "TransferQuery", "TransferQueryRow", "VERSION", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_schema", "query_transfer", "render_query_markdown", "row_schema"]
