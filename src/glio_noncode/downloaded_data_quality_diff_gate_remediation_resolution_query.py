"""Bounded queries over quality-gate remediation resolution ledgers."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate_remediation as remediation_model
from . import downloaded_data_quality_diff_gate_remediation_resolution as resolution_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-remediation-resolution-query-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_remediation_resolution_query"
QUERY_PREFIX = "glio-noncode-download-quality-diff-gate-remediation-resolution-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "entries", "pending", "resolved", "waived", "rejected", "open")
MAX_TOTAL_COUNT = resolution_model.MAX_ENTRIES * len(RESOURCES) + 1
MAX_LIMIT = 100
DEFAULT_LIMIT = 25
ROW_FIELDS = ("ordinal", "resource", "action_address", "finding_address", "identity", "action", "priority", "required", "status", "evidence_addresses", "resolution_entry_address", "content_address")
QUERY_FIELDS = ("resolution_address", "version", "boundary", "resources", "status", "action", "priority", "required_only", "identity", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, optional: bool = False) -> str:
    if optional and value == "":
        return ""
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataQualityDiffGateRemediationResolutionQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, action_address: str, finding_address: str, identity: str, action: str, priority: str, required: bool, status: str, evidence_addresses: Sequence[str], resolution_entry_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality remediation resolution query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "quality remediation resolution query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("quality remediation resolution query row resource is unsupported")
        self.action_address = _address(action_address, "quality remediation resolution query row action address", remediation_model.ACTION_PREFIX, optional=self.resource == "summary")
        self.finding_address = _address(finding_address, "quality remediation resolution query row finding address", optional=self.resource == "summary")
        self.identity = _text(identity, "quality remediation resolution query row identity", 4096)
        self.action = _label(action, "quality remediation resolution query row action")
        if self.resource != "summary" and self.action not in remediation_model.ACTION_KINDS:
            raise ValidationError("quality remediation resolution query row action is unsupported")
        self.priority = _label(priority, "quality remediation resolution query row priority")
        if self.resource != "summary" and self.priority not in remediation_model.PRIORITIES:
            raise ValidationError("quality remediation resolution query row priority is unsupported")
        self.required = _bool(required, "quality remediation resolution query row requiredness")
        self.status = _label(status, "quality remediation resolution query row status")
        if self.resource != "summary" and self.status not in resolution_model.STATUSES:
            raise ValidationError("quality remediation resolution query row status is unsupported")
        self.evidence_addresses = tuple(sorted({_address(item, "quality remediation resolution query row evidence address") for item in _sequence(evidence_addresses, "quality remediation resolution query row evidence", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("quality remediation resolution query rows require evidence")
        self.resolution_entry_address = _address(resolution_entry_address, "quality remediation resolution query row entry address", resolution_model.ENTRY_PREFIX, optional=True)
        self.content_address = _address(content_address, "quality remediation resolution query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and any((self.action_address, self.finding_address, self.action != "summary", self.priority != "summary", self.status != "summary", self.resolution_entry_address, self.required)):
            raise ValidationError("quality remediation resolution summary row contains entry fields")
        if self.resource != "summary" and (not self.action_address or not self.finding_address or self.action == "summary" or self.priority == "summary" or self.status == "summary" or not self.resolution_entry_address):
            raise ValidationError("quality remediation resolution entry row is incomplete")
        if not _public(self.to_dict()):
            raise ValidationError("quality remediation resolution query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("quality remediation resolution query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationResolutionQueryRow":
        value = _mapping(value, "quality remediation resolution query row")
        _strict(value, set(cls.FIELDS), "quality remediation resolution query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataQualityDiffGateRemediationResolutionQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataQualityDiffGateRemediationResolutionQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, resolution_address: str, version: str, boundary: str, resources: Sequence[str], status: str, action: str, priority: str, required_only: bool, identity: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataQualityDiffGateRemediationResolutionQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.resolution_address = _address(resolution_address, "quality remediation resolution query resolution address", resolution_model.RESOLUTION_PREFIX)
        self.version = _text(version, "quality remediation resolution query version")
        self.boundary = _text(boundary, "quality remediation resolution query boundary", 512)
        self.resources = _ordered_labels(resources, "quality remediation resolution query resources", RESOURCES)
        self.status = _label(status, "quality remediation resolution query status", required=False)
        if self.status and self.status not in resolution_model.STATUSES:
            raise ValidationError("quality remediation resolution query status is unsupported")
        self.action = _label(action, "quality remediation resolution query action", required=False)
        if self.action and self.action not in remediation_model.ACTION_KINDS:
            raise ValidationError("quality remediation resolution query action is unsupported")
        self.priority = _label(priority, "quality remediation resolution query priority", required=False)
        if self.priority and self.priority not in remediation_model.PRIORITIES:
            raise ValidationError("quality remediation resolution query priority is unsupported")
        self.required_only = _bool(required_only, "quality remediation resolution query requiredness filter")
        self.identity = _text(identity, "quality remediation resolution query identity", 4096, required=False)
        self.text = _text(text, "quality remediation resolution query text", 1024, required=False)
        self.offset = _count(offset, "quality remediation resolution query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "quality remediation resolution query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "quality remediation resolution query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "quality remediation resolution query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "quality remediation resolution query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "quality remediation resolution query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "quality remediation resolution query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataQualityDiffGateRemediationResolutionQueryRow) else DownloadedDataQualityDiffGateRemediationResolutionQueryRow.from_mapping(item) for item in _sequence(rows, "quality remediation resolution query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "quality remediation resolution query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality remediation resolution query version or boundary is not current")
        if len(self.rows) != self.returned_count or self.returned_count > self.limit or tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("quality remediation resolution query rows are not contiguous")
        if self.matched_count > self.total_count or self.returned_count > self.matched_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("quality remediation resolution query counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("quality remediation resolution query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("quality remediation resolution query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"resolution_address": self.resolution_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "status": self.status, "action": self.action, "priority": self.priority, "required_only": self.required_only, "identity": self.identity, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationResolutionQuery":
        value = _mapping(value, "quality remediation resolution query")
        _strict(value, set(cls.FIELDS), "quality remediation resolution query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataQualityDiffGateRemediationResolutionQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(entry: resolution_model.DownloadedDataQualityDiffGateRemediationResolutionEntry, resource: str, ordinal: int) -> DownloadedDataQualityDiffGateRemediationResolutionQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "action_address": entry.action_address, "finding_address": entry.finding_address, "identity": entry.identity, "action": entry.action, "priority": entry.priority, "required": entry.required, "status": entry.status, "evidence_addresses": entry.evidence_addresses, "resolution_entry_address": entry.content_address, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationResolutionQueryRow(**body)
    return DownloadedDataQualityDiffGateRemediationResolutionQueryRow(**(body | {"content_address": address_row(provisional)}))


def _summary_row(value: resolution_model.DownloadedDataQualityDiffGateRemediationResolution) -> DownloadedDataQualityDiffGateRemediationResolutionQueryRow:
    body = {"ordinal": 1, "resource": "summary", "action_address": "", "finding_address": "", "identity": "summary", "action": "summary", "priority": "summary", "required": False, "status": "summary", "evidence_addresses": (value.content_address, value.plan_address), "resolution_entry_address": "", "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationResolutionQueryRow(**body)
    return DownloadedDataQualityDiffGateRemediationResolutionQueryRow(**(body | {"content_address": address_row(provisional)}))


def _project(value: resolution_model.DownloadedDataQualityDiffGateRemediationResolution, resources: Sequence[str]) -> tuple[DownloadedDataQualityDiffGateRemediationResolutionQueryRow, ...]:
    rows: list[DownloadedDataQualityDiffGateRemediationResolutionQueryRow] = []
    if "summary" in resources:
        rows.append(_summary_row(value))
    for resource in resources:
        if resource == "summary":
            continue
        selected = value.entries
        if resource in resolution_model.STATUSES:
            selected = tuple(item for item in selected if item.status == resource)
        elif resource == "open":
            selected = tuple(item for item in selected if item.required and item.status != "resolved")
        rows.extend(_row(item, resource, len(rows) + 1) for item in selected)
    return tuple(rows)


def _matches(row: DownloadedDataQualityDiffGateRemediationResolutionQueryRow, query: DownloadedDataQualityDiffGateRemediationResolutionQuery) -> bool:
    if row.resource not in query.resources:
        return False
    if row.resource == "summary":
        return not any((query.status, query.action, query.priority, query.required_only, query.identity)) and (not query.text or query.text.casefold() in "summary".casefold())
    if query.status and row.status != query.status:
        return False
    if query.action and row.action != query.action:
        return False
    if query.priority and row.priority != query.priority:
        return False
    if query.required_only and not row.required:
        return False
    if query.identity and query.identity.casefold() not in row.identity.casefold():
        return False
    if query.text:
        haystack = " ".join((row.identity, row.action, row.priority, row.status))
        if query.text.casefold() not in haystack.casefold():
            return False
    return True


def query_resolution(value: resolution_model.DownloadedDataQualityDiffGateRemediationResolution, *, resources: Sequence[str] = ("summary", "entries"), status: str = "", action: str = "", priority: str = "", required_only: bool = False, identity: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataQualityDiffGateRemediationResolutionQuery:
    if not isinstance(value, resolution_model.DownloadedDataQualityDiffGateRemediationResolution):
        raise ValidationError("quality remediation resolution query requires a typed resolution")
    requested = _ordered_labels(resources, "quality remediation resolution query resources", RESOURCES)
    offset = _count(offset, "quality remediation resolution query offset", MAX_TOTAL_COUNT)
    limit = _count(limit, "quality remediation resolution query limit", MAX_LIMIT, positive=True)
    probe = DownloadedDataQualityDiffGateRemediationResolutionQuery(value.content_address, VERSION, BOUNDARY, requested, status, action, priority, required_only, identity, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    all_rows = _project(value, requested)
    matched = tuple(row for row in all_rows if _matches(row, probe))
    page = matched[offset:offset + limit]
    rows = []
    for ordinal, row in enumerate(page, 1):
        body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
        provisional = DownloadedDataQualityDiffGateRemediationResolutionQueryRow(**body)
        rows.append(DownloadedDataQualityDiffGateRemediationResolutionQueryRow(**(body | {"content_address": address_row(provisional)})))
    body = {"resolution_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": requested, "status": status, "action": action, "priority": priority, "required_only": required_only, "identity": identity, "text": text, "offset": offset, "limit": limit, "total_count": len(all_rows), "matched_count": len(matched), "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < len(matched), "rows": tuple(rows)}
    provisional = DownloadedDataQualityDiffGateRemediationResolutionQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateRemediationResolutionQuery(**body, content_address=address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRemediationResolutionQuery:
    return DownloadedDataQualityDiffGateRemediationResolutionQuery.from_mapping(value)


def query_json(value: DownloadedDataQualityDiffGateRemediationResolutionQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataQualityDiffGateRemediationResolutionQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for item in value.rows:
        row = item.to_dict()
        writer.writerow(";".join(row[field]) if field == "evidence_addresses" else row[field] for field in ROW_FIELDS)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataQualityDiffGateRemediationResolutionQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Remediation Resolution Query", "", f"- Resolution: `{value.resolution_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Matched / returned: `{value.matched_count} / {value.returned_count}`", f"- Truncated: `{value.truncated}`", "", "| # | resource | status | action | priority | required | identity |", "| ---: | --- | --- | --- | --- | ---: | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.status}` | `{row.action}` | `{row.priority}` | `{row.required}` | `{row.identity}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation resolution query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {field: {"type": "array" if field == "evidence_addresses" else "string"} for field in ROW_FIELDS}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation resolution query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"resolution_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "status": {"type": "string"}, "action": {"type": "string"}, "priority": {"type": "string"}, "required_only": {"type": "boolean"}, "identity": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "operations": ("query_resolution", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataQualityDiffGateRemediationResolutionQuery", "DownloadedDataQualityDiffGateRemediationResolutionQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_resolution", "query_schema", "render_query_markdown", "row_schema"]
