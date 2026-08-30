"""Deterministic health reporting for certificate-observatory registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_audit as audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-report-v1"
BOUNDARY = registry_model.BOUNDARY + "_report"
REPORT_PREFIX = registry_model.REGISTRY_PREFIX + "-report"
ALERT_PREFIX = REPORT_PREFIX + "-alert"
DEFAULT_REPORT_ID = "consensus-certificate-observatory-archive-registry-report"
SEVERITIES = ("info", "warning", "critical")
STATUSES = ("ready", "review", "blocked")
MAX_ALERTS = registry_model.MAX_ENTRIES * 4


def _text(value: Any, field: str, maximum: int = 2048, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _ratio(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 1:
        raise ValidationError(f"{field} must be between zero and one")
    return float(value)


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


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert:
    """One actionable health observation with explicit evidence."""

    FIELDS = ("alert_id", "kind", "severity", "message", "entry_ids", "evidence_addresses", "content_address")

    def __init__(self, alert_id: str, kind: str, severity: str, message: str, entry_ids: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.alert_id = _label(alert_id, "registry report alert ID")
        self.kind = _label(kind, "registry report alert kind")
        self.severity = _label(severity, "registry report alert severity")
        if self.severity not in SEVERITIES:
            raise ValidationError("registry report alert severity is unsupported")
        self.message = _text(message, "registry report alert message", 1024)
        self.entry_ids = tuple(_label(item, "registry report alert entry ID") for item in _sequence(entry_ids, "registry report alert entries", registry_model.MAX_ENTRIES))
        self.evidence_addresses = tuple(_address(item, "registry report alert evidence address") for item in _sequence(evidence_addresses, "registry report alert evidence", 16))
        if not self.evidence_addresses:
            raise ValidationError("registry report alerts require evidence")
        self.content_address = _address(content_address, "registry report alert address", ALERT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry report alert address")
        self._validate()

    def _validate(self) -> None:
        if len(set(self.entry_ids)) != len(self.entry_ids) or not _public(self.to_dict()):
            raise ValidationError("registry report alert is not a valid public projection")
        if not self.content_address.endswith(":pending") and address_alert(self) != self.content_address:
            raise ValidationError("registry report alert address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert":
        value = _mapping(value, "registry report alert")
        _strict(value, set(cls.FIELDS), "registry report alert")
        return cls(*(value[field] for field in cls.FIELDS))


def address_alert(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert):
        raise ValidationError("registry report alert address requires a typed alert")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ALERT_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport:
    """Path-free readiness report derived from one verified registry."""

    FIELDS = ("report_id", "version", "boundary", "registry_address", "audit_address", "query_address", "entry_count", "package_count", "accepted_count", "held_count", "observation_count", "total_check_count", "total_failed_count", "alert_count", "acceptance_ratio", "failure_ratio", "status", "alerts", "content_address")

    def __init__(self, report_id: str, version: str, boundary: str, registry_address: str, audit_address: str, query_address: str, entry_count: int, package_count: int, accepted_count: int, held_count: int, observation_count: int, total_check_count: int, total_failed_count: int, alert_count: int, acceptance_ratio: float, failure_ratio: float, status: str, alerts: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert], content_address: str) -> None:
        self.report_id = _label(report_id, "registry report ID")
        self.version = _text(version, "registry report version", 1024)
        self.boundary = _text(boundary, "registry report boundary")
        self.registry_address = _address(registry_address, "registry report registry address", registry_model.REGISTRY_PREFIX)
        self.audit_address = _address(audit_address, "registry report audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "registry report query address", query_model.RESULT_PREFIX)
        self.entry_count = _count(entry_count, "registry report entry count", registry_model.MAX_ENTRIES, positive=True)
        self.package_count = _count(package_count, "registry report package count", registry_model.MAX_ENTRIES, positive=True)
        self.accepted_count = _count(accepted_count, "registry report accepted count", self.entry_count)
        self.held_count = _count(held_count, "registry report held count", self.entry_count)
        self.observation_count = _count(observation_count, "registry report observation count", 65536 * registry_model.MAX_ENTRIES)
        self.total_check_count = _count(total_check_count, "registry report check count", 2_000_000_000)
        self.total_failed_count = _count(total_failed_count, "registry report failed count", self.total_check_count)
        self.alert_count = _count(alert_count, "registry report alert count", MAX_ALERTS)
        self.acceptance_ratio = _ratio(acceptance_ratio, "registry report acceptance ratio")
        self.failure_ratio = _ratio(failure_ratio, "registry report failure ratio")
        self.status = _label(status, "registry report status")
        if self.status not in STATUSES:
            raise ValidationError("registry report status is unsupported")
        self.alerts = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert.from_mapping(item) for item in _sequence(alerts, "registry report alerts", MAX_ALERTS))
        self.content_address = _address(content_address, "registry report address", REPORT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry report address")
        self._validate()

    def _validate(self) -> None:
        if self.accepted_count + self.held_count != self.entry_count or self.alert_count != len(self.alerts) or self.package_count > self.entry_count:
            raise ValidationError("registry report counters are not conserved")
        if self.entry_count and self.acceptance_ratio != self.accepted_count / self.entry_count:
            raise ValidationError("registry report acceptance ratio does not replay")
        if self.total_check_count and self.failure_ratio != self.total_failed_count / self.total_check_count:
            raise ValidationError("registry report failure ratio does not replay")
        if tuple((item.severity, item.alert_id) for item in self.alerts) != tuple(sorted((item.severity, item.alert_id) for item in self.alerts)):
            raise ValidationError("registry report alerts are not deterministic")
        expected_status = "blocked" if self.total_failed_count or any(item.severity == "critical" for item in self.alerts) else "review" if self.held_count or self.alerts else "ready"
        if self.status != expected_status:
            raise ValidationError("registry report status does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry report crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_report(self) != self.content_address:
            raise ValidationError("registry report address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, "version": self.version, "boundary": self.boundary, "registry_address": self.registry_address, "audit_address": self.audit_address, "query_address": self.query_address, "entry_count": self.entry_count, "package_count": self.package_count, "accepted_count": self.accepted_count, "held_count": self.held_count, "observation_count": self.observation_count, "total_check_count": self.total_check_count, "total_failed_count": self.total_failed_count, "alert_count": self.alert_count, "acceptance_ratio": self.acceptance_ratio, "failure_ratio": self.failure_ratio, "status": self.status, "alerts": tuple(item.to_dict() for item in self.alerts), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in self.FIELDS if key != "alerts"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport":
        value = _mapping(value, "registry report")
        _strict(value, set(cls.FIELDS), "registry report")
        alerts = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert.from_mapping(item) for item in _sequence(value["alerts"], "registry report alerts", MAX_ALERTS))
        return cls(value["report_id"], value["version"], value["boundary"], value["registry_address"], value["audit_address"], value["query_address"], value["entry_count"], value["package_count"], value["accepted_count"], value["held_count"], value["observation_count"], value["total_check_count"], value["total_failed_count"], value["alert_count"], value["acceptance_ratio"], value["failure_ratio"], value["status"], alerts, value["content_address"])


def address_report(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport):
        raise ValidationError("registry report address requires a typed report")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REPORT_PREFIX)


def _alert(alert_id: str, kind: str, severity: str, message: str, entry_ids: Sequence[str], evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert(alert_id, kind, severity, message, entry_ids, evidence, ALERT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert(provisional.alert_id, provisional.kind, provisional.severity, provisional.message, provisional.entry_ids, provisional.evidence_addresses, address_alert(provisional))


def build_report(value: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry, *, report_id: str = DEFAULT_REPORT_ID) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport:
    value = registry_model.verify_registry(value)
    audit = audit_model.audit_registry(value)
    query = query_model.query_registry(value, resources=query_model.RESOURCES, limit=registry_model.MAX_QUERY_ITEMS)
    alerts = []
    held = tuple(item for item in value.entries if not item.accepted)
    failed = tuple(item for item in value.entries if item.total_failed_count)
    noisy = tuple(item for item in value.entries if item.alert_count)
    if held:
        alerts.append(_alert("held-entries", "held-entries", "warning", f"{len(held)} archive entries are held", tuple(item.entry_id for item in held), tuple(item.content_address for item in held) + (value.content_address,)))
    if failed:
        alerts.append(_alert("failed-checks", "failed-checks", "critical", f"{sum(item.total_failed_count for item in failed)} checks failed", tuple(item.entry_id for item in failed), tuple(item.content_address for item in failed) + (value.content_address,)))
    if noisy:
        alerts.append(_alert("observatory-alerts", "observatory-alerts", "warning", f"{sum(item.alert_count for item in noisy)} source alerts are present", tuple(item.entry_id for item in noisy), tuple(item.content_address for item in noisy) + (value.content_address,)))
    alerts.sort(key=lambda item: (item.severity, item.alert_id))
    metrics = value.metrics
    body = {"report_id": report_id, "version": VERSION, "boundary": BOUNDARY, "registry_address": value.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "entry_count": metrics.entry_count, "package_count": metrics.unique_package_count, "accepted_count": metrics.accepted_count, "held_count": metrics.held_count, "observation_count": metrics.observation_count, "total_check_count": metrics.total_check_count, "total_failed_count": metrics.total_failed_count, "alert_count": len(alerts), "acceptance_ratio": metrics.accepted_count / metrics.entry_count, "failure_ratio": metrics.total_failed_count / metrics.total_check_count, "status": "blocked" if metrics.total_failed_count else "review" if metrics.held_count or alerts else "ready", "alerts": tuple(alerts)}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport(**body, content_address=REPORT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport(provisional.report_id, provisional.version, provisional.boundary, provisional.registry_address, provisional.audit_address, provisional.query_address, provisional.entry_count, provisional.package_count, provisional.accepted_count, provisional.held_count, provisional.observation_count, provisional.total_check_count, provisional.total_failed_count, provisional.alert_count, provisional.acceptance_ratio, provisional.failure_ratio, provisional.status, provisional.alerts, address_report(provisional))


def report_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport:
    return verify_report(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport.from_mapping(value))


def verify_report(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport) or (not value.content_address.endswith(":pending") and address_report(value) != value.content_address):
        raise ValidationError("registry report is not valid")
    return value


def report_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport) -> str:
    return canonical_json(verify_report(value).to_dict())


def report_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport) -> str:
    value = verify_report(value)
    stream = io.StringIO()
    fields = ("report_id", "status", "entry_count", "package_count", "accepted_count", "held_count", "observation_count", "total_check_count", "total_failed_count", "alert_count", "acceptance_ratio", "failure_ratio", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow({field: value.to_dict()[field] for field in fields})
    return stream.getvalue()


def render_report_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport) -> str:
    value = verify_report(value)
    lines = ["# Certificate Observatory Archive Registry Report", "", f"- Registry: `{value.registry_address}`", f"- Status: `{value.status}`", f"- Entries: `{value.entry_count}`", f"- Packages: `{value.package_count}`", f"- Acceptance ratio: `{value.acceptance_ratio:.6f}`", f"- Failure ratio: `{value.failure_ratio:.6f}`", f"- Alerts: `{value.alert_count}`", f"- Address: `{value.content_address}`", "", "| severity | kind | message | evidence |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{item.severity}` | `{item.kind}` | {item.message} | `{len(item.evidence_addresses)}` |" for item in value.alerts)
    return "\n".join(lines) + "\n"


def alert_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert.FIELDS), "properties": {"alert_id": {"type": "string"}, "kind": {"type": "string"}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "message": {"type": "string"}, "entry_ids": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string", "pattern": "^" + ALERT_PREFIX + ":"}}}


def report_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport.FIELDS), "properties": {"report_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "registry_address": {"type": "string", "pattern": "^" + registry_model.REGISTRY_PREFIX + ":"}, "audit_address": {"type": "string", "pattern": "^" + audit_model.AUDIT_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.RESULT_PREFIX + ":"}, "entry_count": {"type": "integer", "minimum": 1}, "package_count": {"type": "integer", "minimum": 1}, "accepted_count": {"type": "integer", "minimum": 0}, "held_count": {"type": "integer", "minimum": 0}, "observation_count": {"type": "integer", "minimum": 0}, "total_check_count": {"type": "integer", "minimum": 0}, "total_failed_count": {"type": "integer", "minimum": 0}, "alert_count": {"type": "integer", "minimum": 0}, "acceptance_ratio": {"type": "number", "minimum": 0, "maximum": 1}, "failure_ratio": {"type": "number", "minimum": 0, "maximum": 1}, "status": {"type": "string", "enum": list(STATUSES)}, "alerts": {"type": "array", "items": alert_schema(), "maxItems": MAX_ALERTS}, "content_address": {"type": "string", "pattern": "^" + REPORT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "report_prefix": REPORT_PREFIX, "alert_prefix": ALERT_PREFIX, "severities": SEVERITIES, "statuses": STATUSES, "limits": {"max_alerts": MAX_ALERTS}, "features": ("deterministic readiness status", "held-entry alerts", "failed-check alerts", "source-alert disclosure", "evidence-linked alerts", "acceptance and failure ratios", "JSON CSV and Markdown exports"), "schemas": ("alert", "report")}


__all__ = ["ALERT_PREFIX", "BOUNDARY", "DEFAULT_REPORT_ID", "MAX_ALERTS", "REPORT_PREFIX", "SEVERITIES", "STATUSES", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReport", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryReportAlert", "VERSION", "address_alert", "address_report", "alert_schema", "build_report", "capabilities", "render_report_markdown", "report_csv", "report_from_mapping", "report_json", "report_schema", "verify_report"]
