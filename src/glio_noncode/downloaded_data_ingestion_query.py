"""Deterministic, bounded projections over downloaded-data ingestion batches."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-ingestion-query-v1"
BOUNDARY = "public_downloaded_data_ingestion_query"
QUERY_PREFIX = "glio-noncode-download-ingest-query"
RESOURCES = ("summary", "records", "lineage", "values")
MAX_TEXT = 512
MAX_LIMIT = 10_000
MAX_TOTAL_COUNT = ingestion_model.MAX_RECORDS * len(RESOURCES) + 1
QUERY_FIELDS = (
    "batch_address",
    "version",
    "boundary",
    "resources",
    "record_id",
    "member_name",
    "data_kind",
    "shape",
    "field",
    "text",
    "offset",
    "limit",
    "total_count",
    "matched_count",
    "returned_count",
    "next_offset",
    "truncated",
    "rows",
    "content_address",
)
ROW_FIELDS = (
    "ordinal",
    "resource",
    "record_id",
    "member_name",
    "data_kind",
    "shape",
    "source_row",
    "fields",
    "lineage",
    "value",
    "record_address",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048, required=True)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
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
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _optional_record_value(value: Any) -> Any:
    if value is None:
        return None
    return ingestion_model._validated_value(value, "query value")


class DownloadedDataIngestionQueryRow:
    """One bounded row in a batch projection."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, record_id: str, member_name: str, data_kind: str, shape: str, source_row: int, fields: Sequence[str], lineage: Mapping[str, Any] | None, value: Any, record_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "query row ordinal", MAX_LIMIT, positive=True)
        self.resource = _label(resource, "query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("query row resource is unsupported")
        self.record_id = _label(record_id, "query row record ID")
        self.member_name = ingestion_model._safe_member_name(member_name) if member_name else ""
        self.data_kind = _label(data_kind, "query row data kind") if data_kind else ""
        self.shape = _label(shape, "query row shape") if shape else ""
        self.source_row = _count(source_row, "query row source row", ingestion_model.MAX_RECORDS) if source_row else 0
        self.fields = tuple(ingestion_model._key(item, "query row field") for item in _sequence(fields, "query row fields", 512))
        self.lineage = None if lineage is None else dict(ingestion_model.DownloadedDataLineage.from_mapping(lineage).to_dict())
        self.value = _optional_record_value(value)
        self.record_address = _address(record_address, "query row record address", ingestion_model.RECORD_PREFIX) if record_address else ""
        self.content_address = _address(content_address, "query row address", QUERY_PREFIX + "-row") if not str(content_address).endswith(":pending") else _text(content_address, "query row address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary":
            if self.record_id != "batch" or self.member_name or self.record_address or self.source_row or self.lineage is not None:
                raise ValidationError("summary query row has record-only fields")
        elif not self.record_id or not self.member_name or not self.record_address or not self.source_row:
            raise ValidationError("record query row is incomplete")
        if self.resource in {"summary", "values"} and self.value is None:
            raise ValidationError("value-bearing query row must contain a value")
        if self.resource not in {"summary", "values"} and self.value is not None:
            raise ValidationError("non-value query row must not contain a value")
        if not _public(self.to_dict()):
            raise ValidationError("query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionQueryRow:
        value = _mapping(value, "downloaded ingestion query row")
        _strict(value, set(cls.FIELDS), "downloaded ingestion query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataIngestionQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX + "-row")


class DownloadedDataIngestionQuery:
    """Content-addressed bounded selection of batch resources."""

    FIELDS = QUERY_FIELDS

    def __init__(self, batch_address: str, version: str, boundary: str, resources: Sequence[str], record_id: str, member_name: str, data_kind: str, shape: str, field: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataIngestionQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.batch_address = _address(batch_address, "query batch address", ingestion_model.INGEST_PREFIX)
        self.version = _text(version, "query version", required=True)
        self.boundary = _text(boundary, "query boundary", 512, required=True)
        self.resources = tuple(_label(item, "query resource") for item in _sequence(resources, "query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources):
            raise ValidationError("query resources are unsupported or duplicated")
        if self.resources != tuple(sorted(self.resources, key=RESOURCES.index)):
            raise ValidationError("query resources must use canonical order")
        self.record_id = _label(record_id, "query record ID") if record_id else ""
        self.member_name = ingestion_model._safe_member_name(member_name, "query member name") if member_name else ""
        self.data_kind = _label(data_kind, "query data kind") if data_kind else ""
        self.shape = _label(shape, "query shape") if shape else ""
        self.field = ingestion_model._key(field, "query field") if field else ""
        self.text = _text(text, "query text", MAX_TEXT)
        self.offset = _count(offset, "query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataIngestionQueryRow) else DownloadedDataIngestionQueryRow.from_mapping(item) for item in _sequence(rows, "query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "query address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.matched_count or self.matched_count < self.returned_count or self.returned_count != len(self.rows) or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("query counts or truncation do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("query row ordinals are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"batch_address": self.batch_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "record_id": self.record_id, "member_name": self.member_name, "data_kind": self.data_kind, "shape": self.shape, "field": self.field, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionQuery:
        value = _mapping(value, "downloaded ingestion query")
        _strict(value, set(cls.FIELDS), "downloaded ingestion query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataIngestionQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _matches(record: ingestion_model.DownloadedDataRecord, query: DownloadedDataIngestionQuery) -> bool:
    if query.record_id and record.record_id != query.record_id:
        return False
    if query.member_name and record.lineage.member_name != query.member_name:
        return False
    if query.data_kind and record.data_kind != query.data_kind:
        return False
    if query.shape and record.shape != query.shape:
        return False
    if query.field and query.field not in record.fields:
        return False
    if query.text:
        haystack = " ".join((record.record_id, record.lineage.member_name, record.data_kind, record.shape, *record.fields)).casefold()
        if query.text.casefold() not in haystack:
            return False
    return True


def _row(ordinal: int, resource: str, batch: ingestion_model.DownloadedDataIngestBatch, record: ingestion_model.DownloadedDataRecord | None = None) -> DownloadedDataIngestionQueryRow:
    if resource == "summary":
        body = {"ordinal": ordinal, "resource": resource, "record_id": "batch", "member_name": "", "data_kind": "", "shape": "", "source_row": 0, "fields": (), "lineage": None, "value": batch.summary(), "record_address": "", "content_address": QUERY_PREFIX + "-row:pending"}
    else:
        if record is None:
            raise ValidationError("record query row requires a record")
        body = {"ordinal": ordinal, "resource": resource, "record_id": record.record_id, "member_name": record.lineage.member_name, "data_kind": record.data_kind, "shape": record.shape, "source_row": record.lineage.source_row, "fields": record.fields, "lineage": record.lineage.to_dict(), "value": record.value if resource == "values" else None, "record_address": record.content_address, "content_address": QUERY_PREFIX + "-row:pending"}
    provisional = DownloadedDataIngestionQueryRow(**body)
    return DownloadedDataIngestionQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_batch(batch: ingestion_model.DownloadedDataIngestBatch, *, resources: Sequence[str] = ("summary", "records"), record_id: str = "", member_name: str = "", data_kind: str = "", shape: str = "", field: str = "", text: str = "", offset: int = 0, limit: int = 100) -> DownloadedDataIngestionQuery:
    if not isinstance(batch, ingestion_model.DownloadedDataIngestBatch):
        raise ValidationError("query requires a typed ingestion batch")
    normalized_resources = tuple(sorted({_label(item, "query resource") for item in resources}, key=RESOURCES.index))
    if not normalized_resources:
        raise ValidationError("query requires at least one resource")
    candidate = DownloadedDataIngestionQuery(batch.content_address, VERSION, BOUNDARY, normalized_resources, record_id, member_name, data_kind, shape, field, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    matched_records = tuple(record for record in batch.records if _matches(record, candidate))
    all_rows: list[tuple[str, ingestion_model.DownloadedDataRecord | None]] = []
    if "summary" in normalized_resources:
        all_rows.append(("summary", None))
    for resource in normalized_resources:
        if resource == "summary":
            continue
        all_rows.extend((resource, record) for record in matched_records)
    total_count = len(all_rows)
    start = min(offset, total_count)
    selected = all_rows[start : start + limit]
    rows = tuple(_row(index, resource, batch, record) for index, (resource, record) in enumerate(selected, 1))
    body = {"batch_address": batch.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": normalized_resources, "record_id": candidate.record_id, "member_name": candidate.member_name, "data_kind": candidate.data_kind, "shape": candidate.shape, "field": candidate.field, "text": candidate.text, "offset": offset, "limit": limit, "total_count": total_count, "matched_count": total_count, "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < total_count, "rows": rows}
    provisional = DownloadedDataIngestionQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataIngestionQuery(**body, content_address=address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataIngestionQuery:
    return DownloadedDataIngestionQuery.from_mapping(value)


def query_json(value: DownloadedDataIngestionQuery) -> str:
    return canonical_json(DownloadedDataIngestionQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataIngestionQuery) -> str:
    value = DownloadedDataIngestionQuery.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field not in {"fields", "lineage", "value"} else (";".join(item.fields) if field == "fields" else canonical_json(item.to_dict()[field]) if item.to_dict()[field] is not None else "") for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataIngestionQuery) -> str:
    value = DownloadedDataIngestionQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Ingestion Query", "", f"- Batch: `{value.batch_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Returned: `{value.returned_count}/{value.matched_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | record | member | row |", "| ---: | --- | --- | --- | ---: |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.record_id}` | `{item.member_name}` | {item.source_row} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "record_id": {"type": "string"}, "member_name": {"type": "string"}, "data_kind": {"type": "string"}, "shape": {"type": "string"}, "source_row": {"type": "integer", "minimum": 0}, "fields": {"type": "array", "items": {"type": "string"}}, "lineage": {"type": ["object", "null"]}, "value": {}, "record_address": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"batch_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "record_id": {"type": "string"}, "member_name": {"type": "string"}, "data_kind": {"type": "string"}, "shape": {"type": "string"}, "field": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "resources": RESOURCES, "operations": ("query_batch", "query_from_mapping", "query_json", "query_csv", "render_query_markdown")}


__all__ = ["BOUNDARY", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "DownloadedDataIngestionQuery", "DownloadedDataIngestionQueryRow", "address_query", "address_row", "capabilities", "query_batch", "query_csv", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
