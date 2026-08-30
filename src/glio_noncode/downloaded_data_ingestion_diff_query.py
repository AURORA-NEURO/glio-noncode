"""Bounded projections over downloaded-data ingestion transitions."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_ingestion_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-ingestion-diff-query-v1"
BOUNDARY = "public_downloaded_data_ingestion_diff_query"
QUERY_PREFIX = "glio-noncode-download-ingest-diff-query"
RESOURCES = ("summary", "items", "added", "removed", "changed", "unchanged")
MAX_TEXT = 512
MAX_LIMIT = 10_000
MAX_TOTAL_COUNT = diff_model.MAX_ITEMS * 4 + 1
QUERY_FIELDS = ("diff_address", "version", "boundary", "resources", "record_key", "member_name", "change", "changed_field", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")
ROW_FIELDS = ("ordinal", "resource", "change", "record_key", "member_name", "source_row", "changed_fields", "left_record_address", "right_record_address", "left_value", "right_value", "item_address", "content_address")


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


class DownloadedDataIngestionDiffQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, change: str, record_key: str, member_name: str, source_row: int, changed_fields: Sequence[str], left_record_address: str, right_record_address: str, left_value: Any, right_value: Any, item_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff query row ordinal", MAX_LIMIT)
        if self.ordinal == 0:
            raise ValidationError("diff query row ordinal must be positive")
        self.resource = _label(resource, "diff query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("diff query row resource is unsupported")
        self.change = _label(change, "diff query row change") if change else ""
        if self.change and self.change not in diff_model.CHANGES:
            raise ValidationError("diff query row change is unsupported")
        self.record_key = _text(record_key, "diff query row key", 2048, required=True) if record_key else ""
        self.member_name = ingestion_model._safe_member_name(member_name) if member_name else ""
        self.source_row = _count(source_row, "diff query row source row", ingestion_model.MAX_RECORDS) if source_row else 0
        self.changed_fields = tuple(_label(item, "diff query changed field") for item in _sequence(changed_fields, "diff query changed fields", len(diff_model.CHANGED_FIELDS)))
        self.left_record_address = _address(left_record_address, "diff query left address", ingestion_model.RECORD_PREFIX) if left_record_address else ""
        self.right_record_address = _address(right_record_address, "diff query right address", ingestion_model.RECORD_PREFIX) if right_record_address else ""
        self.left_value = None if left_value is None else ingestion_model._validated_value(left_value, "diff query left value")
        self.right_value = None if right_value is None else ingestion_model._validated_value(right_value, "diff query right value")
        self.item_address = _address(item_address, "diff query item address", diff_model.ITEM_PREFIX) if item_address else ""
        self.content_address = _address(content_address, "diff query row address", QUERY_PREFIX + "-row") if not str(content_address).endswith(":pending") else _text(content_address, "diff query row address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary":
            if self.change or self.record_key or self.member_name or self.source_row or self.item_address or self.left_record_address or self.right_record_address:
                raise ValidationError("diff summary row has item-only fields")
        elif not self.change or not self.record_key or not self.member_name or not self.source_row or not self.item_address:
            raise ValidationError("diff item query row is incomplete")
        if self.resource == "items" and self.change == "":
            raise ValidationError("items query row requires change")
        if self.resource not in {"summary", "changed", "added", "removed", "items"} and self.change != self.resource:
            raise ValidationError("change query row does not match resource")
        if self.resource == "summary" and self.left_value is not None:
            raise ValidationError("diff summary row must not contain left value")
        if self.resource == "summary" and self.right_value is None:
            raise ValidationError("diff summary row must contain its summary value")
        if self.resource != "summary" and self.resource != "changed" and self.resource != "items" and self.change != self.resource:
            raise ValidationError("diff query resource/change mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("diff query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("diff query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionDiffQueryRow:
        value = _mapping(value, "downloaded diff query row")
        _strict(value, set(cls.FIELDS), "downloaded diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataIngestionDiffQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX + "-row")


class DownloadedDataIngestionDiffQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, diff_address: str, version: str, boundary: str, resources: Sequence[str], record_key: str, member_name: str, change: str, changed_field: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataIngestionDiffQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.diff_address = _address(diff_address, "diff query address", diff_model.DIFF_PREFIX)
        self.version = _text(version, "diff query version", required=True)
        self.boundary = _text(boundary, "diff query boundary", 512, required=True)
        self.resources = tuple(_label(item, "diff query resource") for item in _sequence(resources, "diff query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(sorted(self.resources, key=RESOURCES.index)):
            raise ValidationError("diff query resources are unsupported or not canonical")
        self.record_key = _text(record_key, "diff query record key", 2048) if record_key else ""
        self.member_name = ingestion_model._safe_member_name(member_name, "diff query member name") if member_name else ""
        self.change = _label(change, "diff query change") if change else ""
        if self.change and self.change not in diff_model.CHANGES:
            raise ValidationError("diff query change is unsupported")
        self.changed_field = _label(changed_field, "diff query changed field") if changed_field else ""
        if self.changed_field and self.changed_field not in diff_model.CHANGED_FIELDS:
            raise ValidationError("diff query changed field is unsupported")
        self.text = _text(text, "diff query text", MAX_TEXT)
        self.offset = _count(offset, "diff query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "diff query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "diff query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "diff query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "diff query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "diff query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "diff query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataIngestionDiffQueryRow) else DownloadedDataIngestionDiffQueryRow.from_mapping(item) for item in _sequence(rows, "diff query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "diff query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff query address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.matched_count or self.matched_count < self.returned_count or self.returned_count != len(self.rows) or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("diff query counts or truncation do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)) or not _public(self.to_dict()):
            raise ValidationError("diff query rows or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("diff query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {**{field: getattr(self, field) for field in self.FIELDS if field != "rows"}, "rows": tuple(item.to_dict() for item in self.rows)}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionDiffQuery:
        value = _mapping(value, "downloaded diff query")
        _strict(value, set(cls.FIELDS), "downloaded diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataIngestionDiffQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _matches(item: diff_model.DownloadedDataIngestionDiffItem, query: DownloadedDataIngestionDiffQuery) -> bool:
    if query.record_key and item.record_key != query.record_key:
        return False
    if query.member_name and item.member_name != query.member_name:
        return False
    if query.change and item.change != query.change:
        return False
    if query.changed_field and query.changed_field not in item.changed_fields:
        return False
    if query.text:
        haystack = " ".join((item.record_key, item.member_name, item.change, *item.changed_fields)).casefold()
        if query.text.casefold() not in haystack:
            return False
    return True


def _row(ordinal: int, resource: str, diff: diff_model.DownloadedDataIngestionDiff, item: diff_model.DownloadedDataIngestionDiffItem | None) -> DownloadedDataIngestionDiffQueryRow:
    if resource == "summary":
        body = {"ordinal": ordinal, "resource": resource, "change": "", "record_key": "", "member_name": "", "source_row": 0, "changed_fields": (), "left_record_address": "", "right_record_address": "", "left_value": None, "right_value": diff.summary(), "item_address": "", "content_address": QUERY_PREFIX + "-row:pending"}
    else:
        if item is None:
            raise ValidationError("diff query row requires a diff item")
        body = {"ordinal": ordinal, "resource": resource, "change": item.change, "record_key": item.record_key, "member_name": item.member_name, "source_row": item.source_row, "changed_fields": item.changed_fields, "left_record_address": item.left_record_address, "right_record_address": item.right_record_address, "left_value": item.left_value if resource in {"items", "changed", "removed"} else None, "right_value": item.right_value if resource in {"items", "changed", "added"} else None, "item_address": item.content_address, "content_address": QUERY_PREFIX + "-row:pending"}
    provisional = DownloadedDataIngestionDiffQueryRow(**body)
    return DownloadedDataIngestionDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_diff(diff: diff_model.DownloadedDataIngestionDiff, *, resources: Sequence[str] = ("summary", "items"), record_key: str = "", member_name: str = "", change: str = "", changed_field: str = "", text: str = "", offset: int = 0, limit: int = 100) -> DownloadedDataIngestionDiffQuery:
    if not isinstance(diff, diff_model.DownloadedDataIngestionDiff):
        raise ValidationError("diff query requires a typed diff")
    normalized_resources = tuple(sorted({_label(item, "diff query resource") for item in resources}, key=RESOURCES.index))
    if not normalized_resources:
        raise ValidationError("diff query requires at least one resource")
    candidate = DownloadedDataIngestionDiffQuery(diff.content_address, VERSION, BOUNDARY, normalized_resources, record_key, member_name, change, changed_field, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    matched = tuple(item for item in diff.items if _matches(item, candidate))
    all_rows: list[tuple[str, diff_model.DownloadedDataIngestionDiffItem | None]] = []
    if "summary" in normalized_resources:
        all_rows.append(("summary", None))
    for resource in normalized_resources:
        if resource == "summary":
            continue
        all_rows.extend((resource, item) for item in matched if resource == "items" or item.change == resource)
    total_count = len(all_rows)
    selected = all_rows[offset : offset + limit]
    rows = tuple(_row(index, resource, diff, item) for index, (resource, item) in enumerate(selected, 1))
    body = {"diff_address": diff.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": normalized_resources, "record_key": candidate.record_key, "member_name": candidate.member_name, "change": candidate.change, "changed_field": candidate.changed_field, "text": candidate.text, "offset": offset, "limit": limit, "total_count": total_count, "matched_count": total_count, "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < total_count, "rows": rows}
    provisional = DownloadedDataIngestionDiffQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataIngestionDiffQuery(**body, content_address=address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataIngestionDiffQuery:
    return DownloadedDataIngestionDiffQuery.from_mapping(value)


def query_json(value: DownloadedDataIngestionDiffQuery) -> str:
    return canonical_json(DownloadedDataIngestionDiffQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataIngestionDiffQuery) -> str:
    value = DownloadedDataIngestionDiffQuery.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field not in {"changed_fields", "left_value", "right_value"} else (";".join(item.changed_fields) if field == "changed_fields" else canonical_json(item.to_dict()[field]) if item.to_dict()[field] is not None else "") for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataIngestionDiffQuery) -> str:
    value = DownloadedDataIngestionDiffQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Ingestion Diff Query", "", f"- Diff: `{value.diff_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Returned: `{value.returned_count}/{value.matched_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | change | key | member | row |", "| ---: | --- | --- | --- | --- | ---: |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.change}` | `{item.record_key}` | `{item.member_name}` | {item.source_row} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion diff query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "change": {"type": "string"}, "record_key": {"type": "string"}, "member_name": {"type": "string"}, "source_row": {"type": "integer", "minimum": 0}, "changed_fields": {"type": "array", "items": {"enum": list(diff_model.CHANGED_FIELDS)}}, "left_record_address": {"type": "string"}, "right_record_address": {"type": "string"}, "left_value": {}, "right_value": {}, "item_address": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion diff query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"diff_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "record_key": {"type": "string"}, "member_name": {"type": "string"}, "change": {"type": "string"}, "changed_field": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "resources": RESOURCES, "operations": ("query_diff", "query_from_mapping", "query_json", "query_csv", "render_query_markdown")}


__all__ = ["BOUNDARY", "MAX_LIMIT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "DownloadedDataIngestionDiffQuery", "DownloadedDataIngestionDiffQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_diff", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
