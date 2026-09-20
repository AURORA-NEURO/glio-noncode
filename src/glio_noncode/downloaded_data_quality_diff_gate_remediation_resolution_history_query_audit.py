"""Independent replay audit for remediation resolution history queries."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate_remediation_resolution_history as history_model
from . import downloaded_data_quality_diff_gate_remediation_resolution_history_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-remediation-resolution-history-query-audit-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_remediation_resolution_history_query_audit"
AUDIT_PREFIX = "glio-noncode-download-quality-diff-gate-remediation-resolution-history-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "history-lineage", "resource-order", "row-order", "row-shape", "filter-replay", "count-conservation", "pagination", "public-boundary", "mapping-round-trip", "canonical-json")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


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
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be a content address")
    namespace, digest = value.split(":", 1)
    if not namespace or (digest != "pending" and (len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest))):
        raise ValidationError(f"{field} must be canonical")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


class DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "resolution history query audit ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("resolution history query audit ordinal must be positive")
        self.check_id = _label(check_id, "resolution history query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("resolution history query audit check ID is unsupported")
        self.passed = _bool(passed, "resolution history query audit result")
        self.detail = _text(detail, "resolution history query audit detail", 2048)
        self.evidence_addresses = tuple(sorted({_address(item, "resolution history query audit evidence address") for item in _sequence(evidence_addresses, "resolution history query audit evidence", 16)}))
        if not self.evidence_addresses:
            raise ValidationError("resolution history query audit checks require evidence")
        self.content_address = _address(content_address, "resolution history query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("resolution history query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("resolution history query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAuditCheck":
        value = _mapping(value, "resolution history query audit check")
        _strict(value, set(cls.FIELDS), "resolution history query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "resolution history query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAuditCheck) else DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "resolution history query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "resolution history query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "resolution history query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "resolution history query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "resolution history query audit acceptance")
        self.content_address = _address(content_address, "resolution history query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("resolution history query audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("resolution history query audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("resolution history query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("resolution history query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit":
        value = _mapping(value, "resolution history query audit")
        _strict(value, set(cls.FIELDS), "resolution history query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAuditCheck(**body)
    return DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_query(value: query_model.DownloadedDataQualityDiffGateRemediationResolutionHistoryQuery) -> DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit:
    if not isinstance(value, query_model.DownloadedDataQualityDiffGateRemediationResolutionHistoryQuery):
        raise ValidationError("resolution history query audit requires a typed query")
    summary_rows = tuple(row for row in value.rows if row.resource == "summary")
    entry_rows = tuple(row for row in value.rows if row.resource != "summary")
    evidence = (value.content_address, value.history_address)
    checks = (
        ("version", value.version == query_model.VERSION, "query version is current"),
        ("boundary", value.boundary == query_model.BOUNDARY, "query boundary is public and value-free"),
        ("history-lineage", value.history_address.startswith(history_model.HISTORY_PREFIX + ":"), "query retains the addressed history"),
        ("resource-order", tuple(sorted(value.resources, key=query_model.RESOURCES.index)) == value.resources and len(set(value.resources)) == len(value.resources), "query resources are canonical and unique"),
        ("row-order", tuple(row.ordinal for row in value.rows) == tuple(range(value.offset + 1, value.offset + value.returned_count + 1)), "returned rows are contiguous"),
        ("row-shape", all((row.resource == "summary" and not row.entry_address) or (row.resource != "summary" and row.entry_address and row.resolution_address) for row in value.rows), "summary and entry rows retain their required shapes"),
        ("filter-replay", (not value.state or all(row.resource == "summary" or row.state == value.state for row in value.rows)) and (not value.decision or all(row.resource == "summary" or row.decision == value.decision for row in value.rows)) and (not value.transition or all(row.resource == "summary" or row.transition == value.transition for row in value.rows)), "declared filters hold for returned rows"),
        ("count-conservation", value.returned_count == len(value.rows) and value.matched_count <= value.total_count, "query counts conserve rows"),
        ("pagination", value.next_offset == value.offset + value.returned_count and value.truncated == (value.next_offset < value.offset + value.matched_count), "pagination counters replay"),
        ("public-boundary", _public(value.to_dict()), "query contains no forbidden public metadata"),
        ("mapping-round-trip", query_model.query_from_mapping(value.to_dict()).content_address == value.content_address, "query mapping round-trips to the same address"),
        ("canonical-json", canonical_json(value.to_dict()) == canonical_json(query_model.query_from_mapping(value.to_dict()).to_dict()), "query canonical JSON is deterministic"),
    )
    built = tuple(_check(ordinal, check_id, passed, detail, evidence) for ordinal, (check_id, passed, detail) in enumerate(checks, 1))
    body = {"query_address": value.content_address, "checks": built, "check_count": len(built), "passed_count": sum(item.passed for item in built), "failed_count": sum(not item.passed for item in built), "accepted": all(item.passed for item in built), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit(**body)
    return DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit:
    return DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit.from_mapping(value)


def audit_json(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    for item in value.checks:
        row = item.to_dict()
        writer.writerow(";".join(row[field]) if field == "evidence_addresses" else row[field] for field in CHECK_FIELDS)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Remediation Resolution History Query Audit", "", f"- Query: `{value.query_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data remediation resolution history query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data remediation resolution history query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_query", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit", "DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_query", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
