"""Independent replay audit for runtime admission registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_runtime_history_release_evidence_history as history_model
from . import downloaded_data_quality_runtime_history_release_evidence_history_runtime as runtime_model
from . import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-audit-v1"
BOUNDARY = registry_model.BOUNDARY + "_audit"
AUDIT_PREFIX = registry_model.REGISTRY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("entry_count", "ordinals", "runtime_identity", "runtime_addresses", "entry_states", "entry_readiness", "counters", "entry_addresses", "entries_address", "summary_replay", "manifest_replay", "registry_address", "source_links", "accepted_replay", "empty_boundary", "public_boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("registry_id", "entry_count", "registry_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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
    return history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "runtime registry audit check ID")
        self.passed = _bool(passed, "runtime registry audit result")
        self.actual = _text(actual, "runtime registry audit actual", 32768)
        self.expected = _text(expected, "runtime registry audit expected", 32768)
        self.detail = _text(detail, "runtime registry audit detail", 4096)
        self.content_address = _address(content_address, "runtime registry audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("runtime registry audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("runtime registry audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "runtime registry audit check")
        _strict(value, set(cls.FIELDS), "runtime registry audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("runtime registry audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class RegistryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, registry_id: str, entry_count: int, registry_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.registry_id = _label(registry_id, "runtime registry audit registry ID")
        self.entry_count = _count(entry_count, "runtime registry audit entry count", registry_model.MAX_ENTRIES)
        self.registry_address = _address(registry_address, "runtime registry audit registry address", registry_model.REGISTRY_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "runtime registry audit check")) for item in _sequence(checks, "runtime registry audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "runtime registry audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry audit acceptance")
        self.content_address = _address(content_address, "runtime registry audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry audit checks are incomplete or out of order")
        if (self.passed_count, self.failed_count) != (sum(item.passed for item in self.checks), sum(not item.passed for item in self.checks)):
            raise ValidationError("runtime registry audit counters do not replay")
        if self.accepted != (self.failed_count == 0) or any(item.content_address != address_check(item) for item in self.checks):
            raise ValidationError("runtime registry audit disposition or check addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("runtime registry audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryAudit":
        value = _mapping(value, "runtime registry audit")
        _strict(value, set(cls.FIELDS), "runtime registry audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RegistryAudit) -> str:
    if not isinstance(value, RegistryAudit):
        raise ValidationError("runtime registry audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    return AuditCheck(ordinal, check_id, passed, canonical_json(actual), canonical_json(expected), detail, f"pending:{CHECK_PREFIX}")


def audit_registry(value: registry_model.RuntimeRegistry, runtimes: Sequence[runtime_model.HistoryRuntime] | None = None) -> RegistryAudit:
    registry_model.verify_registry(value)
    entries = value.entries
    runtime_values = tuple(runtimes or ())
    if runtimes is not None:
        if len(runtime_values) != len(entries) or any(not isinstance(item, runtime_model.HistoryRuntime) for item in runtime_values):
            raise ValidationError("runtime registry audit source runtimes do not match entries")
        for item in runtime_values:
            runtime_model.verify_runtime(item)
    ready_count = sum(item.state == "ready" for item in entries)
    blocked_count = sum(item.state == "blocked" for item in entries)
    expected_summary = (value.registry_id, value.entry_count, ready_count, blocked_count, value.accepted, value.release_ready, value.state)
    actual_summary = tuple(getattr(value.summary, field) for field in registry_model.SUMMARY_FIELDS[:-1])
    expected_manifest = (value.registry_id, registry_model.VERSION, registry_model.BOUNDARY, registry_model.FILES, (registry_model.address_entries(entries), value.summary.content_address))
    actual_manifest = (value.manifest.registry_id, value.manifest.version, value.manifest.boundary, value.manifest.files, value.manifest.artifact_addresses)
    source_match = not runtime_values or all(entry.runtime_id == source.runtime_id and entry.runtime_address == source.content_address and entry.history_id == source.history_id and entry.history_address == source.history_address for entry, source in zip(entries, runtime_values))
    checks = (
        _finding(1, "entry_count", value.entry_count == len(entries), value.entry_count, len(entries), "registry entry count must replay"),
        _finding(2, "ordinals", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), tuple(item.ordinal for item in entries), "contiguous ordinals", "entry ordinals must be contiguous"),
        _finding(3, "runtime_identity", len({item.runtime_id for item in entries}) == len(entries), len({item.runtime_id for item in entries}), value.entry_count, "runtime IDs must be unique"),
        _finding(4, "runtime_addresses", len({item.runtime_address for item in entries}) == len(entries), len({item.runtime_address for item in entries}), value.entry_count, "runtime addresses must be unique"),
        _finding(5, "entry_states", all(item.state in runtime_model.STATES for item in entries), tuple(item.state for item in entries), runtime_model.STATES, "entry states must be runtime states"),
        _finding(6, "entry_readiness", all(item.release_ready == (item.state == "ready") for item in entries), tuple(item.release_ready for item in entries), "state-derived readiness", "entry readiness must follow state"),
        _finding(7, "counters", (value.ready_count, value.blocked_count) == (ready_count, blocked_count), (value.ready_count, value.blocked_count), (ready_count, blocked_count), "aggregate state counters must replay"),
        _finding(8, "entry_addresses", all(item.content_address == registry_model.address_entry(item) for item in entries), "replayed", "canonical", "entry addresses must replay"),
        _finding(9, "entries_address", value.manifest.artifact_addresses[0] == registry_model.address_entries(entries), value.manifest.artifact_addresses[0], registry_model.address_entries(entries), "entries artifact address must replay"),
        _finding(10, "summary_replay", actual_summary == expected_summary and value.summary.content_address == registry_model.address_summary(value.summary), actual_summary, expected_summary, "summary fields and address must replay"),
        _finding(11, "manifest_replay", actual_manifest == expected_manifest and value.manifest.content_address == registry_model.address_manifest(value.manifest), actual_manifest, expected_manifest, "manifest fields and address must replay"),
        _finding(12, "registry_address", value.content_address == registry_model.address_registry(value), value.content_address, registry_model.address_registry(value), "registry address must replay"),
        _finding(13, "source_links", source_match, "matched" if source_match else "mismatch", "matched", "source runtimes must match entries when supplied"),
        _finding(14, "accepted_replay", (value.accepted, value.release_ready, value.state) == (value.entry_count > 0, value.entry_count > 0 and value.blocked_count == 0, "empty" if value.entry_count == 0 else "ready" if value.blocked_count == 0 else "blocked"), (value.accepted, value.release_ready, value.state), "derived disposition", "registry disposition must replay"),
        _finding(15, "empty_boundary", (value.entry_count == 0) == (value.state == "empty"), value.entry_count, value.state, "empty registries must remain explicit"),
        _finding(16, "public_boundary", _public(value.to_dict()), True, True, "registry audit output must remain value-only and path-free"),
    )
    sealed = tuple(_seal(item, address_check) for item in checks)
    passed = sum(item.passed for item in sealed)
    return _seal(RegistryAudit(value.registry_id, value.entry_count, value.content_address, sealed, len(sealed), passed, len(sealed) - passed, passed == len(sealed), f"pending:{AUDIT_PREFIX}"), address_audit)


def verify_audit(value: RegistryAudit) -> RegistryAudit:
    if not isinstance(value, RegistryAudit):
        raise ValidationError("runtime registry audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryAudit:
    return RegistryAudit.from_mapping(value)


def audit_json(value: RegistryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: RegistryAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Runtime registry audit {value.registry_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent registry replay", "optional source-runtime link verification", "duplicate identity and address coverage", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "RegistryAudit", "address_check", "address_audit", "audit_registry", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
