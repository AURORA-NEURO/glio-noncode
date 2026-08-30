"""Independent assurance for the federation runtime envelope."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("source-count", "federation-link", "federation-audit-link", "consensus-link", "consensus-audit-link", "report-link", "outcome-link", "public-boundary", "runtime-address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} must use its public address namespace")
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
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return runtime_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation runtime audit ordinal", len(CHECK_IDS))
        self.check_id = _label(check_id, "federation runtime audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("federation runtime audit check ID is unsupported")
        self.passed = _bool(passed, "federation runtime audit result")
        self.detail = _text(detail, "federation runtime audit detail")
        self.evidence_addresses = tuple(_text(item, "federation runtime audit evidence", 2048) for item in _sequence(evidence_addresses, "federation runtime audit evidence", runtime_model.MAX_SOURCE_COUNT + 8))
        self.content_address = _address(content_address, "federation runtime audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation runtime audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("federation runtime audit check is invalid")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("federation runtime audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck":
        value = _mapping(value, "federation runtime audit check")
        _strict(value, set(cls.FIELDS), "federation runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit:
    FIELDS = ("runtime_id", "runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, runtime_id: str, runtime_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "federation runtime audit ID")
        self.runtime_address = _address(runtime_address, "federation runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck.from_mapping(item) for item in _sequence(checks, "federation runtime audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "federation runtime audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "federation runtime audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "federation runtime audit failed count", self.check_count)
        self.accepted = _bool(accepted, "federation runtime audit acceptance")
        self.content_address = _address(content_address, "federation runtime audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation runtime audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("federation runtime audit counters or order are invalid")
        if not _public(self.to_dict()):
            raise ValidationError("federation runtime audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("federation runtime audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "runtime_address": self.runtime_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("runtime_id", "runtime_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit":
        value = _mapping(value, "federation runtime audit")
        _strict(value, set(cls.FIELDS), "federation runtime audit")
        return cls(value["runtime_id"], value["runtime_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "federation runtime audit checks", len(CHECK_IDS))), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_runtime(value: runtime_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit:
    value = runtime_model.verify_runtime(value)
    evidence = (value.federation.content_address, value.consensus.content_address, value.report.content_address)
    checks = (
        _check(1, "source-count", value.source_count == value.federation.peer_count and value.source_count > 0, "runtime source count equals federation peer count", (value.content_address,)),
        _check(2, "federation-link", value.consensus.federation_address == value.federation.content_address and value.report.federation_address == value.federation.content_address, "runtime consumers link to the federation", evidence),
        _check(3, "federation-audit-link", value.federation_audit.federation_address == value.federation.content_address, "federation audit links to the federation", (value.federation_audit.content_address, value.federation.content_address)),
        _check(4, "consensus-link", value.report.consensus_address == value.consensus.content_address, "report links to consensus", (value.report.content_address, value.consensus.content_address)),
        _check(5, "consensus-audit-link", value.consensus_audit.consensus_address == value.consensus.content_address, "consensus audit links to consensus", (value.consensus_audit.content_address, value.consensus.content_address)),
        _check(6, "report-link", value.report.federation_audit_address == value.federation_audit.content_address and value.report.consensus_audit_address == value.consensus_audit.content_address, "report retains both independent audits", (value.report.content_address, value.federation_audit.content_address, value.consensus_audit.content_address)),
        _check(7, "outcome-link", value.accepted == value.report.accepted and value.state == value.report.status, "runtime outcome replays from the report", (value.content_address, value.report.content_address)),
        _check(8, "public-boundary", _public(value.to_dict()), "runtime contains only public evidence", (value.content_address,)),
        _check(9, "runtime-address", runtime_model.address_runtime(value) == value.content_address, "runtime content address replays", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit(value.runtime_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit(provisional.runtime_id, provisional.runtime_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit):
        raise ValidationError("federation runtime audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("federation runtime audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Runtime Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit.FIELDS), "properties": {"runtime_id": {"type": "string"}, "runtime_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "independent": True, "operations": ("audit_runtime", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntimeAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
