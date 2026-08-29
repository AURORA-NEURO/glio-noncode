"""Release-ready operator packet for catalog-promotion decisions.

This boundary packages a promotion gate and its independent gate audit into a
single, path-free disposition.  It preserves every failed assertion as an
explicit action, including the evidence address needed to inspect that
assertion.  A clean gate becomes ``promote``; budget failures become ``hold``;
and blocking or audit failures become ``block``.  The packet is a compact
handoff for release automation and human review, not a second source of
truth: all counters and decisions are derived from the addressed inputs.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate as gate_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit as audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = audit_model.VERSION + "-release-packet-v1"
BOUNDARY = audit_model.BOUNDARY + "_release_packet"
PACKET_PREFIX = gate_model.GATE_PREFIX + "-release-packet"
ACTION_PREFIX = PACKET_PREFIX + "-action"
DEFAULT_PACKET_ID = "glio-noncode-observability-bundle-catalog-promotion-release-packet"
STATES = ("ready", "held", "blocked")
DECISIONS = ("promote", "hold", "block")
SOURCES = ("gate", "audit")
MAX_ACTIONS = gate_model.MAX_CHECKS + audit_model.MAX_CHECKS
MAX_TEXT = 2048


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 128)
    if any(char.isspace() for char in value) or ":" in value:
        raise ValidationError(f"{field} must be a compact public label")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} has an invalid public namespace")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return gate_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction:
    """One failed gate or gate-audit assertion converted to an action."""

    FIELDS = ("ordinal", "source", "check_id", "severity", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, source: str, check_id: str, severity: str, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observability bundle catalog promotion release action ordinal", MAX_ACTIONS)
        if self.ordinal == 0:
            raise ValidationError("observability bundle catalog promotion release action ordinal must be positive")
        self.source = _text(source, "observability bundle catalog promotion release action source", 32)
        self.check_id = _text(check_id, "observability bundle catalog promotion release action check ID", 128)
        self.severity = _text(severity, "observability bundle catalog promotion release action severity", 32)
        if self.source not in SOURCES or self.severity not in gate_model.SEVERITIES:
            raise ValidationError("observability bundle catalog promotion release action source or severity is unsupported")
        self.detail = _text(detail, "observability bundle catalog promotion release action detail", MAX_TEXT)
        self.evidence_address = _address(evidence_address, "observability bundle catalog promotion release action evidence address")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion release action content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion release action content address", ACTION_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_action(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion release action address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "source": self.source, "check_id": self.check_id, "severity": self.severity, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction:
        value = _mapping(value, "observability bundle catalog promotion release action")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion release action")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion release action is missing fields: {missing}")
        return cls(*(value[field] for field in cls.FIELDS))


def address_action(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction):
        raise ValidationError("observability bundle catalog promotion release action address requires a typed action")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ACTION_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket:
    """A deterministic promote, hold, or block release disposition."""

    FIELDS = ("packet_id", "gate_address", "gate_audit_address", "diff_address", "report_address", "state", "decision", "accepted", "release_ready", "check_count", "passed_count", "failed_count", "blocking_failure_count", "hold_failure_count", "failed_check_ids", "action_count", "actions", "content_address")

    def __init__(self, packet_id: str, gate_address: str, gate_audit_address: str, diff_address: str, report_address: str, state: str, decision: str, accepted: bool, release_ready: bool, check_count: int, passed_count: int, failed_count: int, blocking_failure_count: int, hold_failure_count: int, failed_check_ids: Sequence[str], actions: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction], content_address: str) -> None:
        self.packet_id = _label(packet_id, "observability bundle catalog promotion release packet ID")
        self.gate_address = _address(gate_address, "observability bundle catalog promotion release gate address", gate_model.GATE_PREFIX)
        self.gate_audit_address = _address(gate_audit_address, "observability bundle catalog promotion release gate audit address", audit_model.AUDIT_PREFIX)
        self.diff_address = _address(diff_address, "observability bundle catalog promotion release diff address", gate_model.diff_model.DIFF_PREFIX)
        self.report_address = _address(report_address, "observability bundle catalog promotion release report address", gate_model.report_model.REPORT_PREFIX)
        self.state = _text(state, "observability bundle catalog promotion release state", 32)
        self.decision = _text(decision, "observability bundle catalog promotion release decision", 32)
        self.accepted = _bool(accepted, "observability bundle catalog promotion release accepted")
        self.release_ready = _bool(release_ready, "observability bundle catalog promotion release ready")
        self.check_count = _count(check_count, "observability bundle catalog promotion release check count", MAX_ACTIONS)
        self.passed_count = _count(passed_count, "observability bundle catalog promotion release passed count", MAX_ACTIONS)
        self.failed_count = _count(failed_count, "observability bundle catalog promotion release failed count", MAX_ACTIONS)
        self.blocking_failure_count = _count(blocking_failure_count, "observability bundle catalog promotion release blocking failure count", MAX_ACTIONS)
        self.hold_failure_count = _count(hold_failure_count, "observability bundle catalog promotion release hold failure count", MAX_ACTIONS)
        self.failed_check_ids = tuple(_text(item, "observability bundle catalog promotion release failed check ID", 128) for item in _sequence(failed_check_ids, "observability bundle catalog promotion release failed check IDs", MAX_ACTIONS))
        self.actions = tuple(actions)
        self.action_count = len(self.actions)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.state not in STATES or self.decision not in DECISIONS:
            raise ValidationError("observability bundle catalog promotion release state or decision is invalid")
        if self.check_count != gate_model.MAX_CHECKS + audit_model.MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.blocking_failure_count + self.hold_failure_count > self.failed_count:
            raise ValidationError("observability bundle catalog promotion release counts are not conserved")
        if self.action_count != self.failed_count or self.action_count > MAX_ACTIONS or tuple(action.ordinal for action in self.actions) != tuple(range(1, self.action_count + 1)) or any(not isinstance(action, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction) for action in self.actions):
            raise ValidationError("observability bundle catalog promotion release actions are not canonical")
        if tuple(self.failed_check_ids) != tuple(action.check_id for action in self.actions):
            raise ValidationError("observability bundle catalog promotion release failed check IDs do not match actions")
        expected_state = "blocked" if self.blocking_failure_count else "held" if self.hold_failure_count else "ready"
        if self.state != expected_state or self.decision != {"ready": "promote", "held": "hold", "blocked": "block"}[self.state] or self.accepted != (self.state != "blocked") or self.release_ready != (self.state == "ready"):
            raise ValidationError("observability bundle catalog promotion release decision is not derived")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion release packet content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion release packet content address", PACKET_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_packet(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion release packet address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "actions" else tuple(action.to_dict() for action in self.actions) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in self.FIELDS if key != "actions"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket:
        value = _mapping(value, "observability bundle catalog promotion release packet")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion release packet")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion release packet is missing fields: {missing}")
        actions = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction.from_mapping(item) for item in _sequence(value["actions"], "observability bundle catalog promotion release actions", MAX_ACTIONS))
        return cls(value["packet_id"], value["gate_address"], value["gate_audit_address"], value["diff_address"], value["report_address"], value["state"], value["decision"], value["accepted"], value["release_ready"], value["check_count"], value["passed_count"], value["failed_count"], value["blocking_failure_count"], value["hold_failure_count"], value["failed_check_ids"], actions, value["content_address"])


def address_packet(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket):
        raise ValidationError("observability bundle catalog promotion release packet address requires a typed packet")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PACKET_PREFIX)


def _action_from_gate(ordinal: int, check: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction:
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction(ordinal, "gate", check.check_id, check.severity, check.detail, check.evidence_address, "pending:observability-bundle-catalog-promotion-release-action")


def _action_from_audit(ordinal: int, check: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction:
    severity = "blocking" if not check.passed else "hold"
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction(ordinal, "audit", check.check_id, severity, check.detail, check.evidence_address, "pending:observability-bundle-catalog-promotion-release-action")


def build_release_packet(gate: gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate, gate_audit: audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit, *, packet_id: str = DEFAULT_PACKET_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket:
    if not isinstance(gate, gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate) or not isinstance(gate_audit, audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit):
        raise ValidationError("observability bundle catalog promotion release packet requires typed gate and audit")
    gate_model.verify_gate(gate)
    audit_model.verify_audit(gate_audit)
    if gate_audit.gate_address != gate.content_address:
        raise ValidationError("observability bundle catalog promotion release audit must describe the gate")
    gate_failed = tuple(check for check in gate.checks if not check.passed)
    audit_failed = tuple(check for check in gate_audit.checks if not check.passed)
    actions = tuple(_action_from_gate(index, check) for index, check in enumerate(gate_failed, 1)) + tuple(_action_from_audit(len(gate_failed) + index, check) for index, check in enumerate(audit_failed, 1))
    blocking = gate.blocking_failure_count + len(audit_failed)
    holds = gate.hold_failure_count
    state = "blocked" if blocking else "held" if holds else "ready"
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket(_label(packet_id, "observability bundle catalog promotion release packet ID"), gate.content_address, gate_audit.content_address, gate.diff_address, gate.report_address, state, {"ready": "promote", "held": "hold", "blocked": "block"}[state], state != "blocked", state == "ready", gate.check_count + gate_audit.check_count, gate.passed_count + gate_audit.passed_count, gate.failed_count + gate_audit.failed_count, blocking, holds, tuple(action.check_id for action in actions), actions, "pending:observability-bundle-catalog-promotion-release-packet")
    addressed_actions = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction(action.ordinal, action.source, action.check_id, action.severity, action.detail, action.evidence_address, address_action(action)) for action in provisional.actions)
    final = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket(provisional.packet_id, provisional.gate_address, provisional.gate_audit_address, provisional.diff_address, provisional.report_address, provisional.state, provisional.decision, provisional.accepted, provisional.release_ready, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.blocking_failure_count, provisional.hold_failure_count, provisional.failed_check_ids, addressed_actions, "pending:observability-bundle-catalog-promotion-release-packet")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket(final.packet_id, final.gate_address, final.gate_audit_address, final.diff_address, final.report_address, final.state, final.decision, final.accepted, final.release_ready, final.check_count, final.passed_count, final.failed_count, final.blocking_failure_count, final.hold_failure_count, final.failed_check_ids, final.actions, address_packet(final))


def packet_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket:
    return verify_packet(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket.from_mapping(_mapping(value, "observability bundle catalog promotion release packet")))


def verify_packet(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket):
        raise ValidationError("observability bundle catalog promotion release packet verification requires a typed packet")
    value._validate()
    if address_packet(value) != value.content_address:
        raise ValidationError("observability bundle catalog promotion release packet content address does not replay")
    return value


def packet_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket) -> str:
    return canonical_json(verify_packet(value).to_dict())


def packet_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket) -> str:
    value = verify_packet(value)
    fields = ("ordinal", "source", "check_id", "severity", "detail", "evidence_address", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for action in value.actions:
        writer.writerow({field: action.to_dict()[field] for field in fields})
    return output.getvalue()


def render_packet_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket) -> str:
    value = verify_packet(value)
    lines = ["# Assurance History Observatory Catalog Promotion Release Packet", "", f"- Decision: `{value.decision}`", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Checks: `{value.passed_count}/{value.check_count}` passed", f"- Blocking failures: `{value.blocking_failure_count}`", f"- Hold failures: `{value.hold_failure_count}`", f"- Actions: `{value.action_count}`", f"- Content address: `{value.content_address}`", "", "| ordinal | source | check | severity | detail | evidence |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {action.ordinal} | {action.source} | `{action.check_id}` | `{action.severity}` | {action.detail} | `{action.evidence_address}` |" for action in value.actions)
    if not value.actions:
        lines.append("| — | — | No action required | — | The gate and independent audit are complete. | — |")
    return "\n".join(lines) + "\n"


def action_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_ACTIONS}, "source": {"type": "string", "enum": list(SOURCES)}, "check_id": {"type": "string", "maxLength": 128}, "severity": {"type": "string", "enum": list(gate_model.SEVERITIES)}, "detail": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + ACTION_PREFIX + ":"}}}


def packet_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {"packet_id": {"type": "string", "maxLength": 128}, "gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "gate_audit_address": {"type": "string", "pattern": "^" + audit_model.AUDIT_PREFIX + ":"}, "diff_address": {"type": "string", "pattern": "^" + gate_model.diff_model.DIFF_PREFIX + ":"}, "report_address": {"type": "string", "pattern": "^" + gate_model.report_model.REPORT_PREFIX + ":"}, "state": {"type": "string", "enum": list(STATES)}, "decision": {"type": "string", "enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "failed_check_ids": {"type": "array", "maxItems": MAX_ACTIONS, "items": {"type": "string"}}, "actions": {"type": "array", "maxItems": MAX_ACTIONS, "items": action_schema()}, "content_address": {"type": "string", "pattern": "^" + PACKET_PREFIX + ":"}}
    properties.update({field: {"type": "integer", "minimum": 0, "maximum": MAX_ACTIONS} for field in ("check_count", "passed_count", "failed_count", "blocking_failure_count", "hold_failure_count", "action_count")})
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket.FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "packet_prefix": PACKET_PREFIX, "action_prefix": ACTION_PREFIX, "states": STATES, "decisions": DECISIONS, "sources": SOURCES, "limits": {"max_actions": MAX_ACTIONS}, "features": ("gate and independent-audit composition", "promote hold and block disposition", "failure-to-action projection", "gate and audit evidence addresses", "action-level content addressing", "path-free release handoff", "JSON CSV and Markdown exports"), "schemas": ("action", "packet")}


__all__ = [
    "ACTION_PREFIX", "BOUNDARY", "DECISIONS", "DEFAULT_PACKET_ID", "MAX_ACTIONS", "PACKET_PREFIX", "SOURCES", "STATES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket",
    "action_schema", "address_action", "address_packet", "build_release_packet", "capabilities", "packet_csv", "packet_from_mapping", "packet_json", "packet_schema", "render_packet_markdown", "verify_packet",
]
