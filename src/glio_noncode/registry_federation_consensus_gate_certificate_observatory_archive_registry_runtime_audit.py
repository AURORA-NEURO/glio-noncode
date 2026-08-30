"""Independent audit for the archive-registry runtime receipt."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_audit as registry_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_runtime as runtime_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = ("runtime-address", "input-count", "registry-link", "audit-link", "query-link", "persistence-state", "acceptance-state", "public-boundary", "mapping-round-trip", "address-namespaces", "bounded-inputs", "path-free")


def _text(value: Any, field: str, maximum: int = 2048, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime audit finding ordinal", len(CHECK_IDS))
        if self.ordinal == 0 or check_id not in CHECK_IDS:
            raise ValidationError("runtime audit finding check ID is undeclared")
        self.check_id = check_id
        self.passed = _bool(passed, "runtime audit finding state")
        self.observed = _text(observed, "runtime audit observed value", 1024)
        self.expected = _text(expected, "runtime audit expected value", 1024)
        self.detail = _text(detail, "runtime audit detail", 2048)
        self.evidence_address = _address(evidence_address, "runtime audit evidence address")
        self.content_address = _address(content_address, "runtime audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("runtime audit finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding":
        value = _mapping(value, "runtime audit finding")
        _strict(value, set(cls.FIELDS), "runtime audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding):
        raise ValidationError("runtime audit finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit:
    FIELDS = ("runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, runtime_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding.from_mapping(item) for item in _sequence(checks, "runtime audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "runtime audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "runtime audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "runtime audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "runtime audit acceptance")
        self.content_address = _address(content_address, "runtime audit address", AUDIT_PREFIX)
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime audit checks are not canonical")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("runtime audit counters are not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("runtime_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit":
        value = _mapping(value, "runtime audit")
        _strict(value, set(cls.FIELDS), "runtime audit")
        checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding.from_mapping(item) for item in _sequence(value["checks"], "runtime audit checks", len(CHECK_IDS)))
        return cls(value["runtime_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit):
        raise ValidationError("runtime audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str, evidence: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding:
    observed_text = str(observed)
    expected_text = str(expected)
    if len(observed_text) > 1024:
        observed_text = observed_text[:1021] + "..."
    if len(expected_text) > 1024:
        expected_text = expected_text[:1021] + "..."
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding(ordinal, check_id, passed, observed_text, expected_text, detail, evidence, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding(ordinal, check_id, passed, provisional.observed, provisional.expected, detail, evidence, address_finding(provisional))


def audit_runtime(value: runtime_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit:
    value = runtime_model.verify_runtime(value)
    namespaces = value.registry_address.startswith(registry_model.REGISTRY_PREFIX + ":") and value.audit_address.startswith(registry_audit_model.AUDIT_PREFIX + ":") and value.query_address.startswith(query_model.RESULT_PREFIX + ":")
    checks = (
        _finding(1, "runtime-address", runtime_model.address_runtime(value) == value.content_address, value.content_address, runtime_model.address_runtime(value), "runtime address reproduces", value.content_address),
        _finding(2, "input-count", 0 < value.input_count <= registry_model.MAX_ENTRIES, value.input_count, registry_model.MAX_ENTRIES, "runtime input count is bounded", value.content_address),
        _finding(3, "registry-link", value.registry_address.startswith(registry_model.REGISTRY_PREFIX + ":"), value.registry_address, registry_model.REGISTRY_PREFIX, "runtime links to a registry", value.registry_address),
        _finding(4, "audit-link", value.audit_address.startswith(registry_audit_model.AUDIT_PREFIX + ":"), value.audit_address, registry_audit_model.AUDIT_PREFIX, "runtime links to a registry audit", value.audit_address),
        _finding(5, "query-link", value.query_address.startswith(query_model.RESULT_PREFIX + ":"), value.query_address, query_model.RESULT_PREFIX, "runtime links to a query result", value.query_address),
        _finding(6, "persistence-state", isinstance(value.registry_written, bool), value.registry_written, "boolean", "persistence state is explicit", value.content_address),
        _finding(7, "acceptance-state", isinstance(value.accepted, bool), value.accepted, "boolean", "acceptance is explicit", value.content_address),
        _finding(8, "public-boundary", _public(value.to_dict()), True, True, "runtime receipt is public", value.content_address),
        _finding(9, "mapping-round-trip", runtime_model.runtime_from_mapping(value.to_dict()).to_dict() == value.to_dict(), True, True, "runtime mapping reloads exactly", value.content_address),
        _finding(10, "address-namespaces", namespaces, namespaces, True, "runtime links use declared namespaces", value.content_address),
        _finding(11, "bounded-inputs", value.input_count <= registry_model.MAX_ENTRIES, value.input_count, registry_model.MAX_ENTRIES, "runtime input count remains bounded", value.content_address),
        _finding(12, "path-free", _public(value.to_dict()), True, True, "runtime receipt contains no local path", value.content_address),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit(provisional.runtime_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("runtime audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    fields = ("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow({field: item.to_dict()[field] for field in fields})
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Archive Registry Runtime Audit", "", f"- Runtime: `{value.runtime_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit.FIELDS), "properties": {"runtime_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS), "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("runtime address replay", "input and namespace checks", "persistence-state checks", "public-boundary checks", "addressable findings", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntimeAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
