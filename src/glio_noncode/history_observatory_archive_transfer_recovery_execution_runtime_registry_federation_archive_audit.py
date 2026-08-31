"""Independent assurance for runtime-registry federation archives."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = archive_model.VERSION + "-audit-v1"
BOUNDARY = archive_model.BOUNDARY + "_audit"
AUDIT_PREFIX = archive_model.ARCHIVE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
MAX_CHECKS = 18
CHECK_IDS = ("version", "boundary", "archive-address", "archive-identity", "artifact-count", "file-order", "artifact-order", "artifact-receipts", "manifest-linkage", "federation-load", "federation-identity", "federation-projection", "archive-size", "zip-safety", "deterministic-bytes", "public-boundary", "mapping-round-trip", "byte-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("archive_id", "archive_address", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 1024)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return archive_model._public(value)


class RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "archive audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "archive audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("archive audit check ID is unsupported")
        self.passed = _bool(passed, "archive audit check result")
        self.detail = _text(detail, "archive audit check detail", 2048)
        self.evidence_addresses = tuple(_address(item, "archive audit evidence address", allow_pending=True) for item in _sequence(evidence_addresses, "archive audit evidence addresses", 64))
        self.content_address = _address(content_address, "archive audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("archive audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("archive audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck":
        value = _mapping(value, "archive audit check")
        _strict(value, set(cls.FIELDS), "archive audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck):
        raise ValidationError("archive audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RecoveryExecutionRuntimeRegistryFederationArchiveAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, archive_id: str, archive_address: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.archive_id = _label(archive_id, "archive audit archive ID")
        self.archive_address = _address(archive_address, "archive audit archive address", archive_model.ARCHIVE_PREFIX)
        self.version = _text(version, "archive audit version", 2048)
        self.boundary = _text(boundary, "archive audit boundary", 2048)
        self.check_count = _count(check_count, "archive audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "archive audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "archive audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "archive audit acceptance")
        self.checks = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck) else RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck.from_mapping(item) for item in _sequence(checks, "archive audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "archive audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("archive audit conservation or ordering does not replay")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks):
            raise ValidationError("archive audit result counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("archive audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("archive audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"archive_id": self.archive_id, "archive_address": self.archive_address, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("archive_id", "archive_address", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationArchiveAudit":
        value = _mapping(value, "archive audit")
        _strict(value, set(cls.FIELDS), "archive audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RecoveryExecutionRuntimeRegistryFederationArchiveAudit) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationArchiveAudit):
        raise ValidationError("archive audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def audit_archive(value: archive_model.RecoveryExecutionRuntimeRegistryFederationArchive) -> RecoveryExecutionRuntimeRegistryFederationArchiveAudit:
    if not isinstance(value, archive_model.RecoveryExecutionRuntimeRegistryFederationArchive):
        raise ValidationError("archive audit requires a typed archive")
    checks: list[RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck] = []

    def add(check_id: str, passed: bool, detail: str, evidence: Sequence[str] = ()) -> None:
        provisional = RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck(len(checks) + 1, check_id, bool(passed), detail, evidence, CHECK_PREFIX + ":pending")
        checks.append(RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional)))

    raw: Mapping[str, bytes] | None = None
    try:
        raw = value.embedded_bytes()
    except ValidationError:
        raw = None
    add("version", value.version == archive_model.VERSION, "archive version replays from the archive contract", (value.content_address,))
    add("boundary", value.boundary == archive_model.BOUNDARY, "archive boundary replays from the archive contract", (value.content_address,))
    add("archive-address", archive_model.address_archive(value) == value.content_address, "archive address replays from the public envelope", (value.content_address,))
    add("archive-identity", bool(value.archive_id) and bool(value.federation_id) and value.federation_address.startswith(federation_model_prefix()), "archive and nested federation identities are present", (value.content_address, value.federation_address))
    add("artifact-count", value.artifact_count == len(archive_model.EMBEDDED_FILES) == len(value.artifacts), "artifact count is conserved", (value.content_address,))
    add("file-order", value.files == archive_model.EMBEDDED_FILES, "embedded file order matches the exact vocabulary", (value.content_address,))
    add("artifact-order", tuple(item.index for item in value.artifacts) == tuple(range(len(archive_model.EMBEDDED_FILES))) and tuple(item.name for item in value.artifacts) == archive_model.EMBEDDED_FILES, "artifact indices and names are contiguous", tuple(item.hash for item in value.artifacts))
    receipt_ok = raw is not None and all(len(raw[item.name]) == item.size and archive_model.hash_bytes(raw[item.name], prefix=archive_model.ARTIFACT_PREFIX) == item.hash for item in value.artifacts)
    add("artifact-receipts", receipt_ok, "every embedded byte receipt replays", tuple(item.hash for item in value.artifacts))
    manifest_ok = False
    if raw is not None:
        try:
            archive_raw, _ = archive_model._read_archive_bytes(archive_model.archive_bytes(value))
            manifest_ok = archive_raw[archive_model.ARCHIVE_MANIFEST_NAME] == canonical_bytes(archive_model.manifest_document(value))
        except (ValidationError, KeyError):
            manifest_ok = False
    add("manifest-linkage", manifest_ok, "outer manifest bytes and address replay", (value.content_address,))
    add("federation-load", value.federation is not None, "the embedded federation is decoded and verified", (value.federation_address,))
    federation_ok = value.federation is not None and value.federation.content_address == value.federation_address and value.federation.federation_id == value.federation_id
    add("federation-identity", federation_ok, "nested federation identity links to the envelope", (value.federation_address,))
    projection_ok = False
    if raw is not None and value.federation is not None:
        try:
            projection_ok = dict(raw) == archive_model._embedded_federation(value.federation)
        except (ValidationError, KeyError):
            projection_ok = False
    add("federation-projection", projection_ok, "all five nested federation projections replay", (value.federation_address,))
    size_ok = False
    if raw is not None:
        try:
            size_ok = len(archive_model.archive_bytes(value)) == value.archive_size
        except ValidationError:
            size_ok = False
    add("archive-size", size_ok, "physical ZIP size replays from the envelope", (value.content_address,))
    safety_ok = False
    if raw is not None:
        try:
            decoded, physical_size = archive_model._read_archive_bytes(archive_model.archive_bytes(value))
            safety_ok = physical_size == value.archive_size and tuple(decoded) == archive_model.FILES
        except ValidationError:
            safety_ok = False
    add("zip-safety", safety_ok, "ZIP member order and safety rules replay", (value.content_address,))
    deterministic_ok = False
    if raw is not None:
        try:
            deterministic_ok = archive_model.archive_bytes(value) == archive_model.archive_bytes(value)
        except ValidationError:
            deterministic_ok = False
    add("deterministic-bytes", deterministic_ok, "equal public archive inputs yield identical bytes", (value.content_address,))
    add("public-boundary", _public(value.to_dict()), "archive projection contains only bounded public fields", (value.content_address,))
    mapping_ok = False
    try:
        mapping_ok = archive_model.archive_from_mapping(value.to_dict()).content_address == value.content_address
    except ValidationError:
        mapping_ok = False
    add("mapping-round-trip", mapping_ok, "public archive mapping rehydrates to the same address", (value.content_address,))
    byte_ok = False
    if raw is not None:
        try:
            byte_ok = archive_model.load_archive_bytes(archive_model.archive_bytes(value)).content_address == value.content_address
        except ValidationError:
            byte_ok = False
    add("byte-round-trip", byte_ok, "serialized archive bytes reload to the same address", (value.content_address,))
    passed_count = sum(item.passed for item in checks)
    provisional = RecoveryExecutionRuntimeRegistryFederationArchiveAudit(value.archive_id, value.content_address, VERSION, BOUNDARY, len(checks), passed_count, len(checks) - passed_count, passed_count == len(checks), checks, AUDIT_PREFIX + ":pending")
    return RecoveryExecutionRuntimeRegistryFederationArchiveAudit(provisional.archive_id, provisional.archive_address, provisional.version, provisional.boundary, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, provisional.checks, address_audit(provisional))


def federation_model_prefix() -> str:
    return archive_model.federation_model.FEDERATION_PREFIX


def audit_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryFederationArchiveAudit:
    return RecoveryExecutionRuntimeRegistryFederationArchiveAudit.from_mapping(value)


def verify_audit(value: RecoveryExecutionRuntimeRegistryFederationArchiveAudit) -> RecoveryExecutionRuntimeRegistryFederationArchiveAudit:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationArchiveAudit):
        raise ValidationError("archive audit verification requires a typed audit")
    value._validate()
    if not value.accepted:
        raise ValidationError("archive audit contains failed checks")
    return value


def audit_json(value: RecoveryExecutionRuntimeRegistryFederationArchiveAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: RecoveryExecutionRuntimeRegistryFederationArchiveAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address"))
    for item in value.checks:
        writer.writerow((item.ordinal, item.check_id, item.passed, item.detail, "|".join(item.evidence_addresses), item.content_address))
    return output.getvalue()


def render_audit_markdown(value: RecoveryExecutionRuntimeRegistryFederationArchiveAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Runtime Registry Federation Archive Audit", "", f"- Archive: `{value.archive_id}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime registry federation archive audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime registry federation archive audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"archive_id": {"type": "string"}, "archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_count": MAX_CHECKS, "check_ids": list(CHECK_IDS), "operations": ["audit_archive", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"], "privacy": {"values": False, "source_paths": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "MAX_CHECKS", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "RecoveryExecutionRuntimeRegistryFederationArchiveAuditCheck", "RecoveryExecutionRuntimeRegistryFederationArchiveAudit", "address_check", "address_audit", "audit_archive", "audit_from_mapping", "verify_audit", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
