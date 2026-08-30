"""Independent audit for the certificate-observatory archive runtime receipt."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_audit as archive_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_query as query_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_query_audit as query_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_runtime as runtime_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_transfer as transfer_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_transfer_audit as transfer_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_package as package_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = ("runtime-address", "input-count", "package-address", "archive-address", "archive-audit-link", "query-address", "query-audit-link", "transfer-address", "transfer-audit-link", "persistence-flags", "acceptance-shape", "mapping-round-trip", "public-boundary")


def _text(value: Any, field: str, maximum: int = 2048) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field)
    if ":" not in value or "/" in value or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return archive_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1 or ordinal > len(CHECK_IDS) or check_id not in CHECK_IDS:
            raise ValidationError("runtime audit finding identity is invalid")
        self.ordinal, self.check_id = ordinal, check_id
        self.passed = _bool(passed, "runtime finding pass state")
        self.detail = _text(detail, "runtime finding detail")
        self.evidence_address = _text(evidence_address, "runtime finding evidence")
        self.content_address = _address(content_address, "runtime finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("runtime finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAuditFinding":
        value = _mapping(value, "runtime finding")
        _strict(value, set(cls.FIELDS), "runtime finding")
        return cls(*(value[field] for field in cls.FIELDS))


class RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit:
    FIELDS = ("runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, runtime_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(checks)
        self.check_count, self.passed_count, self.failed_count = _count(check_count, "runtime check count", len(CHECK_IDS)), _count(passed_count, "runtime passed count", len(CHECK_IDS)), _count(failed_count, "runtime failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "runtime audit acceptance")
        self.content_address = _address(content_address, "runtime audit address", AUDIT_PREFIX)
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("runtime audit checks are not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("runtime_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAuditFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, detail: str, evidence: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAuditFinding(ordinal, check_id, passed, detail, evidence, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAuditFinding(ordinal, check_id, passed, detail, evidence, address_finding(provisional))


def audit_runtime(value: runtime_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit:
    if not isinstance(value, runtime_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime):
        raise ValidationError("runtime audit requires a typed runtime")
    runtime_model.verify_runtime(value)
    mapping_ok = runtime_model.runtime_from_mapping(value.to_dict()).to_dict() == value.to_dict()
    flags_ok = isinstance(value.archive_written, bool) and isinstance(value.transfer_written, bool) and isinstance(value.accepted, bool)
    acceptance_ok = value.accepted in (True, False)
    checks = (
        _finding(1, "runtime-address", runtime_model.address_runtime(value) == value.content_address, "runtime address reproduces", value.content_address),
        _finding(2, "input-count", value.input_count > 0, "at least one input package was processed", value.package_address),
        _finding(3, "package-address", value.package_address.startswith(package_model.PACKAGE_PREFIX + ":"), "runtime links a certificate observatory package", value.package_address),
        _finding(4, "archive-address", value.archive_address.startswith(archive_model.ARCHIVE_PREFIX + ":"), "runtime links an archive", value.archive_address),
        _finding(5, "archive-audit-link", value.archive_audit_address.startswith(archive_audit_model.AUDIT_PREFIX + ":"), "runtime links the archive audit", value.archive_audit_address),
        _finding(6, "query-address", value.query_address.startswith(query_model.RESULT_PREFIX + ":"), "runtime links the archive query result", value.query_address),
        _finding(7, "query-audit-link", value.query_audit_address.startswith(query_audit_model.AUDIT_PREFIX + ":"), "runtime links the query audit", value.query_audit_address),
        _finding(8, "transfer-address", value.transfer_address.startswith(transfer_model.TRANSFER_PREFIX + ":"), "runtime links the transfer", value.transfer_address),
        _finding(9, "transfer-audit-link", value.transfer_audit_address.startswith(transfer_audit_model.AUDIT_PREFIX + ":"), "runtime links the transfer audit", value.transfer_audit_address),
        _finding(10, "persistence-flags", flags_ok, "persistence options are explicit booleans", value.content_address),
        _finding(11, "acceptance-shape", acceptance_ok, "runtime acceptance is an explicit decision value", value.content_address),
        _finding(12, "mapping-round-trip", mapping_ok, "runtime receipt replays through its mapping form", value.content_address),
        _finding(13, "public-boundary", _public(value.to_dict()), "runtime receipt contains only public values", value.content_address),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit(provisional.runtime_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit:
    value = _mapping(value, "runtime audit")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit.FIELDS), "runtime audit")
    checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAuditFinding.from_mapping(item) for item in _sequence(value["checks"], "runtime audit checks", len(CHECK_IDS)))
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit(value["runtime_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"]))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("runtime audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow({key: item.to_dict()[key] for key in writer.fieldnames})
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Archive Runtime Audit", "", f"- Runtime: `{value.runtime_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit.FIELDS), "properties": {"runtime_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent runtime link audit", "explicit persistence flag checks", "mapping replay", "public-boundary validation", "addressable findings", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRuntimeAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
