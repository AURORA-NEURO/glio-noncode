"""Deterministic health and transition report for certificate observatories."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory as observatory_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = observatory_model.VERSION + "-report-v1"
BOUNDARY = observatory_model.BOUNDARY + "_report"
REPORT_PREFIX = observatory_model.OBSERVATORY_PREFIX + "-report"
ALERT_PREFIX = REPORT_PREFIX + "-alert"
MAX_ALERTS = 16
ALERT_SEVERITIES = ("info", "warning", "critical")
STREAM_STATES = ("steady", "mixed", "held")


def _text(value: Any, field: str, maximum: int = observatory_model.MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _ratio(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 1:
        raise ValidationError(f"{field} must be a ratio between zero and one")
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
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(values) != len(set(values)):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(values))


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


class RegistryFederationConsensusGateCertificateObservatoryAlert:
    """A deterministic, evidence-linked operator signal."""

    FIELDS = ("alert_id", "kind", "severity", "count", "message", "evidence_addresses", "content_address")

    def __init__(self, alert_id: str, kind: str, severity: str, count: int, message: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.alert_id = _label(alert_id, "certificate observatory alert ID")
        self.kind = _label(kind, "certificate observatory alert kind")
        if severity not in ALERT_SEVERITIES:
            raise ValidationError("certificate observatory alert severity is unsupported")
        self.severity = severity
        self.count = _count(count, "certificate observatory alert count", observatory_model.MAX_OBSERVATIONS)
        self.message = _text(message, "certificate observatory alert message", required=True)
        self.evidence_addresses = _addresses(evidence_addresses, "certificate observatory alert evidence addresses", observatory_model.MAX_OBSERVATIONS)
        if not self.evidence_addresses:
            raise ValidationError("certificate observatory alerts require evidence")
        self.content_address = _address(content_address, "certificate observatory alert address", ALERT_PREFIX)
        if not self.content_address.endswith(":pending") and address_alert(self) != self.content_address:
            raise ValidationError("certificate observatory alert address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory alert crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryAlert:
        value = _mapping(value, "certificate observatory alert")
        _strict(value, set(cls.FIELDS), "certificate observatory alert")
        return cls(*(value[field] for field in cls.FIELDS))


def address_alert(value: RegistryFederationConsensusGateCertificateObservatoryAlert) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryAlert):
        raise ValidationError("certificate observatory alert address requires a typed alert")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ALERT_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryReport:
    """Addressed report of stream health, acceptance ratio, and transitions."""

    FIELDS = ("report_id", "observatory_address", "history_count", "observation_count", "issued_count", "withheld_count", "accepted_count", "held_count", "acceptance_ratio", "total_check_count", "total_failed_count", "latest_observation_ordinal", "latest_state", "latest_decision", "consecutive_withheld_count", "transition_count", "recovery_count", "stream_state", "alerts", "alert_count", "content_address")

    def __init__(self, report_id: str, observatory_address: str, history_count: int, observation_count: int, issued_count: int, withheld_count: int, accepted_count: int, held_count: int, acceptance_ratio: float, total_check_count: int, total_failed_count: int, latest_observation_ordinal: int, latest_state: str, latest_decision: str, consecutive_withheld_count: int, transition_count: int, recovery_count: int, stream_state: str, alerts: Sequence[RegistryFederationConsensusGateCertificateObservatoryAlert], alert_count: int, content_address: str) -> None:
        self.report_id = _label(report_id, "certificate observatory report ID")
        self.observatory_address = _address(observatory_address, "certificate observatory report address", observatory_model.OBSERVATORY_PREFIX)
        self.history_count = _count(history_count, "certificate observatory report history count", observatory_model.MAX_HISTORIES, positive=True)
        self.observation_count = _count(observation_count, "certificate observatory report observation count", observatory_model.MAX_OBSERVATIONS, positive=True)
        for name, value in (("issued_count", issued_count), ("withheld_count", withheld_count), ("accepted_count", accepted_count), ("held_count", held_count), ("total_check_count", total_check_count), ("total_failed_count", total_failed_count), ("transition_count", transition_count), ("recovery_count", recovery_count)):
            setattr(self, name, _count(value, f"certificate observatory report {name}", observatory_model.MAX_OBSERVATIONS * 32 if name in {"total_check_count", "total_failed_count"} else self.observation_count))
        self.acceptance_ratio = _ratio(acceptance_ratio, "certificate observatory report acceptance ratio")
        self.latest_observation_ordinal = _count(latest_observation_ordinal, "certificate observatory latest ordinal", self.observation_count, positive=True)
        if latest_state not in observatory_model.STATES or latest_decision not in observatory_model.DECISIONS:
            raise ValidationError("certificate observatory report latest disposition is unsupported")
        self.latest_state, self.latest_decision = latest_state, latest_decision
        self.consecutive_withheld_count = _count(consecutive_withheld_count, "certificate observatory consecutive withheld count", self.observation_count)
        if stream_state not in STREAM_STATES:
            raise ValidationError("certificate observatory report stream state is unsupported")
        self.stream_state = stream_state
        self.alerts = tuple(alerts)
        if len(self.alerts) > MAX_ALERTS or any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryAlert) for item in self.alerts):
            raise ValidationError("certificate observatory report alerts are outside the bound")
        self.alert_count = _count(alert_count, "certificate observatory report alert count", MAX_ALERTS)
        if len(self.alerts) != self.alert_count or self.accepted_count + self.held_count != self.observation_count or self.issued_count + self.withheld_count != self.observation_count or self.total_failed_count > self.total_check_count:
            raise ValidationError("certificate observatory report counters are not conserved")
        if self.acceptance_ratio != (self.accepted_count / self.observation_count):
            raise ValidationError("certificate observatory report acceptance ratio does not replay")
        self.content_address = _address(content_address, "certificate observatory report content address", REPORT_PREFIX)
        if not self.content_address.endswith(":pending") and address_report(self) != self.content_address:
            raise ValidationError("certificate observatory report content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory report crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, "observatory_address": self.observatory_address, "history_count": self.history_count, "observation_count": self.observation_count, "issued_count": self.issued_count, "withheld_count": self.withheld_count, "accepted_count": self.accepted_count, "held_count": self.held_count, "acceptance_ratio": self.acceptance_ratio, "total_check_count": self.total_check_count, "total_failed_count": self.total_failed_count, "latest_observation_ordinal": self.latest_observation_ordinal, "latest_state": self.latest_state, "latest_decision": self.latest_decision, "consecutive_withheld_count": self.consecutive_withheld_count, "transition_count": self.transition_count, "recovery_count": self.recovery_count, "stream_state": self.stream_state, "alerts": tuple(item.to_dict() for item in self.alerts), "alert_count": self.alert_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "alerts"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryReport:
        value = _mapping(value, "certificate observatory report")
        _strict(value, set(cls.FIELDS), "certificate observatory report")
        return cls(value["report_id"], value["observatory_address"], value["history_count"], value["observation_count"], value["issued_count"], value["withheld_count"], value["accepted_count"], value["held_count"], value["acceptance_ratio"], value["total_check_count"], value["total_failed_count"], value["latest_observation_ordinal"], value["latest_state"], value["latest_decision"], value["consecutive_withheld_count"], value["transition_count"], value["recovery_count"], value["stream_state"], tuple(RegistryFederationConsensusGateCertificateObservatoryAlert.from_mapping(item) for item in value["alerts"]), value["alert_count"], value["content_address"])


def address_report(value: RegistryFederationConsensusGateCertificateObservatoryReport) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryReport):
        raise ValidationError("certificate observatory report address requires a typed report")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REPORT_PREFIX)


def _alert(alert_id: str, kind: str, severity: str, count: int, message: str, evidence_addresses: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryAlert:
    provisional = RegistryFederationConsensusGateCertificateObservatoryAlert(alert_id, kind, severity, count, message, evidence_addresses, ALERT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryAlert(provisional.alert_id, provisional.kind, provisional.severity, provisional.count, provisional.message, provisional.evidence_addresses, address_alert(provisional))


def build_report(value: observatory_model.RegistryFederationConsensusGateCertificateObservatory, *, report_id: str = "consensus-certificate-observatory-report") -> RegistryFederationConsensusGateCertificateObservatoryReport:
    value = observatory_model.verify_observatory(value)
    observations = value.observations
    accepted_ratio = value.accepted_count / value.observation_count
    transitions = sum(left.state != right.state or left.decision != right.decision for left, right in zip(observations, observations[1:]))
    recoveries = sum(left.accepted is False and right.accepted is True for left, right in zip(observations, observations[1:]))
    consecutive = 0
    for item in reversed(observations):
        if item.state != "withheld":
            break
        consecutive += 1
    stream_state = "steady" if value.withheld_count == 0 or value.issued_count == 0 else "mixed"
    if consecutive:
        stream_state = "held"
    alerts: list[RegistryFederationConsensusGateCertificateObservatoryAlert] = []
    if value.withheld_count:
        alerts.append(_alert("withheld-decisions", "withheld-decision", "warning", value.withheld_count, "one or more certificate decisions were withheld", tuple(item.certificate_address for item in observations if item.state == "withheld")))
    if consecutive:
        alerts.append(_alert("latest-withheld", "latest-withheld", "critical", consecutive, "the latest certificate decisions remain withheld", tuple(item.certificate_address for item in observations[-consecutive:])))
    if value.total_failed_count:
        alerts.append(_alert("failed-checks", "failed-check", "warning", value.total_failed_count, "certificate checks failed across the observed stream", tuple(item.certificate_address for item in observations if item.failed_count)))
    if value.accepted_count == 0:
        alerts.append(_alert("no-accepted-decisions", "no-accepted-decision", "critical", value.observation_count, "no observed certificate decision was accepted", tuple(item.history_address for item in observations)))
    provisional = RegistryFederationConsensusGateCertificateObservatoryReport(report_id, value.content_address, value.history_count, value.observation_count, value.issued_count, value.withheld_count, value.accepted_count, value.held_count, accepted_ratio, value.total_check_count, value.total_failed_count, observations[-1].ordinal, observations[-1].state, observations[-1].decision, consecutive, transitions, recoveries, stream_state, tuple(alerts), len(alerts), REPORT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryReport(provisional.report_id, provisional.observatory_address, provisional.history_count, provisional.observation_count, provisional.issued_count, provisional.withheld_count, provisional.accepted_count, provisional.held_count, provisional.acceptance_ratio, provisional.total_check_count, provisional.total_failed_count, provisional.latest_observation_ordinal, provisional.latest_state, provisional.latest_decision, provisional.consecutive_withheld_count, provisional.transition_count, provisional.recovery_count, provisional.stream_state, provisional.alerts, provisional.alert_count, address_report(provisional))


def report_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryReport:
    return verify_report(RegistryFederationConsensusGateCertificateObservatoryReport.from_mapping(value))


def verify_report(value: RegistryFederationConsensusGateCertificateObservatoryReport) -> RegistryFederationConsensusGateCertificateObservatoryReport:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryReport) or (not value.content_address.endswith(":pending") and address_report(value) != value.content_address):
        raise ValidationError("certificate observatory report is not valid")
    return value


def report_json(value: RegistryFederationConsensusGateCertificateObservatoryReport) -> str:
    return canonical_json(verify_report(value).to_dict())


def report_csv(value: RegistryFederationConsensusGateCertificateObservatoryReport) -> str:
    value = verify_report(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryAlert.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.alerts:
        row = item.to_dict()
        row["evidence_addresses"] = "|".join(item.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_report_markdown(value: RegistryFederationConsensusGateCertificateObservatoryReport) -> str:
    value = verify_report(value)
    lines = ["# Consensus Release Certificate Observatory Report", "", f"- Report: `{value.report_id}`", f"- Stream: `{value.stream_state}`", f"- Observations: `{value.observation_count}`", f"- Acceptance ratio: `{value.acceptance_ratio:.6f}`", f"- Latest: `{value.latest_state}/{value.latest_decision}`", f"- Transitions: `{value.transition_count}`", f"- Recoveries: `{value.recovery_count}`", f"- Alerts: `{value.alert_count}`", f"- Address: `{value.content_address}`", "", "| alert | severity | count | message |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{item.kind}` | `{item.severity}` | `{item.count}` | {item.message} |" for item in value.alerts)
    return "\n".join(lines) + "\n"


def alert_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryAlert.FIELDS), "properties": {"alert_id": {"type": "string"}, "kind": {"type": "string"}, "severity": {"type": "string"}, "count": {"type": "integer"}, "message": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + ALERT_PREFIX + ":"}}}


def report_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryReport.FIELDS), "properties": {"report_id": {"type": "string"}, "observatory_address": {"type": "string", "pattern": "^" + observatory_model.OBSERVATORY_PREFIX + ":"}, "history_count": {"type": "integer"}, "observation_count": {"type": "integer"}, "issued_count": {"type": "integer"}, "withheld_count": {"type": "integer"}, "accepted_count": {"type": "integer"}, "held_count": {"type": "integer"}, "acceptance_ratio": {"type": "number"}, "total_check_count": {"type": "integer"}, "total_failed_count": {"type": "integer"}, "latest_observation_ordinal": {"type": "integer"}, "latest_state": {"type": "string"}, "latest_decision": {"type": "string"}, "consecutive_withheld_count": {"type": "integer"}, "transition_count": {"type": "integer"}, "recovery_count": {"type": "integer"}, "stream_state": {"type": "string"}, "alerts": {"type": "array", "items": alert_schema()}, "alert_count": {"type": "integer"}, "content_address": {"type": "string", "pattern": "^" + REPORT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "report_prefix": REPORT_PREFIX, "alert_prefix": ALERT_PREFIX, "stream_states": STREAM_STATES, "alert_severities": ALERT_SEVERITIES, "features": ("acceptance ratio reporting", "latest disposition tracking", "withheld streak detection", "transition and recovery counting", "evidence-linked operational alerts", "JSON CSV and Markdown exports"), "limits": {"max_alerts": MAX_ALERTS}, "schemas": ("alert", "report")}


__all__ = ["ALERT_PREFIX", "ALERT_SEVERITIES", "BOUNDARY", "MAX_ALERTS", "REPORT_PREFIX", "STREAM_STATES", "RegistryFederationConsensusGateCertificateObservatoryAlert", "RegistryFederationConsensusGateCertificateObservatoryReport", "VERSION", "address_alert", "address_report", "alert_schema", "build_report", "capabilities", "render_report_markdown", "report_csv", "report_from_mapping", "report_json", "report_schema", "verify_report"]
