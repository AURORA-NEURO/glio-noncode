"""Independent query-shape audit for downloaded-data quality gates."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate as gate_model
from . import downloaded_data_quality_diff_gate_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-query-audit-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_query_audit"
AUDIT_PREFIX = "glio-noncode-download-quality-diff-gate-query-audit"
CHECK_IDS = ("exact-fields", "public-boundary", "gate-linkage", "resource-order", "filter-shape", "row-order", "row-conservation", "pagination", "classification-shape", "row-addresses", "content-address", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
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


class DownloadedDataQualityDiffGateQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality diff gate query audit check ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "quality diff gate query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("quality diff gate query audit check ID is unsupported")
        self.passed = _bool(passed, "quality diff gate query audit result")
        self.detail = _text(detail, "quality diff gate query audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "quality diff gate query audit evidence address") for item in _sequence(evidence_addresses, "quality diff gate query audit evidence", 16))
        self.content_address = _address(content_address, "quality diff gate query audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "quality diff gate query audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality diff gate query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("quality diff gate query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateQueryAuditCheck":
        value = _mapping(value, "downloaded data quality diff gate query audit check")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataQualityDiffGateQueryAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataQualityDiffGateQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[DownloadedDataQualityDiffGateQueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "quality diff gate query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataQualityDiffGateQueryAuditCheck) else DownloadedDataQualityDiffGateQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "quality diff gate query audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "quality diff gate query audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "quality diff gate query audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "quality diff gate query audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "quality diff gate query audit acceptance")
        self.content_address = _address(content_address, "quality diff gate query audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff gate query audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("quality diff gate query audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("quality diff gate query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateQueryAudit":
        value = _mapping(value, "downloaded data quality diff gate query audit")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataQualityDiffGateQueryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataQualityDiffGateQueryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:16]}
    provisional = DownloadedDataQualityDiffGateQueryAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataQualityDiffGateQueryAuditCheck(**body, content_address=address_check(provisional))


def audit_query(value: query_model.DownloadedDataQualityDiffGateQuery) -> DownloadedDataQualityDiffGateQueryAudit:
    """Recompute quality-gate query filters, rows, and pagination."""

    if not isinstance(value, query_model.DownloadedDataQualityDiffGateQuery):
        raise ValidationError("quality diff gate query audit requires a typed query")
    evidence = (value.content_address, value.gate_address)
    checks = (
        _check(1, "exact-fields", set(value.to_dict()) == set(query_model.QUERY_FIELDS), "query exposes exactly its declared public fields", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "query rows contain no forbidden attribution keys", evidence),
        _check(3, "gate-linkage", value.gate_address.startswith(gate_model.GATE_PREFIX + ":"), "query retains its gate address", (value.gate_address,)),
        _check(4, "resource-order", value.resources == tuple(sorted(value.resources, key=query_model.RESOURCES.index)) and len(set(value.resources)) == len(value.resources), "query resources are canonical", evidence),
        _check(5, "filter-shape", (not value.outcome or value.outcome in gate_model.OUTCOMES) and (not value.direction or value.direction in gate_model.diff_model.DIRECTIONS), "query filters use declared vocabularies", evidence),
        _check(6, "row-order", tuple(row.ordinal for row in value.rows) == tuple(range(value.offset + 1, value.offset + value.returned_count + 1)), "query row ordinals are contiguous from the requested offset", evidence),
        _check(7, "row-conservation", value.returned_count == len(value.rows) and value.returned_count <= value.matched_count <= value.total_count, "query counts conserve returned and matched rows", evidence),
        _check(8, "pagination", value.next_offset == value.offset + value.returned_count and value.truncated == (value.next_offset < value.offset + value.matched_count), "query pagination state replays", evidence),
        _check(9, "classification-shape", all(row.resource == "summary" or (row.direction in gate_model.diff_model.DIRECTIONS and row.outcome in gate_model.OUTCOMES) for row in value.rows), "query rows retain valid gate classifications", tuple(row.content_address for row in value.rows)),
        _check(10, "row-addresses", all(query_model.address_row(row) == row.content_address for row in value.rows), "query row addresses replay", tuple(row.content_address for row in value.rows)),
        _check(11, "content-address", query_model.address_query(value) == value.content_address, "query content address replays", (value.content_address,)),
        _check(12, "mapping-round-trip", query_model.query_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "typed query mapping round-trips without projection drift", evidence),
    )
    body = {"query_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataQualityDiffGateQueryAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateQueryAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateQueryAudit:
    return DownloadedDataQualityDiffGateQueryAudit.from_mapping(value)


def audit_json(value: DownloadedDataQualityDiffGateQueryAudit) -> str:
    return canonical_json(DownloadedDataQualityDiffGateQueryAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataQualityDiffGateQueryAudit) -> str:
    value = DownloadedDataQualityDiffGateQueryAudit.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataQualityDiffGateQueryAudit) -> str:
    value = DownloadedDataQualityDiffGateQueryAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Query Audit", "", f"- Query: `{value.query_address}`", f"- Accepted: `{value.accepted}`", f"- Passed: `{value.passed_count}/{value.check_count}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_query", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown")}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataQualityDiffGateQueryAudit", "DownloadedDataQualityDiffGateQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
