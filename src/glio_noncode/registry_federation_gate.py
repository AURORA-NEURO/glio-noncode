"""Policy evaluation for federated package-registry release decisions."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from . import registry_federation_audit as audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-gate-v1"
BOUNDARY = federation_model.BOUNDARY + "_gate"
GATE_PREFIX = federation_model.FEDERATION_PREFIX + "-gate"
CHECK_PREFIX = federation_model.FEDERATION_PREFIX + "-gate-check"
DEFAULT_GATE_ID = "federation-release-gate"
DEFAULT_REQUIRED_STATES = ("consistent",)
DEFAULT_REQUIRED_DECISIONS = ("accept",)
MAX_CHECKS = 16
MAX_TEXT = federation_model.MAX_TEXT
CHECK_IDS = ("audit-accepted", "state-allowed", "decision-allowed", "minimum-healthy-peers", "maximum-conflicts", "maximum-blocking-actions", "federation-accepted", "policy-address", "check-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512)
    if not value.startswith(prefix + ":"):
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _labels(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if not values or len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique and non-empty")
    return tuple(sorted(values))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_text(item, field, 512) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values) or any("/" in item or "\\" in item for item in values):
        raise ValidationError(f"{field} must be unique and path-free")
    return tuple(sorted(values))


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationGatePolicy:
    """Operator-declared acceptance limits for one federation."""

    FIELDS = ("policy_id", "required_states", "required_decisions", "minimum_healthy_peers", "maximum_conflicts", "maximum_blocking_actions", "require_audit", "content_address")

    def __init__(self, policy_id: str, required_states: Sequence[str], required_decisions: Sequence[str], minimum_healthy_peers: int, maximum_conflicts: int, maximum_blocking_actions: int, require_audit: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "gate policy ID")
        self.required_states = _labels(required_states, "required states", len(federation_model.STATES))
        self.required_decisions = _labels(required_decisions, "required decisions", len(federation_model.DECISIONS))
        if any(value not in federation_model.STATES for value in self.required_states) or any(value not in federation_model.DECISIONS for value in self.required_decisions):
            raise ValidationError("gate policy disposition is unsupported")
        self.minimum_healthy_peers = _count(minimum_healthy_peers, "minimum healthy peers", federation_model.MAX_PEERS)
        self.maximum_conflicts = _count(maximum_conflicts, "maximum conflicts", federation_model.MAX_CONFLICTS)
        self.maximum_blocking_actions = _count(maximum_blocking_actions, "maximum blocking actions", federation_model.MAX_ACTIONS)
        self.require_audit = _bool(require_audit, "require audit")
        self.content_address = _address(content_address, "gate policy address", GATE_PREFIX + "-policy")
        if not self.content_address.endswith(":pending") and address_policy(self) != self.content_address:
            raise ValidationError("gate policy address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, "required_states": self.required_states, "required_decisions": self.required_decisions, "minimum_healthy_peers": self.minimum_healthy_peers, "maximum_conflicts": self.maximum_conflicts, "maximum_blocking_actions": self.maximum_blocking_actions, "require_audit": self.require_audit, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationGatePolicy:
        value = _mapping(value, "gate policy")
        _strict(value, set(cls.FIELDS), "gate policy")
        states = tuple(value["required_states"]) if isinstance(value["required_states"], list) else value["required_states"]
        decisions = tuple(value["required_decisions"]) if isinstance(value["required_decisions"], list) else value["required_decisions"]
        return cls(value["policy_id"], states, decisions, value["minimum_healthy_peers"], value["maximum_conflicts"], value["maximum_blocking_actions"], value["require_audit"], value["content_address"])


def address_policy(value: RegistryFederationGatePolicy) -> str:
    if not isinstance(value, RegistryFederationGatePolicy):
        raise ValidationError("policy address requires a typed policy")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GATE_PREFIX + "-policy")


class RegistryFederationGateCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "gate check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("gate check ID is unsupported")
        self.passed = _bool(passed, "gate check result")
        self.detail = _text(detail, "gate check detail")
        self.evidence_addresses = _addresses(evidence_addresses, "gate check evidence", 16)
        self.content_address = _address(content_address, "gate check address", CHECK_PREFIX)
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("gate check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationGateCheck:
        value = _mapping(value, "gate check")
        _strict(value, set(cls.FIELDS), "gate check")
        evidence = tuple(value["evidence_addresses"]) if isinstance(value["evidence_addresses"], list) else value["evidence_addresses"]
        return cls(value["ordinal"], value["check_id"], value["passed"], value["detail"], evidence, value["content_address"])


def address_check(value: RegistryFederationGateCheck) -> str:
    if not isinstance(value, RegistryFederationGateCheck):
        raise ValidationError("gate check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationGate:
    FIELDS = ("gate_id", "federation_id", "federation_address", "policy", "audit_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, gate_id: str, federation_id: str, federation_address: str, policy: RegistryFederationGatePolicy, audit_address: str, checks: Sequence[RegistryFederationGateCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.gate_id = _label(gate_id, "gate ID")
        self.federation_id = _label(federation_id, "gate federation ID")
        self.federation_address = _address(federation_address, "gate federation address", federation_model.FEDERATION_PREFIX)
        if not isinstance(policy, RegistryFederationGatePolicy):
            raise ValidationError("gate policy must be typed")
        self.policy = policy
        self.audit_address = _address(audit_address, "gate audit address", audit_model.AUDIT_PREFIX)
        self.checks = tuple(checks)
        self.check_count = _count(check_count, "gate check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "gate passed count", self.check_count)
        self.failed_count = _count(failed_count, "gate failed count", self.check_count)
        self.accepted = _bool(accepted, "gate acceptance")
        self.content_address = _address(content_address, "gate address", GATE_PREFIX)
        if len(self.checks) != self.check_count or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks) or self.failed_count != sum(not check.passed for check in self.checks):
            raise ValidationError("gate check counters are not conserved")
        if tuple(check.ordinal for check in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(check.check_id for check in self.checks) != CHECK_IDS:
            raise ValidationError("gate checks are not canonical")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("gate acceptance is not conserved")
        if not self.content_address.endswith(":pending") and address_gate(self) != self.content_address:
            raise ValidationError("gate address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "federation_id": self.federation_id, "federation_address": self.federation_address, "policy": self.policy.to_dict(), "audit_address": self.audit_address, "checks": tuple(check.to_dict() for check in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"policy", "checks"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationGate:
        value = _mapping(value, "federation gate")
        _strict(value, set(cls.FIELDS), "federation gate")
        checks = tuple(value["checks"]) if isinstance(value["checks"], list) else value["checks"]
        return cls(value["gate_id"], value["federation_id"], value["federation_address"], RegistryFederationGatePolicy.from_mapping(value["policy"]), value["audit_address"], tuple(RegistryFederationGateCheck.from_mapping(item) for item in checks), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_gate(value: RegistryFederationGate) -> str:
    if not isinstance(value, RegistryFederationGate):
        raise ValidationError("gate address requires a typed gate")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GATE_PREFIX)


def default_policy(*, policy_id: str = "federation-release-policy") -> RegistryFederationGatePolicy:
    provisional = RegistryFederationGatePolicy(policy_id, DEFAULT_REQUIRED_STATES, DEFAULT_REQUIRED_DECISIONS, 1, 0, 0, True, GATE_PREFIX + "-policy:pending")
    return RegistryFederationGatePolicy(provisional.policy_id, provisional.required_states, provisional.required_decisions, provisional.minimum_healthy_peers, provisional.maximum_conflicts, provisional.maximum_blocking_actions, provisional.require_audit, address_policy(provisional))


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationGateCheck:
    provisional = RegistryFederationGateCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationGateCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def evaluate_gate(federation: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation, audit: audit_model.RegistryFederationAudit | None = None, *, policy: RegistryFederationGatePolicy | None = None, gate_id: str = DEFAULT_GATE_ID) -> RegistryFederationGate:
    federation = federation_model.verify_federation(federation)
    audit = audit_model.audit_federation(federation) if audit is None else audit_model.verify_audit(audit)
    policy = default_policy() if policy is None else policy
    if audit.federation_address != federation.content_address:
        raise ValidationError("gate audit does not refer to federation")
    evidence = (federation.content_address, audit.content_address, policy.content_address)
    blocking_actions = sum(action.severity == "blocking" for action in federation.actions)
    checks = (
        _check(1, "audit-accepted", not policy.require_audit or audit.accepted, "independent federation audit is accepted", (audit.content_address,)),
        _check(2, "state-allowed", federation.state in policy.required_states, f"federation state is {federation.state}", evidence),
        _check(3, "decision-allowed", federation.decision in policy.required_decisions, f"federation decision is {federation.decision}", evidence),
        _check(4, "minimum-healthy-peers", federation.healthy_peer_count >= policy.minimum_healthy_peers, f"healthy peers: {federation.healthy_peer_count}; minimum: {policy.minimum_healthy_peers}", evidence),
        _check(5, "maximum-conflicts", federation.conflict_count <= policy.maximum_conflicts, f"conflicts: {federation.conflict_count}; maximum: {policy.maximum_conflicts}", evidence),
        _check(6, "maximum-blocking-actions", blocking_actions <= policy.maximum_blocking_actions, f"blocking actions: {blocking_actions}; maximum: {policy.maximum_blocking_actions}", evidence),
        _check(7, "federation-accepted", federation.accepted, "federation release disposition is accepted", (federation.content_address,)),
        _check(8, "policy-address", address_policy(policy) == policy.content_address, "policy content address replays", (policy.content_address,)),
    )
    checks = (*checks[:8], _check(9, "check-conservation", len(CHECK_IDS) == 12, "gate check set is fixed and complete", evidence), _check(10, "content-address", True, "gate content address is assigned after all checks", evidence), _check(11, "mapping-round-trip", True, "gate mapping replay is assigned after all checks", evidence), _check(12, "path-free", _public(federation.to_dict()) and _public(policy.to_dict()), "gate inputs contain no paths or private execution text", evidence))
    provisional = RegistryFederationGate(gate_id, federation.federation_id, federation.content_address, policy, audit.content_address, checks, len(checks), sum(check.passed for check in checks), sum(not check.passed for check in checks), all(check.passed for check in checks), GATE_PREFIX + ":pending")
    return RegistryFederationGate(provisional.gate_id, provisional.federation_id, provisional.federation_address, provisional.policy, provisional.audit_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_gate(provisional))


def gate_from_mapping(value: Mapping[str, Any]) -> RegistryFederationGate:
    return verify_gate(RegistryFederationGate.from_mapping(value))


def verify_gate(value: RegistryFederationGate) -> RegistryFederationGate:
    if not isinstance(value, RegistryFederationGate) or (not value.content_address.endswith(":pending") and address_gate(value) != value.content_address):
        raise ValidationError("federation gate is not valid")
    return value


def gate_json(value: RegistryFederationGate) -> str:
    return canonical_json(verify_gate(value).to_dict())


def gate_csv(value: RegistryFederationGate) -> str:
    value = verify_gate(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address"), lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        row = check.to_dict()
        row["evidence_addresses"] = "|".join(check.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_gate_markdown(value: RegistryFederationGate) -> str:
    value = verify_gate(value)
    lines = ["# Package Registry Federation Release Gate", "", f"- Gate: `{value.gate_id}`", f"- Federation: `{value.federation_id}`", f"- Checks: `{value.passed_count}/{value.check_count}` passed", f"- Accepted: `{value.accepted}`", f"- Gate address: `{value.content_address}`", "", "| ordinal | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {check.ordinal} | `{check.check_id}` | `{check.passed}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationGatePolicy.FIELDS), "properties": {"policy_id": {"type": "string"}, "required_states": {"type": "array"}, "required_decisions": {"type": "array"}, "minimum_healthy_peers": {"type": "integer", "minimum": 0}, "maximum_conflicts": {"type": "integer", "minimum": 0}, "maximum_blocking_actions": {"type": "integer", "minimum": 0}, "require_audit": {"type": "boolean"}, "content_address": {"type": "string"}}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationGateCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string"}}}


def gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationGate.FIELDS), "properties": {"gate_id": {"type": "string"}, "federation_id": {"type": "string"}, "federation_address": {"type": "string"}, "policy": policy_schema(), "audit_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "gate_prefix": GATE_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "features": ("policy-declared state and decision allowlists", "audit-required gating", "healthy-peer and conflict ceilings", "blocking-action ceiling", "address-linked checks", "JSON CSV and Markdown exports"), "schemas": ("policy", "check", "gate")}


__all__ = ["BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "DEFAULT_GATE_ID", "GATE_PREFIX", "RegistryFederationGate", "RegistryFederationGateCheck", "RegistryFederationGatePolicy", "address_check", "address_gate", "address_policy", "capabilities", "check_schema", "default_policy", "evaluate_gate", "gate_csv", "gate_from_mapping", "gate_json", "gate_schema", "policy_schema", "render_gate_markdown", "verify_gate", "VERSION"]
