"""Independent verification for exact remediation-resolution runtimes."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_runtime as runtime_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-runtime-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_runtime_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-runtime-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "manifest-files", "plan-linkage", "resolution-linkage", "component-linkage", "audit-linkage", "query-linkage", "aggregate-replay", "readiness-replay", "artifact-addresses", "runtime-address", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "resolution runtime audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "resolution runtime audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("resolution runtime audit check ID is unsupported")
        self.passed = _bool(passed, "resolution runtime audit check result")
        self.detail = _text(detail, "resolution runtime audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "resolution runtime audit evidence address") for item in _sequence(evidence_addresses, "resolution runtime audit evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("resolution runtime audit checks require evidence")
        self.content_address = _address(content_address, "resolution runtime audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("resolution runtime audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("resolution runtime audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck:
        value = _mapping(value, "resolution runtime audit check")
        _strict(value, set(cls.FIELDS), "resolution runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck):
        raise ValidationError("resolution runtime audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "resolution runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck.from_mapping(item) for item in _sequence(checks, "resolution runtime audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "resolution runtime audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "resolution runtime audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "resolution runtime audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "resolution runtime audit acceptance")
        self.content_address = _address(content_address, "resolution runtime audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("resolution runtime audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("resolution runtime audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("resolution runtime audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("resolution runtime audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit:
        value = _mapping(value, "resolution runtime audit")
        _strict(value, set(cls.FIELDS), "resolution runtime audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit):
        raise ValidationError("resolution runtime audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_runtime(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime) -> DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit:
    if not isinstance(value, runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime):
        raise ValidationError("resolution runtime audit requires a typed runtime")
    expected_addresses = tuple(item.content_address for item in (value.plan, value.resolution, value.audit, value.query, value.query_audit))
    checks = (
        _check(1, "version", value.version == runtime_model.VERSION, "resolution runtime version is current", (value.content_address,)),
        _check(2, "boundary", value.boundary == runtime_model.BOUNDARY, "resolution runtime boundary is public and value-free", (value.content_address,)),
        _check(3, "manifest-files", value.manifest.files == runtime_model.FILES and len(value.manifest.artifact_addresses) == runtime_model.MAX_ARTIFACTS, "runtime manifest names the exact seven files", (value.manifest.content_address,)),
        _check(4, "plan-linkage", (value.plan_id, value.plan_address) == (value.plan.plan_id, value.plan.content_address), "runtime retains the exact remediation plan", (value.plan_address,)),
        _check(5, "resolution-linkage", (value.resolution_id, value.resolution_address) == (value.resolution.resolution_id, value.resolution.content_address) and value.resolution.plan_address == value.plan_address, "runtime retains the exact resolution ledger", (value.resolution_address,)),
        _check(6, "component-linkage", value.audit.resolution_address == value.resolution_address and value.query.resolution_address == value.resolution_address, "runtime audit and query retain the resolution link", (value.audit_address, value.query_address)),
        _check(7, "audit-linkage", value.audit_address == value.audit.content_address and value.audit.resolution_address == value.resolution_address, "resolution audit linkage is retained", (value.audit_address,)),
        _check(8, "query-linkage", value.query_address == value.query.content_address and value.query_audit.query_address == value.query_address, "query and query audit linkage is retained", (value.query_address, value.query_audit_address)),
        _check(9, "aggregate-replay", (value.resolution_count, value.required_open_count) == (value.resolution.resolution_count, value.resolution.required_open_count), "runtime aggregates replay the resolution ledger", (value.resolution_address,)),
        _check(10, "readiness-replay", (value.accepted, value.release_ready, value.state == "complete") == (value.resolution.accepted and value.audit.accepted and value.query_audit.accepted, value.resolution.accepted and value.audit.accepted and value.query_audit.accepted, value.resolution.accepted and value.audit.accepted and value.query_audit.accepted), "runtime readiness replays component acceptance", (value.content_address,)),
        _check(11, "artifact-addresses", tuple(value.manifest.artifact_addresses) == expected_addresses, "manifest artifact addresses replay nested components", (value.manifest.content_address,)),
        _check(12, "runtime-address", runtime_model.address_runtime(value) == value.content_address, "runtime content address replays", (value.content_address,)),
        _check(13, "public-boundary", _public(value.to_dict()), "runtime contains no forbidden public metadata", (value.content_address,)),
        _check(14, "mapping-round-trip", runtime_model.runtime_from_mapping(value.to_dict()).content_address == value.content_address, "runtime mapping round-trips to the same address", (value.content_address,)),
    )
    passed = sum(item.passed for item in checks)
    body = {"runtime_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution Runtime Audit", "", f"- Runtime: `{value.runtime_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution runtime audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution runtime audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"runtime_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_runtime", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionRuntimeAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
