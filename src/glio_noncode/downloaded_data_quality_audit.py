"""Independent replay audit for downloaded-data quality decisions."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile as profile_model
from . import downloaded_data_quality as quality_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-audit-v1"
BOUNDARY = "public_downloaded_data_quality_audit"
AUDIT_PREFIX = "glio-noncode-download-quality-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "current-version",
    "profile-link",
    "policy-link",
    "policy-address",
    "result-address",
    "count-conservation",
    "finding-ordinals",
    "finding-addresses",
    "rule-identifiers",
    "scope-targets",
    "severity-values",
    "decision-state",
    "decision-accepted",
    "policy-replay",
    "findings-replay",
    "evidence-addresses",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("quality_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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


class DownloadedDataQualityAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality audit check ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "quality audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("quality audit check ID is unsupported")
        self.passed = _bool(passed, "quality audit check result")
        self.detail = _text(detail, "quality audit check detail", 1024)
        self.evidence_addresses = tuple(_address(item, "quality audit evidence address") for item in _sequence(evidence_addresses, "quality audit evidence", 6))
        if not self.evidence_addresses:
            raise ValidationError("quality audit check requires evidence")
        self.content_address = _address(content_address, "quality audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("quality audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataQualityAuditCheck:
        value = _mapping(value, "downloaded data quality audit check")
        _strict(value, set(cls.FIELDS), "downloaded data quality audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataQualityAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataQualityAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, quality_address: str, checks: Sequence[DownloadedDataQualityAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.quality_address = _address(quality_address, "quality audit result address", quality_model.QUALITY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataQualityAuditCheck) else DownloadedDataQualityAuditCheck.from_mapping(item) for item in _sequence(checks, "quality audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "quality audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "quality audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "quality audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "quality audit acceptance")
        self.content_address = _address(content_address, "quality audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("quality audit counts do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("quality audit checks are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("quality audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("quality audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"quality_address": self.quality_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataQualityAudit:
        value = _mapping(value, "downloaded data quality audit")
        _strict(value, set(cls.FIELDS), "downloaded data quality audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataQualityAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataQualityAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataQualityAuditCheck(**body)
    return DownloadedDataQualityAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_quality(value: quality_model.DownloadedDataQuality) -> DownloadedDataQualityAudit:
    """Recompute independent integrity checks for a quality decision."""

    if not isinstance(value, quality_model.DownloadedDataQuality):
        raise ValidationError("quality audit requires a typed quality result")
    policy = quality_model.DownloadedDataQualityPolicy.from_mapping(value.policy.to_dict())
    expected = quality_model.address_quality(quality_model.DownloadedDataQuality.from_mapping(value.to_dict()))
    findings = tuple(quality_model.DownloadedDataQualityFinding.from_mapping(item.to_dict()) for item in value.findings)
    evidence = (value.content_address, value.profile_address, policy.content_address)
    checks = (
        _check(1, "exact-fields", tuple(value.to_dict()) == set(value.FIELDS) or set(value.to_dict()) == set(value.FIELDS), "quality fields are exact", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "quality result is public", evidence),
        _check(3, "current-version", value.version == quality_model.VERSION and value.boundary == quality_model.BOUNDARY, "quality version and boundary are current", evidence),
        _check(4, "profile-link", value.profile_address.startswith(profile_model.PROFILE_PREFIX + ":"), "quality links to a profile", evidence),
        _check(5, "policy-link", value.policy.content_address == policy.content_address, "quality embeds the declared policy", evidence),
        _check(6, "policy-address", quality_model.address_policy(policy) == policy.content_address, "policy address replays", evidence),
        _check(7, "result-address", expected == value.content_address, "quality address replays", evidence),
        _check(8, "count-conservation", value.check_count == value.passed_count + value.failed_count == len(findings), "finding counts conserve", evidence),
        _check(9, "finding-ordinals", tuple(item.ordinal for item in findings) == tuple(range(1, len(findings) + 1)), "finding ordinals are canonical", evidence),
        _check(10, "finding-addresses", all(quality_model.address_finding(item) == item.content_address for item in findings), "finding addresses replay", evidence),
        _check(11, "rule-identifiers", all(item.rule_id in quality_model.RULE_IDS for item in findings), "finding rules are registered", evidence),
        _check(12, "scope-targets", all((item.scope == "summary" and not item.member_name and not item.field_name) or (item.scope == "member" and bool(item.member_name)) or (item.scope == "field" and bool(item.field_name)) for item in findings), "finding scopes have valid targets", evidence),
        _check(13, "severity-values", all(item.severity == policy.failure_state for item in findings), "finding severities match policy", evidence),
        _check(14, "decision-state", value.state == ("accepted" if value.failed_count == 0 else policy.failure_state), "decision state follows failed checks", evidence),
        _check(15, "decision-accepted", value.accepted == (value.state == "accepted"), "accepted flag follows state", evidence),
        _check(16, "policy-replay", quality_model.DownloadedDataQualityPolicy.from_mapping(policy.to_dict()).to_dict() == policy.to_dict(), "policy mapping replays", evidence),
        _check(17, "findings-replay", tuple(quality_model.DownloadedDataQualityFinding.from_mapping(item.to_dict()).to_dict() for item in findings) == tuple(item.to_dict() for item in findings), "finding mappings replay", evidence),
        _check(18, "evidence-addresses", all(item.evidence_addresses and all(":" in address for address in item.evidence_addresses) for item in findings), "findings retain evidence addresses", evidence),
    )
    body = {"quality_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataQualityAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataQualityAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityAudit:
    return DownloadedDataQualityAudit.from_mapping(value)


def audit_json(value: DownloadedDataQualityAudit) -> str:
    return canonical_json(DownloadedDataQualityAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataQualityAudit) -> str:
    value = DownloadedDataQualityAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataQualityAudit) -> str:
    value = DownloadedDataQualityAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Audit", "", f"- Quality: `{value.quality_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"quality_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_quality", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": len(CHECK_IDS)}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataQualityAudit", "DownloadedDataQualityAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_quality", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
