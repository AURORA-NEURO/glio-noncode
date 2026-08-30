"""Independent replay audit for compatibility queries."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility as compatibility_model
from . import downloaded_data_profile_contract_compatibility_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-query-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_query_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "gate-linkage", "resource-order", "row-order", "count-conservation", "filter-replay", "summary-replay", "finding-replay", "public-boundary", "mapping-round-trip")
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "compatibility query audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "compatibility query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("compatibility query audit check ID is unsupported")
        self.passed = _bool(passed, "compatibility query audit check result")
        self.detail = _text(detail, "compatibility query audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "compatibility query audit evidence address") for item in _sequence(evidence_addresses, "compatibility query audit evidence addresses", 16)}))
        if not self.evidence_addresses:
            raise ValidationError("compatibility query audit checks require evidence")
        self.content_address = _address(content_address, "compatibility query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("compatibility query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("compatibility query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityQueryAuditCheck:
        value = _mapping(value, "compatibility query audit check")
        _strict(value, set(cls.FIELDS), "compatibility query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityQueryAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityQueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "compatibility query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityQueryAuditCheck) else DownloadedDataProfileContractCompatibilityQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "compatibility query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "compatibility query audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "compatibility query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "compatibility query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "compatibility query audit acceptance")
        self.content_address = _address(content_address, "compatibility query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("compatibility query audit checks are not canonical")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("compatibility query audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("compatibility query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("compatibility query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityQueryAudit:
        value = _mapping(value, "compatibility query audit")
        _strict(value, set(cls.FIELDS), "compatibility query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityQueryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityQueryAuditCheck:
    provisional = DownloadedDataProfileContractCompatibilityQueryAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityQueryAuditCheck(ordinal, check_id, passed, detail, provisional.evidence_addresses, address_check(provisional))


def audit_query(value: query_model.DownloadedDataProfileContractCompatibilityQuery) -> DownloadedDataProfileContractCompatibilityQueryAudit:
    if not isinstance(value, query_model.DownloadedDataProfileContractCompatibilityQuery):
        raise ValidationError("compatibility query audit requires a typed query")
    query = value
    evidence = (query.content_address, query.gate_address)
    expected_resource_order = tuple(sorted(query.resources, key=query_model.RESOURCES.index))
    rows = query.rows
    checks = (
        _check(1, "version", query.version == query_model.VERSION, "compatibility query uses the current version", evidence),
        _check(2, "boundary", query.boundary == query_model.BOUNDARY, "compatibility query uses the public boundary", evidence),
        _check(3, "gate-linkage", query.gate_address.startswith(compatibility_model.GATE_PREFIX + ":"), "query retains the compatibility gate address", (query.gate_address,)),
        _check(4, "resource-order", query.resources == expected_resource_order and len(set(query.resources)) == len(query.resources), "query resources use canonical order", evidence),
        _check(5, "row-order", tuple(item.ordinal for item in rows) == tuple(range(1, query.returned_count + 1)), "query rows use contiguous returned ordinals", tuple(item.content_address for item in rows)[:8] or evidence),
        _check(6, "count-conservation", query.returned_count == len(rows) and query.total_count >= query.matched_count >= query.returned_count and query.next_offset == query.offset + query.returned_count and query.truncated == (query.next_offset < query.matched_count), "query counts and truncation replay", evidence),
        _check(7, "filter-replay", all((not query.outcome or row.outcome == query.outcome) and (not query.reason or query.reason in row.reason_codes) for row in rows if row.resource == "findings"), "query filters replay against returned findings", evidence),
        _check(8, "summary-replay", sum(row.resource == "summary" for row in rows) <= 1 and all(row.identity == "summary" for row in rows if row.resource == "summary"), "summary projection is singular and structural", evidence),
        _check(9, "finding-replay", all(row.resource == "findings" and row.finding_address.startswith(compatibility_model.FINDING_PREFIX + ":") and row.diff_item_address.startswith(compatibility_model.diff_model.ITEM_PREFIX + ":") for row in rows if row.resource == "findings"), "finding rows retain nested addresses", tuple(row.finding_address for row in rows if row.resource == "findings")[:8] or evidence),
        _check(10, "public-boundary", _public(query.to_dict()), "query remains value-free and public", evidence),
        _check(11, "mapping-round-trip", query_model.query_from_mapping(query.to_dict()).to_dict() == query.to_dict(), "query mapping replay is lossless", evidence),
    )
    body = {"query_address": query.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataProfileContractCompatibilityQueryAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityQueryAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityQueryAudit:
    return DownloadedDataProfileContractCompatibilityQueryAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityQueryAudit) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityQueryAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityQueryAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityQueryAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityQueryAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityQueryAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Query Audit", "", f"- Query: `{value.query_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "checks": CHECK_IDS, "operations": ("audit_query", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityQueryAudit", "DownloadedDataProfileContractCompatibilityQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
