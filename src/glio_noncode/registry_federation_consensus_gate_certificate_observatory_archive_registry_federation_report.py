"""Operational report for archive-registry federation reconciliation."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_audit as federation_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus as consensus_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus_audit as consensus_audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-report-v1"
BOUNDARY = federation_model.BOUNDARY + "_report"
REPORT_PREFIX = federation_model.FEDERATION_PREFIX + "-report"
ALERT_PREFIX = REPORT_PREFIX + "-alert"
DEFAULT_REPORT_ID = "consensus-certificate-observatory-archive-registry-federation-report"
SEVERITIES = ("info", "warning", "critical")
STATUSES = ("ready", "review", "blocked")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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
    return federation_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert:
    FIELDS = ("ordinal", "alert_id", "severity", "kind", "entry_id", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, alert_id: str, severity: str, kind: str, entry_id: str, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation report alert ordinal", federation_model.MAX_ENTRIES + federation_model.MAX_PEERS)
        self.alert_id = _label(alert_id, "federation report alert ID")
        self.severity = _label(severity, "federation report alert severity")
        self.kind = _label(kind, "federation report alert kind")
        self.entry_id = _label(entry_id, "federation report alert entry ID", required=False)
        self.detail = _text(detail, "federation report alert detail")
        self.evidence_addresses = tuple(_text(item, "federation report alert evidence", 2048) for item in _sequence(evidence_addresses, "federation report alert evidence", federation_model.MAX_PEERS + 2))
        self.content_address = _address(content_address, "federation report alert address", ALERT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation report alert address")
        self._validate()

    def _validate(self) -> None:
        if self.severity not in SEVERITIES or not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("federation report alert is invalid")
        if not self.content_address.endswith(":pending") and address_alert(self) != self.content_address:
            raise ValidationError("federation report alert address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert":
        value = _mapping(value, "federation report alert")
        _strict(value, set(cls.FIELDS), "federation report alert")
        return cls(*(value[field] for field in cls.FIELDS))


def address_alert(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ALERT_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport:
    FIELDS = ("report_id", "federation_id", "federation_address", "consensus_address", "federation_audit_address", "consensus_audit_address", "alerts", "alert_count", "conflict_count", "resolved_count", "held_count", "status", "decision", "accepted", "content_address")

    def __init__(self, report_id: str, federation_id: str, federation_address: str, consensus_address: str, federation_audit_address: str, consensus_audit_address: str, alerts: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert], alert_count: int, conflict_count: int, resolved_count: int, held_count: int, status: str, decision: str, accepted: bool, content_address: str) -> None:
        self.report_id = _label(report_id, "federation report ID")
        self.federation_id = _label(federation_id, "federation report federation ID")
        self.federation_address = _address(federation_address, "federation report federation address", federation_model.FEDERATION_PREFIX)
        self.consensus_address = _address(consensus_address, "federation report consensus address", consensus_model.CONSENSUS_PREFIX)
        self.federation_audit_address = _address(federation_audit_address, "federation report federation audit address", federation_audit_model.AUDIT_PREFIX)
        self.consensus_audit_address = _address(consensus_audit_address, "federation report consensus audit address", consensus_audit_model.AUDIT_PREFIX)
        self.alerts = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert.from_mapping(item) for item in _sequence(alerts, "federation report alerts", federation_model.MAX_ENTRIES + federation_model.MAX_PEERS))
        self.alert_count = _count(alert_count, "federation report alert count", len(self.alerts) if self.alerts else federation_model.MAX_ENTRIES + federation_model.MAX_PEERS)
        self.conflict_count = _count(conflict_count, "federation report conflict count", federation_model.MAX_ENTRIES)
        self.resolved_count = _count(resolved_count, "federation report resolved count", self.conflict_count)
        self.held_count = _count(held_count, "federation report held count", federation_model.MAX_ENTRIES)
        self.status = _label(status, "federation report status")
        self.decision = _label(decision, "federation report decision")
        self.accepted = _bool(accepted, "federation report acceptance")
        self.content_address = _address(content_address, "federation report address", REPORT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation report address")
        self._validate()

    def _validate(self) -> None:
        if self.alert_count != len(self.alerts) or self.status not in STATUSES or self.decision not in ("accept", "review", "hold") or self.resolved_count > self.conflict_count:
            raise ValidationError("federation report counters or outcome are invalid")
        if self.accepted != (self.status == "ready") or self.decision != ("accept" if self.status == "ready" else "hold" if self.status == "blocked" else "review"):
            raise ValidationError("federation report outcome does not replay")
        if tuple(item.ordinal for item in self.alerts) != tuple(range(1, self.alert_count + 1)):
            raise ValidationError("federation report alerts are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("federation report crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_report(self) != self.content_address:
            raise ValidationError("federation report address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, "federation_id": self.federation_id, "federation_address": self.federation_address, "consensus_address": self.consensus_address, "federation_audit_address": self.federation_audit_address, "consensus_audit_address": self.consensus_audit_address, "alerts": tuple(item.to_dict() for item in self.alerts), "alert_count": self.alert_count, "conflict_count": self.conflict_count, "resolved_count": self.resolved_count, "held_count": self.held_count, "status": self.status, "decision": self.decision, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("report_id", "federation_id", "federation_address", "consensus_address", "alert_count", "conflict_count", "resolved_count", "held_count", "status", "decision", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport":
        value = _mapping(value, "federation report")
        _strict(value, set(cls.FIELDS), "federation report")
        return cls(value["report_id"], value["federation_id"], value["federation_address"], value["consensus_address"], value["federation_audit_address"], value["consensus_audit_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert.from_mapping(item) for item in _sequence(value["alerts"], "federation report alerts", federation_model.MAX_ENTRIES + federation_model.MAX_PEERS)), value["alert_count"], value["conflict_count"], value["resolved_count"], value["held_count"], value["status"], value["decision"], value["accepted"], value["content_address"])


def address_report(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REPORT_PREFIX)


def _alert(ordinal: int, kind: str, severity: str, entry_id: str, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert:
    alert_id = f"{kind}-{entry_id}" if entry_id else kind
    body = {"ordinal": ordinal, "alert_id": alert_id, "severity": severity, "kind": kind, "entry_id": entry_id, "detail": detail, "evidence_addresses": tuple(evidence)}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert(**body, content_address=ALERT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert(**body, content_address=address_alert(provisional))


def build_report(value: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation, *, consensus: consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus | None = None, federation_audit: federation_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit | None = None, consensus_audit: consensus_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit | None = None, report_id: str = DEFAULT_REPORT_ID) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport:
    value = federation_model.verify_federation(value)
    consensus = consensus_model.build_consensus(value) if consensus is None else consensus_model.verify_consensus(consensus)
    federation_audit = federation_audit_model.audit_federation(value) if federation_audit is None else federation_audit_model.verify_audit(federation_audit)
    consensus_audit = consensus_audit_model.audit_consensus(consensus) if consensus_audit is None else consensus_audit_model.verify_audit(consensus_audit)
    alerts: list[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert] = []
    for observation in value.observations:
        if observation.state == "missing":
            alerts.append(_alert(len(alerts) + 1, "peer-missing", "warning", observation.entry_id, "one or more federation peers do not contain this entry", (observation.content_address,)))
        elif observation.state == "divergent":
            alerts.append(_alert(len(alerts) + 1, "peer-divergence", "warning", observation.entry_id, "peers reported different archive evidence for this entry", (observation.content_address,)))
    for decision in consensus.decisions:
        if decision.state == "held":
            alerts.append(_alert(len(alerts) + 1, "quorum-unresolved", "critical", decision.entry_id, "no archive address reached the configured quorum", decision.evidence_addresses))
    if not federation_audit.accepted:
        alerts.append(_alert(len(alerts) + 1, "federation-audit-failed", "critical", "", "the independent federation audit did not accept the comparison", (federation_audit.content_address,)))
    if not consensus_audit.accepted:
        alerts.append(_alert(len(alerts) + 1, "consensus-audit-failed", "critical", "", "the independent consensus audit did not accept the quorum result", (consensus_audit.content_address,)))
    alerts_tuple = tuple(alerts)
    blocked = consensus.held_count > 0 or not federation_audit.accepted or not consensus_audit.accepted
    status = "blocked" if blocked else "review" if value.conflict_count else "ready"
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport(report_id, value.federation_id, value.content_address, consensus.content_address, federation_audit.content_address, consensus_audit.content_address, alerts_tuple, len(alerts_tuple), value.conflict_count, value.conflict_count - sum(item.state == "held" for item in consensus.decisions if value.observation(item.entry_id).state != "consistent"), consensus.held_count, status, "accept" if status == "ready" else "hold" if status == "blocked" else "review", status == "ready", REPORT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport(provisional.report_id, provisional.federation_id, provisional.federation_address, provisional.consensus_address, provisional.federation_audit_address, provisional.consensus_audit_address, provisional.alerts, provisional.alert_count, provisional.conflict_count, provisional.resolved_count, provisional.held_count, provisional.status, provisional.decision, provisional.accepted, address_report(provisional))


def report_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport:
    return verify_report(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport.from_mapping(value))


def verify_report(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport):
        raise ValidationError("federation report verification requires a typed report")
    value._validate()
    if not value.content_address.endswith(":pending") and address_report(value) != value.content_address:
        raise ValidationError("federation report address verification failed")
    return value


def report_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport) -> str:
    return canonical_json(verify_report(value).to_dict())


def report_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport) -> str:
    value = verify_report(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "alert_id", "severity", "kind", "entry_id", "detail", "evidence_addresses", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in value.alerts:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_report_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport) -> str:
    value = verify_report(value)
    lines = ["# Archive Registry Federation Report", "", f"- Status: `{value.status}`", f"- Decision: `{value.decision}`", f"- Conflicts: `{value.conflict_count}`", f"- Resolved: `{value.resolved_count}`", f"- Held: `{value.held_count}`", "", "| # | severity | kind | entry | detail |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.severity}` | `{item.kind}` | `{item.entry_id}` | {item.detail} |" for item in value.alerts)
    return "\n".join(lines) + "\n"


def alert_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "alert_id": {"type": "string"}, "severity": {"enum": list(SEVERITIES)}, "kind": {"type": "string"}, "entry_id": {"type": "string"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def report_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport.FIELDS), "properties": {"report_id": {"type": "string"}, "federation_id": {"type": "string"}, "federation_address": {"type": "string"}, "consensus_address": {"type": "string"}, "federation_audit_address": {"type": "string"}, "consensus_audit_address": {"type": "string"}, "alerts": {"type": "array", "items": alert_schema()}, "alert_count": {"type": "integer", "minimum": 0}, "conflict_count": {"type": "integer", "minimum": 0}, "resolved_count": {"type": "integer", "minimum": 0}, "held_count": {"type": "integer", "minimum": 0}, "status": {"enum": list(STATUSES)}, "decision": {"enum": ["accept", "review", "hold"]}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "operations": ("build_report", "report_from_mapping", "report_json", "report_csv", "render_report_markdown", "verify_report"), "statuses": STATUSES, "severities": SEVERITIES}


__all__ = ["ALERT_PREFIX", "BOUNDARY", "DEFAULT_REPORT_ID", "REPORT_PREFIX", "SEVERITIES", "STATUSES", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReportAlert", "address_alert", "address_report", "alert_schema", "build_report", "capabilities", "render_report_markdown", "report_csv", "report_from_mapping", "report_json", "report_schema", "verify_report"]
