"""Independent assurance for value-free remediation resolutions."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution as resolution_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "plan-linkage",
    "action-order",
    "metadata-replay",
    "status-counts",
    "open-count",
    "state-decision",
    "acceptance-replay",
    "entry-addresses",
    "public-boundary",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("resolution_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "resolution audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "resolution audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("resolution audit check ID is unsupported")
        self.passed = _bool(passed, "resolution audit check result")
        self.detail = _text(detail, "resolution audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "resolution audit evidence address") for item in _sequence(evidence_addresses, "resolution audit evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("resolution audit checks require evidence")
        self.content_address = _address(content_address, "resolution audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("resolution audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("resolution audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck:
        value = _mapping(value, "resolution audit check")
        _strict(value, set(cls.FIELDS), "resolution audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck):
        raise ValidationError("resolution audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, resolution_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.resolution_address = _address(resolution_address, "resolution audit resolution address", resolution_model.RESOLUTION_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck.from_mapping(item) for item in _sequence(checks, "resolution audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "resolution audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "resolution audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "resolution audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "resolution audit acceptance")
        self.content_address = _address(content_address, "resolution audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)):
            raise ValidationError("resolution audit check order is not conserved")
        if tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("resolution audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("resolution audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("resolution audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("resolution audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"resolution_address": self.resolution_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionAudit:
        value = _mapping(value, "resolution audit")
        _strict(value, set(cls.FIELDS), "resolution audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionAudit):
        raise ValidationError("resolution audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_resolution(value: resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution) -> DownloadedDataProfileContractCompatibilityRemediationResolutionAudit:
    if not isinstance(value, resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution):
        raise ValidationError("resolution audit requires a typed resolution")
    actions = value.plan.actions
    expected_state = "blocked" if value.rejected_count else "review" if value.required_open_count else "clear"
    expected_decision = {"clear": "promote", "review": "hold", "blocked": "block"}[expected_state]
    expected_counts = tuple(sum(item.status == status for item in value.entries) for status in resolution_model.STATUSES)
    checks = (
        _check(1, "version", value.version == resolution_model.VERSION, "resolution version is current", (value.content_address,)),
        _check(2, "boundary", value.boundary == resolution_model.BOUNDARY, "resolution boundary is public and value-free", (value.content_address,)),
        _check(3, "plan-linkage", (value.plan_id, value.plan_address) == (value.plan.plan_id, value.plan.content_address), "resolution retains the exact remediation plan", (value.plan_address,)),
        _check(4, "action-order", tuple(item.ordinal for item in value.entries) == tuple(range(1, len(value.entries) + 1)) and tuple(item.action_address for item in value.entries) == tuple(item.content_address for item in actions), "resolution entries retain plan action order", tuple(item.content_address for item in actions[:8]) or (value.content_address,)),
        _check(5, "metadata-replay", len(actions) == len(value.entries) and all((entry.identity, entry.action, entry.priority, entry.required) == (action.identity, action.action, action.priority, action.required) for entry, action in zip(value.entries, actions, strict=True)), "resolution metadata replays each planned action", tuple(item.action_address for item in value.entries[:8]) or (value.content_address,)),
        _check(6, "status-counts", expected_counts == (value.pending_count, value.resolved_count, value.waived_count, value.rejected_count, value.not_applicable_count), "resolution status counts are conserved", (value.content_address,)),
        _check(7, "open-count", value.required_open_count == sum(item.required and item.status != "resolved" for item in value.entries), "required open actions are counted independently", (value.content_address,)),
        _check(8, "state-decision", (value.state, value.decision) == (expected_state, expected_decision), "resolution state and decision replay from dispositions", (value.content_address,)),
        _check(9, "acceptance-replay", (value.accepted, value.release_ready) == (expected_state == "clear", expected_state == "clear"), "release readiness replays from closed required actions", (value.content_address,)),
        _check(10, "entry-addresses", all(resolution_model.address_entry(item) == item.content_address for item in value.entries), "every resolution entry has a stable content address", tuple(item.content_address for item in value.entries[:8]) or (value.content_address,)),
        _check(11, "public-boundary", _public(value.to_dict()), "resolution contains no forbidden public metadata", (value.content_address,)),
        _check(12, "mapping-round-trip", resolution_model.resolution_from_mapping(value.to_dict()).content_address == value.content_address, "resolution mapping round-trips to the same address", (value.content_address,)),
    )
    passed = sum(item.passed for item in checks)
    body = {"resolution_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionAudit) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution Audit", "", f"- Resolution: `{value.resolution_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"resolution_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_resolution", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_resolution", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
