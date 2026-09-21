"""Independent replay audit for diff-runtime admission registries."""
from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d269_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-audit-v1"
BOUNDARY = registry_model.BOUNDARY + "_audit"
AUDIT_PREFIX = registry_model.REGISTRY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("registry_identity", "entry_order", "entry_addresses", "duplicate_identity", "duplicate_addresses", "state_counters", "summary_replay", "manifest_replay", "disposition", "runtime_links", "diff_links", "readiness_fold", "accepted_fold", "registry_address", "public_boundary", "bounds")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("registry_id", "registry_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff runtime registry audit check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "diff runtime registry audit check ID"); self.passed = _bool(passed, "diff runtime registry audit check result"); self.actual = _text(canonical_json(actual), "diff runtime registry audit actual", 16384); self.expected = _text(canonical_json(expected), "diff runtime registry audit expected", 16384); self.detail = _text(detail, "diff runtime registry audit detail", 4096); self.content_address = _address(content_address, "diff runtime registry audit check address", CHECK_PREFIX); self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS: raise ValidationError("diff runtime registry audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("diff runtime registry audit check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("diff runtime registry audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "diff runtime registry audit check"); _strict(value, set(cls.FIELDS), "diff runtime registry audit check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck): raise ValidationError("diff runtime registry audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class RegistryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, registry_id: str, registry_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.registry_id = _label(registry_id, "diff runtime registry audit registry ID"); self.registry_address = _address(registry_address, "diff runtime registry audit registry address", registry_model.REGISTRY_PREFIX); self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "diff runtime registry audit check")) for item in _sequence(checks, "diff runtime registry audit checks", MAX_CHECKS)); self.check_count = _count(check_count, "diff runtime registry audit check count", MAX_CHECKS); self.passed_count = _count(passed_count, "diff runtime registry audit passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "diff runtime registry audit failed count", MAX_CHECKS); self.accepted = _bool(accepted, "diff runtime registry audit acceptance"); self.content_address = _address(content_address, "diff runtime registry audit address", AUDIT_PREFIX); self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0): raise ValidationError("diff runtime registry audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("diff runtime registry audit check order does not replay")
        if any(item.content_address != address_check(item) for item in self.checks): raise ValidationError("diff runtime registry audit check addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address: raise ValidationError("diff runtime registry audit address does not replay")
        if not _public(self.to_dict()): raise ValidationError("diff runtime registry audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryAudit":
        value = _mapping(value, "diff runtime registry audit"); _strict(value, set(cls.FIELDS), "diff runtime registry audit"); return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RegistryAudit) -> str:
    if not isinstance(value, RegistryAudit): raise ValidationError("diff runtime registry audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    return AuditCheck(ordinal, check_id, passed, actual, expected, detail, f"pending:{CHECK_PREFIX}")


def audit_registry(value: registry_model.RuntimeRegistry) -> RegistryAudit:
    registry_model.verify_registry(value); entries = value.entries; ready = sum(item.state == "ready" for item in entries); blocked = sum(item.state == "blocked" for item in entries)
    checks = (
        _finding(1, "registry_identity", value.registry_id == value.summary.registry_id and value.registry_id == value.manifest.registry_id, value.registry_id, value.summary.registry_id, "registry identity must replay"),
        _finding(2, "entry_order", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), tuple(item.ordinal for item in entries), "contiguous ordinals", "entry order must replay"),
        _finding(3, "entry_addresses", all(item.content_address == registry_model.address_entry(item) for item in entries), "replayed", "canonical", "entry addresses must replay"),
        _finding(4, "duplicate_identity", len({item.runtime_id for item in entries}) == len(entries), tuple(item.runtime_id for item in entries), "unique runtime IDs", "runtime identities must be unique"),
        _finding(5, "duplicate_addresses", len({item.runtime_address for item in entries}) == len(entries), tuple(item.runtime_address for item in entries), "unique runtime addresses", "runtime addresses must be unique"),
        _finding(6, "state_counters", (value.ready_count, value.blocked_count) == (ready, blocked), (value.ready_count, value.blocked_count), (ready, blocked), "state counters must replay"),
        _finding(7, "summary_replay", value.summary.content_address == registry_model.address_summary(value.summary), value.summary.content_address, registry_model.address_summary(value.summary), "summary address must replay"),
        _finding(8, "manifest_replay", value.manifest.content_address == registry_model.address_manifest(value.manifest) and value.manifest.artifact_addresses == (registry_model.address_entries(entries), value.summary.content_address), value.manifest.artifact_addresses, (registry_model.address_entries(entries), value.summary.content_address), "manifest must replay"),
        _finding(9, "disposition", (value.state, value.release_ready, value.accepted) == (("empty" if not entries else "ready" if not blocked else "blocked"), bool(entries and not blocked), bool(entries)), (value.state, value.release_ready, value.accepted), "folded disposition", "registry disposition must replay"),
        _finding(10, "runtime_links", all(item.runtime_address.startswith(registry_model.runtime_model.RUNTIME_PREFIX + ":") and item.check_count >= item.passed_count for item in entries), "canonical", "runtime links", "runtime links must remain bounded"),
        _finding(11, "diff_links", all(item.diff_address.startswith(registry_model.runtime_model.diff_model.DIFF_PREFIX + ":") and bool(item.diff_id) for item in entries), "canonical", "diff links", "diff links must remain canonical"),
        _finding(12, "readiness_fold", value.release_ready == (bool(entries) and blocked == 0), value.release_ready, bool(entries) and blocked == 0, "readiness must fold from entries"),
        _finding(13, "accepted_fold", value.accepted == bool(entries), value.accepted, bool(entries), "acceptance must fold from entries"),
        _finding(14, "registry_address", value.content_address == registry_model.address_registry(value), value.content_address, registry_model.address_registry(value), "registry address must replay"),
        _finding(15, "public_boundary", _public(value.to_dict()), True, True, "registry audit must remain value-only and path-free"),
        _finding(16, "bounds", len(entries) <= registry_model.MAX_ENTRIES and value.entry_count == len(entries), (len(entries), value.entry_count), registry_model.MAX_ENTRIES, "registry bounds must hold"),
    )
    sealed = tuple(_seal(item, address_check) for item in checks); passed = sum(item.passed for item in sealed)
    return _seal(RegistryAudit(value.registry_id, value.content_address, sealed, len(sealed), passed, len(sealed) - passed, passed == len(sealed), f"pending:{AUDIT_PREFIX}"), address_audit)


def verify_audit(value: RegistryAudit) -> RegistryAudit:
    if not isinstance(value, RegistryAudit): raise ValidationError("diff runtime registry audit verification requires a typed audit")
    value._validate(); return value
def audit_from_mapping(value: Mapping[str, Any]) -> RegistryAudit: return RegistryAudit.from_mapping(value)
def audit_json(value: RegistryAudit) -> str: return canonical_json(verify_audit(value).to_dict())
def audit_csv(value: RegistryAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()
def render_audit_markdown(value: RegistryAudit) -> str:
    value = verify_audit(value); lines = [f"# Diff runtime registry audit {value.registry_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks); return "\n".join(lines) + "\n"
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def audit_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent registry replay", "duplicate and aggregate verification", "canonical check-address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "RegistryAudit", "address_check", "address_audit", "audit_registry", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]












