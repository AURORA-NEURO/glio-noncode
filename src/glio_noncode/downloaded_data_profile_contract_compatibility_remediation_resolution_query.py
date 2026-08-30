"""Bounded queries over value-free remediation resolution ledgers."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation as remediation_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution as resolution_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "entries")
QUERY_FIELDS = (
    "resolution_address",
    "version",
    "boundary",
    "resources",
    "status",
    "action",
    "priority",
    "required",
    "identity",
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
ROW_FIELDS = ("ordinal", "resource", "action_address", "identity", "action", "priority", "required", "status", "evidence_addresses", "resolution_entry_address", "content_address")
MAX_TOTAL_COUNT = resolution_model.MAX_ENTRIES + 1
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


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, action_address: str, identity: str, action: str, priority: str, required: bool, status: str, evidence_addresses: Sequence[str], resolution_entry_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "resolution query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "resolution query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("resolution query row resource is unsupported")
        self.action_address = _address(action_address, "resolution query row action address") if action_address else ""
        self.identity = _text(identity, "resolution query row identity", 4096)
        self.action = _label(action, "resolution query row action")
        if self.action != "summary" and self.action not in remediation_model.ACTION_KINDS:
            raise ValidationError("resolution query row action is unsupported")
        self.priority = _label(priority, "resolution query row priority")
        if self.priority != "summary" and self.priority not in remediation_model.PRIORITIES:
            raise ValidationError("resolution query row priority is unsupported")
        self.required = _bool(required, "resolution query row requiredness")
        self.status = _label(status, "resolution query row status")
        if self.status != "summary" and self.status not in resolution_model.STATUSES:
            raise ValidationError("resolution query row status is unsupported")
        self.evidence_addresses = tuple(sorted({_address(item, "resolution query row evidence address") for item in _sequence(evidence_addresses, "resolution query row evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("resolution query rows require evidence")
        self.resolution_entry_address = _address(resolution_entry_address, "resolution query row entry address") if resolution_entry_address else ""
        self.content_address = _address(content_address, "resolution query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and any((self.action_address, self.action != "summary", self.priority != "summary", self.status != "summary", self.resolution_entry_address)):
            raise ValidationError("resolution summary row contains entry fields")
        if self.resource == "entries" and (not self.action_address or self.action == "summary" or self.priority == "summary" or self.status == "summary" or not self.resolution_entry_address):
            raise ValidationError("resolution entry row is incomplete")
        if not _public(self.to_dict()):
            raise ValidationError("resolution query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("resolution query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow:
        value = _mapping(value, "resolution query row")
        _strict(value, set(cls.FIELDS), "resolution query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow):
        raise ValidationError("resolution query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, resolution_address: str, version: str, boundary: str, resources: Sequence[str], status: str, action: str, priority: str, required: bool, identity: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.resolution_address = _address(resolution_address, "resolution query resolution address", resolution_model.RESOLUTION_PREFIX)
        self.version = _text(version, "resolution query version")
        self.boundary = _text(boundary, "resolution query boundary", 512)
        self.resources = _ordered_labels(resources, "resolution query resources", RESOURCES)
        self.status = _label(status, "resolution query status", required=False)
        if self.status and self.status not in resolution_model.STATUSES:
            raise ValidationError("resolution query status is unsupported")
        self.action = _label(action, "resolution query action", required=False)
        if self.action and self.action not in remediation_model.ACTION_KINDS:
            raise ValidationError("resolution query action is unsupported")
        self.priority = _label(priority, "resolution query priority", required=False)
        if self.priority and self.priority not in remediation_model.PRIORITIES:
            raise ValidationError("resolution query priority is unsupported")
        self.required = _bool(required, "resolution query requiredness")
        self.identity = _text(identity, "resolution query identity", 4096, required=False)
        self.text = _text(text, "resolution query text", 1024, required=False)
        self.offset = _count(offset, "resolution query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "resolution query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "resolution query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "resolution query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "resolution query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "resolution query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "resolution query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow.from_mapping(item) for item in _sequence(rows, "resolution query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "resolution query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("resolution query version or boundary is not current")
        if len(self.rows) != self.returned_count or self.returned_count > self.limit or tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("resolution query row order does not replay")
        if self.matched_count > self.total_count or self.returned_count > self.matched_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("resolution query counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("resolution query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("resolution query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"resolution_address": self.resolution_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "status": self.status, "action": self.action, "priority": self.priority, "required": self.required, "identity": self.identity, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQuery:
        value = _mapping(value, "resolution query")
        _strict(value, set(cls.FIELDS), "resolution query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionQuery):
        raise ValidationError("resolution query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _summary_row(value: resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow:
    body = {"ordinal": 1, "resource": "summary", "action_address": "", "identity": "resolution-summary", "action": "summary", "priority": "summary", "required": False, "status": "summary", "evidence_addresses": (value.content_address,), "resolution_entry_address": "", "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow(**(body | {"content_address": address_row(provisional)}))


def _entry_row(value: resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolutionEntry, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow:
    body = {"ordinal": ordinal, "resource": "entries", "action_address": value.action_address, "identity": value.identity, "action": value.action, "priority": value.priority, "required": value.required, "status": value.status, "evidence_addresses": value.evidence_addresses, "resolution_entry_address": value.content_address, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow(**(body | {"content_address": address_row(provisional)}))


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow, query: DownloadedDataProfileContractCompatibilityRemediationResolutionQuery) -> bool:
    if row.resource == "summary":
        return not any((query.status, query.action, query.priority, query.identity)) and not query.required and (not query.text or query.text.casefold() in "resolution-summary")
    if query.status and row.status != query.status:
        return False
    if query.action and row.action != query.action:
        return False
    if query.priority and row.priority != query.priority:
        return False
    if query.required and not row.required:
        return False
    if query.identity and query.identity.casefold() not in row.identity.casefold():
        return False
    haystack = " ".join((row.identity, row.action_address, row.action, row.priority, row.status, row.resolution_entry_address)).casefold()
    return not query.text or query.text.casefold() in haystack


def query_resolution(value: resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution, *, resources: Sequence[str] = RESOURCES, status: str = "", action: str = "", priority: str = "", required: bool = False, identity: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQuery:
    if not isinstance(value, resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution):
        raise ValidationError("resolution query requires a typed resolution")
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionQuery(value.content_address, VERSION, BOUNDARY, resources, status, action, priority, required, identity, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    rows = tuple([_summary_row(value)] if "summary" in provisional.resources else []) + tuple(_entry_row(item, ordinal) for ordinal, item in enumerate(value.entries, 2) if "entries" in provisional.resources)
    matched = tuple(item for item in rows if _matches(item, provisional))
    selected = matched[offset : offset + limit]
    selected = tuple(_readdress(item, ordinal) for ordinal, item in enumerate(selected, 1))
    body = {"resolution_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": provisional.resources, "status": provisional.status, "action": provisional.action, "priority": provisional.priority, "required": provisional.required, "identity": provisional.identity, "text": provisional.text, "offset": provisional.offset, "limit": provisional.limit, "total_count": len(rows), "matched_count": len(matched), "returned_count": len(selected), "next_offset": provisional.offset + len(selected), "truncated": provisional.offset + len(selected) < len(matched), "rows": selected, "content_address": QUERY_PREFIX + ":pending"}
    provisional_result = DownloadedDataProfileContractCompatibilityRemediationResolutionQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionQuery(**(body | {"content_address": address_query(provisional_result)}))


def _readdress(row: DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQuery:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionQuery) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionQuery) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionQuery.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionQuery) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution Query", "", f"- Resolution: `{value.resolution_address}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", f"- Address: `{value.content_address}`", "", "| # | identity | action | status | priority | required |", "| ---: | --- | --- | --- | --- | ---: |"]
    lines.extend(f"| {row.ordinal} | `{row.identity}` | `{row.action}` | `{row.status}` | `{row.priority}` | `{row.required}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "action_address": {"type": "string"}, "identity": {"type": "string"}, "action": {"type": "string"}, "priority": {"type": "string"}, "required": {"type": "boolean"}, "status": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "resolution_entry_address": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"resolution_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "status": {"type": "string"}, "action": {"type": "string"}, "priority": {"type": "string"}, "required": {"type": "boolean"}, "identity": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "statuses": resolution_model.STATUSES, "operations": ("query_resolution", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_resolution", "query_schema", "render_query_markdown", "row_schema"]
