"""Independent audit for certificate-observatory registry health reports."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_report as report_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = report_model.VERSION + "-audit-v1"
BOUNDARY = report_model.BOUNDARY + "_audit"
AUDIT_PREFIX = report_model.REPORT_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = (
    "report-address",
    "registry-link",
    "audit-link",
    "query-link",
    "entry-count",
    "package-count",
    "accepted-count",
    "held-count",
    "observation-count",
    "check-count",
    "failure-count",
    "alert-count",
    "ratio-replay",
    "status-logic",
    "alert-order",
    "alert-evidence",
    "mapping-round-trip",
    "export-replay",
    "public-boundary",
    "bounded-report",
)
MAX_TEXT = 2048


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
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
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding:
    """One independently addressable report assertion."""

    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "report audit finding ordinal", len(CHECK_IDS))
        if self.ordinal == 0 or not isinstance(check_id, str) or check_id not in CHECK_IDS:
            raise ValidationError("report audit finding check ID is undeclared")
        self.check_id = check_id
        self.passed = _bool(passed, "report audit finding pass state")
        self.observed = _text(observed, "report audit observed value", 1024)
        self.expected = _text(expected, "report audit expected value", 1024)
        self.detail = _text(detail, "report audit detail", 2048)
        self.evidence_address = _address(evidence_address, "report audit evidence address")
        self.content_address = _address(content_address, "report audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("report audit finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding":
        value = _mapping(value, "report audit finding")
        _strict(value, set(cls.FIELDS), "report audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding):
        raise ValidationError("report audit finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit:
    """Full report audit; acceptance requires every declared check."""

    FIELDS = ("report_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, report_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.report_address = _address(report_address, "report audit report address", report_model.REPORT_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding.from_mapping(item) for item in _sequence(checks, "report audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "report audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "report audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "report audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "report audit acceptance")
        self.content_address = _address(content_address, "report audit address", AUDIT_PREFIX)
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("report audit check order is not exact")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("report audit counters are not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("report audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("report audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"report_address": self.report_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("report_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit":
        value = _mapping(value, "report audit")
        _strict(value, set(cls.FIELDS), "report audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding.from_mapping(item) for item in _sequence(value["checks"], "report audit checks", len(CHECK_IDS)))
        return cls(value["report_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit):
        raise ValidationError("report audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str, evidence: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding:
    observed_text = str(observed)
    expected_text = str(expected)
    if len(observed_text) > 1024:
        observed_text = observed_text[:1021] + "..."
    if len(expected_text) > 1024:
        expected_text = expected_text[:1021] + "..."
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding(ordinal, check_id, passed, observed_text, expected_text, detail, evidence, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding(ordinal, check_id, passed, provisional.observed, provisional.expected, detail, evidence, address_finding(provisional))


def audit_report(value: report_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit:
    value = report_model.verify_report(value)
    alerts = value.alerts
    expected_status = "blocked" if value.total_failed_count or any(item.severity == "critical" for item in alerts) else "review" if value.held_count or alerts else "ready"
    expected_alert_order = tuple(sorted((item.severity, item.alert_id) for item in alerts))
    evidence_ok = all(item.evidence_addresses and len(set(item.entry_ids)) == len(item.entry_ids) for item in alerts)
    checks = (
        _finding(1, "report-address", report_model.address_report(value) == value.content_address, value.content_address, report_model.address_report(value), "report address reproduces from public fields", value.content_address),
        _finding(2, "registry-link", value.registry_address.startswith(registry_model.REGISTRY_PREFIX + ":"), value.registry_address, "registry content address", "report links to a registry", value.registry_address),
        _finding(3, "audit-link", value.audit_address.startswith(report_model.audit_model.AUDIT_PREFIX + ":"), value.audit_address, "registry audit content address", "report links to a registry audit", value.audit_address),
        _finding(4, "query-link", ":" in value.query_address, value.query_address, "query result content address", "report links to a query result", value.query_address),
        _finding(5, "entry-count", value.entry_count > 0, value.entry_count, "> 0", "report covers at least one entry", value.registry_address),
        _finding(6, "package-count", 0 < value.package_count <= value.entry_count, value.package_count, f"1..{value.entry_count}", "package cardinality is bounded by entries", value.registry_address),
        _finding(7, "accepted-count", value.accepted_count + value.held_count == value.entry_count, value.accepted_count, value.entry_count - value.held_count, "accepted and held entries conserve the entry total", value.registry_address),
        _finding(8, "held-count", value.held_count <= value.entry_count, value.held_count, f"0..{value.entry_count}", "held entries remain bounded", value.registry_address),
        _finding(9, "observation-count", value.observation_count >= value.entry_count, value.observation_count, f">= {value.entry_count}", "observations cover the registry entries", value.registry_address),
        _finding(10, "check-count", value.total_check_count > 0, value.total_check_count, "> 0", "report contains check evidence", value.audit_address),
        _finding(11, "failure-count", value.total_failed_count <= value.total_check_count, value.total_failed_count, f"0..{value.total_check_count}", "failed checks remain bounded", value.audit_address),
        _finding(12, "alert-count", value.alert_count == len(alerts), value.alert_count, len(alerts), "alert count matches alert records", value.content_address),
        _finding(13, "ratio-replay", value.acceptance_ratio == value.accepted_count / value.entry_count and value.failure_ratio == value.total_failed_count / value.total_check_count, (value.acceptance_ratio, value.failure_ratio), (value.accepted_count / value.entry_count, value.total_failed_count / value.total_check_count), "ratios replay from counters", value.content_address),
        _finding(14, "status-logic", value.status == expected_status, value.status, expected_status, "readiness status follows held, alert, and failure evidence", value.content_address),
        _finding(15, "alert-order", tuple((item.severity, item.alert_id) for item in alerts) == expected_alert_order, tuple((item.severity, item.alert_id) for item in alerts), expected_alert_order, "alerts are deterministically ordered", value.content_address),
        _finding(16, "alert-evidence", evidence_ok, evidence_ok, True, "each alert has bounded entry IDs and evidence", value.content_address),
        _finding(17, "mapping-round-trip", report_model.report_from_mapping(value.to_dict()).to_dict() == value.to_dict(), True, True, "public mapping reloads exactly", value.content_address),
        _finding(18, "export-replay", bool(report_model.report_json(value) and report_model.report_csv(value) and report_model.render_report_markdown(value)), True, True, "JSON CSV and Markdown exports are available", value.content_address),
        _finding(19, "public-boundary", _public(value.to_dict()), True, True, "report projection contains only public values", value.content_address),
        _finding(20, "bounded-report", len(alerts) <= report_model.MAX_ALERTS and len(value.to_dict()["alerts"]) == value.alert_count, len(alerts), f"0..{report_model.MAX_ALERTS}", "report alert cardinality remains bounded", value.content_address),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit(provisional.report_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("report audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    fields = ("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow({field: item.to_dict()[field] for field in fields})
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Archive Registry Report Audit", "", f"- Report: `{value.report_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit.FIELDS), "properties": {"report_address": {"type": "string", "pattern": "^" + report_model.REPORT_PREFIX + ":"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS), "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent report verification", "counter conservation", "ratio replay", "readiness status verification", "alert evidence verification", "path-free JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_report", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
