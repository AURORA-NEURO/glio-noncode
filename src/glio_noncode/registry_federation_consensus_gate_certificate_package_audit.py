"""Independent verification of certificate package closures."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from . import registry_federation_consensus_gate_certificate as certificate_model
from . import registry_federation_consensus_gate_certificate_package as package_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = package_model.VERSION + "-audit-v1"
BOUNDARY = package_model.BOUNDARY + "_audit"
AUDIT_PREFIX = package_model.PACKAGE_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
MAX_TEXT = certificate_model.MAX_TEXT
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "certificate-link",
    "runtime-link",
    "gate-link",
    "audit-link",
    "query-link",
    "certificate-audit-link",
    "certificate-query-link",
    "policy-link",
    "nested-gate-link",
    "certificate-address",
    "package-address",
    "acceptance-conservation",
    "projection-shape",
    "mapping-round-trip",
    "content-address",
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


def _address(value: Any, field: str, prefix: str | None = None) -> str:
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


class RegistryFederationConsensusGateCertificatePackageAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate package audit ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "certificate package audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("certificate package audit check ID is unsupported")
        self.passed = _bool(passed, "certificate package audit result")
        self.observed = _text(observed, "certificate package audit observed value")
        self.expected = _text(expected, "certificate package audit expected value")
        self.detail = _text(detail, "certificate package audit detail", required=True)
        self.content_address = _address(content_address, "certificate package finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("certificate package finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate package finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificatePackageAuditFinding:
        value = _mapping(value, "certificate package audit finding")
        _strict(value, set(cls.FIELDS), "certificate package audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificatePackageAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificatePackageAuditFinding):
        raise ValidationError("certificate package finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificatePackageAudit:
    FIELDS = ("package_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, package_address: str, checks: Sequence[RegistryFederationConsensusGateCertificatePackageAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.package_address = _address(package_address, "audited certificate package address", package_model.PACKAGE_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificatePackageAuditFinding) for item in self.checks):
            raise ValidationError("certificate package audit findings must be typed")
        self.check_count = _count(check_count, "certificate package audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "certificate package audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "certificate package audit failed count", self.check_count)
        self.accepted = _bool(accepted, "certificate package audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("certificate package audit check ordering is not conserved")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("certificate package audit counters are not conserved")
        self.content_address = _address(content_address, "certificate package audit address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("certificate package audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate package audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"package_address": self.package_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificatePackageAudit:
        value = _mapping(value, "consensus gate certificate package audit")
        _strict(value, set(cls.FIELDS), "consensus gate certificate package audit")
        return cls(value["package_address"], tuple(RegistryFederationConsensusGateCertificatePackageAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificatePackageAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificatePackageAudit):
        raise ValidationError("certificate package audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificatePackageAuditFinding:
    provisional = RegistryFederationConsensusGateCertificatePackageAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificatePackageAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_package(value: package_model.RegistryFederationConsensusGateCertificatePackage) -> RegistryFederationConsensusGateCertificatePackageAudit:
    """Recompute the typed package closure and all child links."""

    value = package_model.verify_package(value)
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(package_model.RegistryFederationConsensusGateCertificatePackage.FIELDS), set(value.to_dict()), package_model.RegistryFederationConsensusGateCertificatePackage.FIELDS, "package fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "package is public and path-free"),
        _finding(3, "certificate-link", value.certificate.runtime_address == value.runtime.content_address and value.certificate.gate_address == value.gate.content_address, (value.certificate.runtime_address, value.certificate.gate_address), (value.runtime.content_address, value.gate.content_address), "certificate points to package runtime and gate"),
        _finding(4, "runtime-link", value.runtime.gate.runtime_address == value.runtime.consensus_runtime.content_address, value.runtime.gate.runtime_address, value.runtime.consensus_runtime.content_address, "runtime contains the referenced consensus runtime"),
        _finding(5, "gate-link", value.gate.content_address == value.certificate.gate_address, value.gate.content_address, value.certificate.gate_address, "package gate address is conserved"),
        _finding(6, "audit-link", value.gate_audit.gate_address == value.gate.content_address and value.certificate.audit_address == value.gate_audit.content_address, (value.gate_audit.gate_address, value.certificate.audit_address), (value.gate.content_address, value.gate_audit.content_address), "gate audit links replay"),
        _finding(7, "query-link", value.gate_query.query.gate_address == value.gate.content_address and value.certificate.query_address == value.gate_query.content_address, (value.gate_query.query.gate_address, value.certificate.query_address), (value.gate.content_address, value.gate_query.content_address), "gate query links replay"),
        _finding(8, "certificate-audit-link", value.certificate_audit.certificate_address == value.certificate.content_address, value.certificate_audit.certificate_address, value.certificate.content_address, "certificate audit points to the certificate"),
        _finding(9, "certificate-query-link", value.certificate_query.query.certificate_address == value.certificate.content_address, value.certificate_query.query.certificate_address, value.certificate.content_address, "certificate query points to the certificate"),
        _finding(10, "policy-link", certificate_model.address_policy(value.certificate.policy) == value.certificate.policy.content_address, value.certificate.policy.content_address, certificate_model.address_policy(value.certificate.policy), "policy address replays"),
        _finding(11, "nested-gate-link", value.gate.consensus_address == value.runtime.consensus_runtime.consensus.content_address, value.gate.consensus_address, value.runtime.consensus_runtime.consensus.content_address, "gate consensus link is conserved"),
        _finding(12, "certificate-address", certificate_model.address_certificate(value.certificate) == value.certificate.content_address, value.certificate.content_address, certificate_model.address_certificate(value.certificate), "certificate address replays"),
        _finding(13, "package-address", package_model.address_package(value) == value.content_address, value.content_address, package_model.address_package(value), "package address replays"),
        _finding(14, "acceptance-conservation", value.certificate.accepted == (value.certificate.failed_count == 0), value.certificate.accepted, value.certificate.failed_count == 0, "certificate acceptance is fail-closed"),
        _finding(15, "projection-shape", set(package_model.package_bytes(value)) == set(package_model.FILES), tuple(sorted(package_model.package_bytes(value))), package_model.FILES, "package exposes every exact projection"),
        _finding(16, "mapping-round-trip", package_model.package_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original package", "package mapping is lossless"),
        _finding(17, "content-address", package_model.address_package(value) == value.content_address, value.content_address, package_model.address_package(value), "package content address replays"),
        _finding(18, "path-free", _public(value.to_dict()), True, True, "package contains no private paths or attribution fields"),
    )
    provisional = RegistryFederationConsensusGateCertificatePackageAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificatePackageAudit(provisional.package_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificatePackageAudit:
    return verify_audit(RegistryFederationConsensusGateCertificatePackageAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificatePackageAudit) -> RegistryFederationConsensusGateCertificatePackageAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificatePackageAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("certificate package audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificatePackageAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificatePackageAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificatePackageAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificatePackageAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Release Certificate Package Audit", "", f"- Package: `{value.package_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | observed | expected |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.observed} | {item.expected} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificatePackageAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificatePackageAudit.FIELDS), "properties": {"package_address": {"type": "string", "pattern": "^" + package_model.PACKAGE_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent nine-file package checks", "nested certificate/runtime/gate linkage", "projection-shape verification", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificatePackageAudit", "RegistryFederationConsensusGateCertificatePackageAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_package", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
