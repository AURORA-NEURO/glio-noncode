"""Bounded, deterministic queries over downloaded-data quality decisions."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality as quality_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-query-v1"
BOUNDARY = "public_downloaded_data_quality_query"
QUERY_PREFIX = "glio-noncode-download-quality-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "findings")
MAX_TEXT = 512
MAX_LIMIT = 10_000
MAX_TOTAL_COUNT = quality_model.MAX_FINDINGS + 1
ROW_FIELDS = ("ordinal", "resource", "rule_id", "scope", "member_name", "field_name", "severity", "passed", "measured", "limit", "detail", "total_count", "content_address")
QUERY_FIELDS = ("quality_address", "version", "boundary", "resources", "rule_id", "scope", "severity", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")


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


class DownloadedDataQualityQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, rule_id: str, scope: str, member_name: str, field_name: str, severity: str, passed: bool, measured: int, limit: int, detail: str, total_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality query row ordinal", MAX_LIMIT, positive=True)
        self.resource = _label(resource, "quality query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("quality query row resource is unsupported")
        self.rule_id = _label(rule_id, "quality query row rule") if rule_id else ""
        if self.rule_id and self.rule_id not in quality_model.RULE_IDS:
            raise ValidationError("quality query row rule is unsupported")
        self.scope = _label(scope, "quality query row scope") if scope else ""
        if self.scope and self.scope not in quality_model.SCOPES:
            raise ValidationError("quality query row scope is unsupported")
        self.member_name = ingestion_model._safe_member_name(member_name, "quality query row member") if member_name else ""
        self.field_name = ingestion_model._key(field_name, "quality query row field") if field_name else ""
        self.severity = _label(severity, "quality query row severity") if severity else ""
        if self.severity and self.severity not in quality_model.SEVERITIES:
            raise ValidationError("quality query row severity is unsupported")
        self.passed = _bool(passed, "quality query row result")
        self.measured = _count(measured, "quality query row measured", max(quality_model.MAX_FINDINGS, ingestion_model.MAX_RECORD_BYTES))
        self.limit = _count(limit, "quality query row limit", max(quality_model.MAX_FINDINGS, ingestion_model.MAX_RECORD_BYTES))
        self.detail = _text(detail, "quality query row detail", MAX_TEXT)
        self.total_count = _count(total_count, "quality query row total count", MAX_TOTAL_COUNT)
        self.content_address = _address(content_address, "quality query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality query row address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and any((self.rule_id, self.scope, self.member_name, self.field_name, self.severity, self.measured, self.limit, self.detail)):
            raise ValidationError("summary quality query row contains finding-only fields")
        if self.resource == "findings" and not self.rule_id:
            raise ValidationError("finding quality query row is missing its rule")
        if not _public(self.to_dict()):
            raise ValidationError("quality query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("quality query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataQualityQueryRow:
        value = _mapping(value, "downloaded data quality query row")
        _strict(value, set(cls.FIELDS), "downloaded data quality query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataQualityQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataQualityQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, quality_address: str, version: str, boundary: str, resources: Sequence[str], rule_id: str, scope: str, severity: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataQualityQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.quality_address = _address(quality_address, "quality query quality address", quality_model.QUALITY_PREFIX)
        self.version = _text(version, "quality query version", required=True)
        self.boundary = _text(boundary, "quality query boundary", 512, required=True)
        self.resources = tuple(_label(item, "quality query resource") for item in _sequence(resources, "quality query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(sorted(self.resources, key=RESOURCES.index)):
            raise ValidationError("quality query resources are unsupported, duplicated, or unordered")
        self.rule_id = _label(rule_id, "quality query rule") if rule_id else ""
        if self.rule_id and self.rule_id not in quality_model.RULE_IDS:
            raise ValidationError("quality query rule is unsupported")
        self.scope = _label(scope, "quality query scope") if scope else ""
        if self.scope and self.scope not in quality_model.SCOPES:
            raise ValidationError("quality query scope is unsupported")
        self.severity = _label(severity, "quality query severity") if severity else ""
        if self.severity and self.severity not in quality_model.SEVERITIES:
            raise ValidationError("quality query severity is unsupported")
        self.text = _text(text, "quality query text", MAX_TEXT)
        self.offset = _count(offset, "quality query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "quality query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "quality query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "quality query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "quality query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "quality query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "quality query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataQualityQueryRow) else DownloadedDataQualityQueryRow.from_mapping(item) for item in _sequence(rows, "quality query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "quality query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality query address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.matched_count or self.matched_count < self.returned_count or self.returned_count != len(self.rows) or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("quality query counts or truncation do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("quality query row ordinals are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("quality query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("quality query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"quality_address": self.quality_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "rule_id": self.rule_id, "scope": self.scope, "severity": self.severity, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataQualityQuery:
        value = _mapping(value, "downloaded data quality query")
        _strict(value, set(cls.FIELDS), "downloaded data quality query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataQualityQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(ordinal: int, resource: str, finding: quality_model.DownloadedDataQualityFinding | None, total_count: int, quality: quality_model.DownloadedDataQuality) -> DownloadedDataQualityQueryRow:
    if finding is None:
        body = {"ordinal": ordinal, "resource": "summary", "rule_id": "", "scope": "", "member_name": "", "field_name": "", "severity": "", "passed": quality.accepted, "measured": 0, "limit": 0, "detail": "", "total_count": total_count, "content_address": ROW_PREFIX + ":pending"}
    else:
        body = {"ordinal": ordinal, "resource": resource, "rule_id": finding.rule_id, "scope": finding.scope, "member_name": finding.member_name, "field_name": finding.field_name, "severity": finding.severity, "passed": finding.passed, "measured": finding.measured, "limit": finding.limit, "detail": finding.detail, "total_count": total_count, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataQualityQueryRow(**body)
    return DownloadedDataQualityQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_quality(value: quality_model.DownloadedDataQuality, *, resources: Sequence[str] = RESOURCES, rule_id: str = "", scope: str = "", severity: str = "", text: str = "", offset: int = 0, limit: int = 100) -> DownloadedDataQualityQuery:
    if not isinstance(value, quality_model.DownloadedDataQuality):
        raise ValidationError("quality query requires a typed quality result")
    normalized_resources = tuple(resources)
    if "summary" in normalized_resources:
        candidates: list[quality_model.DownloadedDataQualityFinding | None] = [None]
    else:
        candidates = []
    if "findings" in normalized_resources:
        candidates.extend(value.findings)
    rule_id = _label(rule_id, "quality query rule") if rule_id else ""
    scope = _label(scope, "quality query scope") if scope else ""
    severity = _label(severity, "quality query severity") if severity else ""
    text = _text(text, "quality query text", MAX_TEXT)
    filtered = []
    for finding in candidates:
        if finding is None:
            if any((rule_id, scope, severity, text)):
                continue
        elif (rule_id and finding.rule_id != rule_id) or (scope and finding.scope != scope) or (severity and finding.severity != severity) or (text and text.casefold() not in finding.detail.casefold()):
            continue
        filtered.append(finding)
    total_count = len(candidates)
    matched_count = len(filtered)
    offset = _count(offset, "quality query offset", MAX_TOTAL_COUNT)
    limit = _count(limit, "quality query limit", MAX_LIMIT, positive=True)
    selected = filtered[offset : offset + limit]
    rows = tuple(_row(index, "findings", finding, total_count, value) if finding is not None else _row(index, "summary", None, total_count, value) for index, finding in enumerate(selected, 1))
    body = {"quality_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": normalized_resources, "rule_id": rule_id, "scope": scope, "severity": severity, "text": text, "offset": offset, "limit": limit, "total_count": total_count, "matched_count": matched_count, "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < matched_count, "rows": rows}
    provisional = DownloadedDataQualityQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataQualityQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityQuery:
    return DownloadedDataQualityQuery.from_mapping(value)


def query_json(value: DownloadedDataQualityQuery) -> str:
    return canonical_json(DownloadedDataQualityQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataQualityQuery) -> str:
    value = DownloadedDataQualityQuery.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataQualityQuery) -> str:
    value = DownloadedDataQualityQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Query", "", f"- Quality: `{value.quality_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.matched_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | rule | target | passed |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.rule_id or 'summary'}` | `{item.field_name or item.member_name or 'summary'}` | `{item.passed}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "rule_id": {"type": "string"}, "scope": {"type": "string"}, "member_name": {"type": "string"}, "field_name": {"type": "string"}, "severity": {"type": "string"}, "passed": {"type": "boolean"}, "measured": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 0}, "detail": {"type": "string"}, "total_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"quality_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "rule_id": {"type": "string"}, "scope": {"type": "string"}, "severity": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "resources": RESOURCES, "operations": ("query_quality", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_limit": MAX_LIMIT, "max_total_count": MAX_TOTAL_COUNT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "DownloadedDataQualityQuery", "DownloadedDataQualityQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_quality", "query_schema", "render_query_markdown", "row_schema"]
