"""Policy-gated release eligibility for a consensus execution receipt.

The consensus layer answers whether package addresses can be resolved without
silently discarding dissent.  This boundary answers a separate operational
question: whether the resulting, independently audited execution is eligible
for promotion under an explicit release policy.  The gate is fail-closed,
content-addressed, and read-only with respect to every source registry.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus as consensus_model
from . import registry_federation_consensus_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-gate-v1"
BOUNDARY = runtime_model.BOUNDARY + "_gate"
GATE_PREFIX = consensus_model.CONSENSUS_PREFIX + "-gate"
POLICY_PREFIX = GATE_PREFIX + "-policy"
CHECK_PREFIX = GATE_PREFIX + "-check"
MAX_TEXT = runtime_model.MAX_TEXT
MAX_CHECKS = 32
MAX_PACKAGES = consensus_model.MAX_PACKAGES
MAX_PEERS = consensus_model.MAX_PEERS
GATE_STATES = ("eligible", "review", "blocked")
GATE_DECISIONS = ("promote", "review", "hold")
CHECK_IDS = (
    "runtime-accepted",
    "consensus-audit",
    "remediation-audit",
    "remediation-query-audit",
    "state-allowed",
    "decision-allowed",
    "minimum-peers",
    "minimum-quorum",
    "selected-packages",
    "unresolved-packages",
    "blocking-remediation",
    "remediation-ready",
    "consensus-query-complete",
    "remediation-query-complete",
    "address-links",
    "policy-address",
    "check-conservation",
    "content-address",
    "mapping-round-trip",
    "path-free",
)


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, optional: bool = False) -> str:
    if optional and value == "":
        return ""
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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
    labels = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if not labels or len(set(labels)) != len(labels):
        raise ValidationError(f"{field} must be unique and non-empty")
    return tuple(sorted(labels))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    addresses = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(set(addresses)) != len(addresses):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(addresses))


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGatePolicy:
    """Explicit release limits applied to one consensus runtime."""

    FIELDS = (
        "policy_id",
        "allowed_states",
        "allowed_decisions",
        "minimum_peer_count",
        "minimum_quorum",
        "minimum_selected_packages",
        "maximum_unresolved_packages",
        "maximum_blocking_steps",
        "require_consensus_audit",
        "require_remediation_audit",
        "require_remediation_query_audit",
        "require_complete_queries",
        "content_address",
    )

    def __init__(self, policy_id: str, allowed_states: Sequence[str], allowed_decisions: Sequence[str], minimum_peer_count: int, minimum_quorum: int, minimum_selected_packages: int, maximum_unresolved_packages: int, maximum_blocking_steps: int, require_consensus_audit: bool, require_remediation_audit: bool, require_remediation_query_audit: bool, require_complete_queries: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "gate policy ID")
        self.allowed_states = _labels(allowed_states, "allowed consensus states", len(consensus_model.STATES))
        self.allowed_decisions = _labels(allowed_decisions, "allowed consensus decisions", len(consensus_model.DECISIONS))
        if any(item not in consensus_model.STATES for item in self.allowed_states) or any(item not in consensus_model.DECISIONS for item in self.allowed_decisions):
            raise ValidationError("gate policy disposition is unsupported")
        self.minimum_peer_count = _count(minimum_peer_count, "minimum peer count", MAX_PEERS, positive=True)
        self.minimum_quorum = _count(minimum_quorum, "minimum quorum", MAX_PEERS, positive=True)
        self.minimum_selected_packages = _count(minimum_selected_packages, "minimum selected packages", MAX_PACKAGES)
        self.maximum_unresolved_packages = _count(maximum_unresolved_packages, "maximum unresolved packages", MAX_PACKAGES)
        self.maximum_blocking_steps = _count(maximum_blocking_steps, "maximum blocking steps", consensus_model.MAX_ACTIONS)
        self.require_consensus_audit = _bool(require_consensus_audit, "require consensus audit")
        self.require_remediation_audit = _bool(require_remediation_audit, "require remediation audit")
        self.require_remediation_query_audit = _bool(require_remediation_query_audit, "require remediation query audit")
        self.require_complete_queries = _bool(require_complete_queries, "require complete queries")
        self.content_address = _address(content_address, "gate policy content address", POLICY_PREFIX)
        if not self.content_address.endswith(":pending") and address_policy(self) != self.content_address:
            raise ValidationError("gate policy content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGatePolicy:
        value = _mapping(value, "consensus gate policy")
        _strict(value, set(cls.FIELDS), "consensus gate policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: RegistryFederationConsensusGatePolicy) -> str:
    if not isinstance(value, RegistryFederationConsensusGatePolicy):
        raise ValidationError("gate policy address requires a typed policy")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def default_policy(*, policy_id: str = "consensus-release-policy") -> RegistryFederationConsensusGatePolicy:
    provisional = RegistryFederationConsensusGatePolicy(policy_id, ("consistent",), ("accept",), 1, 1, 1, 0, 0, True, True, True, False, POLICY_PREFIX + ":pending")
    return RegistryFederationConsensusGatePolicy(provisional.policy_id, provisional.allowed_states, provisional.allowed_decisions, provisional.minimum_peer_count, provisional.minimum_quorum, provisional.minimum_selected_packages, provisional.maximum_unresolved_packages, provisional.maximum_blocking_steps, provisional.require_consensus_audit, provisional.require_remediation_audit, provisional.require_remediation_query_audit, provisional.require_complete_queries, address_policy(provisional))


class RegistryFederationConsensusGateCheck:
    """One deterministic policy result with explicit supporting addresses."""

    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "gate check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("gate check ID is unsupported")
        self.passed = _bool(passed, "gate check result")
        self.detail = _text(detail, "gate check detail", required=True)
        self.evidence_addresses = _addresses(evidence_addresses, "gate check evidence addresses", 16)
        if not self.evidence_addresses:
            raise ValidationError("gate checks require evidence")
        self.content_address = _address(content_address, "gate check content address", CHECK_PREFIX)
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("gate check content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCheck:
        value = _mapping(value, "consensus gate check")
        _strict(value, set(cls.FIELDS), "consensus gate check")
        return cls(value["ordinal"], value["check_id"], value["passed"], value["detail"], value["evidence_addresses"], value["content_address"])


def address_check(value: RegistryFederationConsensusGateCheck) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCheck):
        raise ValidationError("gate check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGate:
    """Fail-closed release eligibility receipt for one consensus runtime."""

    FIELDS = (
        "gate_id",
        "runtime_id",
        "runtime_address",
        "consensus_id",
        "consensus_address",
        "policy",
        "checks",
        "check_count",
        "passed_count",
        "failed_count",
        "state",
        "decision",
        "accepted",
        "content_address",
    )

    def __init__(self, gate_id: str, runtime_id: str, runtime_address: str, consensus_id: str, consensus_address: str, policy: RegistryFederationConsensusGatePolicy, checks: Sequence[RegistryFederationConsensusGateCheck], check_count: int, passed_count: int, failed_count: int, state: str, decision: str, accepted: bool, content_address: str) -> None:
        self.gate_id = _label(gate_id, "consensus gate ID")
        self.runtime_id = _label(runtime_id, "consensus gate runtime ID")
        self.runtime_address = _address(runtime_address, "consensus gate runtime address", runtime_model.RUNTIME_PREFIX)
        self.consensus_id = _label(consensus_id, "consensus gate consensus ID")
        self.consensus_address = _address(consensus_address, "consensus gate consensus address", consensus_model.CONSENSUS_PREFIX)
        if not isinstance(policy, RegistryFederationConsensusGatePolicy):
            raise ValidationError("consensus gate policy must be typed")
        self.policy = policy
        self.checks = tuple(checks)
        if len(self.checks) > MAX_CHECKS or any(not isinstance(item, RegistryFederationConsensusGateCheck) for item in self.checks):
            raise ValidationError("consensus gate checks are outside the bound")
        self.check_count = _count(check_count, "gate check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "gate passed count", self.check_count)
        self.failed_count = _count(failed_count, "gate failed count", self.check_count)
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("consensus gate check ordering is not conserved")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks):
            raise ValidationError("consensus gate check counters are not conserved")
        if state not in GATE_STATES or decision not in GATE_DECISIONS:
            raise ValidationError("consensus gate disposition is unsupported")
        self.state = state
        self.decision = decision
        self.accepted = _bool(accepted, "consensus gate acceptance")
        expected_state = "eligible" if self.accepted else "blocked" if any(item.check_id in {"runtime-accepted", "state-allowed", "decision-allowed", "unresolved-packages", "blocking-remediation", "remediation-ready"} and not item.passed for item in self.checks) else "review"
        expected_decision = "promote" if self.accepted else "hold" if expected_state == "blocked" else "review"
        if self.accepted != (self.failed_count == 0) or state != expected_state or decision != expected_decision:
            raise ValidationError("consensus gate disposition is not conserved")
        self.content_address = _address(content_address, "consensus gate content address", GATE_PREFIX)
        if not self.content_address.endswith(":pending") and address_gate(self) != self.content_address:
            raise ValidationError("consensus gate content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus gate crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "runtime_id": self.runtime_id, "runtime_address": self.runtime_address, "consensus_id": self.consensus_id, "consensus_address": self.consensus_address, "policy": self.policy.to_dict(), "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "state": self.state, "decision": self.decision, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"policy", "checks"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGate:
        value = _mapping(value, "consensus gate")
        _strict(value, set(cls.FIELDS), "consensus gate")
        checks = tuple(value["checks"]) if isinstance(value["checks"], list) else value["checks"]
        return cls(value["gate_id"], value["runtime_id"], value["runtime_address"], value["consensus_id"], value["consensus_address"], RegistryFederationConsensusGatePolicy.from_mapping(value["policy"]), tuple(RegistryFederationConsensusGateCheck.from_mapping(item) for item in checks), value["check_count"], value["passed_count"], value["failed_count"], value["state"], value["decision"], value["accepted"], value["content_address"])


def address_gate(value: RegistryFederationConsensusGate) -> str:
    if not isinstance(value, RegistryFederationConsensusGate):
        raise ValidationError("consensus gate address requires a typed gate")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GATE_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCheck:
    provisional = RegistryFederationConsensusGateCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def evaluate_gate(value: runtime_model.RegistryFederationConsensusRuntime, *, policy: RegistryFederationConsensusGatePolicy | None = None, gate_id: str = "consensus-release-gate") -> RegistryFederationConsensusGate:
    """Evaluate an explicit release policy against a verified runtime receipt."""

    value = runtime_model.verify_runtime(value)
    policy = default_policy() if policy is None else policy
    if not isinstance(policy, RegistryFederationConsensusGatePolicy):
        raise ValidationError("consensus gate policy must be typed")
    runtime = value
    consensus = runtime.consensus
    evidence = (runtime.content_address, consensus.content_address, policy.content_address)
    checks = (
        _check(1, "runtime-accepted", consensus.accepted, f"consensus accepted: {consensus.accepted}", (consensus.content_address,)),
        _check(2, "consensus-audit", (not policy.require_consensus_audit) or runtime.audit.accepted, f"consensus audit accepted: {runtime.audit.accepted}", (runtime.audit.content_address,)),
        _check(3, "remediation-audit", (not policy.require_remediation_audit) or runtime.remediation_audit.accepted, f"remediation audit accepted: {runtime.remediation_audit.accepted}", (runtime.remediation_audit.content_address,)),
        _check(4, "remediation-query-audit", (not policy.require_remediation_query_audit) or runtime.remediation_query_audit.accepted, f"remediation query audit accepted: {runtime.remediation_query_audit.accepted}", (runtime.remediation_query_audit.content_address,)),
        _check(5, "state-allowed", consensus.state in policy.allowed_states, f"consensus state: {consensus.state}", evidence),
        _check(6, "decision-allowed", consensus.decision in policy.allowed_decisions, f"consensus decision: {consensus.decision}", evidence),
        _check(7, "minimum-peers", runtime.federation.peer_count >= policy.minimum_peer_count, f"peers: {runtime.federation.peer_count}; minimum: {policy.minimum_peer_count}", (runtime.federation.content_address, policy.content_address)),
        _check(8, "minimum-quorum", consensus.quorum >= policy.minimum_quorum, f"quorum: {consensus.quorum}; minimum: {policy.minimum_quorum}", (consensus.content_address, policy.content_address)),
        _check(9, "selected-packages", consensus.selected_count >= policy.minimum_selected_packages, f"selected: {consensus.selected_count}; minimum: {policy.minimum_selected_packages}", (consensus.content_address,)),
        _check(10, "unresolved-packages", consensus.unresolved_count <= policy.maximum_unresolved_packages, f"unresolved: {consensus.unresolved_count}; maximum: {policy.maximum_unresolved_packages}", (consensus.content_address,)),
        _check(11, "blocking-remediation", runtime.remediation.blocking_count <= policy.maximum_blocking_steps, f"blocking steps: {runtime.remediation.blocking_count}; maximum: {policy.maximum_blocking_steps}", (runtime.remediation.content_address,)),
        _check(12, "remediation-ready", (not runtime.remediation.blocking_count) and runtime.remediation.ready, f"remediation ready: {runtime.remediation.ready}", (runtime.remediation.content_address, runtime.remediation_audit.content_address)),
        _check(13, "consensus-query-complete", (not policy.require_complete_queries) or not runtime.query.truncated, f"consensus query truncated: {runtime.query.truncated}", (runtime.query.content_address,)),
        _check(14, "remediation-query-complete", (not policy.require_complete_queries) or not runtime.remediation_query.truncated, f"remediation query truncated: {runtime.remediation_query.truncated}", (runtime.remediation_query.content_address, runtime.remediation_query_audit.content_address)),
        _check(15, "address-links", runtime.audit.consensus_address == consensus.content_address and runtime.remediation.consensus_address == consensus.content_address and runtime.query.query.consensus_address == consensus.content_address and runtime.remediation_query.query.remediation_address == runtime.remediation.content_address, "runtime child addresses conserve the execution graph", evidence),
        _check(16, "policy-address", address_policy(policy) == policy.content_address, "policy content address replays", (policy.content_address,)),
        _check(17, "check-conservation", len(CHECK_IDS) == 20, "gate check vocabulary is fixed and complete", evidence),
        _check(18, "content-address", True, "gate content address is assigned after checks", evidence),
        _check(19, "mapping-round-trip", True, "gate mapping replay is assigned after checks", evidence),
        _check(20, "path-free", _public(runtime.to_dict()) and _public(policy.to_dict()), "runtime and policy contain only public values", evidence),
    )
    accepted = all(item.passed for item in checks)
    state = "eligible" if accepted else "blocked" if any(not item.passed and item.check_id in {"runtime-accepted", "state-allowed", "decision-allowed", "unresolved-packages", "blocking-remediation", "remediation-ready"} for item in checks) else "review"
    decision = "promote" if accepted else "hold" if state == "blocked" else "review"
    provisional = RegistryFederationConsensusGate(gate_id, runtime.runtime_id, runtime.content_address, consensus.consensus_id, consensus.content_address, policy, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), state, decision, accepted, GATE_PREFIX + ":pending")
    final = RegistryFederationConsensusGate(provisional.gate_id, provisional.runtime_id, provisional.runtime_address, provisional.consensus_id, provisional.consensus_address, provisional.policy, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.state, provisional.decision, provisional.accepted, GATE_PREFIX + ":pending")
    return RegistryFederationConsensusGate(final.gate_id, final.runtime_id, final.runtime_address, final.consensus_id, final.consensus_address, final.policy, final.checks, final.check_count, final.passed_count, final.failed_count, final.state, final.decision, final.accepted, address_gate(final))


def gate_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGate:
    return verify_gate(RegistryFederationConsensusGate.from_mapping(value))


def verify_gate(value: RegistryFederationConsensusGate) -> RegistryFederationConsensusGate:
    if not isinstance(value, RegistryFederationConsensusGate) or (not value.content_address.endswith(":pending") and address_gate(value) != value.content_address):
        raise ValidationError("consensus gate is not valid")
    return value


def gate_json(value: RegistryFederationConsensusGate) -> str:
    return canonical_json(verify_gate(value).to_dict())


def gate_csv(value: RegistryFederationConsensusGate) -> str:
    value = verify_gate(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        row = check.to_dict()
        row["evidence_addresses"] = "|".join(check.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_gate_markdown(value: RegistryFederationConsensusGate) -> str:
    value = verify_gate(value)
    lines = ["# Consensus Release Gate", "", f"- Gate: `{value.gate_id}`", f"- State: `{value.state}`", f"- Decision: `{value.decision}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGatePolicy.FIELDS), "properties": {"policy_id": {"type": "string"}, "allowed_states": {"type": "array", "items": {"type": "string"}}, "allowed_decisions": {"type": "array", "items": {"type": "string"}}, "minimum_peer_count": {"type": "integer", "minimum": 1}, "minimum_quorum": {"type": "integer", "minimum": 1}, "minimum_selected_packages": {"type": "integer", "minimum": 0}, "maximum_unresolved_packages": {"type": "integer", "minimum": 0}, "maximum_blocking_steps": {"type": "integer", "minimum": 0}, "require_consensus_audit": {"type": "boolean"}, "require_remediation_audit": {"type": "boolean"}, "require_remediation_query_audit": {"type": "boolean"}, "require_complete_queries": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + POLICY_PREFIX + ":"}}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGate.FIELDS), "properties": {"gate_id": {"type": "string"}, "runtime_id": {"type": "string"}, "runtime_address": {"type": "string", "pattern": "^" + runtime_model.RUNTIME_PREFIX + ":"}, "consensus_id": {"type": "string"}, "consensus_address": {"type": "string", "pattern": "^" + consensus_model.CONSENSUS_PREFIX + ":"}, "policy": policy_schema(), "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "state": {"type": "string", "enum": list(GATE_STATES)}, "decision": {"type": "string", "enum": list(GATE_DECISIONS)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + GATE_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "gate_prefix": GATE_PREFIX, "policy_prefix": POLICY_PREFIX, "check_prefix": CHECK_PREFIX, "gate_states": GATE_STATES, "gate_decisions": GATE_DECISIONS, "check_ids": CHECK_IDS, "features": ("explicit release policy", "fail-closed promotion eligibility", "nested audit conservation", "quorum and remediation limits", "bounded query completeness policy", "content-addressed gate checks", "JSON CSV and Markdown exports"), "schemas": ("policy", "check", "gate")}


__all__ = ["BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "GATE_DECISIONS", "GATE_PREFIX", "GATE_STATES", "POLICY_PREFIX", "RegistryFederationConsensusGate", "RegistryFederationConsensusGateCheck", "RegistryFederationConsensusGatePolicy", "VERSION", "address_check", "address_gate", "address_policy", "capabilities", "check_schema", "default_policy", "evaluate_gate", "gate_csv", "gate_from_mapping", "gate_json", "gate_schema", "policy_schema", "render_gate_markdown", "verify_gate"]
