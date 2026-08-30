"""Bounded public queries over policy package registry history diffs."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff as diff_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "items", "added", "removed", "changed", "unchanged")
CHANGES = diff_model.CHANGES
DIRECTIONS = diff_model.DIRECTIONS
QUERY_FIELDS = ("diff_address", "version", "boundary", "resources", "resource", "change", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")
ROW_FIELDS = ("ordinal", "resource", "identity", "change", "left_registry_address", "right_registry_address", "left_snapshot", "right_snapshot", "detail", "content_address")
MAX_TOTAL_COUNT = 1 + 2 * diff_model.MAX_ITEMS
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
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} must be a bounded count")
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
    values = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not values or len(values) != len(set(values)) or any(item not in allowed for item in values) or values != tuple(sorted(values, key=allowed.index)):
        raise ValidationError(f"{field} must contain unique values in canonical order")
    return values


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, change: str, left_registry_address: str, right_registry_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history diff query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "registry history diff query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("registry history diff query row resource is unsupported")
        self.identity = _label(identity, "registry history diff query row identity")
        self.change = _label(change, "registry history diff query row change")
        if self.change not in CHANGES:
            raise ValidationError("registry history diff query row change is unsupported")
        self.left_registry_address = _address(left_registry_address, "registry history diff query row left registry address", diff_model.registry_model.REGISTRY_PREFIX, required=False)
        self.right_registry_address = _address(right_registry_address, "registry history diff query row right registry address", diff_model.registry_model.REGISTRY_PREFIX, required=False)
        self.left_snapshot = _mapping(left_snapshot, "registry history diff query row left snapshot")
        self.right_snapshot = _mapping(right_snapshot, "registry history diff query row right snapshot")
        self.detail = _text(detail, "registry history diff query row detail", 1024)
        self.content_address = _address(content_address, "registry history diff query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource != "summary":
            if self.change == "added" and (not self.right_snapshot or self.left_snapshot or not self.right_registry_address or self.left_registry_address):
                raise ValidationError("added registry history diff query row is not one-sided")
            if self.change == "removed" and (not self.left_snapshot or self.right_snapshot or not self.left_registry_address or self.right_registry_address):
                raise ValidationError("removed registry history diff query row is not one-sided")
            if self.change in {"changed", "unchanged"} and (not self.left_snapshot or not self.right_snapshot or not self.left_registry_address or not self.right_registry_address):
                raise ValidationError("paired registry history diff query row is incomplete")
            if self.change == "unchanged" and (self.left_snapshot != self.right_snapshot or self.left_registry_address != self.right_registry_address):
                raise ValidationError("unchanged registry history diff query row contains a difference")
            if self.change == "changed" and self.left_snapshot == self.right_snapshot and self.left_registry_address == self.right_registry_address:
                raise ValidationError("changed registry history diff query row contains no difference")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("registry history diff query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow:
        value = _mapping(value, "registry history diff query row")
        _strict(value, set(cls.FIELDS), "registry history diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow):
        raise ValidationError("registry history diff query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, diff_address: str, version: str, boundary: str, resources: Sequence[str], resource: str, change: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.diff_address = _address(diff_address, "registry history diff query diff address", diff_model.DIFF_PREFIX)
        self.version = _text(version, "registry history diff query version", 512)
        self.boundary = _text(boundary, "registry history diff query boundary", 512)
        self.resources = _ordered_labels(resources, "registry history diff query resources", RESOURCES)
        self.resource = _label(resource, "registry history diff query resource", required=False)
        if self.resource and self.resource not in self.resources:
            raise ValidationError("registry history diff query resource filter is not selected")
        self.change = _label(change, "registry history diff query change", required=False)
        if self.change and self.change not in CHANGES:
            raise ValidationError("registry history diff query change filter is unsupported")
        self.text = _text(text, "registry history diff query text", 512, required=False)
        self.offset = _count(offset, "registry history diff query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "registry history diff query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "registry history diff query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "registry history diff query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "registry history diff query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "registry history diff query next offset", MAX_TOTAL_COUNT + MAX_LIMIT)
        self.truncated = _bool(truncated, "registry history diff query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow.from_mapping(item) for item in _sequence(rows, "registry history diff query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "registry history diff query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("registry history diff query version or boundary is not current")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.matched_count > self.total_count or self.returned_count > self.matched_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count) or tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)) or not _public(self.to_dict()):
            raise ValidationError("registry history diff query counts or rows do not replay")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("registry history diff query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "resource": self.resource, "change": self.change, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery:
        value = _mapping(value, "registry history diff query")
        _strict(value, set(cls.FIELDS), "registry history diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery):
        raise ValidationError("registry history diff query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(ordinal: int, resource: str, identity: str, change: str, left_address: str, right_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], detail: str) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "identity": identity, "change": change, "left_registry_address": left_address, "right_registry_address": right_address, "left_snapshot": left_snapshot, "right_snapshot": right_snapshot, "detail": detail, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def _rows(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff, resources: Sequence[str]) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow, ...]:
    rows: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow] = []
    ordinal = 1
    for resource in resources:
        if resource == "summary":
            rows.append(_row(ordinal, resource, value.diff_id, "changed" if value.direction == "mixed" else "unchanged", "", "", {}, {}, "registry history diff summary"))
            ordinal += 1
        else:
            for item in value.items:
                if resource == "items" or resource == item.change:
                    rows.append(_row(ordinal, resource, item.identity, item.change, item.left_registry_address, item.right_registry_address, item.left_snapshot, item.right_snapshot, f"{item.change} registry history snapshot"))
                    ordinal += 1
    return tuple(rows)


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow, query: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery) -> bool:
    if query.resource and row.resource != query.resource:
        return False
    if query.change and row.change != query.change:
        return False
    if query.text and query.text.casefold() not in " ".join((row.identity, row.change, row.left_registry_address, row.right_registry_address, row.detail)).casefold():
        return False
    return True


def query_diff(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff, *, resources: Sequence[str] = RESOURCES, resource: str = "", change: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery:
    if not isinstance(value, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff):
        raise ValidationError("registry history diff query requires a typed diff")
    resources = _ordered_labels(resources, "registry history diff query resources", RESOURCES)
    body = {"diff_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": resources, "resource": resource, "change": change, "text": text, "offset": offset, "limit": limit, "total_count": 0, "matched_count": 0, "returned_count": 0, "next_offset": 0, "truncated": False, "rows": (), "content_address": QUERY_PREFIX + ":pending"}
    provisional_query = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery(**body)
    all_rows = _rows(value, resources)
    matching = tuple(item for item in all_rows if _matches(item, provisional_query))
    page = matching[offset:offset + limit]
    rows = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow(**(item.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"})) for ordinal, item in enumerate(page, 1))
    rows = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow(**(item.to_dict() | {"content_address": address_row(item)})) for item in rows)
    body = body | {"total_count": len(all_rows), "matched_count": len(matching), "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < len(matching), "rows": rows}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery) -> str:
    value = query_from_mapping(value.to_dict())
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for item in value.rows:
        writer.writerow(tuple(json.dumps(item.to_dict()[field], ensure_ascii=False, sort_keys=True) if isinstance(item.to_dict()[field], (tuple, list, dict)) else item.to_dict()[field] for field in ROW_FIELDS))
    return output.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry History Diff Query", "", f"- Diff: `{value.diff_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | resource | identity | change | left | right |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.identity}` | `{item.change}` | `{item.left_registry_address}` | `{item.right_registry_address}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "change": {"enum": list(CHANGES)}, "left_registry_address": {"type": "string"}, "right_registry_address": {"type": "string"}, "left_snapshot": {"type": "object"}, "right_snapshot": {"type": "object"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"diff_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "resource": {"type": "string"}, "change": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": {"$ref": "#/$defs/row"}}, "content_address": {"type": "string"}}, "$defs": {"row": row_schema()}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": list(RESOURCES), "changes": list(CHANGES), "directions": list(DIRECTIONS), "max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT, "features": ["bounded diff summary queries", "item and change projections", "text and change filters", "deterministic pagination", "addressable rows", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False}}


__all__ = ["BOUNDARY", "CHANGES", "DIRECTIONS", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_diff", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
