"""Independent assurance for bounded remediation resolution queries."""

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
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_query as query_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-query-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_query_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resolution-linkage", "resource-order", "row-order", "count-conservation", "filter-replay", "summary-replay", "entry-replay", "address-replay", "public-boundary", "mapping-round-trip")
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


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "resolution query audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "resolution query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("resolution query audit check ID is unsupported")
        self.passed = _bool(passed, "resolution query audit check result")
        self.detail = _text(detail, "resolution query audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "resolution query audit evidence address") for item in _sequence(evidence_addresses, "resolution query audit evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("resolution query audit checks require evidence")
        self.content_address = _address(content_address, "resolution query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("resolution query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("resolution query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck:
        value = _mapping(value, "resolution query audit check")
        _strict(value, set(cls.FIELDS), "resolution query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck):
        raise ValidationError("resolution query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "resolution query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "resolution query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "resolution query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "resolution query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "resolution query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "resolution query audit acceptance")
        self.content_address = _address(content_address, "resolution query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("resolution query audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("resolution query audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("resolution query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("resolution query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit:
        value = _mapping(value, "resolution query audit")
        _strict(value, set(cls.FIELDS), "resolution query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit):
        raise ValidationError("resolution query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_query(value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionQuery) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit:
    if not isinstance(value, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionQuery):
        raise ValidationError("resolution query audit requires a typed query")
    rows = value.rows
    summary_rows = tuple(row for row in rows if row.resource == "summary")
    entry_rows = tuple(row for row in rows if row.resource == "entries")
    checks = (
        _check(1, "version", value.version == query_model.VERSION, "resolution query version is current", (value.content_address,)),
        _check(2, "boundary", value.boundary == query_model.BOUNDARY, "resolution query boundary is public and value-free", (value.content_address,)),
        _check(3, "resolution-linkage", value.resolution_address.startswith(resolution_model.RESOLUTION_PREFIX + ":"), "query retains the resolution address", (value.resolution_address,)),
        _check(4, "resource-order", tuple(item.resource for item in rows) == (tuple("summary" for _ in summary_rows) + tuple("entries" for _ in entry_rows)) and all(row.resource in value.resources for row in rows), "query resources retain their declared order", (value.content_address,)),
        _check(5, "row-order", tuple(item.ordinal for item in rows) == tuple(range(1, len(rows) + 1)), "query rows are consecutively ordinal", tuple(item.content_address for item in rows[:8]) or (value.content_address,)),
        _check(6, "count-conservation", len(rows) == value.returned_count and value.returned_count <= value.limit and value.matched_count <= value.total_count and value.next_offset == value.offset + value.returned_count and value.truncated == (value.next_offset < value.matched_count), "query count fields remain internally consistent", (value.content_address,)),
        _check(7, "filter-replay", not any(row.resource == "summary" for row in rows if any((value.status, value.action, value.priority, value.identity, value.required))) and all(not value.status or row.status == value.status for row in entry_rows) and all(not value.action or row.action == value.action for row in entry_rows) and all(not value.priority or row.priority == value.priority for row in entry_rows) and (not value.required or all(row.required for row in entry_rows)), "active filters do not leak the summary row", (value.content_address,)),
        _check(8, "summary-replay", all(row.action == "summary" and row.status == "summary" and not row.action_address for row in summary_rows), "summary rows retain summary-only fields", tuple(row.content_address for row in summary_rows) or (value.content_address,)),
        _check(9, "entry-replay", all(row.resource == "entries" and row.action in remediation_model.ACTION_KINDS and row.status in resolution_model.STATUSES and row.resolution_entry_address for row in entry_rows), "entry rows retain bounded disposition fields", tuple(row.resolution_entry_address for row in entry_rows[:8]) or (value.content_address,)),
        _check(10, "address-replay", all(query_model.address_row(row) == row.content_address for row in rows), "query row addresses replay", tuple(row.content_address for row in rows[:8]) or (value.content_address,)),
        _check(11, "public-boundary", _public(value.to_dict()), "query contains no forbidden public metadata", (value.content_address,)),
        _check(12, "mapping-round-trip", query_model.query_from_mapping(value.to_dict()).content_address == value.content_address, "query mapping round-trips to the same address", (value.content_address,)),
    )
    passed = sum(item.passed for item in checks)
    body = {"query_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution Query Audit", "", f"- Query: `{value.query_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_query", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
