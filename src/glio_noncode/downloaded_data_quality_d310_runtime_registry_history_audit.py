"""Independent replay audit for runtime registry histories."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d309_runtime_registry as registry_model
from . import downloaded_data_quality_d310_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-audit-v1"
BOUNDARY = history_model.BOUNDARY + "_audit"
AUDIT_PREFIX = history_model.HISTORY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("entry_count", "ordinals", "identity", "snapshot_uniqueness", "registry_uniqueness", "transition_sequence", "transition_conservation", "predecessor_links", "entry_addresses", "summary_replay", "manifest_replay", "latest_replay", "accepted_replay", "registry_identity", "history_address", "public_boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("history_id", "registry_id", "history_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "runtime registry history audit check ID")
        self.passed = _bool(passed, "runtime registry history audit result")
        self.actual = _text(actual, "runtime registry history audit actual", 32768)
        self.expected = _text(expected, "runtime registry history audit expected", 32768)
        self.detail = _text(detail, "runtime registry history audit detail", 4096)
        self.content_address = _address(content_address, "runtime registry history audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("runtime registry history audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "runtime registry history audit check")
        _strict(value, set(cls.FIELDS), "runtime registry history audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("runtime registry history audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class HistoryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, history_id: str, registry_id: str, history_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.history_id = _label(history_id, "runtime registry history audit history ID")
        self.registry_id = _label(registry_id, "runtime registry history audit registry ID")
        self.history_address = _address(history_address, "runtime registry history audit history address", history_model.HISTORY_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "runtime registry history audit check")) for item in _sequence(checks, "runtime registry history audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "runtime registry history audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry history audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry history audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry history audit acceptance")
        self.content_address = _address(content_address, "runtime registry history audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry history audit checks are incomplete or out of order")
        if (self.passed_count, self.failed_count) != (sum(item.passed for item in self.checks), sum(not item.passed for item in self.checks)):
            raise ValidationError("runtime registry history audit counters do not replay")
        if self.accepted != (self.failed_count == 0) or any(item.content_address != address_check(item) for item in self.checks):
            raise ValidationError("runtime registry history audit disposition or check addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryAudit":
        value = _mapping(value, "runtime registry history audit")
        _strict(value, set(cls.FIELDS), "runtime registry history audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: HistoryAudit) -> str:
    if not isinstance(value, HistoryAudit):
        raise ValidationError("runtime registry history audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    return AuditCheck(ordinal, check_id, passed, canonical_json(actual), canonical_json(expected), detail, f"pending:{CHECK_PREFIX}")


def audit_history(value: history_model.RegistryHistory) -> HistoryAudit:
    history_model.verify_history(value)
    entries = value.entries
    expected_summary = (value.history_id, value.registry_id, value.entry_count, value.initial_count, value.improved_count, value.regressed_count, value.unchanged_count, value.changed_count, value.latest_state, value.latest_release_ready, value.accepted)
    actual_summary = tuple(getattr(value.summary, field) for field in history_model.SUMMARY_FIELDS[:-1])
    expected_manifest = (value.history_id, value.registry_id, history_model.VERSION, history_model.BOUNDARY, history_model.FILES, (history_model.address_entries(entries), value.summary.content_address))
    actual_manifest = (value.manifest.history_id, value.manifest.registry_id, value.manifest.version, value.manifest.boundary, value.manifest.files, value.manifest.artifact_addresses)
    checks = (
        _finding(1, "entry_count", value.entry_count == len(entries) and value.entry_count > 0, value.entry_count, len(entries), "history entry count must replay"),
        _finding(2, "ordinals", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), tuple(item.ordinal for item in entries), "contiguous ordinals", "history ordinals must be contiguous"),
        _finding(3, "identity", all(item.registry_id == value.registry_id for item in entries), tuple(item.registry_id for item in entries), value.registry_id, "all entries must share registry identity"),
        _finding(4, "snapshot_uniqueness", len({item.snapshot_id for item in entries}) == len(entries), len({item.snapshot_id for item in entries}), len(entries), "snapshot IDs must be unique"),
        _finding(5, "registry_uniqueness", len({item.registry_address for item in entries}) == len(entries), len({item.registry_address for item in entries}), len(entries), "registry addresses must be unique"),
        _finding(6, "transition_sequence", entries[0].transition == "initial" and all(item.transition != "initial" for item in entries[1:]), tuple(item.transition for item in entries), "initial then non-initial", "history must have one initial transition"),
        _finding(7, "transition_conservation", sum(item.transition in history_model.TRANSITIONS for item in entries) == value.entry_count, value.entry_count, "recognized transitions", "transitions must conserve entries"),
        _finding(8, "predecessor_links", all((not item.previous_address if item.ordinal == 1 else item.previous_address == entries[item.ordinal - 2].content_address) for item in entries), tuple(item.previous_address for item in entries), "ordered predecessor addresses", "predecessors must form a chain"),
        _finding(9, "entry_addresses", all(item.content_address == history_model.address_entry(item) for item in entries), "replayed", "canonical", "entry addresses must replay"),
        _finding(10, "summary_replay", actual_summary == expected_summary and value.summary.content_address == history_model.address_summary(value.summary), actual_summary, expected_summary, "summary fields and address must replay"),
        _finding(11, "manifest_replay", actual_manifest == expected_manifest and value.manifest.content_address == history_model.address_manifest(value.manifest), actual_manifest, expected_manifest, "manifest fields and address must replay"),
        _finding(12, "latest_replay", (value.latest_state, value.latest_release_ready) == (entries[-1].state, entries[-1].release_ready), (value.latest_state, value.latest_release_ready), (entries[-1].state, entries[-1].release_ready), "latest projection must replay"),
        _finding(13, "accepted_replay", value.accepted is True, value.accepted, True, "valid history must be accepted"),
        _finding(14, "registry_identity", all(item.registry_id == entries[0].registry_id for item in entries), tuple(item.registry_id for item in entries), value.registry_id, "registry identity must remain stable"),
        _finding(15, "history_address", value.content_address == history_model.address_history(value), value.content_address, history_model.address_history(value), "history address must replay"),
        _finding(16, "public_boundary", _public(value.to_dict()), True, True, "history audit output must remain value-only and path-free"),
    )
    sealed = tuple(_seal(item, address_check) for item in checks)
    passed = sum(item.passed for item in sealed)
    return _seal(HistoryAudit(value.history_id, value.registry_id, value.content_address, sealed, len(sealed), passed, len(sealed) - passed, passed == len(sealed), f"pending:{AUDIT_PREFIX}"), address_audit)


def verify_audit(value: HistoryAudit) -> HistoryAudit:
    if not isinstance(value, HistoryAudit):
        raise ValidationError("runtime registry history audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> HistoryAudit:
    return HistoryAudit.from_mapping(value)


def audit_json(value: HistoryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: HistoryAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: HistoryAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Runtime registry history audit {value.history_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistoryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistoryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent history replay", "stable registry identity verification", "predecessor-chain verification", "transition conservation", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "HistoryAudit", "address_check", "address_audit", "audit_history", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]




















