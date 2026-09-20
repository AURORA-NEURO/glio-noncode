"""Independent assurance checks for quality gate remediation queries."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate as gate_model
from . import downloaded_data_quality_diff_gate_remediation as remediation_model
from . import downloaded_data_quality_diff_gate_remediation_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-remediation-query-audit-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_remediation_query_audit"
AUDIT_PREFIX = "glio-noncode-download-quality-diff-gate-remediation-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version-boundary", "plan-address", "resource-order", "row-order", "row-resource", "summary-shape", "action-shape", "filter-replay", "count-conservation", "pagination", "public-boundary", "canonical-round-trip")
MAX_CHECKS = len(CHECK_IDS)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "version", "boundary", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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
        raise ValidationError(f"{field} must be a canonical content address")
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


class DownloadedDataQualityDiffGateRemediationQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality gate remediation query audit check ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("quality gate remediation query audit check ordinal must be positive")
        self.check_id = _label(check_id, "quality gate remediation query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("quality gate remediation query audit check ID is unsupported")
        self.passed = _bool(passed, "quality gate remediation query audit check result")
        self.detail = _text(detail, "quality gate remediation query audit check detail", 2048)
        self.evidence_addresses = tuple(sorted({_address(item, "quality gate remediation query audit evidence address") for item in _sequence(evidence_addresses, "quality gate remediation query audit evidence", 16)}))
        if not self.evidence_addresses:
            raise ValidationError("quality gate remediation query audit checks require evidence")
        self.content_address = _address(content_address, "quality gate remediation query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality gate remediation query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("quality gate remediation query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationQueryAuditCheck":
        value = _mapping(value, "quality gate remediation query audit check")
        _strict(value, set(cls.FIELDS), "quality gate remediation query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataQualityDiffGateRemediationQueryAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataQualityDiffGateRemediationQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, version: str, boundary: str, checks: Sequence[DownloadedDataQualityDiffGateRemediationQueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "quality gate remediation query audit query address", query_model.QUERY_PREFIX)
        self.version = _text(version, "quality gate remediation query audit version")
        self.boundary = _text(boundary, "quality gate remediation query audit boundary", 512)
        self.checks = tuple(item if isinstance(item, DownloadedDataQualityDiffGateRemediationQueryAuditCheck) else DownloadedDataQualityDiffGateRemediationQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "quality gate remediation query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "quality gate remediation query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "quality gate remediation query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "quality gate remediation query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "quality gate remediation query audit acceptance")
        self.content_address = _address(content_address, "quality gate remediation query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality gate remediation query audit version or boundary is not current")
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("quality gate remediation query audit checks are not ordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("quality gate remediation query audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("quality gate remediation query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("quality gate remediation query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "version": self.version, "boundary": self.boundary, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationQueryAudit":
        value = _mapping(value, "quality gate remediation query audit")
        _strict(value, set(cls.FIELDS), "quality gate remediation query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataQualityDiffGateRemediationQueryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _make_check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataQualityDiffGateRemediationQueryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationQueryAuditCheck(**body)
    return DownloadedDataQualityDiffGateRemediationQueryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_query(query: query_model.DownloadedDataQualityDiffGateRemediationQuery) -> DownloadedDataQualityDiffGateRemediationQueryAudit:
    if not isinstance(query, query_model.DownloadedDataQualityDiffGateRemediationQuery):
        raise ValidationError("quality gate remediation query audit requires a typed query")
    evidence = (query.content_address, query.plan_address)
    summary_rows = tuple(row for row in query.rows if row.resource == "summary")
    action_rows = tuple(row for row in query.rows if row.resource != "summary")
    checks = (
        ("version-boundary", query.version == query_model.VERSION and query.boundary == query_model.BOUNDARY, "query version and public boundary replay"),
        ("plan-address", query.plan_address.startswith(remediation_model.PLAN_PREFIX + ":"), "query retains the remediation plan address"),
        ("resource-order", tuple(sorted(query.resources, key=query_model.RESOURCES.index)) == query.resources and len(set(query.resources)) == len(query.resources), "query resources are canonical and unique"),
        ("row-order", tuple(row.ordinal for row in query.rows) == tuple(range(1, query.returned_count + 1)), "returned rows are contiguous"),
        ("row-resource", all(row.resource in query.resources for row in query.rows), "every row belongs to a requested resource"),
        ("summary-shape", all(row.resource != "summary" or (row.identity == "summary" and row.outcome == "summary" and row.action == "summary" and not row.action_address) for row in summary_rows), "summary rows do not expose action-only fields"),
        ("action-shape", all(row.resource == "summary" or (row.finding_address and row.action_address and row.outcome in gate_model.OUTCOMES and row.action in remediation_model.ACTION_KINDS) for row in action_rows), "action rows retain finding and action lineage"),
        ("filter-replay", (not query.outcome or all(row.resource == "summary" or row.outcome == query.outcome for row in query.rows)) and (not query.action or all(row.resource == "summary" or row.action == query.action for row in query.rows)) and (not query.priority or all(row.resource == "summary" or row.priority == query.priority for row in query.rows)), "declared filters hold for returned rows"),
        ("count-conservation", query.returned_count == len(query.rows) and query.matched_count <= query.total_count, "query counts conserve rows"),
        ("pagination", query.next_offset == query.offset + query.returned_count and query.truncated == (query.next_offset < query.matched_count), "pagination counters replay"),
        ("public-boundary", _public(query.to_dict()), "query remains value-free and public"),
        ("canonical-round-trip", query_model.query_from_mapping(query.to_dict()).to_dict() == query.to_dict(), "canonical query mapping replays"),
    )
    built = tuple(_make_check(ordinal, check_id, passed, detail, evidence) for ordinal, (check_id, passed, detail) in enumerate(checks, 1))
    body = {"query_address": query.content_address, "version": VERSION, "boundary": BOUNDARY, "checks": built, "check_count": len(built), "passed_count": sum(item.passed for item in built), "failed_count": sum(not item.passed for item in built), "accepted": all(item.passed for item in built), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationQueryAudit(**body)
    return DownloadedDataQualityDiffGateRemediationQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRemediationQueryAudit:
    return DownloadedDataQualityDiffGateRemediationQueryAudit.from_mapping(value)


def audit_json(value: DownloadedDataQualityDiffGateRemediationQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataQualityDiffGateRemediationQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    for item in value.checks:
        row = item.to_dict()
        writer.writerow(";".join(row[field]) if field == "evidence_addresses" else row[field] for field in CHECK_FIELDS)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataQualityDiffGateRemediationQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Remediation Query Audit", "", f"- Query: `{value.query_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_query", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataQualityDiffGateRemediationQueryAudit", "DownloadedDataQualityDiffGateRemediationQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
