"""Independent assurance receipts for registry snapshot histories."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-audit-v1"
BOUNDARY = history_model.BOUNDARY + "_audit"
AUDIT_PREFIX = history_model.HISTORY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "history-address",
    "entry-count",
    "entry-order",
    "entry-addresses",
    "registry-identity",
    "ancestry",
    "transition-replay",
    "latest-snapshot",
    "transition-counts",
    "summary-linkage",
    "entries-linkage",
    "manifest-linkage",
    "public-boundary",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("history_address", "history_id", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
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


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck:
    """One independently addressed history finding."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history audit check ordinal", MAX_CHECKS, lower=1)
        if check_id not in CHECK_IDS:
            raise ValidationError("runtime registry history audit check ID is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "runtime registry history audit check result")
        self.detail = _text(detail, "runtime registry history audit check detail")
        self.evidence_addresses = tuple(_address(item, "runtime registry history audit evidence address") for item in _sequence(evidence_addresses, "runtime registry history audit evidence addresses", 128))
        self.content_address = _address(content_address, "runtime registry history audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime registry history audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck:
        value = _mapping(value, "runtime registry history audit check")
        _strict(value, set(cls.FIELDS), "runtime registry history audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck):
        raise ValidationError("runtime registry history audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit:
    """A fixed-size independently recomputed history audit."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, history_address: str, history_id: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.history_address = _address(history_address, "runtime registry history audit history address", history_model.HISTORY_PREFIX)
        self.history_id = _label(history_id, "runtime registry history audit history ID")
        self.version = _text(version, "runtime registry history audit version", 1024)
        self.boundary = _text(boundary, "runtime registry history audit boundary", 1024)
        self.check_count = _count(check_count, "runtime registry history audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry history audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry history audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry history audit acceptance")
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime registry history audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "runtime registry history audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry history audit does not replay checks")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime registry history audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "history_id": self.history_id, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit:
        value = _mapping(value, "runtime registry history audit")
        _strict(value, set(cls.FIELDS), "runtime registry history audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit):
        raise ValidationError("runtime registry history audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck:
    body = {"ordinal": CHECK_IDS.index(check_id) + 1, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_history(value: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit:
    value = history_model.verify_history(value)
    entries = value.entries
    latest = entries[-1] if entries else None
    expected_latest = (latest.registry_address, latest.entry_count, latest.accepted_count, latest.ready_count, latest.blocked_count) if latest else ("", 0, 0, 0, 0)
    expected_transitions = tuple(sum(item.transition == transition for item in entries) for transition in history_model.TRANSITIONS)
    registry_ids = tuple(item.registry_id for item in entries)
    checks = (
        _check("version", value.version == history_model.VERSION, "history version is current", (value.content_address,)),
        _check("boundary", value.boundary == history_model.BOUNDARY, "history boundary is current", (value.content_address,)),
        _check("history-address", history_model.address_history(value) == value.content_address, "history address replays", (value.content_address,)),
        _check("entry-count", value.entry_count == len(entries), "history entry count matches snapshots", (value.summary.content_address,)),
        _check("entry-order", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), "history ordinals retain append order", tuple(item.content_address for item in entries)),
        _check("entry-addresses", all(history_model.address_entry(item) == item.content_address for item in entries), "history snapshot addresses replay", tuple(item.content_address for item in entries)),
        _check("registry-identity", len(set(registry_ids)) <= 1 and value.registry_id == (registry_ids[0] if registry_ids else ""), "history retains one registry identity", tuple(item.registry_address for item in entries)),
        _check("ancestry", all(index == 0 or item.previous_registry_address == entries[index - 1].registry_address for index, item in enumerate(entries)), "history ancestry links every adjacent snapshot", tuple(item.content_address for item in entries)),
        _check("transition-replay", all(item.transition == history_model._transition(item, entries[index - 1] if index else None) for index, item in enumerate(entries)), "history transitions replay from counters and state", tuple(item.content_address for item in entries)),
        _check("latest-snapshot", (value.latest_registry_address, value.latest_entry_count, value.latest_accepted_count, value.latest_ready_count, value.latest_blocked_count) == expected_latest, "latest snapshot metrics replay", (value.summary.content_address,)),
        _check("transition-counts", (value.initial_count, value.improved_count, value.regressed_count, value.unchanged_count, value.changed_count) == expected_transitions, "transition counters conserve snapshots", (value.summary.content_address,)),
        _check("summary-linkage", tuple(getattr(value.summary, field) for field in history_model.SUMMARY_FIELDS[:-1]) == (value.history_id, value.registry_id, value.entry_count, value.latest_registry_address, value.latest_entry_count, value.latest_accepted_count, value.latest_ready_count, value.latest_blocked_count, value.initial_count, value.improved_count, value.regressed_count, value.unchanged_count, value.changed_count, value.state, value.accepted), "summary mirrors history", (value.summary.content_address,)),
        _check("entries-linkage", history_model.address_entries(entries) == value.manifest.artifact_addresses[0], "entries projection links through manifest", (value.manifest.artifact_addresses[0],)),
        _check("manifest-linkage", value.manifest.history_id == value.history_id and value.manifest.files == history_model.FILES and history_model.address_manifest(value.manifest) == value.manifest.content_address, "manifest files and address replay", (value.manifest.content_address,)),
        _check("public-boundary", _public(value.to_dict()), "history projection is public and value-free", (value.content_address,)),
        _check("mapping-round-trip", history_model.history_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "history mapping round trip is stable", (value.content_address,)),
    )
    body = {"history_address": value.content_address, "history_id": value.history_id, "version": VERSION, "boundary": BOUNDARY, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit(**(body | {"content_address": address_audit(provisional)}))


def verify_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit):
        raise ValidationError("runtime registry history audit verification requires a typed audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit.from_mapping(value)


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit) -> str:
    value = verify_audit(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    for item in value.checks:
        writer.writerow((item.ordinal, item.check_id, item.passed, item.detail, json.dumps(item.evidence_addresses, ensure_ascii=False), item.content_address))
    return output.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit) -> str:
    value = verify_audit(value)
    lines = ["# History-Diff Archive Transfer Recovery Execution Runtime Registry History audit", "", f"History: {value.history_id}", f"Passed: {value.passed_count}/{value.check_count}", f"Accepted: {value.accepted}", f"Address: {value.content_address}", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"history_address": {"type": "string"}, "history_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": MAX_CHECKS, "operations": ("audit_history", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit", "address_check", "address_audit", "audit_history", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
