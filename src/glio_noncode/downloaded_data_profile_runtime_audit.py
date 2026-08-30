"""Independent assurance for downloaded-data profile runtime closures."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-runtime-audit-v1"
BOUNDARY = "public_downloaded_data_profile_runtime_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-runtime-audit"
CHECK_IDS = (
    "version",
    "boundary",
    "manifest-files",
    "manifest-address",
    "batch-linkage",
    "profile-audit",
    "query-linkage",
    "query-audit",
    "aggregate-state",
    "release-readiness",
    "runtime-address",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileRuntimeAuditCheck:
    """One independent runtime-closure finding."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "profile runtime audit ordinal", len(CHECK_IDS))
        if self.ordinal == 0:
            raise ValidationError("profile runtime audit ordinal must be positive")
        self.check_id = _label(check_id, "profile runtime audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("profile runtime audit check ID is unsupported")
        self.passed = _bool(passed, "profile runtime audit result")
        self.detail = _text(detail, "profile runtime audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "profile runtime audit evidence address") for item in _sequence(evidence_addresses, "profile runtime audit evidence", 16))
        self.content_address = _address(content_address, "profile runtime audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "profile runtime audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("profile runtime audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("profile runtime audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileRuntimeAuditCheck:
        value = _mapping(value, "profile runtime audit check")
        _strict(value, set(cls.FIELDS), "profile runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileRuntimeAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataProfileRuntimeAudit:
    """Fixed-size independent audit for the profile runtime closure."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_address: str, checks: Sequence[DownloadedDataProfileRuntimeAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "profile runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileRuntimeAuditCheck) else DownloadedDataProfileRuntimeAuditCheck.from_mapping(item) for item in _sequence(checks, "profile runtime audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "profile runtime audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "profile runtime audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "profile runtime audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "profile runtime audit acceptance")
        self.content_address = _address(content_address, "profile runtime audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "profile runtime audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("profile runtime audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("profile runtime audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileRuntimeAudit:
        value = _mapping(value, "profile runtime audit")
        _strict(value, set(cls.FIELDS), "profile runtime audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileRuntimeAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileRuntimeAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:16]}
    provisional = DownloadedDataProfileRuntimeAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataProfileRuntimeAuditCheck(**body, content_address=address_check(provisional))


def audit_runtime(value: runtime_model.DownloadedDataProfileRuntime) -> DownloadedDataProfileRuntimeAudit:
    """Audit component links and derived readiness without reading source values."""

    if not isinstance(value, runtime_model.DownloadedDataProfileRuntime):
        raise ValidationError("profile runtime audit requires a typed runtime")
    evidence = (value.content_address, value.manifest.content_address, value.batch_address)
    checks = (
        _check(1, "version", value.version == runtime_model.VERSION, "profile runtime version is current", evidence),
        _check(2, "boundary", value.boundary == runtime_model.BOUNDARY, "profile runtime boundary is public", evidence),
        _check(3, "manifest-files", value.manifest.files == runtime_model.FILES and len(value.manifest.artifact_addresses) == len(runtime_model.MANIFEST_ARTIFACT_FILES), "manifest closes the exact profile runtime file set", (value.manifest.content_address,)),
        _check(4, "manifest-address", runtime_model.address_manifest(value.manifest) == value.manifest.content_address, "profile runtime manifest address replays", (value.manifest.content_address,)),
        _check(5, "batch-linkage", value.batch_address == value.profile.batch_address and value.profile.batch_address.startswith(ingestion_model.INGEST_PREFIX + ":"), "profile retains the ingestion batch linkage", (value.batch_address, value.profile_address)),
        _check(6, "profile-audit", value.audit.profile_address == value.profile_address and value.audit.accepted, "profile audit closes the structural profile", (value.audit_address, value.profile_address)),
        _check(7, "query-linkage", value.query.profile_address == value.profile_address and value.query_address == value.query.content_address, "profile query links to the same profile", (value.query_address, value.profile_address)),
        _check(8, "query-audit", value.query_audit.query_address == value.query_address and value.query_audit.accepted, "profile query audit closes the query", (value.query_audit_address, value.query_address)),
        _check(9, "aggregate-state", value.record_count == value.profile.record_count and value.member_count == value.profile.member_count and value.field_count == value.profile.field_count, "runtime aggregates replay profile aggregates", evidence),
        _check(10, "release-readiness", value.accepted == (value.audit.accepted and value.query_audit.accepted) and value.release_ready == value.accepted and value.state == ("complete" if value.release_ready else "incomplete"), "runtime readiness is derived from accepted component closure", evidence),
        _check(11, "runtime-address", runtime_model.address_runtime(value) == value.content_address, "profile runtime address replays", (value.content_address,)),
        _check(12, "mapping-round-trip", runtime_model.runtime_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "profile runtime mapping round-trips without projection drift", evidence),
    )
    body = {"runtime_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataProfileRuntimeAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileRuntimeAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileRuntimeAudit:
    return DownloadedDataProfileRuntimeAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileRuntimeAudit) -> str:
    return canonical_json(DownloadedDataProfileRuntimeAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileRuntimeAudit) -> str:
    value = DownloadedDataProfileRuntimeAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileRuntimeAudit) -> str:
    value = DownloadedDataProfileRuntimeAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Runtime Audit", "", f"- Runtime: `{value.runtime_address}`", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile runtime audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile runtime audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"runtime_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_runtime", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown")}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataProfileRuntimeAudit", "DownloadedDataProfileRuntimeAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
