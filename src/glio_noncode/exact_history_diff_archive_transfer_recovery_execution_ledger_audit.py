"""Independent audits for exact archive-transfer recovery execution ledgers."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger as ledger_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = ledger_model.VERSION + "-audit-v1"
BOUNDARY = ledger_model.BOUNDARY + "_audit"
AUDIT_PREFIX = ledger_model.LEDGER_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version", "boundary", "ledger-address", "entry-count", "entry-order", "entry-addresses",
    "ancestry", "component-linkage", "transition-replay", "state-replay", "decision-replay",
    "counter-replay", "byte-replay", "latest-replay", "head-replay", "public-boundary",
    "mapping-round-trip", "summary-replay",
)
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "content_address")
AUDIT_FIELDS = ("ledger_address", "ledger_id", "version", "boundary", "checks", "check_count", "passed", "content_address")
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
        raise ValidationError(f"{field} has the wrong address namespace")
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


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck:
    """One independently recomputed ledger check."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, content_address: str) -> None:
        if check_id not in CHECK_IDS:
            raise ValidationError("ledger audit check is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "ledger audit check result")
        self.observed = observed
        self.expected = expected
        self.content_address = _address(content_address, "ledger audit check address", CHECK_PREFIX, allow_pending=True)
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("ledger audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck":
        value = _mapping(value, "ledger audit check")
        _strict(value, set(cls.FIELDS), "ledger audit check")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit:
    """A fixed-size, value-free audit of a ledger chain."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, ledger_address: str, ledger_id: str, version: str, boundary: str, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck], check_count: int, passed: bool, content_address: str) -> None:
        self.ledger_address = _address(ledger_address, "ledger audit ledger address", ledger_model.LEDGER_PREFIX)
        self.ledger_id = _label(ledger_id, "ledger audit ID")
        self.version = _text(version, "ledger audit version", 2048)
        self.boundary = _text(boundary, "ledger audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck.from_mapping(item) for item in _sequence(checks, "ledger audit checks", MAX_CHECKS))
        if isinstance(check_count, bool) or not isinstance(check_count, int) or check_count < 0 or check_count > MAX_CHECKS:
            raise ValidationError("ledger audit check count is outside its bound")
        self.check_count = check_count
        self.passed = _bool(passed, "ledger audit result")
        self.content_address = _address(content_address, "ledger audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger audit version or boundary is not current")
        if self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("ledger audit checks do not replay")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("ledger audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"ledger_address": self.ledger_address, "ledger_id": self.ledger_id, "version": self.version, "boundary": self.boundary, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed": self.passed, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit":
        value = _mapping(value, "ledger audit")
        _strict(value, set(cls.FIELDS), "ledger audit")
        return cls(value["ledger_address"], value["ledger_id"], value["version"], value["boundary"], tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "ledger audit checks", MAX_CHECKS)), value["check_count"], value["passed"], value["content_address"])


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck):
        raise ValidationError("ledger audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit):
        raise ValidationError("ledger audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck:
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck(check_id, observed == expected, observed, expected, "pending:ledger-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck(check_id, provisional.passed, observed, expected, address_check(provisional))


def audit_ledger(value: ledger_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit:
    if not isinstance(value, ledger_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedger):
        raise ValidationError("ledger audit requires a typed ledger")
    value = ledger_model.verify_ledger(value)
    entries = value.entries
    expected_transitions = tuple("initial" if index == 0 else item.decision for index, item in enumerate(entries))
    expected_states = tuple(item.state for item in entries)
    expected_decisions = tuple("block" if item.state == "blocked" else "assemble" if item.state == "complete" else "resume" for item in entries)
    expected_counts = tuple(sum(item.transition == transition for item in entries) for transition in ledger_model.TRANSITIONS) + tuple(sum(item.state == state for item in entries) for state in ledger_model.STATES)
    observed_counts = (value.initial_count, value.resume_count, value.assemble_count, value.block_count, value.planned_count, value.in_progress_count, value.complete_count, value.blocked_count)
    expected_ancestry = tuple(("" if index == 0 else entries[index - 1].execution_address, "" if index == 0 else entries[index - 1].content_address) for index in range(len(entries)))
    observed_ancestry = tuple((item.previous_execution_address, item.previous_entry_address) for item in entries)
    expected_components = tuple((item.execution_address, item.recovery_address, item.transfer_address, item.archive_address) for item in entries)
    observed_components = tuple(item.evidence_addresses for item in entries)
    expected_latest = ("" if not entries else entries[-1].execution_id, "" if not entries else entries[-1].execution_address, "" if not entries else entries[-1].state, "" if not entries else entries[-1].decision)
    observed_latest = (value.latest_execution_id, value.latest_execution_address, value.latest_state, value.latest_decision)
    checks = (
        _check("version", value.version, ledger_model.VERSION),
        _check("boundary", value.boundary, ledger_model.BOUNDARY),
        _check("ledger-address", ledger_model.address_ledger(value), value.content_address),
        _check("entry-count", value.entry_count, len(entries)),
        _check("entry-order", tuple(item.ordinal for item in entries), tuple(range(1, len(entries) + 1))),
        _check("entry-addresses", tuple(ledger_model.address_entry(item) for item in entries), tuple(item.content_address for item in entries)),
        _check("ancestry", observed_ancestry, expected_ancestry),
        _check("component-linkage", observed_components, expected_components),
        _check("transition-replay", tuple(item.transition for item in entries), expected_transitions),
        _check("state-replay", tuple(item.state for item in entries), expected_states),
        _check("decision-replay", tuple(item.decision for item in entries), expected_decisions),
        _check("counter-replay", observed_counts, expected_counts),
        _check("byte-replay", tuple(item.current_received_bytes + item.current_remaining_bytes for item in entries), tuple(item.archive_size for item in entries)),
        _check("latest-replay", observed_latest, expected_latest),
        _check("head-replay", value.head_address, ledger_model.INITIAL_HEAD if not entries else entries[-1].content_address),
        _check("public-boundary", ledger_model._public(value.to_dict()), True),
        _check("mapping-round-trip", ledger_model.ledger_from_mapping(value.to_dict()).content_address, value.content_address),
        _check("summary-replay", ledger_model.address_summary(value.summary()), value.summary()["content_address"]),
    )
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit(value.content_address, value.ledger_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), "pending:ledger-audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit(value.content_address, value.ledger_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit.from_mapping(value)


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Exact archive-transfer recovery execution ledger audit", "", f"- Ledger: `{value.ledger_id}`", f"- Checks: `{value.check_count}`", f"- Passed: `{str(value.passed).lower()}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | observed | expected |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {index} | `{item.check_id}` | `{str(item.passed).lower()}` | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for index, item in enumerate(value.checks, 1))
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"ledger_address": {"type": "string", "pattern": "^" + ledger_model.LEDGER_PREFIX + ":"}, "ledger_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": MAX_CHECKS, "operations": ("audit_ledger", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_ledger", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
