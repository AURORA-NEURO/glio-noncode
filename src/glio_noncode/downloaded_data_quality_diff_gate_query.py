"""Bounded deterministic queries over downloaded-data quality-gate findings."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-query-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_query"
QUERY_PREFIX = "glio-noncode-download-quality-diff-gate-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "findings", "safe", "review", "blocked", "allowed", "disallowed")
MAX_LIMIT = 1000
MAX_TOTAL_COUNT = gate_model.MAX_FINDINGS * 3 + 1
ROW_FIELDS = ("ordinal", "resource", "identity", "direction", "outcome", "reason_codes", "left_address", "right_address", "diff_item_address", "content_address")
QUERY_FIELDS = ("gate_address", "version", "boundary", "resources", "outcome", "direction", "identity", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")


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


class DownloadedDataQualityDiffGateQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, direction: str, outcome: str, reason_codes: Sequence[str], left_address: str, right_address: str, diff_item_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality diff gate query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "quality diff gate query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("quality diff gate query row resource is unsupported")
        self.identity = _text(identity, "quality diff gate query row identity", 4096, required=True)
        self.direction = _label(direction, "quality diff gate query row direction") if direction else ""
        if self.direction and self.direction not in gate_model.diff_model.DIRECTIONS:
            raise ValidationError("quality diff gate query row direction is unsupported")
        self.outcome = _label(outcome, "quality diff gate query row outcome") if outcome else ""
        if self.outcome and self.outcome not in gate_model.OUTCOMES:
            raise ValidationError("quality diff gate query row outcome is unsupported")
        self.reason_codes = tuple(_label(item, "quality diff gate query reason code") for item in _sequence(reason_codes, "quality diff gate query reason codes", len(gate_model.REASON_CODES)))
        if len(set(self.reason_codes)) != len(self.reason_codes) or any(item not in gate_model.REASON_CODES for item in self.reason_codes) or tuple(sorted(self.reason_codes, key=gate_model.REASON_CODES.index)) != self.reason_codes:
            raise ValidationError("quality diff gate query reason codes are unsupported, duplicated, or unordered")
        self.left_address = _address(left_address, "quality diff gate query row left address") if left_address else ""
        self.right_address = _address(right_address, "quality diff gate query row right address") if right_address else ""
        self.diff_item_address = _address(diff_item_address, "quality diff gate query row diff item address") if diff_item_address else ""
        self.content_address = _address(content_address, "quality diff gate query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff gate query row address")
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and (self.direction or self.outcome or self.reason_codes or self.left_address or self.right_address or self.diff_item_address):
            raise ValidationError("summary gate query row contains finding-only fields")
        if self.resource != "summary" and (not self.direction or not self.outcome or not self.diff_item_address):
            raise ValidationError("finding gate query row is missing classification fields")
        if not _public(self.to_dict()):
            raise ValidationError("quality diff gate query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("quality diff gate query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateQueryRow":
        value = _mapping(value, "downloaded data quality diff gate query row")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataQualityDiffGateQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataQualityDiffGateQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, gate_address: str, version: str, boundary: str, resources: Sequence[str], outcome: str, direction: str, identity: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataQualityDiffGateQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.gate_address = _address(gate_address, "quality diff gate query gate address", gate_model.GATE_PREFIX)
        self.version = _text(version, "quality diff gate query version")
        self.boundary = _text(boundary, "quality diff gate query boundary", 512)
        self.resources = tuple(_label(item, "quality diff gate query resource") for item in _sequence(resources, "quality diff gate query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(sorted(self.resources, key=RESOURCES.index)):
            raise ValidationError("quality diff gate query resources are unsupported, duplicated, or unordered")
        self.outcome = _label(outcome, "quality diff gate query outcome") if outcome else ""
        self.direction = _label(direction, "quality diff gate query direction") if direction else ""
        if self.outcome and self.outcome not in gate_model.OUTCOMES or self.direction and self.direction not in gate_model.diff_model.DIRECTIONS:
            raise ValidationError("quality diff gate query filter is unsupported")
        self.identity = _text(identity, "quality diff gate query identity")
        self.text = _text(text, "quality diff gate query text", 1024)
        self.offset = _count(offset, "quality diff gate query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "quality diff gate query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "quality diff gate query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "quality diff gate query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "quality diff gate query returned count", MAX_TOTAL_COUNT)
        self.next_offset = _count(next_offset, "quality diff gate query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "quality diff gate query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataQualityDiffGateQueryRow) else DownloadedDataQualityDiffGateQueryRow.from_mapping(item) for item in _sequence(rows, "quality diff gate query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "quality diff gate query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff gate query address")
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.matched_count or self.matched_count < self.returned_count or self.returned_count != len(self.rows) or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.offset + self.matched_count) or tuple(row.ordinal for row in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("quality diff gate query pagination does not replay")
        if any(row.resource not in self.resources and row.resource != "summary" for row in self.rows):
            raise ValidationError("quality diff gate query row resource is outside the request")
        if self.version != VERSION or self.boundary != BOUNDARY or not _public(self.to_dict()):
            raise ValidationError("quality diff gate query version, boundary, or public projection failed")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("quality diff gate query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_address": self.gate_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "outcome": self.outcome, "direction": self.direction, "identity": self.identity, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(row.to_dict() for row in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateQuery":
        value = _mapping(value, "downloaded data quality diff gate query")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataQualityDiffGateQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(ordinal: int, resource: str, finding: gate_model.DownloadedDataQualityDiffGateFinding | None) -> DownloadedDataQualityDiffGateQueryRow:
    if resource == "summary":
        body = {"ordinal": ordinal, "resource": "summary", "identity": "summary", "direction": "", "outcome": "", "reason_codes": (), "left_address": "", "right_address": "", "diff_item_address": ""}
    else:
        if finding is None:
            raise ValidationError("quality diff gate query finding row requires a finding")
        body = {"ordinal": ordinal, "resource": resource, "identity": finding.identity, "direction": finding.direction, "outcome": finding.outcome, "reason_codes": finding.reason_codes, "left_address": finding.left_address, "right_address": finding.right_address, "diff_item_address": finding.diff_item_address}
    provisional = DownloadedDataQualityDiffGateQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateQueryRow(**body, content_address=address_row(provisional))


def query_gate(value: gate_model.DownloadedDataQualityDiffGate, *, resources: Sequence[str] = RESOURCES, outcome: str = "", direction: str = "", identity: str = "", text: str = "", offset: int = 0, limit: int = 100) -> DownloadedDataQualityDiffGateQuery:
    if not isinstance(value, gate_model.DownloadedDataQualityDiffGate):
        raise ValidationError("quality diff gate query requires a typed gate")
    requested = tuple(_label(item, "quality diff gate query resource") for item in resources)
    if not requested or len(set(requested)) != len(requested) or any(item not in RESOURCES for item in requested) or requested != tuple(sorted(requested, key=RESOURCES.index)):
        raise ValidationError("quality diff gate query resources are unsupported, duplicated, or unordered")
    outcome = _label(outcome, "quality diff gate query outcome") if outcome else ""
    direction = _label(direction, "quality diff gate query direction") if direction else ""
    identity = _text(identity, "quality diff gate query identity")
    text = _text(text, "quality diff gate query text", 1024)
    offset = _count(offset, "quality diff gate query offset", MAX_TOTAL_COUNT)
    limit = _count(limit, "quality diff gate query limit", MAX_LIMIT, positive=True)
    if outcome and outcome not in gate_model.OUTCOMES or direction and direction not in gate_model.diff_model.DIRECTIONS:
        raise ValidationError("quality diff gate query filter is unsupported")
    candidates: list[tuple[str, gate_model.DownloadedDataQualityDiffGateFinding | None]] = []
    for resource in requested:
        if resource == "summary":
            candidates.append((resource, None))
            continue
        for finding in value.findings:
            include = resource == "findings" or resource == finding.outcome or (resource == "allowed" and finding.direction in value.policy.allowed_directions) or (resource == "disallowed" and finding.direction not in value.policy.allowed_directions)
            if include:
                candidates.append((resource, finding))
    filtered = []
    for resource, finding in candidates:
        if finding is not None:
            if outcome and finding.outcome != outcome or direction and finding.direction != direction or identity and identity not in finding.identity:
                continue
            if text and text.casefold() not in canonical_json(finding.to_dict()).casefold():
                continue
        elif outcome or direction or identity or text:
            continue
        filtered.append((resource, finding))
    total_count = len(candidates)
    matched_count = len(filtered)
    page = filtered[offset:offset + limit]
    rows = tuple(_row(offset + ordinal, resource, finding) for ordinal, (resource, finding) in enumerate(page, 1))
    body = {"gate_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": requested, "outcome": outcome, "direction": direction, "identity": identity, "text": text, "offset": offset, "limit": limit, "total_count": total_count, "matched_count": matched_count, "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < offset + matched_count, "rows": rows}
    provisional = DownloadedDataQualityDiffGateQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateQuery(**body, content_address=address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateQuery:
    return DownloadedDataQualityDiffGateQuery.from_mapping(value)


def query_json(value: DownloadedDataQualityDiffGateQuery) -> str:
    return canonical_json(DownloadedDataQualityDiffGateQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataQualityDiffGateQuery) -> str:
    value = DownloadedDataQualityDiffGateQuery.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(";".join(row.reason_codes) if field == "reason_codes" else row.to_dict()[field] for field in ROW_FIELDS) for row in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataQualityDiffGateQuery) -> str:
    value = DownloadedDataQualityDiffGateQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Query", "", f"- Gate: `{value.gate_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", "", "| ordinal | resource | direction | outcome | identity |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | {row.resource} | {row.direction or '—'} | {row.outcome or '—'} | `{row.identity}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "direction": {"type": "string"}, "outcome": {"type": "string"}, "reason_codes": {"type": "array", "items": {"enum": list(gate_model.REASON_CODES)}}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "diff_item_address": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"gate_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "outcome": {"type": "string"}, "direction": {"type": "string"}, "identity": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "resources": RESOURCES, "operations": ("query_gate", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_limit": MAX_LIMIT, "max_total_count": MAX_TOTAL_COUNT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "DownloadedDataQualityDiffGateQuery", "DownloadedDataQualityDiffGateQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_gate", "query_json", "query_schema", "render_query_markdown", "row_schema"]
