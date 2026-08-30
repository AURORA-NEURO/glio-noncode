"""Bounded, value-free queries over downloaded-data contract transitions."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-diff-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_diff_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-diff-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary",) + diff_model.RESOURCES
MAX_TEXT = 512
MAX_LIMIT = 10_000
MAX_TOTAL_COUNT = 1 + diff_model.MAX_ITEMS
QUERY_FIELDS = (
    "diff_address", "version", "boundary", "resources", "change", "identity", "attribute", "text",
    "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated",
    "rows", "content_address",
)
ROW_FIELDS = (
    "ordinal", "resource", "change", "identity", "changed_attributes", "left_address", "right_address",
    "left_snapshot", "right_snapshot", "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
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
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value):
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and value and not value.startswith(prefix + ":"):
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


class DownloadedDataProfileContractDiffQueryRow:
    """One value-free transition row returned by a diff query."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, change: str, identity: str, changed_attributes: Sequence[str], left_address: str, right_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "contract diff query row ordinal", MAX_LIMIT, positive=True)
        self.resource = _label(resource, "contract diff query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("contract diff query row resource is unsupported")
        self.change = _label(change, "contract diff query row change")
        if self.resource == "summary":
            if self.change != "summary":
                raise ValidationError("summary diff query row must use summary change")
        elif self.change not in diff_model.CHANGES:
            raise ValidationError("contract diff query row change is unsupported")
        self.identity = _text(identity, "contract diff query row identity", 4096, required=True)
        allowed = () if self.resource == "summary" else diff_model._attribute_names(self.resource)
        self.changed_attributes = tuple(_label(item, "contract diff query changed attribute") for item in _sequence(changed_attributes, "contract diff query changed attributes", len(allowed)))
        if len(set(self.changed_attributes)) != len(self.changed_attributes) or any(item not in allowed for item in self.changed_attributes) or tuple(self.changed_attributes) != tuple(sorted(self.changed_attributes, key=allowed.index)):
            raise ValidationError("contract diff query changed attributes are unsupported, duplicated, or unordered")
        self.left_address = _address(left_address, "contract diff query left address", required=False)
        self.right_address = _address(right_address, "contract diff query right address", required=False)
        self.left_snapshot = dict(_mapping(left_snapshot, "contract diff query left snapshot"))
        self.right_snapshot = dict(_mapping(right_snapshot, "contract diff query right snapshot"))
        if self.resource == "summary":
            if self.identity != "summary" or not self.left_snapshot or not self.right_snapshot or not self.left_address or not self.right_address:
                raise ValidationError("summary diff query row is incomplete")
        else:
            if self.change == "added" and (self.left_address or self.left_snapshot or not self.right_address or not self.right_snapshot):
                raise ValidationError("added diff query row has invalid left side")
            if self.change == "removed" and (not self.left_address or not self.left_snapshot or self.right_address or self.right_snapshot):
                raise ValidationError("removed diff query row has invalid right side")
            if self.change in {"changed", "unchanged"} and (not self.left_address or not self.right_address or not self.left_snapshot or not self.right_snapshot):
                raise ValidationError("paired diff query row is missing a side")
            if self.change == "unchanged" and self.changed_attributes:
                raise ValidationError("unchanged diff query row has changed attributes")
            if self.change == "changed" and not self.changed_attributes:
                raise ValidationError("changed diff query row has no changed attributes")
            typed = diff_model.DownloadedDataProfileContractDiffItem(
                self.ordinal, self.resource, self.identity, self.change, self.changed_attributes,
                self.left_address, self.right_address, self.left_snapshot, self.right_snapshot,
                diff_model.ITEM_PREFIX + ":pending",
            )
            if typed.change != self.change:
                raise ValidationError("diff query row does not replay a transition")
        self.content_address = _address(content_address, "contract diff query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract diff query row address", required=True)
        if not _public(self.to_dict()):
            raise ValidationError("contract diff query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("contract diff query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffQueryRow:
        value = _mapping(value, "downloaded data profile contract diff query row")
        _strict(value, set(cls.FIELDS), "downloaded data profile contract diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractDiffQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractDiffQuery:
    """Content-addressed bounded selection of contract-diff resources."""

    FIELDS = QUERY_FIELDS

    def __init__(self, diff_address: str, version: str, boundary: str, resources: Sequence[str], change: str, identity: str, attribute: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractDiffQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.diff_address = _address(diff_address, "contract diff query diff address", diff_model.DIFF_PREFIX)
        self.version = _text(version, "contract diff query version", required=True)
        self.boundary = _text(boundary, "contract diff query boundary", 512, required=True)
        self.resources = tuple(_label(item, "contract diff query resource") for item in _sequence(resources, "contract diff query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(sorted(self.resources, key=RESOURCES.index)):
            raise ValidationError("contract diff query resources are unsupported, duplicated, or unordered")
        self.change = _label(change, "contract diff query change", required=False)
        if self.change and self.change not in diff_model.CHANGES:
            raise ValidationError("contract diff query change filter is unsupported")
        self.identity = _text(identity, "contract diff query identity", 4096)
        self.attribute = _label(attribute, "contract diff query attribute", required=False)
        if self.attribute and not any(self.attribute in diff_model._attribute_names(resource) for resource in diff_model.RESOURCES):
            raise ValidationError("contract diff query attribute filter is unsupported")
        self.text = _text(text, "contract diff query text", MAX_TEXT)
        self.offset = _count(offset, "contract diff query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "contract diff query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "contract diff query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "contract diff query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "contract diff query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "contract diff query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "contract diff query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractDiffQueryRow) else DownloadedDataProfileContractDiffQueryRow.from_mapping(item) for item in _sequence(rows, "contract diff query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "contract diff query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract diff query address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("contract diff query version or boundary is not current")
        if self.total_count < self.matched_count or self.matched_count < self.returned_count or self.returned_count != len(self.rows) or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("contract diff query counts or truncation do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)) or any(item.resource not in self.resources for item in self.rows):
            raise ValidationError("contract diff query row order or resource selection is invalid")
        if self.change and any(item.change not in {self.change} for item in self.rows if item.resource != "summary"):
            raise ValidationError("contract diff query change filter does not replay")
        if self.attribute and any(self.attribute not in item.changed_attributes for item in self.rows if item.resource != "summary"):
            raise ValidationError("contract diff query attribute filter does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("contract diff query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("contract diff query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "change": self.change, "identity": self.identity, "attribute": self.attribute, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffQuery:
        value = _mapping(value, "downloaded data profile contract diff query")
        _strict(value, set(cls.FIELDS), "downloaded data profile contract diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractDiffQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _summary_row(value: diff_model.DownloadedDataProfileContractDiff) -> DownloadedDataProfileContractDiffQueryRow:
    left = {"record_count": value.left_record_count, "field_count": value.left_field_count, "member_count": value.left_member_count}
    right = {"record_count": value.right_record_count, "field_count": value.right_field_count, "member_count": value.right_member_count}
    body = {"ordinal": 1, "resource": "summary", "change": "summary", "identity": "summary", "changed_attributes": (), "left_address": value.left_contract_address, "right_address": value.right_contract_address, "left_snapshot": left, "right_snapshot": right, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractDiffQueryRow(**body)
    return DownloadedDataProfileContractDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def _item_row(ordinal: int, item: diff_model.DownloadedDataProfileContractDiffItem) -> DownloadedDataProfileContractDiffQueryRow:
    body = item.to_dict() | {"content_address": ROW_PREFIX + ":pending"}
    body["ordinal"] = ordinal
    provisional = DownloadedDataProfileContractDiffQueryRow(**body)
    return DownloadedDataProfileContractDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def _readdress_row(row: DownloadedDataProfileContractDiffQueryRow, ordinal: int) -> DownloadedDataProfileContractDiffQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractDiffQueryRow(**body)
    return DownloadedDataProfileContractDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def _matches(row: DownloadedDataProfileContractDiffQueryRow, query: DownloadedDataProfileContractDiffQuery) -> bool:
    if row.resource not in query.resources:
        return False
    if query.change and row.change != query.change:
        return False
    if query.identity and query.identity.casefold() not in row.identity.casefold():
        return False
    if query.attribute and query.attribute not in row.changed_attributes:
        return False
    haystack = " ".join((row.resource, row.change, row.identity, *row.changed_attributes)).casefold()
    return not query.text or query.text.casefold() in haystack


def query_diff(value: diff_model.DownloadedDataProfileContractDiff, *, resources: Sequence[str] = RESOURCES, change: str = "", identity: str = "", attribute: str = "", text: str = "", offset: int = 0, limit: int = 100) -> DownloadedDataProfileContractDiffQuery:
    if not isinstance(value, diff_model.DownloadedDataProfileContractDiff):
        raise ValidationError("contract diff query requires a typed diff")
    if not resources:
        raise ValidationError("contract diff query requires resources")
    provisional = DownloadedDataProfileContractDiffQuery(value.content_address, VERSION, BOUNDARY, resources, change, identity, attribute, text, offset, limit, 0, 0, 0, 0, False, (), QUERY_PREFIX + ":pending")
    all_rows = []
    if "summary" in provisional.resources:
        all_rows.append(_summary_row(value))
    for item in value.items:
        if item.resource in provisional.resources:
            all_rows.append(_item_row(len(all_rows) + 1, item))
    matched = tuple(row for row in all_rows if _matches(row, provisional))
    selected = tuple(_readdress_row(row, index) for index, row in enumerate(matched[offset:offset + limit], 1))
    body = {"diff_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": provisional.resources, "change": provisional.change, "identity": provisional.identity, "attribute": provisional.attribute, "text": provisional.text, "offset": provisional.offset, "limit": provisional.limit, "total_count": len(all_rows), "matched_count": len(matched), "returned_count": len(selected), "next_offset": provisional.offset + len(selected), "truncated": provisional.offset + len(selected) < len(matched), "rows": selected, "content_address": QUERY_PREFIX + ":pending"}
    final = DownloadedDataProfileContractDiffQuery(**body)
    return DownloadedDataProfileContractDiffQuery(**(body | {"content_address": address_query(final)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffQuery:
    return DownloadedDataProfileContractDiffQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractDiffQuery) -> str:
    return canonical_json(DownloadedDataProfileContractDiffQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractDiffQuery) -> str:
    value = DownloadedDataProfileContractDiffQuery.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(canonical_json(item.to_dict()[field]) if field in {"changed_attributes", "left_snapshot", "right_snapshot"} else item.to_dict()[field] for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractDiffQuery) -> str:
    value = DownloadedDataProfileContractDiffQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Diff Query", "", f"- Diff: `{value.diff_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", f"- Address: `{value.content_address}`", "", "| # | resource | identity | change | attributes |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.identity}` | `{row.change}` | `{', '.join(row.changed_attributes)}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract diff query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "change": {"type": "string"}, "identity": {"type": "string"}, "changed_attributes": {"type": "array", "items": {"type": "string"}}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "left_snapshot": {"type": "object"}, "right_snapshot": {"type": "object"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract diff query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"diff_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "change": {"type": "string"}, "identity": {"type": "string"}, "attribute": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "operations": ("query_diff", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "DownloadedDataProfileContractDiffQuery", "DownloadedDataProfileContractDiffQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_diff", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
