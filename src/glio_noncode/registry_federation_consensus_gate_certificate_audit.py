"""Independent audit for consensus gate release certificates.

Certificate creation applies an issuance policy.  This module recomputes the
structural contract independently so a withheld certificate can be separated
from a malformed certificate.  It checks links, vocabulary, counters,
addresses, mapping replay, and public-boundary safety without trusting the
certificate's own summary fields.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from . import registry_federation_consensus_gate_audit as gate_audit_model
from . import registry_federation_consensus_gate_certificate as certificate_model
from . import registry_federation_consensus_gate_query as query_model
from . import registry_federation_consensus_gate_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = certificate_model.VERSION + "-audit-v1"
BOUNDARY = certificate_model.BOUNDARY + "_audit"
AUDIT_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
MAX_TEXT = certificate_model.MAX_TEXT
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "runtime-link",
    "gate-link",
    "audit-link",
    "query-link",
    "package-link",
    "policy-address",
    "policy-vocabulary",
    "check-vocabulary",
    "ordinal-conservation",
    "counter-conservation",
    "blocking-conservation",
    "evidence-conservation",
    "disposition-conservation",
    "acceptance-conservation",
    "certificate-address",
    "mapping-round-trip",
    "nested-addresses",
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
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


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


class RegistryFederationConsensusGateCertificateAuditFinding:
    """One independently recomputed certificate assertion."""

    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate audit ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "certificate audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("certificate audit check ID is unsupported")
        self.passed = _bool(passed, "certificate audit result")
        self.observed = _text(observed, "certificate audit observed value")
        self.expected = _text(expected, "certificate audit expected value")
        self.detail = _text(detail, "certificate audit detail", required=True)
        self.content_address = _address(content_address, "certificate finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("certificate finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateAuditFinding:
        value = _mapping(value, "certificate audit finding")
        _strict(value, set(cls.FIELDS), "certificate audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateAuditFinding):
        raise ValidationError("certificate finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateAudit:
    """Independent certificate audit with conserved result counts."""

    FIELDS = ("certificate_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, certificate_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.certificate_address = _address(certificate_address, "audited certificate address", certificate_model.CERTIFICATE_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateAuditFinding) for item in self.checks):
            raise ValidationError("certificate audit findings must be typed")
        self.check_count = _count(check_count, "certificate audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "certificate audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "certificate audit failed count", self.check_count)
        self.accepted = _bool(accepted, "certificate audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("certificate audit check ordering is not conserved")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("certificate audit counters are not conserved")
        self.content_address = _address(content_address, "certificate audit address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("certificate audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"certificate_address": self.certificate_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateAudit:
        value = _mapping(value, "consensus gate certificate audit")
        _strict(value, set(cls.FIELDS), "consensus gate certificate audit")
        return cls(value["certificate_address"], tuple(RegistryFederationConsensusGateCertificateAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateAudit):
        raise ValidationError("certificate audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificateAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_certificate(value: certificate_model.RegistryFederationConsensusGateCertificate) -> RegistryFederationConsensusGateCertificateAudit:
    """Recompute the certificate contract independently of issuance policy."""

    value = certificate_model.verify_certificate(value)
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(certificate_model.RegistryFederationConsensusGateCertificate.FIELDS), set(value.to_dict()), certificate_model.RegistryFederationConsensusGateCertificate.FIELDS, "certificate fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "certificate is public and path-free"),
        _finding(3, "runtime-link", value.runtime_address.startswith(runtime_model.RUNTIME_PREFIX + ":"), value.runtime_address, runtime_model.RUNTIME_PREFIX + ":", "certificate retains a gate runtime address"),
        _finding(4, "gate-link", value.gate_address.startswith(gate_model.GATE_PREFIX + ":"), value.gate_address, gate_model.GATE_PREFIX + ":", "certificate retains a gate address"),
        _finding(5, "audit-link", value.audit_address.startswith(gate_audit_model.AUDIT_PREFIX + ":"), value.audit_address, gate_audit_model.AUDIT_PREFIX + ":", "certificate retains an independent gate audit"),
        _finding(6, "query-link", value.query_address.startswith(query_model.RESULT_PREFIX + ":"), value.query_address, query_model.RESULT_PREFIX + ":", "certificate retains a bounded gate query"),
        _finding(7, "package-link", value.package_address == "" or value.package_address.startswith(certificate_model.PACKAGE_PREFIX + ":"), value.package_address, "optional package address", "optional package linkage is well formed"),
        _finding(8, "policy-address", certificate_model.address_policy(value.policy) == value.policy.content_address, value.policy.content_address, certificate_model.address_policy(value.policy), "certificate policy address replays"),
        _finding(9, "policy-vocabulary", all(item in gate_model.GATE_STATES for item in value.policy.allowed_gate_states) and all(item in gate_model.GATE_DECISIONS for item in value.policy.allowed_gate_decisions), (value.policy.allowed_gate_states, value.policy.allowed_gate_decisions), "gate vocabulary", "certificate policy vocabulary is valid"),
        _finding(10, "check-vocabulary", tuple(item.check_id for item in value.checks) == certificate_model.CHECK_IDS, tuple(item.check_id for item in value.checks), certificate_model.CHECK_IDS, "certificate check vocabulary is fixed"),
        _finding(11, "ordinal-conservation", tuple(item.ordinal for item in value.checks) == tuple(range(1, value.check_count + 1)), tuple(item.ordinal for item in value.checks), tuple(range(1, value.check_count + 1)), "certificate ordinals are contiguous"),
        _finding(12, "counter-conservation", value.passed_count + value.failed_count == value.check_count and value.passed_count == sum(item.passed for item in value.checks), (value.passed_count, value.failed_count), value.check_count, "certificate counters replay"),
        _finding(13, "blocking-conservation", value.blocking_check_ids == tuple(sorted(item.check_id for item in value.checks if not item.passed)), value.blocking_check_ids, tuple(sorted(item.check_id for item in value.checks if not item.passed)), "blocking checks identify every failed assertion"),
        _finding(14, "evidence-conservation", bool(value.evidence_addresses) and len(set(value.evidence_addresses)) == len(value.evidence_addresses), len(value.evidence_addresses), "unique evidence addresses", "certificate evidence is conserved"),
        _finding(15, "disposition-conservation", (value.certificate_state, value.certificate_decision) == (("issued", "promote") if value.accepted else ("withheld", "hold")), (value.certificate_state, value.certificate_decision), ("issued", "promote") if value.accepted else ("withheld", "hold"), "certificate disposition follows acceptance"),
        _finding(16, "acceptance-conservation", value.accepted == (value.failed_count == 0), value.accepted, value.failed_count == 0, "certificate acceptance is fail-closed"),
        _finding(17, "certificate-address", certificate_model.address_certificate(value) == value.content_address, value.content_address, certificate_model.address_certificate(value), "certificate content address replays"),
        _finding(18, "mapping-round-trip", certificate_model.certificate_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original certificate", "certificate mapping is lossless"),
        _finding(19, "nested-addresses", bool(value.runtime_address and value.gate_address and value.audit_address and value.query_address and value.policy.content_address), "nested addresses present", True, "certificate has a complete evidence spine"),
        _finding(20, "path-free", _public(value.to_dict()), True, True, "certificate contains no private paths or attribution fields"),
    )
    provisional = RegistryFederationConsensusGateCertificateAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateAudit(provisional.certificate_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateAudit) -> RegistryFederationConsensusGateCertificateAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("certificate audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Release Certificate Audit", "", f"- Certificate: `{value.certificate_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | observed | expected |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.observed} | {item.expected} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateAudit.FIELDS), "properties": {"certificate_address": {"type": "string", "pattern": "^" + certificate_model.CERTIFICATE_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent certificate structure checks", "nested evidence spine validation", "policy and disposition conservation", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateAudit", "RegistryFederationConsensusGateCertificateAuditFinding", "VERSION", "address_audit", "address_finding", "audit_certificate", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
