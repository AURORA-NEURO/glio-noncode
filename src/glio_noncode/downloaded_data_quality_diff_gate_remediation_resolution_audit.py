"""Independent assurance checks for quality-gate remediation resolutions."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate_remediation as remediation_model
from . import downloaded_data_quality_diff_gate_remediation_resolution as resolution_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-remediation-resolution-audit-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_remediation_resolution_audit"
AUDIT_PREFIX = "glio-noncode-download-quality-diff-gate-remediation-resolution-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version-boundary", "plan-linkage", "entry-order", "action-conservation", "metadata-replay", "status-counts", "open-count", "state-decision", "acceptance-readiness", "entry-addresses", "rationale-boundary", "public-boundary", "mapping-round-trip", "status-closure")
MAX_CHECKS = len(CHECK_IDS)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("resolution_address", "version", "boundary", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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


class DownloadedDataQualityDiffGateRemediationResolutionAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality remediation resolution audit check ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("quality remediation resolution audit check ordinal must be positive")
        self.check_id = _label(check_id, "quality remediation resolution audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("quality remediation resolution audit check ID is unsupported")
        self.passed = _bool(passed, "quality remediation resolution audit check result")
        self.detail = _text(detail, "quality remediation resolution audit check detail", 2048)
        self.evidence_addresses = tuple(sorted({_address(item, "quality remediation resolution audit evidence address") for item in _sequence(evidence_addresses, "quality remediation resolution audit evidence", 16)}))
        if not self.evidence_addresses:
            raise ValidationError("quality remediation resolution audit checks require evidence")
        self.content_address = _address(content_address, "quality remediation resolution audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality remediation resolution audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("quality remediation resolution audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationResolutionAuditCheck":
        value = _mapping(value, "quality remediation resolution audit check")
        _strict(value, set(cls.FIELDS), "quality remediation resolution audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataQualityDiffGateRemediationResolutionAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataQualityDiffGateRemediationResolutionAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, resolution_address: str, version: str, boundary: str, checks: Sequence[DownloadedDataQualityDiffGateRemediationResolutionAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.resolution_address = _address(resolution_address, "quality remediation resolution audit resolution address", resolution_model.RESOLUTION_PREFIX)
        self.version = _text(version, "quality remediation resolution audit version")
        self.boundary = _text(boundary, "quality remediation resolution audit boundary", 512)
        self.checks = tuple(item if isinstance(item, DownloadedDataQualityDiffGateRemediationResolutionAuditCheck) else DownloadedDataQualityDiffGateRemediationResolutionAuditCheck.from_mapping(item) for item in _sequence(checks, "quality remediation resolution audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "quality remediation resolution audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "quality remediation resolution audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "quality remediation resolution audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "quality remediation resolution audit acceptance")
        self.content_address = _address(content_address, "quality remediation resolution audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality remediation resolution audit version or boundary is not current")
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("quality remediation resolution audit checks are not ordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("quality remediation resolution audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("quality remediation resolution audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("quality remediation resolution audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"resolution_address": self.resolution_address, "version": self.version, "boundary": self.boundary, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationResolutionAudit":
        value = _mapping(value, "quality remediation resolution audit")
        _strict(value, set(cls.FIELDS), "quality remediation resolution audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataQualityDiffGateRemediationResolutionAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _make_check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataQualityDiffGateRemediationResolutionAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationResolutionAuditCheck(**body)
    return DownloadedDataQualityDiffGateRemediationResolutionAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_resolution(value: resolution_model.DownloadedDataQualityDiffGateRemediationResolution) -> DownloadedDataQualityDiffGateRemediationResolutionAudit:
    if not isinstance(value, resolution_model.DownloadedDataQualityDiffGateRemediationResolution):
        raise ValidationError("quality remediation resolution audit requires a typed resolution")
    actions = value.plan.actions
    expected_state = "blocked" if value.rejected_count else "review" if value.required_open_count else "clear"
    expected_decision = {"clear": "promote", "review": "hold", "blocked": "block"}[expected_state]
    expected_counts = tuple(sum(item.status == status for item in value.entries) for status in resolution_model.STATUSES)
    evidence = (value.content_address, value.plan_address)
    checks = (
        ("version-boundary", value.version == resolution_model.VERSION and value.boundary == resolution_model.BOUNDARY, "resolution version and public boundary replay"),
        ("plan-linkage", (value.plan_id, value.plan_address) == (value.plan.plan_id, value.plan.content_address), "resolution retains the exact remediation plan"),
        ("entry-order", tuple(item.ordinal for item in value.entries) == tuple(range(1, len(value.entries) + 1)), "resolution entries are contiguous"),
        ("action-conservation", len(actions) == len(value.entries) and tuple(item.action_address for item in value.entries) == tuple(item.content_address for item in actions), "resolution entries conserve plan actions"),
        ("metadata-replay", all((entry.finding_address, entry.identity, entry.action, entry.priority, entry.required) == (action.finding_address, action.identity, action.action, action.priority, action.required) for entry, action in zip(value.entries, actions, strict=True)), "resolution metadata replays each action"),
        ("status-counts", expected_counts == (value.pending_count, value.resolved_count, value.waived_count, value.rejected_count, value.not_applicable_count), "resolution status counts are conserved"),
        ("open-count", value.required_open_count == sum(item.required and item.status != "resolved" for item in value.entries), "required open actions are counted independently"),
        ("state-decision", (value.state, value.decision) == (expected_state, expected_decision), "resolution state and decision replay from dispositions"),
        ("acceptance-readiness", (value.accepted, value.release_ready) == (expected_state == "clear", expected_state == "clear"), "release readiness requires every required action to resolve"),
        ("entry-addresses", all(resolution_model.address_entry(item) == item.content_address for item in value.entries), "every resolution entry has a stable address"),
        ("rationale-boundary", all(item.rationale and len(item.rationale) <= 1024 for item in value.entries), "every disposition retains bounded rationale"),
        ("public-boundary", _public(value.to_dict()), "resolution contains no forbidden public metadata"),
        ("mapping-round-trip", resolution_model.resolution_from_mapping(value.to_dict()).content_address == value.content_address, "resolution mapping round-trips to the same address"),
        ("status-closure", all(item.status in resolution_model.STATUSES for item in value.entries), "every entry has one closed status vocabulary"),
    )
    checks = tuple(_make_check(ordinal, check_id, passed, detail, evidence) for ordinal, (check_id, passed, detail) in enumerate(checks, 1))
    body = {"resolution_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationResolutionAudit(**body)
    return DownloadedDataQualityDiffGateRemediationResolutionAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRemediationResolutionAudit:
    return DownloadedDataQualityDiffGateRemediationResolutionAudit.from_mapping(value)


def audit_json(value: DownloadedDataQualityDiffGateRemediationResolutionAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataQualityDiffGateRemediationResolutionAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    for item in value.checks:
        row = item.to_dict()
        writer.writerow(";".join(row[field]) if field == "evidence_addresses" else row[field] for field in CHECK_FIELDS)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataQualityDiffGateRemediationResolutionAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Remediation Resolution Audit", "", f"- Resolution: `{value.resolution_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation resolution audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation resolution audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"resolution_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_resolution", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataQualityDiffGateRemediationResolutionAudit", "DownloadedDataQualityDiffGateRemediationResolutionAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_resolution", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
