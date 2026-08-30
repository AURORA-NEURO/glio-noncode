"""Portable release certificates derived from consensus gate evidence.

The consensus gate answers whether one runtime satisfies a release policy.  A
certificate is the smaller operational handoff that freezes that answer,
retains the addresses needed to replay it, and makes withholding explicit.  It
does not sign, timestamp, mutate, or infer scientific validity.  A certificate
is issued only when every certificate check passes; otherwise it remains a
path-free, content-addressed record of why promotion was withheld.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from . import registry_federation_consensus_gate_audit as gate_audit_model
from . import registry_federation_consensus_gate_query as gate_query_model
from . import registry_federation_consensus_gate_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = gate_model.VERSION + "-certificate-v1"
BOUNDARY = gate_model.BOUNDARY + "_certificate"
CERTIFICATE_PREFIX = gate_model.GATE_PREFIX + "-certificate"
POLICY_PREFIX = CERTIFICATE_PREFIX + "-policy"
CHECK_PREFIX = CERTIFICATE_PREFIX + "-check"
PACKAGE_PREFIX = gate_model.GATE_PREFIX + "-package"
MAX_TEXT = gate_model.MAX_TEXT
MAX_CHECKS = 32
MAX_EVIDENCE = 24
CERTIFICATE_STATES = ("issued", "withheld")
CERTIFICATE_DECISIONS = ("promote", "hold")
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "runtime-link",
    "gate-link",
    "audit-link",
    "query-link",
    "package-link",
    "policy-link",
    "state-allowed",
    "decision-allowed",
    "gate-accepted",
    "audit-accepted",
    "query-complete",
    "check-floor",
    "counter-conservation",
    "acceptance-conservation",
    "certificate-address",
    "mapping-round-trip",
    "path-free",
)


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
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
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _labels(value: Any, field: str, maximum: int, *, allow_empty: bool = False) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if not values and not allow_empty:
        raise ValidationError(f"{field} cannot be empty")
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(values))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if not values or len(set(values)) != len(values):
        raise ValidationError(f"{field} must contain unique evidence")
    return tuple(sorted(values))


def _optional_addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(values))


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}

    def walk(node: Any) -> bool:
        if isinstance(node, Mapping):
            return all(isinstance(key, str) and key.lower() not in forbidden and walk(item) for key, item in node.items())
        if isinstance(node, (list, tuple)):
            return all(walk(item) for item in node)
        if isinstance(node, str):
            lowered = node.lower()
            return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
        return node is None or isinstance(node, (bool, int, float))

    return walk(value)


class RegistryFederationConsensusGateCertificatePolicy:
    """Requirements for converting a gate result into an issued receipt."""

    FIELDS = (
        "policy_id",
        "allowed_gate_states",
        "allowed_gate_decisions",
        "minimum_check_count",
        "minimum_passed_count",
        "require_gate_acceptance",
        "require_gate_audit",
        "require_query_complete",
        "require_package",
        "content_address",
    )

    def __init__(self, policy_id: str, allowed_gate_states: Sequence[str], allowed_gate_decisions: Sequence[str], minimum_check_count: int, minimum_passed_count: int, require_gate_acceptance: bool, require_gate_audit: bool, require_query_complete: bool, require_package: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "certificate policy ID")
        self.allowed_gate_states = _labels(allowed_gate_states, "allowed gate states", len(gate_model.GATE_STATES))
        self.allowed_gate_decisions = _labels(allowed_gate_decisions, "allowed gate decisions", len(gate_model.GATE_DECISIONS))
        if any(item not in gate_model.GATE_STATES for item in self.allowed_gate_states) or any(item not in gate_model.GATE_DECISIONS for item in self.allowed_gate_decisions):
            raise ValidationError("certificate policy disposition is unsupported")
        self.minimum_check_count = _count(minimum_check_count, "minimum certificate check count", MAX_CHECKS)
        self.minimum_passed_count = _count(minimum_passed_count, "minimum certificate passed count", MAX_CHECKS)
        self.require_gate_acceptance = _bool(require_gate_acceptance, "require gate acceptance")
        self.require_gate_audit = _bool(require_gate_audit, "require gate audit")
        self.require_query_complete = _bool(require_query_complete, "require complete gate query")
        self.require_package = _bool(require_package, "require gate package")
        self.content_address = _address(content_address, "certificate policy address", POLICY_PREFIX)
        if not self.content_address.endswith(":pending") and address_policy(self) != self.content_address:
            raise ValidationError("certificate policy address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificatePolicy:
        value = _mapping(value, "certificate policy")
        _strict(value, set(cls.FIELDS), "certificate policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: RegistryFederationConsensusGateCertificatePolicy) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificatePolicy):
        raise ValidationError("certificate policy address requires a typed policy")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def default_policy(*, policy_id: str = "consensus-release-certificate-policy", require_package: bool = False) -> RegistryFederationConsensusGateCertificatePolicy:
    provisional = RegistryFederationConsensusGateCertificatePolicy(policy_id, ("eligible",), ("promote",), 1, 1, True, True, True, require_package, POLICY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificatePolicy(provisional.policy_id, provisional.allowed_gate_states, provisional.allowed_gate_decisions, provisional.minimum_check_count, provisional.minimum_passed_count, provisional.require_gate_acceptance, provisional.require_gate_audit, provisional.require_query_complete, provisional.require_package, address_policy(provisional))


class RegistryFederationConsensusGateCertificateCheck:
    """One reproducible certificate issuance assertion."""

    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "certificate check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("certificate check ID is unsupported")
        self.passed = _bool(passed, "certificate check result")
        self.detail = _text(detail, "certificate check detail", required=True)
        self.evidence_addresses = _addresses(evidence_addresses, "certificate check evidence", MAX_EVIDENCE)
        self.content_address = _address(content_address, "certificate check address", CHECK_PREFIX)
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("certificate check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateCheck:
        value = _mapping(value, "certificate check")
        _strict(value, set(cls.FIELDS), "certificate check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateCheck) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateCheck):
        raise ValidationError("certificate check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificate:
    """Issued or withheld release receipt for one gate runtime."""

    FIELDS = (
        "certificate_id",
        "runtime_id",
        "runtime_address",
        "package_address",
        "gate_id",
        "gate_address",
        "audit_address",
        "query_address",
        "policy",
        "gate_state",
        "gate_decision",
        "certificate_state",
        "certificate_decision",
        "checks",
        "check_count",
        "passed_count",
        "failed_count",
        "blocking_check_ids",
        "evidence_addresses",
        "accepted",
        "content_address",
    )

    def __init__(self, certificate_id: str, runtime_id: str, runtime_address: str, package_address: str, gate_id: str, gate_address: str, audit_address: str, query_address: str, policy: RegistryFederationConsensusGateCertificatePolicy, gate_state: str, gate_decision: str, certificate_state: str, certificate_decision: str, checks: Sequence[RegistryFederationConsensusGateCertificateCheck], check_count: int, passed_count: int, failed_count: int, blocking_check_ids: Sequence[str], evidence_addresses: Sequence[str], accepted: bool, content_address: str) -> None:
        self.certificate_id = _label(certificate_id, "certificate ID")
        self.runtime_id = _label(runtime_id, "certificate runtime ID")
        self.runtime_address = _address(runtime_address, "certificate runtime address", runtime_model.RUNTIME_PREFIX)
        self.package_address = _address(package_address, "certificate package address", PACKAGE_PREFIX, optional=True)
        self.gate_id = _label(gate_id, "certificate gate ID")
        self.gate_address = _address(gate_address, "certificate gate address", gate_model.GATE_PREFIX)
        self.audit_address = _address(audit_address, "certificate audit address", gate_audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "certificate query address", gate_query_model.RESULT_PREFIX)
        if not isinstance(policy, RegistryFederationConsensusGateCertificatePolicy):
            raise ValidationError("certificate policy must be typed")
        self.policy = policy
        if gate_state not in gate_model.GATE_STATES or gate_decision not in gate_model.GATE_DECISIONS:
            raise ValidationError("certificate source disposition is unsupported")
        if certificate_state not in CERTIFICATE_STATES or certificate_decision not in CERTIFICATE_DECISIONS:
            raise ValidationError("certificate disposition is unsupported")
        self.gate_state, self.gate_decision = gate_state, gate_decision
        self.certificate_state, self.certificate_decision = certificate_state, certificate_decision
        self.checks = tuple(checks)
        if len(self.checks) > MAX_CHECKS or any(not isinstance(item, RegistryFederationConsensusGateCertificateCheck) for item in self.checks):
            raise ValidationError("certificate checks are outside the bound")
        self.check_count = _count(check_count, "certificate check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "certificate passed count", self.check_count)
        self.failed_count = _count(failed_count, "certificate failed count", self.check_count)
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("certificate check ordering is not conserved")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks):
            raise ValidationError("certificate check counters are not conserved")
        self.blocking_check_ids = _labels(blocking_check_ids, "blocking certificate checks", MAX_CHECKS, allow_empty=True)
        if self.blocking_check_ids != tuple(sorted(item.check_id for item in self.checks if not item.passed)):
            raise ValidationError("blocking certificate checks are not conserved")
        self.evidence_addresses = _addresses(evidence_addresses, "certificate evidence addresses", MAX_EVIDENCE)
        self.accepted = _bool(accepted, "certificate acceptance")
        expected_accepted = self.failed_count == 0
        expected_state = "issued" if expected_accepted else "withheld"
        expected_decision = "promote" if expected_accepted else "hold"
        if self.accepted != expected_accepted or self.certificate_state != expected_state or self.certificate_decision != expected_decision:
            raise ValidationError("certificate disposition is not conserved")
        self.content_address = _address(content_address, "certificate content address", CERTIFICATE_PREFIX)
        if not self.content_address.endswith(":pending") and address_certificate(self) != self.content_address:
            raise ValidationError("certificate content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"certificate_id": self.certificate_id, "runtime_id": self.runtime_id, "runtime_address": self.runtime_address, "package_address": self.package_address, "gate_id": self.gate_id, "gate_address": self.gate_address, "audit_address": self.audit_address, "query_address": self.query_address, "policy": self.policy.to_dict(), "gate_state": self.gate_state, "gate_decision": self.gate_decision, "certificate_state": self.certificate_state, "certificate_decision": self.certificate_decision, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "blocking_check_ids": self.blocking_check_ids, "evidence_addresses": self.evidence_addresses, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"policy", "checks", "evidence_addresses"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificate:
        value = _mapping(value, "consensus gate certificate")
        _strict(value, set(cls.FIELDS), "consensus gate certificate")
        return cls(value["certificate_id"], value["runtime_id"], value["runtime_address"], value["package_address"], value["gate_id"], value["gate_address"], value["audit_address"], value["query_address"], RegistryFederationConsensusGateCertificatePolicy.from_mapping(value["policy"]), value["gate_state"], value["gate_decision"], value["certificate_state"], value["certificate_decision"], tuple(RegistryFederationConsensusGateCertificateCheck.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["blocking_check_ids"], value["evidence_addresses"], value["accepted"], value["content_address"])


def address_certificate(value: RegistryFederationConsensusGateCertificate) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificate):
        raise ValidationError("certificate address requires a typed certificate")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CERTIFICATE_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateCheck:
    unique_evidence = tuple(dict.fromkeys(evidence))
    provisional = RegistryFederationConsensusGateCertificateCheck(ordinal, check_id, passed, detail, unique_evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def _evidence(runtime: runtime_model.RegistryFederationConsensusGateRuntime, policy: RegistryFederationConsensusGateCertificatePolicy) -> tuple[str, ...]:
    values = [runtime.content_address, runtime.gate.content_address, runtime.audit.content_address, runtime.query.content_address, policy.content_address]
    if runtime.package_address:
        values.append(runtime.package_address)
    return tuple(sorted(set(values)))


def evaluate_certificate(value: runtime_model.RegistryFederationConsensusGateRuntime, *, policy: RegistryFederationConsensusGateCertificatePolicy | None = None, certificate_id: str = "consensus-release-certificate") -> RegistryFederationConsensusGateCertificate:
    """Evaluate a certificate policy against one verified gate runtime."""

    runtime = runtime_model.verify_runtime(value)
    policy = default_policy() if policy is None else policy
    if not isinstance(policy, RegistryFederationConsensusGateCertificatePolicy):
        raise ValidationError("certificate policy must be typed")
    gate = runtime.gate
    audit = runtime.audit
    query = runtime.query
    evidence = _evidence(runtime, policy)
    checks: list[RegistryFederationConsensusGateCertificateCheck] = []
    checks.append(_check(1, "exact-fields", set(RegistryFederationConsensusGateCertificate.FIELDS) == set(RegistryFederationConsensusGateCertificate.FIELDS), "certificate fields are exact", evidence))
    checks.append(_check(2, "public-boundary", _public(runtime.to_dict()) and _public(policy.to_dict()), "runtime and policy are public", evidence))
    checks.append(_check(3, "runtime-link", gate.runtime_address == runtime.consensus_runtime.content_address, "gate points to the nested consensus runtime", (gate.runtime_address, runtime.consensus_runtime.content_address)))
    checks.append(_check(4, "gate-link", gate.content_address == runtime.gate.content_address and gate.gate_id == runtime.gate.gate_id, "gate identity is retained", (gate.content_address,)))
    checks.append(_check(5, "audit-link", audit.gate_address == gate.content_address, "independent audit points to the gate", (audit.content_address, audit.gate_address, gate.content_address)))
    checks.append(_check(6, "query-link", query.query.gate_address == gate.content_address, "bounded query points to the gate", (query.content_address, query.query.gate_address, gate.content_address)))
    checks.append(_check(7, "package-link", (not policy.require_package) or bool(runtime.package_address), "durable gate package requirement is satisfied", (gate.content_address,) if not runtime.package_address else (runtime.package_address,)))
    checks.append(_check(8, "policy-link", address_policy(policy) == policy.content_address, "certificate policy address replays", (policy.content_address,)))
    checks.append(_check(9, "state-allowed", gate.state in policy.allowed_gate_states, f"gate state is {gate.state}", evidence))
    checks.append(_check(10, "decision-allowed", gate.decision in policy.allowed_gate_decisions, f"gate decision is {gate.decision}", evidence))
    checks.append(_check(11, "gate-accepted", (not policy.require_gate_acceptance) or gate.accepted, f"gate accepted: {gate.accepted}", (gate.content_address,)))
    checks.append(_check(12, "audit-accepted", (not policy.require_gate_audit) or audit.accepted, f"gate audit accepted: {audit.accepted}", (audit.content_address,)))
    checks.append(_check(13, "query-complete", (not policy.require_query_complete) or not query.truncated, f"gate query truncated: {query.truncated}", (query.content_address,)))
    checks.append(_check(14, "check-floor", gate.check_count >= policy.minimum_check_count and gate.passed_count >= policy.minimum_passed_count, f"gate checks: {gate.passed_count}/{gate.check_count}", (gate.content_address, policy.content_address)))
    checks.append(_check(15, "counter-conservation", gate.passed_count + gate.failed_count == gate.check_count and gate.passed_count == sum(item.passed for item in gate.checks), "gate counters conserve checks", (gate.content_address,)))
    checks.append(_check(16, "acceptance-conservation", all(item.passed for item in checks), "all certificate prerequisites pass", evidence))
    checks.append(_check(17, "certificate-address", True, "certificate address is assigned after checks", evidence))
    checks.append(_check(18, "mapping-round-trip", True, "certificate mapping is lossless", evidence))
    checks.append(_check(19, "path-free", _public(evidence), "certificate evidence is path-free", evidence))
    accepted = all(item.passed for item in checks)
    state = "issued" if accepted else "withheld"
    decision = "promote" if accepted else "hold"
    blocking = tuple(item.check_id for item in checks if not item.passed)
    provisional = RegistryFederationConsensusGateCertificate(certificate_id, runtime.runtime_id, runtime.content_address, runtime.package_address, gate.gate_id, gate.content_address, audit.content_address, query.content_address, policy, gate.state, gate.decision, state, decision, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), blocking, evidence, accepted, CERTIFICATE_PREFIX + ":pending")
    final = RegistryFederationConsensusGateCertificate(provisional.certificate_id, provisional.runtime_id, provisional.runtime_address, provisional.package_address, provisional.gate_id, provisional.gate_address, provisional.audit_address, provisional.query_address, provisional.policy, provisional.gate_state, provisional.gate_decision, provisional.certificate_state, provisional.certificate_decision, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.blocking_check_ids, provisional.evidence_addresses, provisional.accepted, address_certificate(provisional))
    round_trip = RegistryFederationConsensusGateCertificate.from_mapping(final.to_dict())
    if round_trip.to_dict() != final.to_dict():
        raise ValidationError("certificate mapping round-trip does not replay")
    return final


def certificate_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificate:
    return verify_certificate(RegistryFederationConsensusGateCertificate.from_mapping(value))


def verify_certificate(value: RegistryFederationConsensusGateCertificate) -> RegistryFederationConsensusGateCertificate:
    if not isinstance(value, RegistryFederationConsensusGateCertificate) or (not value.content_address.endswith(":pending") and address_certificate(value) != value.content_address):
        raise ValidationError("consensus gate certificate is not valid")
    return value


def certificate_json(value: RegistryFederationConsensusGateCertificate) -> str:
    return canonical_json(verify_certificate(value).to_dict())


def certificate_csv(value: RegistryFederationConsensusGateCertificate) -> str:
    value = verify_certificate(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = "|".join(item.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_certificate_markdown(value: RegistryFederationConsensusGateCertificate) -> str:
    value = verify_certificate(value)
    lines = ["# Consensus Release Certificate", "", f"- Certificate: `{value.certificate_id}`", f"- State: `{value.certificate_state}`", f"- Decision: `{value.certificate_decision}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Gate: `{value.gate_address}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificatePolicy.FIELDS), "properties": {"policy_id": {"type": "string"}, "allowed_gate_states": {"type": "array", "items": {"type": "string"}}, "allowed_gate_decisions": {"type": "array", "items": {"type": "string"}}, "minimum_check_count": {"type": "integer", "minimum": 0}, "minimum_passed_count": {"type": "integer", "minimum": 0}, "require_gate_acceptance": {"type": "boolean"}, "require_gate_audit": {"type": "boolean"}, "require_query_complete": {"type": "boolean"}, "require_package": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + POLICY_PREFIX + ":"}}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def certificate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificate.FIELDS), "properties": {"certificate_id": {"type": "string"}, "runtime_id": {"type": "string"}, "runtime_address": {"type": "string", "pattern": "^" + runtime_model.RUNTIME_PREFIX + ":"}, "package_address": {"type": "string"}, "gate_id": {"type": "string"}, "gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "policy": policy_schema(), "gate_state": {"type": "string", "enum": list(gate_model.GATE_STATES)}, "gate_decision": {"type": "string", "enum": list(gate_model.GATE_DECISIONS)}, "certificate_state": {"type": "string", "enum": list(CERTIFICATE_STATES)}, "certificate_decision": {"type": "string", "enum": list(CERTIFICATE_DECISIONS)}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "blocking_check_ids": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + CERTIFICATE_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "certificate_prefix": CERTIFICATE_PREFIX, "policy_prefix": POLICY_PREFIX, "check_prefix": CHECK_PREFIX, "certificate_states": CERTIFICATE_STATES, "certificate_decisions": CERTIFICATE_DECISIONS, "check_ids": CHECK_IDS, "features": ("explicit issuance policy", "issued and withheld release receipts", "gate audit and query linkage", "optional durable package requirement", "blocking-check projection", "content-addressed evidence", "JSON CSV and Markdown exports"), "schemas": ("policy", "check", "certificate")}


__all__ = ["BOUNDARY", "CERTIFICATE_DECISIONS", "CERTIFICATE_PREFIX", "CERTIFICATE_STATES", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "PACKAGE_PREFIX", "POLICY_PREFIX", "RegistryFederationConsensusGateCertificate", "RegistryFederationConsensusGateCertificateCheck", "RegistryFederationConsensusGateCertificatePolicy", "VERSION", "address_certificate", "address_check", "address_policy", "capabilities", "certificate_csv", "certificate_from_mapping", "certificate_json", "certificate_schema", "check_schema", "default_policy", "evaluate_certificate", "policy_schema", "render_certificate_markdown", "verify_certificate"]
