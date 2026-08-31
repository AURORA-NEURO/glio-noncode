"""Independent audit receipts for history-diff recovery runtime registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_runtime as runtime_model
from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-audit-v1"
BOUNDARY = registry_model.BOUNDARY + "_audit"
AUDIT_PREFIX = registry_model.REGISTRY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "registry-address", "entry-count", "entry-order", "entry-addresses", "identity-uniqueness", "runtime-linkage", "state-replay", "count-replay", "acceptance-replay", "summary-linkage", "entries-linkage", "manifest-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("registry_address", "registry_id", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry audit check ordinal", MAX_CHECKS, lower=1)
        if check_id not in CHECK_IDS:
            raise ValidationError("runtime registry audit check ID is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "runtime registry audit check result")
        self.detail = _text(detail, "runtime registry audit check detail")
        self.evidence_addresses = tuple(_address(item, "runtime registry audit evidence address") for item in _sequence(evidence_addresses, "runtime registry audit evidence addresses", 64))
        self.content_address = _address(content_address, "runtime registry audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime registry audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck:
        value = _mapping(value, "runtime registry audit check")
        _strict(value, set(cls.FIELDS), "runtime registry audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck):
        raise ValidationError("runtime registry audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, registry_address: str, registry_id: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.registry_address = _address(registry_address, "runtime registry audit registry address", registry_model.REGISTRY_PREFIX)
        self.registry_id = _label(registry_id, "runtime registry audit registry ID")
        self.version = _text(version, "runtime registry audit version", 1024)
        self.boundary = _text(boundary, "runtime registry audit boundary", 1024)
        self.check_count = _count(check_count, "runtime registry audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry audit acceptance")
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime registry audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "runtime registry audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry audit does not replay checks")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime registry audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit:
        value = _mapping(value, "runtime registry audit")
        _strict(value, set(cls.FIELDS), "runtime registry audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit):
        raise ValidationError("runtime registry audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck:
    body = {"ordinal": CHECK_IDS.index(check_id) + 1, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_registry(value: registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit:
    value = registry_model.verify_registry(value)
    entries = value.entries
    keys = tuple((item.runtime_id, item.runtime_address) for item in entries)
    expected_state = "empty" if not entries else "ready" if all(item.accepted for item in entries) else "blocked"
    expected_counts = (sum(item.accepted for item in entries), sum(item.state == "ready" for item in entries), sum(item.state == "blocked" for item in entries))
    checks = (
        _check("version", value.version == registry_model.VERSION, "registry version is current", (value.content_address,)),
        _check("boundary", value.boundary == registry_model.BOUNDARY, "registry boundary is current", (value.content_address,)),
        _check("registry-address", registry_model.address_registry(value) == value.content_address, "registry address replays", (value.content_address,)),
        _check("entry-count", value.entry_count == len(entries), "entry count matches entries", (value.summary.content_address,)),
        _check("entry-order", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)) and keys == tuple(sorted(keys)), "entry ordinals and identities are ordered", tuple(item.content_address for item in entries)),
        _check("entry-addresses", all(registry_model.address_entry(item) == item.content_address for item in entries), "entry addresses replay", tuple(item.content_address for item in entries)),
        _check("identity-uniqueness", len(keys) == len(set(keys)), "runtime identities are unique", tuple(item.runtime_address for item in entries)),
        _check("runtime-linkage", all(item.runtime_version == runtime_model.VERSION and item.runtime_address.startswith(runtime_model.RUNTIME_PREFIX + ":") for item in entries), "entries retain history-diff runtime linkage", tuple(item.runtime_address for item in entries)),
        _check("state-replay", value.state == expected_state, "registry state folds entry acceptance", (value.summary.content_address,)),
        _check("count-replay", (value.accepted_count, value.ready_count, value.blocked_count) == expected_counts, "registry counts conserve entry states", (value.summary.content_address,)),
        _check("acceptance-replay", value.accepted == (not entries or value.accepted_count == value.entry_count), "registry acceptance folds all entries", (value.content_address,)),
        _check("summary-linkage", value.summary.to_dict() == {"registry_id": value.registry_id, "entry_count": value.entry_count, "accepted_count": value.accepted_count, "ready_count": value.ready_count, "blocked_count": value.blocked_count, "state": value.state, "accepted": value.accepted, "content_address": value.summary.content_address}, "summary mirrors registry", (value.summary.content_address,)),
        _check("entries-linkage", registry_model.address_entries(entries) == value.manifest.artifact_addresses[0], "entries projection address links through manifest", (value.manifest.artifact_addresses[0],)),
        _check("manifest-linkage", value.manifest.registry_id == value.registry_id and value.manifest.files == registry_model.FILES and registry_model.address_manifest(value.manifest) == value.manifest.content_address, "manifest files and address replay", (value.manifest.content_address,)),
        _check("public-boundary", _public(value.to_dict()), "registry projection is value-free and public", (value.content_address,)),
        _check("mapping-round-trip", registry_model.registry_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "registry mapping round trip is stable", (value.content_address,)),
    )
    body = {"registry_address": value.content_address, "registry_id": value.registry_id, "version": VERSION, "boundary": BOUNDARY, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit(**(body | {"content_address": address_audit(provisional)}))


def verify_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit):
        raise ValidationError("runtime registry audit verification requires a typed audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit.from_mapping(value)


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit) -> str:
    value = verify_audit(value)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address"))
    for item in value.checks:
        writer.writerow((item.ordinal, item.check_id, item.passed, item.detail, json.dumps(item.evidence_addresses, ensure_ascii=False), item.content_address))
    return output.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit) -> str:
    value = verify_audit(value)
    lines = ["# History-Diff Archive Transfer Recovery Execution Runtime Registry Audit", "", f"- Registry: `{value.registry_id}`", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"registry_address": {"type": "string"}, "registry_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": MAX_CHECKS, "operations": ("audit_registry", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAuditCheck", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryAudit", "address_check", "address_audit", "audit_registry", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
