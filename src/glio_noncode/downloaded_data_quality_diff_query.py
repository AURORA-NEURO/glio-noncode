"""Bounded deterministic queries over downloaded-data quality diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality as quality_model
from . import downloaded_data_quality_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-query-v1"
BOUNDARY = "public_downloaded_data_quality_diff_query"
QUERY_PREFIX = "glio-noncode-download-quality-diff-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "items", "added", "removed", "changed", "unchanged", "improved", "regressed")
MAX_LIMIT = 1000
MAX_TOTAL_COUNT = diff_model.MAX_ITEMS * 3 + 1
ROW_FIELDS = ("ordinal", "resource", "identity", "change", "direction", "changed_attributes", "left_address", "right_address", "content_address")
QUERY_FIELDS = ("diff_address", "version", "boundary", "resources", "change", "direction", "identity", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
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


class DownloadedDataQualityDiffQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, change: str, direction: str, changed_attributes: Sequence[str], left_address: str, right_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality diff query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "quality diff query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("quality diff query row resource is unsupported")
        self.identity = _text(identity, "quality diff query row identity", 4096, required=True)
        self.change = _label(change, "quality diff query row change") if change else ""
        if self.change and self.change not in diff_model.CHANGES:
            raise ValidationError("quality diff query row change is unsupported")
        self.direction = _label(direction, "quality diff query row direction") if direction else ""
        if self.direction and self.direction not in diff_model.DIRECTIONS:
            raise ValidationError("quality diff query row direction is unsupported")
        self.changed_attributes = tuple(_label(item, "quality diff query changed attribute") for item in _sequence(changed_attributes, "quality diff query changed attributes", len(diff_model.ITEM_CHANGED_ATTRIBUTES)))
        if len(set(self.changed_attributes)) != len(self.changed_attributes) or any(item not in diff_model.ITEM_CHANGED_ATTRIBUTES for item in self.changed_attributes) or tuple(self.changed_attributes) != tuple(sorted(self.changed_attributes, key=diff_model.ITEM_CHANGED_ATTRIBUTES.index)):
            raise ValidationError("quality diff query changed attributes are unsupported, duplicated, or unordered")
        self.left_address = _address(left_address, "quality diff query row left address") if left_address else ""
        self.right_address = _address(right_address, "quality diff query row right address") if right_address else ""
        self.content_address = _address(content_address, "quality diff query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff query row address")
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and (self.change or self.direction or self.changed_attributes or self.left_address or self.right_address):
            raise ValidationError("summary query row contains item-only fields")
        if self.resource != "summary" and (not self.change or not self.direction):
            raise ValidationError("item query row is missing transition fields")
        if not _public(self.to_dict()):
            raise ValidationError("quality diff query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("quality diff query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffQueryRow":
        value = _mapping(value, "downloaded data quality diff query row")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataQualityDiffQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataQualityDiffQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, diff_address: str, version: str, boundary: str, resources: Sequence[str], change: str, direction: str, identity: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataQualityDiffQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.diff_address = _address(diff_address, "quality diff query diff address", diff_model.DIFF_PREFIX)
        self.version = _text(version, "quality diff query version")
        self.boundary = _text(boundary, "quality diff query boundary", 512)
        self.resources = tuple(_label(item, "quality diff query resource") for item in _sequence(resources, "quality diff query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(sorted(self.resources, key=RESOURCES.index)):
            raise ValidationError("quality diff query resources are unsupported, duplicated, or unordered")
        self.change = _label(change, "quality diff query change") if change else ""
        self.direction = _label(direction, "quality diff query direction") if direction else ""
        if self.change and self.change not in diff_model.CHANGES or self.direction and self.direction not in diff_model.DIRECTIONS:
            raise ValidationError("quality diff query filter is unsupported")
        self.identity = _text(identity, "quality diff query identity")
        self.text = _text(text, "quality diff query text", 1024)
        self.offset = _count(offset, "quality diff query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "quality diff query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "quality diff query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "quality diff query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "quality diff query returned count", MAX_TOTAL_COUNT)
        self.next_offset = _count(next_offset, "quality diff query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "quality diff query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataQualityDiffQueryRow) else DownloadedDataQualityDiffQueryRow.from_mapping(item) for item in _sequence(rows, "quality diff query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "quality diff query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff query address")
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.matched_count or self.matched_count < self.returned_count or self.returned_count != len(self.rows) or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.offset + self.matched_count) or tuple(row.ordinal for row in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("quality diff query pagination does not replay")
        if any(row.resource not in self.resources and row.resource != "summary" for row in self.rows):
            raise ValidationError("quality diff query row resource is outside the request")
        if self.version != VERSION or self.boundary != BOUNDARY or not _public(self.to_dict()):
            raise ValidationError("quality diff query version, boundary, or public projection failed")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("quality diff query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "change": self.change, "direction": self.direction, "identity": self.identity, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(row.to_dict() for row in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffQuery":
        value = _mapping(value, "downloaded data quality diff query")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataQualityDiffQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(ordinal: int, resource: str, item: diff_model.DownloadedDataQualityDiffItem | None) -> DownloadedDataQualityDiffQueryRow:
    if resource == "summary":
        body = {"ordinal": ordinal, "resource": "summary", "identity": "summary", "change": "", "direction": "", "changed_attributes": (), "left_address": "", "right_address": ""}
    else:
        if item is None:
            raise ValidationError("quality diff query item row requires an item")
        body = {"ordinal": ordinal, "resource": resource, "identity": item.identity, "change": item.change, "direction": item.direction, "changed_attributes": item.changed_attributes, "left_address": item.left_address, "right_address": item.right_address}
    provisional = DownloadedDataQualityDiffQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return DownloadedDataQualityDiffQueryRow(**body, content_address=address_row(provisional))


def query_diff(value: diff_model.DownloadedDataQualityDiff, *, resources: Sequence[str] = RESOURCES, change: str = "", direction: str = "", identity: str = "", text: str = "", offset: int = 0, limit: int = 100) -> DownloadedDataQualityDiffQuery:
    if not isinstance(value, diff_model.DownloadedDataQualityDiff):
        raise ValidationError("quality diff query requires a typed diff")
    requested = tuple(_label(item, "quality diff query resource") for item in resources)
    if not requested or len(set(requested)) != len(requested) or any(item not in RESOURCES for item in requested) or requested != tuple(sorted(requested, key=RESOURCES.index)):
        raise ValidationError("quality diff query resources are unsupported, duplicated, or unordered")
    change = _label(change, "quality diff query change") if change else ""
    direction = _label(direction, "quality diff query direction") if direction else ""
    identity = _text(identity, "quality diff query identity")
    text = _text(text, "quality diff query text", 1024)
    offset = _count(offset, "quality diff query offset", MAX_TOTAL_COUNT)
    limit = _count(limit, "quality diff query limit", MAX_LIMIT, positive=True)
    if change and change not in diff_model.CHANGES or direction and direction not in diff_model.DIRECTIONS:
        raise ValidationError("quality diff query filter is unsupported")
    candidates: list[tuple[str, diff_model.DownloadedDataQualityDiffItem | None]] = []
    for resource in requested:
        if resource == "summary":
            candidates.append((resource, None))
            continue
        for item in value.items:
            if resource in {"items", item.change, item.direction}:
                candidates.append((resource, item))
    filtered = []
    for resource, item in candidates:
        if item is not None:
            if change and item.change != change or direction and item.direction != direction or identity and identity not in item.identity:
                continue
            searchable = canonical_json(item.summary())
            if text and text.casefold() not in searchable.casefold():
                continue
        elif identity or change or direction or text:
            continue
        filtered.append((resource, item))
    total_count = len(candidates)
    matched_count = len(filtered)
    page = filtered[offset:offset + limit]
    rows = tuple(_row(offset + ordinal, resource, item) for ordinal, (resource, item) in enumerate(page, 1))
    body = {"diff_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": requested, "change": change, "direction": direction, "identity": identity, "text": text, "offset": offset, "limit": limit, "total_count": total_count, "matched_count": matched_count, "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < offset + matched_count, "rows": rows}
    provisional = DownloadedDataQualityDiffQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataQualityDiffQuery(**body, content_address=address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffQuery:
    return DownloadedDataQualityDiffQuery.from_mapping(value)


def query_json(value: DownloadedDataQualityDiffQuery) -> str:
    return canonical_json(DownloadedDataQualityDiffQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataQualityDiffQuery) -> str:
    value = DownloadedDataQualityDiffQuery.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(row.to_dict()[field] if field != "changed_attributes" else ";".join(row.changed_attributes) for field in ROW_FIELDS) for row in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataQualityDiffQuery) -> str:
    value = DownloadedDataQualityDiffQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Query", "", f"- Diff: `{value.diff_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", "", "| ordinal | resource | change | direction | identity |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | {row.resource} | {row.change or '—'} | {row.direction or '—'} | `{row.identity}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "change": {"enum": [""] + list(diff_model.CHANGES)}, "direction": {"enum": [""] + list(diff_model.DIRECTIONS)}, "changed_attributes": {"type": "array", "items": {"enum": list(diff_model.ITEM_CHANGED_ATTRIBUTES)}}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"diff_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "change": {"type": "string"}, "direction": {"type": "string"}, "identity": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "resources": RESOURCES, "operations": ("query_diff", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_limit": MAX_LIMIT, "max_total_count": MAX_TOTAL_COUNT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "DownloadedDataQualityDiffQuery", "DownloadedDataQualityDiffQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_diff", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
