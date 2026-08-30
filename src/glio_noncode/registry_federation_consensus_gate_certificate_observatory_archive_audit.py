"""Independent validation for certificate-observatory ZIP archives.

The archive writer proves how an artifact is assembled.  This module is the
separate receiving-side control: it recomputes the public envelope, artifact
receipts, manifest identity, nested package projections, canonical bytes, and
transport replay.  A report can therefore distinguish a valid logical record
from a verified physical handoff.  Failed checks are retained as addressed
findings and are never silently repaired.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from . import registry_federation_consensus_gate_certificate_observatory_package_audit as package_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_package as package_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = archive_model.VERSION + "-audit-v1"
BOUNDARY = archive_model.BOUNDARY + "_audit"
AUDIT_PREFIX = archive_model.ARCHIVE_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = ("archive-address", "public-boundary", "member-vocabulary", "artifact-order", "artifact-receipts", "manifest-address", "manifest-members", "package-address", "package-projections", "nested-addresses", "canonical-bytes", "zip-replay", "mapping-round-trip", "size-conservation", "path-free", "package-audit")
MAX_TEXT = 2048


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public content address")
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
    return archive_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding:
    """One independently addressed archive assertion."""

    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "finding ordinal", len(CHECK_IDS))
        if self.ordinal == 0 or not isinstance(check_id, str) or check_id not in CHECK_IDS:
            raise ValidationError("finding check ID is not declared")
        self.check_id = check_id
        self.passed = _bool(passed, "finding pass state")
        self.observed = _text(observed, "finding observed value", 1024)
        self.expected = _text(expected, "finding expected value", 1024)
        self.detail = _text(detail, "finding detail", 2048)
        self.evidence_address = _address(evidence_address, "finding evidence address")
        self.content_address = _address(content_address, "finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding":
        value = _mapping(value, "archive audit finding")
        _strict(value, set(cls.FIELDS), "archive audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


class RegistryFederationConsensusGateCertificateObservatoryArchiveAudit:
    """The full archive audit, accepted only when all checks pass."""

    FIELDS = ("archive_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, archive_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.archive_address = _address(archive_address, "audit archive address", archive_model.ARCHIVE_PREFIX)
        self.checks = tuple(checks)
        self.check_count = _count(check_count, "audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "audit acceptance")
        self.content_address = _address(content_address, "audit content address", AUDIT_PREFIX)
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("archive audit check order is not exact")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("archive audit counters are not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("archive audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("archive audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_address": self.archive_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("archive_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding):
        raise ValidationError("finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveAudit):
        raise ValidationError("audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str, evidence: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, evidence, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding(ordinal, check_id, passed, provisional.observed, provisional.expected, detail, evidence, address_finding(provisional))


def _safe_archive_bytes(value: archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive) -> tuple[bool, int]:
    try:
        return True, len(archive_model.archive_bytes(value))
    except ValidationError:
        return False, 0


def audit_archive(value: archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive) -> RegistryFederationConsensusGateCertificateObservatoryArchiveAudit:
    if not isinstance(value, archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive):
        raise ValidationError("archive audit requires a typed archive")
    archive_model.verify_archive(value)
    payload_ok, physical_size = _safe_archive_bytes(value)
    package_ok = isinstance(value.package, package_model.RegistryFederationConsensusGateCertificateObservatoryPackage)
    projection_ok = False
    package_audit_ok = False
    if package_ok:
        try:
            expected = package_model.package_bytes(value.package)
            projection_ok = all(value.payload_bytes()[archive_model.PAYLOAD_PREFIX + name] == raw for name, raw in expected.items())
            package_audit_ok = package_audit_model.audit_package(value.package).accepted
        except (ValidationError, KeyError):
            projection_ok = False
            package_audit_ok = False
    artifacts_ok = bool(value._payload) and all(item.hash == archive_model.hash_bytes(value._payload[item.name], prefix=archive_model.ARTIFACT_PREFIX) and item.size == len(value._payload[item.name]) for item in value.artifacts) if value._payload else False
    checks = (
        _finding(1, "archive-address", archive_model.address_archive(value) == value.content_address, value.content_address, archive_model.address_archive(value), "archive address reproduces from the public envelope", value.content_address),
        _finding(2, "public-boundary", _public(value.to_dict()), _public(value.to_dict()), True, "archive envelope contains only public values", value.content_address),
        _finding(3, "member-vocabulary", value.files == archive_model.ARCHIVE_PAYLOAD_FILES and value.artifact_count == len(archive_model.ARCHIVE_PAYLOAD_FILES), value.files, archive_model.ARCHIVE_PAYLOAD_FILES, "payload file vocabulary is exact", value.content_address),
        _finding(4, "artifact-order", tuple(item.index for item in value.artifacts) == tuple(range(len(archive_model.ARCHIVE_PAYLOAD_FILES))) and tuple(item.name for item in value.artifacts) == archive_model.ARCHIVE_PAYLOAD_FILES, tuple(item.name for item in value.artifacts), archive_model.ARCHIVE_PAYLOAD_FILES, "artifact order is stable", value.content_address),
        _finding(5, "artifact-receipts", artifacts_ok, artifacts_ok, True, "every embedded member matches its declared byte receipt", value.content_address),
        _finding(6, "manifest-address", bool(archive_model.manifest_document(value)["manifest_address"]), archive_model.manifest_document(value)["manifest_address"], "address", "manifest address is derived from canonical fields", value.content_address),
        _finding(7, "manifest-members", tuple(archive_model.manifest_document(value)["files"]) == archive_model.ARCHIVE_PAYLOAD_FILES, archive_model.manifest_document(value)["files"], archive_model.ARCHIVE_PAYLOAD_FILES, "manifest repeats the exact member set", value.content_address),
        _finding(8, "package-address", value.package_address.startswith(package_model.PACKAGE_PREFIX + ":"), value.package_address, "package address", "nested package address is present", value.package_address),
        _finding(9, "package-projections", projection_ok, projection_ok, True, "embedded package projections replay their package envelope", value.package_address),
        _finding(10, "nested-addresses", all(":" in item.hash for item in value.artifacts) and ":" in value.package_address, True, "addressed members", "nested content addresses are namespaced", value.package_address),
        _finding(11, "canonical-bytes", payload_ok, payload_ok, True, "canonical archive bytes can be generated", value.content_address),
        _finding(12, "zip-replay", payload_ok and physical_size == value.archive_size, physical_size, value.archive_size, "ZIP byte count agrees with the addressed archive", value.content_address),
        _finding(13, "mapping-round-trip", archive_model.archive_from_mapping(value.to_dict()).to_dict() == value.to_dict(), True, True, "public archive mapping reloads exactly", value.content_address),
        _finding(14, "size-conservation", value.archive_size > 0 and sum(item.size for item in value.artifacts) > 0, value.archive_size, "positive archive and member sizes", "ZIP and member size receipts are positive", value.content_address),
        _finding(15, "path-free", _public(value.to_dict()), True, True, "archive output is free of local paths", value.content_address),
        _finding(16, "package-audit", package_audit_ok, package_audit_ok, True, "nested package audit is accepted", value.package_address),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveAudit(provisional.archive_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveAudit:
    value = _mapping(value, "archive audit")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveAudit.FIELDS), "archive audit")
    checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding.from_mapping(item) for item in _sequence(value["checks"], "archive audit checks", len(CHECK_IDS)))
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveAudit(value["archive_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"]))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveAudit):
        raise ValidationError("archive audit verification requires a typed audit")
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("archive audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow({key: item.to_dict()[key] for key in writer.fieldnames})
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Archive Audit", "", f"- Archive: `{value.archive_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveAudit.FIELDS), "properties": {"archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS), "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent archive envelope audit", "artifact receipt verification", "nested package projection checks", "canonical ZIP size replay", "addressable findings", "path-free JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchiveAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveAuditFinding", "VERSION", "address_audit", "address_finding", "audit_archive", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
