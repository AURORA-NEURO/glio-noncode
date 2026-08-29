"""Independent structural audit for consensus release gates.

The gate evaluator applies policy.  This module is deliberately separate and
recomputes the gate's public invariants from the resulting receipt so callers
can distinguish a failed release policy from a malformed or tampered gate.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus as consensus_model
from . import registry_federation_consensus_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = gate_model.VERSION + "-audit-v1"
BOUNDARY = gate_model.BOUNDARY + "_audit"
AUDIT_PREFIX = gate_model.GATE_PREFIX + "-audit"
FINDING_PREFIX = gate_model.GATE_PREFIX + "-audit-finding"
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "runtime-link",
    "consensus-link",
    "policy-conservation",
    "check-vocabulary",
    "ordinal-conservation",
    "counter-conservation",
    "disposition-conservation",
    "acceptance-conservation",
    "check-addresses",
    "mapping-round-trip",
    "nested-receipt",
    "gate-address",
    "content-address",
    "path-free",
)
MAX_TEXT = gate_model.MAX_TEXT


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
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
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "gate audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("gate audit check ID is unsupported")
        self.passed = _bool(passed, "gate audit finding result")
        self.observed = _text(observed, "gate audit observed value")
        self.expected = _text(expected, "gate audit expected value")
        self.detail = _text(detail, "gate audit detail", required=True)
        self.content_address = _address(content_address, "gate audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("gate audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateAuditFinding:
        value = _mapping(value, "gate audit finding")
        _strict(value, set(cls.FIELDS), "gate audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateAuditFinding):
        raise ValidationError("gate audit finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateAudit:
    FIELDS = ("gate_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, gate_address: str, checks: Sequence[RegistryFederationConsensusGateAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.gate_address = _address(gate_address, "audited gate address", gate_model.GATE_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateAuditFinding) for item in self.checks):
            raise ValidationError("gate audit checks must be typed")
        self.check_count = _count(check_count, "gate audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "gate audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "gate audit failed count", self.check_count)
        self.accepted = _bool(accepted, "gate audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("gate audit check ordering is not conserved")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("gate audit counters are not conserved")
        self.content_address = _address(content_address, "gate audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("gate audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_address": self.gate_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateAudit:
        value = _mapping(value, "consensus gate audit")
        _strict(value, set(cls.FIELDS), "consensus gate audit")
        return cls(value["gate_address"], tuple(RegistryFederationConsensusGateAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateAudit):
        raise ValidationError("gate audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateAuditFinding:
    provisional = RegistryFederationConsensusGateAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_gate(value: gate_model.RegistryFederationConsensusGate) -> RegistryFederationConsensusGateAudit:
    value = gate_model.verify_gate(value)
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(gate_model.RegistryFederationConsensusGate.FIELDS), tuple(sorted(value.to_dict())), gate_model.RegistryFederationConsensusGate.FIELDS, "gate fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "gate is public and path-free"),
        _finding(3, "runtime-link", value.runtime_address.startswith(runtime_prefix := gate_model.runtime_model.RUNTIME_PREFIX + ":"), value.runtime_address, runtime_prefix, "gate links one consensus runtime"),
        _finding(4, "consensus-link", value.consensus_address.startswith(consensus_model.CONSENSUS_PREFIX + ":"), value.consensus_address, consensus_model.CONSENSUS_PREFIX + ":", "gate links one consensus receipt"),
        _finding(5, "policy-conservation", gate_model.address_policy(value.policy) == value.policy.content_address, value.policy.content_address, gate_model.address_policy(value.policy), "policy address replays"),
        _finding(6, "check-vocabulary", tuple(item.check_id for item in value.checks) == gate_model.CHECK_IDS, tuple(item.check_id for item in value.checks), gate_model.CHECK_IDS, "check vocabulary and order are fixed"),
        _finding(7, "ordinal-conservation", tuple(item.ordinal for item in value.checks) == tuple(range(1, value.check_count + 1)), tuple(item.ordinal for item in value.checks), tuple(range(1, value.check_count + 1)), "check ordinals are contiguous"),
        _finding(8, "counter-conservation", value.passed_count + value.failed_count == value.check_count and value.passed_count == sum(item.passed for item in value.checks), (value.passed_count, value.failed_count), value.check_count, "gate counters replay"),
        _finding(9, "disposition-conservation", value.state in gate_model.GATE_STATES and value.decision in gate_model.GATE_DECISIONS, (value.state, value.decision), gate_model.GATE_STATES, "gate disposition uses the public vocabulary"),
        _finding(10, "acceptance-conservation", value.accepted == (value.failed_count == 0), value.accepted, value.failed_count == 0, "promotion eligibility is fail-closed"),
        _finding(11, "check-addresses", all(gate_model.address_check(item) == item.content_address for item in value.checks), "replayed check addresses", "stored check addresses", "every check address replays"),
        _finding(12, "mapping-round-trip", gate_model.gate_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original gate", "mapping conversion is lossless"),
        _finding(13, "nested-receipt", bool(value.runtime_id and value.consensus_id and value.runtime_address and value.consensus_address), "runtime and consensus identities", "non-empty identities", "nested receipt identities are retained"),
        _finding(14, "gate-address", gate_model.address_gate(value) == value.content_address, value.content_address, gate_model.address_gate(value), "gate content address replays"),
        _finding(15, "content-address", value.content_address.startswith(gate_model.GATE_PREFIX + ":"), value.content_address, gate_model.GATE_PREFIX + ":", "gate address uses the gate namespace"),
        _finding(16, "path-free", _public(value.to_dict()), True, True, "gate contains no local paths or private execution text"),
    )
    provisional = RegistryFederationConsensusGateAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateAudit(provisional.gate_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateAudit:
    return verify_audit(RegistryFederationConsensusGateAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateAudit) -> RegistryFederationConsensusGateAudit:
    if not isinstance(value, RegistryFederationConsensusGateAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("consensus gate audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for finding in value.checks:
        writer.writerow(finding.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Release Gate Audit", "", f"- Gate: `{value.gate_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | observed | expected |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.observed} | {item.expected} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateAudit.FIELDS), "properties": {"gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent policy-gate structure checks", "nested receipt link verification", "fail-closed acceptance conservation", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateAudit", "RegistryFederationConsensusGateAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_gate", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
