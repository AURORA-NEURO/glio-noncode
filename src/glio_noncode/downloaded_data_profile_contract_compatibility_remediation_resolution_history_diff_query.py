"""Bounded queries over value-free remediation-history diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff as diff_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "items")
QUERY_FIELDS = ("diff_address", "version", "boundary", "resources", "resource", "change", "direction", "identity", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")
ROW_FIELDS = ("ordinal", "resource", "identity", "change", "changed_attributes", "left_address", "right_address", "content_address")
MAX_TOTAL_COUNT = diff_model.MAX_ITEMS + 1
MAX_LIMIT = 100


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
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


def _ordered_labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not labels or len(set(labels)) != len(labels) or any(item not in allowed for item in labels) or tuple(sorted(labels, key=allowed.index)) != labels:
        raise ValidationError(f"{field} contains unsupported or unordered labels")
    return labels


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, change: str, changed_attributes: Sequence[str], left_address: str, right_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "history diff query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("history diff query row resource is unsupported")
        self.identity = _label(identity, "history diff query row identity")
        self.change = _label(change, "history diff query row change")
        if self.change not in diff_model.CHANGES:
            raise ValidationError("history diff query row change is unsupported")
        self.changed_attributes = tuple(_label(item, "history diff query changed attribute") for item in _sequence(changed_attributes, "history diff query changed attributes", len(diff_model.CHANGED_ATTRIBUTES)))
        if len(set(self.changed_attributes)) != len(self.changed_attributes) or any(item not in diff_model.CHANGED_ATTRIBUTES for item in self.changed_attributes) or tuple(self.changed_attributes) != tuple(sorted(self.changed_attributes, key=diff_model.CHANGED_ATTRIBUTES.index)):
            raise ValidationError("history diff query changed attributes are unsupported, duplicated, or unordered")
        self.left_address = _address(left_address, "history diff query row left address", "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-entry", required=False)
        self.right_address = _address(right_address, "history diff query row right address", "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-entry", required=False)
        self.content_address = _address(content_address, "history diff query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and (self.left_address or self.right_address or self.changed_attributes):
            raise ValidationError("history diff query summary row contains item fields")
        if self.resource == "items" and self.change in {"changed", "unchanged"} and (not self.left_address or not self.right_address):
            raise ValidationError("history diff query item row is incomplete")
        if self.resource == "items" and self.change == "added" and (self.left_address or not self.right_address):
            raise ValidationError("history diff query added row has invalid addresses")
        if self.resource == "items" and self.change == "removed" and (not self.left_address or self.right_address):
            raise ValidationError("history diff query removed row has invalid addresses")
        if not _public(self.to_dict()):
            raise ValidationError("history diff query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("history diff query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow:
        value = _mapping(value, "history diff query row")
        _strict(value, set(cls.FIELDS), "history diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow):
        raise ValidationError("history diff query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, diff_address: str, version: str, boundary: str, resources: Sequence[str], resource: str, change: str, direction: str, identity: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.diff_address = _address(diff_address, "history diff query diff address", diff_model.DIFF_PREFIX)
        self.version = _text(version, "history diff query version")
        self.boundary = _text(boundary, "history diff query boundary", 512)
        self.resources = _ordered_labels(resources, "history diff query resources", RESOURCES)
        self.resource = _label(resource, "history diff query resource filter", required=False)
        if self.resource and self.resource not in RESOURCES:
            raise ValidationError("history diff query resource filter is unsupported")
        self.change = _label(change, "history diff query change filter", required=False)
        if self.change and self.change not in diff_model.CHANGES:
            raise ValidationError("history diff query change filter is unsupported")
        self.direction = _label(direction, "history diff query direction filter", required=False)
        if self.direction and self.direction not in diff_model.DIRECTIONS:
            raise ValidationError("history diff query direction filter is unsupported")
        self.identity = _label(identity, "history diff query identity filter", required=False)
        self.text = _text(text, "history diff query text", 1024, required=False)
        self.offset = _count(offset, "history diff query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "history diff query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "history diff query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "history diff query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "history diff query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "history diff query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "history diff query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow.from_mapping(item) for item in _sequence(rows, "history diff query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "history diff query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff query version or boundary is not current")
        if len(self.rows) != self.returned_count or self.returned_count > self.limit or tuple(row.ordinal for row in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("history diff query row order does not replay")
        if self.matched_count > self.total_count or self.returned_count > self.matched_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("history diff query counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("history diff query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "resource": self.resource, "change": self.change, "direction": self.direction, "identity": self.identity, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(row.to_dict() for row in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery:
        value = _mapping(value, "history diff query")
        _strict(value, set(cls.FIELDS), "history diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery):
        raise ValidationError("history diff query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _summary_row(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow:
    body = {"ordinal": 1, "resource": "summary", "identity": value.diff_id, "change": "unchanged", "changed_attributes": (), "left_address": "", "right_address": "", "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def _item_row(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow:
    body = {"ordinal": ordinal, "resource": "items", "identity": value.identity, "change": value.change, "changed_attributes": value.changed_attributes, "left_address": value.left_address, "right_address": value.right_address, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow, query: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery) -> bool:
    if row.resource == "summary":
        return not any((query.resource, query.change, query.identity, query.text))
    if query.resource and row.resource != query.resource:
        return False
    if query.change and row.change != query.change:
        return False
    if query.identity and query.identity.casefold() not in row.identity.casefold():
        return False
    haystack = " ".join((row.identity, row.change, " ".join(row.changed_attributes), row.left_address, row.right_address)).casefold()
    return not query.text or query.text.casefold() in haystack


def query_diff(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff, *, resources: Sequence[str] = RESOURCES, resource: str = "", change: str = "", direction: str = "", identity: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery:
    if not isinstance(value, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff):
        raise ValidationError("history diff query requires a typed diff")
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery(value.content_address, VERSION, BOUNDARY, resources, resource, change, direction, identity, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    rows = tuple([_summary_row(value)] if "summary" in provisional.resources else []) + tuple(_item_row(item, ordinal) for ordinal, item in enumerate(value.items, 2) if "items" in provisional.resources)
    matched = tuple(item for item in rows if _matches(item, provisional) and (not provisional.direction or (item.resource == "summary" and provisional.direction == value.direction)))
    selected = tuple(_readdress(item, ordinal) for ordinal, item in enumerate(matched[offset : offset + limit], 1))
    body = {"diff_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": provisional.resources, "resource": provisional.resource, "change": provisional.change, "direction": provisional.direction, "identity": provisional.identity, "text": provisional.text, "offset": provisional.offset, "limit": provisional.limit, "total_count": len(rows), "matched_count": len(matched), "returned_count": len(selected), "next_offset": provisional.offset + len(selected), "truncated": provisional.offset + len(selected) < len(matched), "rows": selected, "content_address": QUERY_PREFIX + ":pending"}
    provisional_result = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery(**(body | {"content_address": address_query(provisional_result)}))


def _readdress(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(";".join(item.changed_attributes) if field == "changed_attributes" else item.to_dict()[field] for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Diff Query", "", f"- Diff: `{value.diff_address}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", f"- Address: `{value.content_address}`", "", "| # | resource | identity | change |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.identity}` | `{row.change}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "change": {"enum": list(diff_model.CHANGES)}, "changed_attributes": {"type": "array", "items": {"enum": list(diff_model.CHANGED_ATTRIBUTES)}}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"diff_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "resource": {"type": "string"}, "change": {"type": "string"}, "direction": {"type": "string"}, "identity": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "changes": diff_model.CHANGES, "directions": diff_model.DIRECTIONS, "operations": ("query_diff", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_diff", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
