"""Bounded value-free queries over downloaded-data structural profiles."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile as profile_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-query-v1"
BOUNDARY = "public_downloaded_data_profile_query"
QUERY_PREFIX = "glio-noncode-download-profile-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "members", "fields", "types")
MAX_TEXT = 512
MAX_LIMIT = 10_000
MAX_TOTAL_COUNT = profile_model.MAX_FIELDS * 2 + profile_model.MAX_MEMBERS + profile_model.MAX_TYPE_COUNTS + 1
QUERY_FIELDS = (
    "profile_address",
    "version",
    "boundary",
    "resources",
    "member_name",
    "data_kind",
    "field_name",
    "value_type",
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
    "member_name",
    "data_kind",
    "field_name",
    "value_type",
    "count",
    "observed_count",
    "missing_count",
    "null_count",
    "distinct_value_count",
    "distinct_truncated",
    "min_value_size",
    "max_value_size",
    "member_count",
    "field_count",
    "record_count",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
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


class DownloadedDataProfileQueryRow:
    """One bounded structural-profile query row."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, member_name: str, data_kind: str, field_name: str, value_type: str, count: int, observed_count: int, missing_count: int, null_count: int, distinct_value_count: int, distinct_truncated: bool, min_value_size: int, max_value_size: int, member_count: int, field_count: int, record_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "profile query row ordinal", MAX_LIMIT, positive=True)
        self.resource = _label(resource, "profile query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("profile query row resource is unsupported")
        self.member_name = ingestion_model._safe_member_name(member_name, "profile query row member name") if member_name else ""
        self.data_kind = _label(data_kind, "profile query row data kind") if data_kind else ""
        if self.data_kind and self.data_kind not in ingestion_model.DATA_KINDS:
            raise ValidationError("profile query row data kind is unsupported")
        self.field_name = ingestion_model._key(field_name, "profile query row field name") if field_name else ""
        self.value_type = _label(value_type, "profile query row value type") if value_type else ""
        if self.value_type and self.value_type not in profile_model.VALUE_TYPES:
            raise ValidationError("profile query row value type is unsupported")
        self.count = _count(count, "profile query row count", profile_model.MAX_TOTAL_RECORDS)
        self.observed_count = _count(observed_count, "profile query row observed count", profile_model.MAX_TOTAL_RECORDS)
        self.missing_count = _count(missing_count, "profile query row missing count", profile_model.MAX_TOTAL_RECORDS)
        self.null_count = _count(null_count, "profile query row null count", profile_model.MAX_TOTAL_RECORDS)
        self.distinct_value_count = _count(distinct_value_count, "profile query row distinct count", profile_model.MAX_DISTINCT_VALUES)
        self.distinct_truncated = _bool(distinct_truncated, "profile query row distinct truncation")
        self.min_value_size = _count(min_value_size, "profile query row minimum size", ingestion_model.MAX_RECORD_BYTES)
        self.max_value_size = _count(max_value_size, "profile query row maximum size", ingestion_model.MAX_RECORD_BYTES)
        self.member_count = _count(member_count, "profile query row member count", profile_model.MAX_MEMBERS)
        self.field_count = _count(field_count, "profile query row field count", profile_model.MAX_FIELDS)
        self.record_count = _count(record_count, "profile query row record count", profile_model.MAX_RECORDS)
        self.content_address = _address(content_address, "profile query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "profile query row address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary":
            if any((self.member_name, self.data_kind, self.field_name, self.value_type, self.count, self.observed_count, self.missing_count, self.null_count, self.distinct_value_count, self.min_value_size, self.max_value_size)):
                raise ValidationError("summary profile query row has detail-only fields")
        elif self.resource == "members":
            if not self.member_name or not self.data_kind or not self.record_count or self.member_count or self.field_name or self.value_type:
                raise ValidationError("member profile query row is incomplete")
        elif self.resource == "fields":
            if not self.field_name or not self.observed_count + self.missing_count or self.member_name or self.data_kind or self.value_type:
                raise ValidationError("field profile query row is incomplete")
            if self.observed_count and self.min_value_size == 0:
                raise ValidationError("field profile query row has an invalid size range")
        elif self.resource == "types" and (not self.value_type or any((self.member_name, self.data_kind, self.field_name, self.observed_count, self.missing_count, self.null_count, self.distinct_value_count, self.min_value_size, self.max_value_size))):
            raise ValidationError("type profile query row is incomplete")
        if self.distinct_truncated and self.distinct_value_count != profile_model.MAX_DISTINCT_VALUES:
            raise ValidationError("profile query row has an invalid distinct cap")
        if not _public(self.to_dict()):
            raise ValidationError("profile query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("profile query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileQueryRow:
        value = _mapping(value, "profile query row")
        _strict(value, set(cls.FIELDS), "profile query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileQuery:
    """Content-addressed bounded selection of structural profile resources."""

    FIELDS = QUERY_FIELDS

    def __init__(self, profile_address: str, version: str, boundary: str, resources: Sequence[str], member_name: str, data_kind: str, field_name: str, value_type: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.profile_address = _address(profile_address, "profile query profile address", profile_model.PROFILE_PREFIX)
        self.version = _text(version, "profile query version", required=True)
        self.boundary = _text(boundary, "profile query boundary", 512, required=True)
        self.resources = tuple(_label(item, "profile query resource") for item in _sequence(resources, "profile query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(sorted(self.resources, key=RESOURCES.index)):
            raise ValidationError("profile query resources are unsupported, duplicated, or unordered")
        self.member_name = ingestion_model._safe_member_name(member_name, "profile query member name") if member_name else ""
        self.data_kind = _label(data_kind, "profile query data kind") if data_kind else ""
        if self.data_kind and self.data_kind not in ingestion_model.DATA_KINDS:
            raise ValidationError("profile query data kind is unsupported")
        self.field_name = ingestion_model._key(field_name, "profile query field name") if field_name else ""
        self.value_type = _label(value_type, "profile query value type") if value_type else ""
        if self.value_type and self.value_type not in profile_model.VALUE_TYPES:
            raise ValidationError("profile query value type is unsupported")
        self.text = _text(text, "profile query text", MAX_TEXT)
        self.offset = _count(offset, "profile query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "profile query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "profile query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "profile query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "profile query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "profile query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "profile query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileQueryRow) else DownloadedDataProfileQueryRow.from_mapping(item) for item in _sequence(rows, "profile query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "profile query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "profile query address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.matched_count or self.matched_count < self.returned_count or self.returned_count != len(self.rows) or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("profile query counts or truncation do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("profile query row ordinals are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("profile query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("profile query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"profile_address": self.profile_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "member_name": self.member_name, "data_kind": self.data_kind, "field_name": self.field_name, "value_type": self.value_type, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileQuery:
        value = _mapping(value, "downloaded data profile query")
        _strict(value, set(cls.FIELDS), "downloaded data profile query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _member_row(ordinal: int, member: profile_model.DownloadedDataMemberProfile) -> DownloadedDataProfileQueryRow:
    body = {"ordinal": ordinal, "resource": "members", "member_name": member.member_name, "data_kind": member.data_kind, "field_name": "", "value_type": "", "count": 0, "observed_count": 0, "missing_count": 0, "null_count": 0, "distinct_value_count": 0, "distinct_truncated": False, "min_value_size": 0, "max_value_size": 0, "member_count": 0, "field_count": member.field_count, "record_count": member.record_count, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileQueryRow(**body)
    return DownloadedDataProfileQueryRow(**(body | {"content_address": address_row(provisional)}))


def _field_row(ordinal: int, field: profile_model.DownloadedDataFieldProfile) -> DownloadedDataProfileQueryRow:
    body = {"ordinal": ordinal, "resource": "fields", "member_name": "", "data_kind": "", "field_name": field.field_name, "value_type": "", "count": 0, "observed_count": field.observed_count, "missing_count": field.missing_count, "null_count": field.null_count, "distinct_value_count": field.distinct_value_count, "distinct_truncated": field.distinct_truncated, "min_value_size": field.min_value_size, "max_value_size": field.max_value_size, "member_count": 0, "field_count": 0, "record_count": 0, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileQueryRow(**body)
    return DownloadedDataProfileQueryRow(**(body | {"content_address": address_row(provisional)}))


def _type_row(ordinal: int, entry: profile_model.DownloadedDataTypeCount) -> DownloadedDataProfileQueryRow:
    body = {"ordinal": ordinal, "resource": "types", "member_name": "", "data_kind": "", "field_name": "", "value_type": entry.value_type, "count": entry.count, "observed_count": 0, "missing_count": 0, "null_count": 0, "distinct_value_count": 0, "distinct_truncated": False, "min_value_size": 0, "max_value_size": 0, "member_count": 0, "field_count": 0, "record_count": 0, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileQueryRow(**body)
    return DownloadedDataProfileQueryRow(**(body | {"content_address": address_row(provisional)}))


def _summary_row(ordinal: int, profile: profile_model.DownloadedDataProfile) -> DownloadedDataProfileQueryRow:
    body = {"ordinal": ordinal, "resource": "summary", "member_name": "", "data_kind": "", "field_name": "", "value_type": "", "count": 0, "observed_count": 0, "missing_count": 0, "null_count": 0, "distinct_value_count": 0, "distinct_truncated": False, "min_value_size": 0, "max_value_size": 0, "member_count": profile.member_count, "field_count": profile.field_count, "record_count": profile.record_count, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileQueryRow(**body)
    return DownloadedDataProfileQueryRow(**(body | {"content_address": address_row(provisional)}))


def _matches(row: DownloadedDataProfileQueryRow, query: DownloadedDataProfileQuery) -> bool:
    if query.member_name and row.member_name != query.member_name:
        return False
    if query.data_kind and row.data_kind != query.data_kind:
        return False
    if query.field_name and row.field_name != query.field_name:
        return False
    if query.value_type and row.value_type != query.value_type:
        return False
    if query.text:
        haystack = " ".join((row.resource, row.member_name, row.data_kind, row.field_name, row.value_type)).casefold()
        if query.text.casefold() not in haystack:
            return False
    return True


def _readdress_row(row: DownloadedDataProfileQueryRow, ordinal: int) -> DownloadedDataProfileQueryRow:
    """Re-sequence a filtered row and derive its address from the final row body."""

    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileQueryRow(**body)
    return DownloadedDataProfileQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_profile(profile: profile_model.DownloadedDataProfile, *, resources: Sequence[str] = ("summary", "members", "fields", "types"), member_name: str = "", data_kind: str = "", field_name: str = "", value_type: str = "", text: str = "", offset: int = 0, limit: int = 100) -> DownloadedDataProfileQuery:
    if not isinstance(profile, profile_model.DownloadedDataProfile):
        raise ValidationError("profile query requires a typed downloaded data profile")
    normalized = tuple(sorted({_label(item, "profile query resource") for item in resources}, key=RESOURCES.index))
    if not normalized:
        raise ValidationError("profile query requires at least one resource")
    candidate = DownloadedDataProfileQuery(profile.content_address, VERSION, BOUNDARY, normalized, member_name, data_kind, field_name, value_type, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    all_rows: list[DownloadedDataProfileQueryRow] = []
    if "summary" in normalized:
        all_rows.append(_summary_row(1, profile))
    next_ordinal = len(all_rows) + 1
    if "members" in normalized:
        all_rows.extend(_member_row(next_ordinal + index, member) for index, member in enumerate(profile.members))
        next_ordinal = len(all_rows) + 1
    if "fields" in normalized:
        all_rows.extend(_field_row(next_ordinal + index, field) for index, field in enumerate(profile.fields))
        next_ordinal = len(all_rows) + 1
    if "types" in normalized:
        all_rows.extend(_type_row(next_ordinal + index, entry) for index, entry in enumerate(profile.type_counts))
    matched = tuple(row for row in all_rows if _matches(row, candidate))
    total_count = len(all_rows)
    start = min(offset, len(matched))
    selected = matched[start : start + limit]
    rows = tuple(_readdress_row(row, index) for index, row in enumerate(selected, 1))
    body = {"profile_address": profile.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": normalized, "member_name": candidate.member_name, "data_kind": candidate.data_kind, "field_name": candidate.field_name, "value_type": candidate.value_type, "text": candidate.text, "offset": offset, "limit": limit, "total_count": total_count, "matched_count": len(matched), "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < len(matched), "rows": rows}
    provisional = DownloadedDataProfileQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataProfileQuery(**body, content_address=address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileQuery:
    return DownloadedDataProfileQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileQuery) -> str:
    return canonical_json(DownloadedDataProfileQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileQuery) -> str:
    value = DownloadedDataProfileQuery.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for row in value.rows:
        writer.writerow(tuple(canonical_json(row.to_dict()[field]) if field == "content_address" else row.to_dict()[field] for field in ROW_FIELDS))
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileQuery) -> str:
    value = DownloadedDataProfileQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Query", "", f"- Profile: `{value.profile_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Returned: `{value.returned_count}/{value.matched_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | member | field | type | count | records |", "| ---: | --- | --- | --- | --- | ---: | ---: |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.member_name}` | `{row.field_name}` | `{row.value_type}` | {row.count} | {row.record_count} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "member_name": {"type": "string"}, "data_kind": {"type": "string"}, "field_name": {"type": "string"}, "value_type": {"enum": list(profile_model.VALUE_TYPES) + [""]}, "count": {"type": "integer", "minimum": 0}, "observed_count": {"type": "integer", "minimum": 0}, "missing_count": {"type": "integer", "minimum": 0}, "null_count": {"type": "integer", "minimum": 0}, "distinct_value_count": {"type": "integer", "minimum": 0, "maximum": profile_model.MAX_DISTINCT_VALUES}, "distinct_truncated": {"type": "boolean"}, "min_value_size": {"type": "integer", "minimum": 0}, "max_value_size": {"type": "integer", "minimum": 0}, "member_count": {"type": "integer", "minimum": 0}, "field_count": {"type": "integer", "minimum": 0}, "record_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"profile_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "member_name": {"type": "string"}, "data_kind": {"type": "string"}, "field_name": {"type": "string"}, "value_type": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "value_types": profile_model.VALUE_TYPES, "operations": ("query_profile", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"default_limit": 100, "max_limit": MAX_LIMIT, "max_query_items": MAX_TOTAL_COUNT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "DownloadedDataProfileQuery", "DownloadedDataProfileQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_profile", "query_schema", "render_query_markdown", "row_schema"]
