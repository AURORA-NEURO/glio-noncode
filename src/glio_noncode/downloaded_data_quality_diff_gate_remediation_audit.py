"""Independent assurance checks for downloaded-data gate remediation plans."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate as gate_model
from . import downloaded_data_quality_diff_gate_remediation as remediation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-remediation-audit-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_remediation_audit"
AUDIT_PREFIX = "glio-noncode-download-quality-diff-gate-remediation-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version-boundary", "gate-lineage", "gate-address", "action-order",
    "action-replay", "finding-conservation", "reason-conservation",
    "direction-conservation", "evidence-lineage", "action-kind-conservation",
    "priority-conservation", "required-count", "critical-count", "safe-actions",
    "blocked-actions", "state-replay", "decision-replay", "canonical-round-trip",
)
MAX_CHECKS = len(CHECK_IDS)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("plan_address", "version", "boundary", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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


class DownloadedDataQualityDiffGateRemediationAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality gate remediation audit check ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("quality gate remediation audit check ordinal must be positive")
        self.check_id = _label(check_id, "quality gate remediation audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("quality gate remediation audit check ID is unsupported")
        self.passed = _bool(passed, "quality gate remediation audit check result")
        self.detail = _text(detail, "quality gate remediation audit check detail", 2048)
        self.evidence_addresses = tuple(sorted({_address(item, "quality gate remediation audit evidence address") for item in _sequence(evidence_addresses, "quality gate remediation audit evidence", 16)}))
        if not self.evidence_addresses:
            raise ValidationError("quality gate remediation audit checks require evidence")
        self.content_address = _address(content_address, "quality gate remediation audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality gate remediation audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("quality gate remediation audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationAuditCheck":
        value = _mapping(value, "quality gate remediation audit check")
        _strict(value, set(cls.FIELDS), "quality gate remediation audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataQualityDiffGateRemediationAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataQualityDiffGateRemediationAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, plan_address: str, version: str, boundary: str, checks: Sequence[DownloadedDataQualityDiffGateRemediationAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.plan_address = _address(plan_address, "quality gate remediation audit plan address", remediation_model.PLAN_PREFIX)
        self.version = _text(version, "quality gate remediation audit version")
        self.boundary = _text(boundary, "quality gate remediation audit boundary", 512)
        self.checks = tuple(item if isinstance(item, DownloadedDataQualityDiffGateRemediationAuditCheck) else DownloadedDataQualityDiffGateRemediationAuditCheck.from_mapping(item) for item in _sequence(checks, "quality gate remediation audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "quality gate remediation audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "quality gate remediation audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "quality gate remediation audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "quality gate remediation audit acceptance")
        self.content_address = _address(content_address, "quality gate remediation audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality gate remediation audit version or boundary is not current")
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("quality gate remediation audit checks are not ordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("quality gate remediation audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("quality gate remediation audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("quality gate remediation audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"plan_address": self.plan_address, "version": self.version, "boundary": self.boundary, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationAudit":
        value = _mapping(value, "quality gate remediation audit")
        _strict(value, set(cls.FIELDS), "quality gate remediation audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataQualityDiffGateRemediationAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _make_check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataQualityDiffGateRemediationAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationAuditCheck(**body)
    return DownloadedDataQualityDiffGateRemediationAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_plan(plan: remediation_model.DownloadedDataQualityDiffGateRemediationPlan) -> DownloadedDataQualityDiffGateRemediationAudit:
    if not isinstance(plan, remediation_model.DownloadedDataQualityDiffGateRemediationPlan):
        raise ValidationError("quality gate remediation audit requires a typed plan")
    expected = remediation_model.build_plan(plan.gate, plan_id=plan.plan_id)
    evidence = (plan.content_address, plan.gate_address)
    checks = (
        ("version-boundary", plan.version == remediation_model.VERSION and plan.boundary == remediation_model.BOUNDARY, "plan version and public boundary replay"),
        ("gate-lineage", plan.gate_id == plan.gate.gate_id and plan.gate_address == plan.gate.content_address, "plan retains the gate identity and address"),
        ("gate-address", plan.gate_address.startswith(gate_model.GATE_PREFIX + ":"), "gate address uses the release-gate namespace"),
        ("action-order", tuple(item.ordinal for item in plan.actions) == tuple(range(1, plan.action_count + 1)), "actions are contiguous and ordered"),
        ("action-replay", tuple(item.to_dict() for item in plan.actions) == tuple(item.to_dict() for item in expected.actions), "actions replay deterministically from findings"),
        ("finding-conservation", tuple(item.finding_address for item in plan.actions) == tuple(item.content_address for item in plan.gate.findings), "one action is retained for every gate finding"),
        ("reason-conservation", all(set(item.reason_codes).issubset(set(gate_model.REASON_CODES)) for item in plan.actions), "all action reasons are gate reason codes"),
        ("direction-conservation", tuple(item.direction for item in plan.actions) == tuple(item.direction for item in plan.gate.findings), "finding directions are conserved"),
        ("evidence-lineage", all(plan.gate_address in item.evidence_addresses and item.finding_address in item.evidence_addresses for item in plan.actions), "every action retains gate and finding evidence"),
        ("action-kind-conservation", sum(sum(item.action == action for item in plan.actions) for action in remediation_model.ACTION_KINDS) == plan.action_count, "action kinds partition the plan"),
        ("priority-conservation", all(item.priority in remediation_model.PRIORITIES for item in plan.actions), "priorities are bounded"),
        ("required-count", plan.required_action_count == sum(item.required for item in plan.actions), "required actions are conserved"),
        ("critical-count", plan.critical_action_count == sum(item.priority == "critical" for item in plan.actions), "critical actions are conserved"),
        ("safe-actions", all(item.action == "none" and item.priority == "low" and not item.required for item in plan.actions if item.outcome == "safe"), "safe findings are explicit no-ops"),
        ("blocked-actions", all(item.action != "none" and item.priority == "critical" and item.required for item in plan.actions if item.outcome == "blocked"), "blocked findings require critical actions"),
        ("state-replay", plan.state == ("blocked" if any(item.outcome == "blocked" for item in plan.actions) else "review" if plan.required_action_count else "clear"), "plan state replays from action outcomes"),
        ("decision-replay", plan.decision == {"clear": "close", "review": "hold", "blocked": "block"}[plan.state], "plan decision replays from state"),
        ("canonical-round-trip", remediation_model.plan_from_mapping(plan.to_dict()).to_dict() == plan.to_dict(), "canonical plan mapping replays byte-stable structure"),
    )
    built = tuple(_make_check(ordinal, check_id, passed, detail, evidence) for ordinal, (check_id, passed, detail) in enumerate(checks, 1))
    body = {"plan_address": plan.content_address, "version": VERSION, "boundary": BOUNDARY, "checks": built, "check_count": len(built), "passed_count": sum(item.passed for item in built), "failed_count": sum(not item.passed for item in built), "accepted": all(item.passed for item in built), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataQualityDiffGateRemediationAudit(**body)
    return DownloadedDataQualityDiffGateRemediationAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRemediationAudit:
    return DownloadedDataQualityDiffGateRemediationAudit.from_mapping(value)


def audit_json(value: DownloadedDataQualityDiffGateRemediationAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataQualityDiffGateRemediationAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    for item in value.checks:
        row = item.to_dict()
        writer.writerow(";".join(row[field]) if field == "evidence_addresses" else row[field] for field in CHECK_FIELDS)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataQualityDiffGateRemediationAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Remediation Audit", "", f"- Plan: `{value.plan_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"plan_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_plan", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataQualityDiffGateRemediationAudit", "DownloadedDataQualityDiffGateRemediationAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_plan", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
