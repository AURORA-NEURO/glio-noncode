"""Independent audits for exact execution-ledger runtime registry histories."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry as registry_model
from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = history_model.VERSION + "-audit-v1"
BOUNDARY = history_model.BOUNDARY + "_audit"
AUDIT_PREFIX = history_model.HISTORY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "history-address", "entry-count", "entry-order", "identity-replay", "ancestry-replay", "transition-replay", "transition-counts", "latest-replay", "state-replay", "acceptance-replay", "manifest-linkage", "summary-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "content_address")
AUDIT_FIELDS = ("history_address", "history_id", "version", "boundary", "checks", "check_count", "passed", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
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
        raise ValidationError(f"{field} has the wrong public address namespace")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck:
    """One independently recomputed history check."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, content_address: str) -> None:
        if check_id not in CHECK_IDS:
            raise ValidationError("ledger runtime registry history audit check is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "ledger runtime registry history audit check result")
        self.observed = observed
        self.expected = expected
        self.content_address = _address(content_address, "ledger runtime registry history audit check address", CHECK_PREFIX, allow_pending=True)
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("ledger runtime registry history audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck":
        value = _mapping(value, "ledger runtime registry history audit check")
        _strict(value, set(cls.FIELDS), "ledger runtime registry history audit check")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit:
    """A fixed-size value-free audit of a registry history."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, history_address: str, history_id: str, version: str, boundary: str, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck], check_count: int, passed: bool, content_address: str) -> None:
        self.history_address = _address(history_address, "ledger runtime registry history audit history address", history_model.HISTORY_PREFIX)
        self.history_id = _label(history_id, "ledger runtime registry history audit history ID")
        self.version = _text(version, "ledger runtime registry history audit version", 2048)
        self.boundary = _text(boundary, "ledger runtime registry history audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck.from_mapping(item) for item in _sequence(checks, "ledger runtime registry history audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "ledger runtime registry history audit check count", MAX_CHECKS)
        self.passed = _bool(passed, "ledger runtime registry history audit result")
        self.content_address = _address(content_address, "ledger runtime registry history audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger runtime registry history audit version or boundary is not current")
        if self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("ledger runtime registry history audit checks do not replay")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("ledger runtime registry history audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "history_id": self.history_id, "version": self.version, "boundary": self.boundary, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed": self.passed, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit":
        value = _mapping(value, "ledger runtime registry history audit")
        _strict(value, set(cls.FIELDS), "ledger runtime registry history audit")
        return cls(value["history_address"], value["history_id"], value["version"], value["boundary"], tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "ledger runtime registry history audit checks", MAX_CHECKS)), value["check_count"], value["passed"], value["content_address"])


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck):
        raise ValidationError("ledger runtime registry history audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit):
        raise ValidationError("ledger runtime registry history audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck:
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck(check_id, observed == expected, observed, expected, "pending:ledger-runtime-registry-history-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck(check_id, provisional.passed, observed, expected, address_check(provisional))


def _expected_summary(value: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory) -> history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary:
    body = history_model._summary_body(value.history_id, value.registry_id, value.entries)
    provisional = history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary(**body)
    return history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistorySummary(**(body | {"content_address": history_model.address_summary(provisional)}))


def audit_history(value: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit:
    if not isinstance(value, history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory):
        raise ValidationError("ledger runtime registry history audit requires a typed history")
    value = history_model.verify_history(value)
    expected_entries = tuple(history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryEntry.from_mapping(item.to_dict()) for item in value.entries)
    expected_ancestry = tuple(item.previous_registry_address for item in value.entries)
    observed_ancestry = tuple(item.previous_registry_address for item in value.entries)
    expected_transitions = tuple(history_model._transition(item, value.entries[index - 1] if index else None) for index, item in enumerate(value.entries))
    expected_counts = tuple(sum(item.transition == transition for item in value.entries) for transition in history_model.TRANSITIONS)
    latest = value.entries[-1] if value.entries else None
    expected_latest = (latest.registry_address, latest.entry_count, latest.accepted_count, latest.ready_count, latest.blocked_count) if latest else ("", 0, 0, 0, 0)
    expected_summary = _expected_summary(value)
    checks = (
        _check("version", value.version, history_model.VERSION),
        _check("boundary", value.boundary, history_model.BOUNDARY),
        _check("history-address", history_model.address_history(value), value.content_address),
        _check("entry-count", (value.entry_count, len(value.entries)), (len(expected_entries), len(expected_entries))),
        _check("entry-order", tuple(item.ordinal for item in value.entries), tuple(range(1, len(value.entries) + 1))),
        _check("identity-replay", (value.registry_id, tuple(item.registry_id for item in value.entries)), (value.registry_id, (value.registry_id,) * len(value.entries))),
        _check("ancestry-replay", observed_ancestry, expected_ancestry),
        _check("transition-replay", tuple(item.transition for item in value.entries), expected_transitions),
        _check("transition-counts", (value.initial_count, value.improved_count, value.regressed_count, value.unchanged_count, value.changed_count), expected_counts),
        _check("latest-replay", (value.latest_registry_address, value.latest_entry_count, value.latest_accepted_count, value.latest_ready_count, value.latest_blocked_count), expected_latest),
        _check("state-replay", value.state, latest.state if latest else "empty"),
        _check("acceptance-replay", value.accepted, latest.accepted if latest else False),
        _check("manifest-linkage", (value.manifest.history_id, value.manifest.registry_id, value.manifest.files, tuple(item.name for item in value.manifest.artifacts), value.manifest.history_address), (value.history_id, value.registry_id, history_model.FILES, history_model.ARTIFACT_FILES, value.content_address)),
        _check("summary-linkage", value.summary.to_dict(), expected_summary.to_dict()),
        _check("public-boundary", history_model._public(value.to_dict()), True),
        _check("mapping-round-trip", history_model.history_from_mapping(value.to_dict()).content_address, value.content_address),
    )
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit(value.content_address, value.history_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), "pending:ledger-runtime-registry-history-audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit(value.content_address, value.history_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit.from_mapping(value)


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Exact execution ledger runtime registry history audit", "", f"- History: `{value.history_id}`", f"- Checks: `{value.check_count}`", f"- Passed: `{value.passed}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | observed | expected |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {index} | `{item.check_id}` | `{item.passed}` | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for index, item in enumerate(value.checks, 1))
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry history audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry history audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"history_address": {"type": "string", "pattern": "^" + history_model.HISTORY_PREFIX + ":"}, "history_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": MAX_CHECKS, "operations": ("audit_history", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_history", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
