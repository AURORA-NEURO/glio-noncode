"""Independent assurance for federation operational reports."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_report as report_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = report_model.VERSION + "-audit-v1"
BOUNDARY = report_model.BOUNDARY + "_audit"
AUDIT_PREFIX = report_model.REPORT_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("alert-count", "alert-order", "severity-bound", "evidence", "status-bound", "decision-replay", "address-links", "public-boundary", "report-address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} must use its public address namespace")
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
    return report_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation report audit ordinal", len(CHECK_IDS))
        self.check_id = _label(check_id, "federation report audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("federation report audit check ID is unsupported")
        self.passed = _bool(passed, "federation report audit result")
        self.detail = _text(detail, "federation report audit detail")
        self.evidence_addresses = tuple(_text(item, "federation report audit evidence", 2048) for item in _sequence(evidence_addresses, "federation report audit evidence", report_model.federation_model.MAX_ENTRIES + report_model.federation_model.MAX_PEERS))
        self.content_address = _address(content_address, "federation report audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation report audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("federation report audit check is invalid")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("federation report audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck":
        value = _mapping(value, "federation report audit check")
        _strict(value, set(cls.FIELDS), "federation report audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit:
    FIELDS = ("report_id", "report_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, report_id: str, report_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.report_id = _label(report_id, "federation report audit ID")
        self.report_address = _address(report_address, "federation report audit report address", report_model.REPORT_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck.from_mapping(item) for item in _sequence(checks, "federation report audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "federation report audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "federation report audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "federation report audit failed count", self.check_count)
        self.accepted = _bool(accepted, "federation report audit acceptance")
        self.content_address = _address(content_address, "federation report audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation report audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("federation report audit counters or order are invalid")
        if not _public(self.to_dict()):
            raise ValidationError("federation report audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("federation report audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, "report_address": self.report_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("report_id", "report_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit":
        value = _mapping(value, "federation report audit")
        _strict(value, set(cls.FIELDS), "federation report audit")
        return cls(value["report_id"], value["report_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "federation report audit checks", len(CHECK_IDS))), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_report(value: report_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit:
    value = report_model.verify_report(value)
    evidence = tuple(item.content_address for item in value.alerts)
    checks = (
        _check(1, "alert-count", value.alert_count == len(value.alerts), "alert count matches the alert set", evidence or (value.content_address,)),
        _check(2, "alert-order", tuple(item.ordinal for item in value.alerts) == tuple(range(1, value.alert_count + 1)), "alerts are ordered", evidence or (value.content_address,)),
        _check(3, "severity-bound", all(item.severity in report_model.SEVERITIES for item in value.alerts), "alerts use known severities", evidence or (value.content_address,)),
        _check(4, "evidence", all(item.evidence_addresses for item in value.alerts), "alerts retain evidence addresses", evidence or (value.content_address,)),
        _check(5, "status-bound", value.status in report_model.STATUSES, "report status is bounded", (value.content_address,)),
        _check(6, "decision-replay", value.accepted == (value.status == "ready") and value.decision == ("accept" if value.status == "ready" else "hold" if value.status == "blocked" else "review"), "report decision replays from status", (value.content_address,)),
        _check(7, "address-links", all(bool(item) for item in (value.federation_address, value.consensus_address, value.federation_audit_address, value.consensus_audit_address)), "report links all upstream evidence", (value.content_address,)),
        _check(8, "public-boundary", _public(value.to_dict()), "report contains only public data", (value.content_address,)),
        _check(9, "report-address", report_model.address_report(value) == value.content_address, "report content address replays", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit(value.report_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit(provisional.report_id, provisional.report_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit):
        raise ValidationError("federation report audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("federation report audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Report Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit.FIELDS), "properties": {"report_id": {"type": "string"}, "report_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "independent": True, "operations": ("audit_report", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_report", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
