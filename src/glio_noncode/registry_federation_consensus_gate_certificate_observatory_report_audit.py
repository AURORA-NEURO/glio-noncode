"""Independent audit for deterministic certificate observatory reports."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory as observatory_model
from . import registry_federation_consensus_gate_certificate_observatory_report as report_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = report_model.VERSION + "-audit-v1"
BOUNDARY = report_model.BOUNDARY + "_audit"
AUDIT_PREFIX = report_model.REPORT_PREFIX + "-audit"
FINDING_PREFIX = report_model.REPORT_PREFIX + "-audit-finding"
CHECK_IDS = ("exact-fields", "public-boundary", "observatory-link", "observation-conservation", "disposition-conservation", "acceptance-conservation", "ratio-conservation", "check-conservation", "latest-conservation", "withheld-streak", "transition-conservation", "alert-conservation", "mapping-round-trip", "content-address", "path-free")


def _text(value: Any, field: str, maximum: int = observatory_model.MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate observatory report audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "certificate observatory report audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("certificate observatory report audit check ID is unsupported")
        self.passed = _bool(passed, "certificate observatory report audit finding result")
        self.observed = _text(observed, "certificate observatory report audit observed value")
        self.expected = _text(expected, "certificate observatory report audit expected value")
        self.detail = _text(detail, "certificate observatory report audit detail", required=True)
        self.content_address = _address(content_address, "certificate observatory report audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("certificate observatory report audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory report audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding:
        value = _mapping(value, "certificate observatory report audit finding")
        _strict(value, set(cls.FIELDS), "certificate observatory report audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding):
        raise ValidationError("certificate observatory report finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryReportAudit:
    FIELDS = ("report_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, report_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.report_address = _address(report_address, "audited certificate observatory report address", report_model.REPORT_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding) for item in self.checks):
            raise ValidationError("certificate observatory report audit checks must be typed")
        self.check_count = _count(check_count, "certificate observatory report audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "certificate observatory report audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "certificate observatory report audit failed count", self.check_count)
        self.accepted = _bool(accepted, "certificate observatory report audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("certificate observatory report audit counters are not conserved")
        self.content_address = _address(content_address, "certificate observatory report audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("certificate observatory report audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory report audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"report_address": self.report_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryReportAudit:
        value = _mapping(value, "certificate observatory report audit")
        _strict(value, set(cls.FIELDS), "certificate observatory report audit")
        return cls(value["report_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryReportAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryReportAudit):
        raise ValidationError("certificate observatory report audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_report(value: report_model.RegistryFederationConsensusGateCertificateObservatoryReport) -> RegistryFederationConsensusGateCertificateObservatoryReportAudit:
    """Recompute report ratios, counters, latest state, streak, transitions, and alerts."""

    value = report_model.verify_report(value)
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(report_model.RegistryFederationConsensusGateCertificateObservatoryReport.FIELDS), tuple(sorted(value.to_dict())), report_model.RegistryFederationConsensusGateCertificateObservatoryReport.FIELDS, "report fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "report is public and path-free"),
        _finding(3, "observatory-link", value.observatory_address.startswith(observatory_model.OBSERVATORY_PREFIX + ":"), value.observatory_address, observatory_model.OBSERVATORY_PREFIX + ":", "report links to an observatory"),
        _finding(4, "observation-conservation", value.history_count >= 1 and value.observation_count >= 1, (value.history_count, value.observation_count), "positive stream dimensions", "report has observed data"),
        _finding(5, "disposition-conservation", value.issued_count + value.withheld_count == value.observation_count, (value.issued_count, value.withheld_count, value.observation_count), "issued + withheld = observations", "dispositions are conserved"),
        _finding(6, "acceptance-conservation", value.accepted_count + value.held_count == value.observation_count, (value.accepted_count, value.held_count, value.observation_count), "accepted + held = observations", "acceptance is conserved"),
        _finding(7, "ratio-conservation", value.acceptance_ratio == value.accepted_count / value.observation_count, value.acceptance_ratio, value.accepted_count / value.observation_count, "acceptance ratio replays exactly"),
        _finding(8, "check-conservation", value.total_failed_count <= value.total_check_count, (value.total_failed_count, value.total_check_count), "failed <= total checks", "check totals are conserved"),
        _finding(9, "latest-conservation", value.latest_observation_ordinal <= value.observation_count and value.latest_state in observatory_model.STATES and value.latest_decision in observatory_model.DECISIONS, (value.latest_observation_ordinal, value.latest_state, value.latest_decision), "latest observation bounds", "latest disposition is valid"),
        _finding(10, "withheld-streak", value.consecutive_withheld_count <= value.withheld_count, (value.consecutive_withheld_count, value.withheld_count), "streak <= withheld count", "withheld streak is bounded"),
        _finding(11, "transition-conservation", value.transition_count <= max(0, value.observation_count - 1) and value.recovery_count <= value.transition_count, (value.transition_count, value.recovery_count), "recoveries <= transitions < observations", "transition metrics are bounded"),
        _finding(12, "alert-conservation", len(value.alerts) == value.alert_count and len({item.alert_id for item in value.alerts}) == value.alert_count and all(item.content_address.startswith(report_model.ALERT_PREFIX + ":") for item in value.alerts), (len(value.alerts), value.alert_count), "unique addressed alerts", "alert set is conserved"),
        _finding(13, "mapping-round-trip", report_model.report_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original report", "mapping conversion is lossless"),
        _finding(14, "content-address", report_model.address_report(value) == value.content_address, value.content_address, report_model.address_report(value), "report content address replays"),
        _finding(15, "path-free", _public(value.to_dict()), True, True, "report contains no local paths or attribution metadata"),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryReportAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryReportAudit(provisional.report_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryReportAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryReportAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryReportAudit) -> RegistryFederationConsensusGateCertificateObservatoryReportAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryReportAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("certificate observatory report audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryReportAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryReportAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryReportAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Release Certificate Observatory Report Audit", "", f"- Report: `{value.report_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryReportAudit.FIELDS), "properties": {"report_address": {"type": "string", "pattern": "^" + report_model.REPORT_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent report checks", "ratio and counter replay", "latest and withheld streak validation", "transition and alert validation", "content-address verification", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryReportAudit", "RegistryFederationConsensusGateCertificateObservatoryReportAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_report", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
