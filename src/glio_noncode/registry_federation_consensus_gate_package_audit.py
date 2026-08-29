"""Independent audit for consensus gate release-control packages."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_package as package_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = package_model.VERSION + "-audit-v1"
BOUNDARY = package_model.BOUNDARY + "_audit"
AUDIT_PREFIX = package_model.PACKAGE_PREFIX + "-audit"
FINDING_PREFIX = package_model.PACKAGE_PREFIX + "-audit-finding"
CHECK_IDS = ("exact-fields", "public-boundary", "runtime-link", "gate-link", "audit-link", "query-link", "package-address", "member-vocabulary", "nested-addresses", "mapping-round-trip", "content-address", "path-free")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
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


class RegistryFederationConsensusGatePackageAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate package audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "gate package audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("gate package audit check ID is unsupported")
        self.passed = _bool(passed, "gate package audit result")
        self.observed = _text(observed, "gate package audit observed value")
        self.expected = _text(expected, "gate package audit expected value")
        self.detail = _text(detail, "gate package audit detail", required=True)
        self.content_address = _address(content_address, "gate package audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("gate package audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate package audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGatePackageAuditFinding:
        value = _mapping(value, "gate package audit finding")
        _strict(value, set(cls.FIELDS), "gate package audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGatePackageAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGatePackageAuditFinding):
        raise ValidationError("gate package finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGatePackageAudit:
    FIELDS = ("package_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, package_address: str, checks: Sequence[RegistryFederationConsensusGatePackageAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.package_address = _address(package_address, "audited gate package address", package_model.PACKAGE_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGatePackageAuditFinding) for item in self.checks):
            raise ValidationError("gate package audit checks must be typed")
        self.check_count = _count(check_count, "gate package audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "gate package audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "gate package audit failed count", self.check_count)
        self.accepted = _bool(accepted, "gate package audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("gate package audit counters are not conserved")
        self.content_address = _address(content_address, "gate package audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("gate package audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate package audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"package_address": self.package_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGatePackageAudit:
        value = _mapping(value, "consensus gate package audit")
        _strict(value, set(cls.FIELDS), "consensus gate package audit")
        return cls(value["package_address"], tuple(RegistryFederationConsensusGatePackageAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGatePackageAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGatePackageAudit):
        raise ValidationError("gate package audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGatePackageAuditFinding:
    provisional = RegistryFederationConsensusGatePackageAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGatePackageAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_package(value: package_model.RegistryFederationConsensusGatePackage) -> RegistryFederationConsensusGatePackageAudit:
    value = package_model.verify_package(value)
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(package_model.RegistryFederationConsensusGatePackage.FIELDS), tuple(sorted(value.to_dict())), package_model.RegistryFederationConsensusGatePackage.FIELDS, "package fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "package is public and path-free"),
        _finding(3, "runtime-link", value.gate.runtime_address == value.runtime.content_address, value.gate.runtime_address, value.runtime.content_address, "gate points to the embedded runtime"),
        _finding(4, "gate-link", value.gate.consensus_address == value.runtime.consensus.content_address, value.gate.consensus_address, value.runtime.consensus.content_address, "gate points to the embedded consensus"),
        _finding(5, "audit-link", value.audit.gate_address == value.gate.content_address, value.audit.gate_address, value.gate.content_address, "audit points to the embedded gate"),
        _finding(6, "query-link", value.query.query.gate_address == value.gate.content_address, value.query.query.gate_address, value.gate.content_address, "query points to the embedded gate"),
        _finding(7, "package-address", package_model.address_package(value) == value.content_address, value.content_address, package_model.address_package(value), "package content address replays"),
        _finding(8, "member-vocabulary", tuple(sorted(package_model.FILES)) == tuple(sorted({package_model.MANIFEST_NAME, package_model.PACKAGE_NAME, package_model.RUNTIME_NAME, package_model.GATE_NAME, package_model.AUDIT_NAME, package_model.QUERY_NAME})), package_model.FILES, "six canonical members", "member vocabulary is fixed"),
        _finding(9, "nested-addresses", bool(value.runtime.content_address and value.gate.content_address and value.audit.content_address and value.query.content_address), "all nested addresses", "all nested addresses", "nested addresses are present"),
        _finding(10, "mapping-round-trip", package_model.package_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original package", "mapping conversion is lossless"),
        _finding(11, "content-address", value.content_address.startswith(package_model.PACKAGE_PREFIX + ":"), value.content_address, package_model.PACKAGE_PREFIX + ":", "package uses the package namespace"),
        _finding(12, "path-free", _public(value.to_dict()), True, True, "package contains no local paths or private execution text"),
    )
    provisional = RegistryFederationConsensusGatePackageAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGatePackageAudit(provisional.package_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGatePackageAudit:
    return verify_audit(RegistryFederationConsensusGatePackageAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGatePackageAudit) -> RegistryFederationConsensusGatePackageAudit:
    if not isinstance(value, RegistryFederationConsensusGatePackageAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("consensus gate package audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGatePackageAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGatePackageAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGatePackageAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for finding in value.checks:
        writer.writerow(finding.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGatePackageAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Gate Package Audit", "", f"- Package: `{value.package_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGatePackageAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGatePackageAudit.FIELDS), "properties": {"package_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent package member checks", "embedded runtime and gate link checks", "canonical member vocabulary checks", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGatePackageAudit", "RegistryFederationConsensusGatePackageAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_package", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
