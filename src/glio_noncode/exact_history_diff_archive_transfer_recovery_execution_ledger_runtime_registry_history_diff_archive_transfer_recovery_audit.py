"""Independent assurance for exact archive transfer recovery plans."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery as recovery_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = recovery_model.VERSION + "-audit-v1"
BOUNDARY = recovery_model.BOUNDARY + "_audit"
AUDIT_PREFIX = recovery_model.RECOVERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "recovery-address",
    "transfer-linkage",
    "archive-linkage",
    "index-conservation",
    "byte-conservation",
    "action-coverage",
    "action-addresses",
    "action-ranges",
    "state-replay",
    "decision-replay",
    "next-index",
    "checkpoint-type",
    "safety-state",
    "public-boundary",
    "mapping-round-trip",
    "deterministic-plan",
)
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "evidence", "content_address")
AUDIT_FIELDS = ("version", "boundary", "recovery_id", "transfer_id", "chunk_count", "action_count", "check_count", "passed", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 2048)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or value.startswith(("/", "\\")) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
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
    return recovery_model.transfer_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, evidence: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "recovery audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("recovery audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("recovery audit result must be boolean")
        self.passed = passed
        self.observed = observed
        self.expected = expected
        self.evidence = tuple(_text(item, "recovery audit evidence", 4096) for item in _sequence(evidence, "recovery audit evidence", 12))
        if not self.evidence:
            raise ValidationError("recovery audit check needs evidence")
        self.content_address = _address(content_address, "recovery audit check address", CHECK_PREFIX, allow_pending=True)
        if not _public(self.to_dict()):
            raise ValidationError("recovery audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("recovery audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history diff archive transfer recovery audit check")
        _strict(value, set(cls.FIELDS), "history diff archive transfer recovery audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAuditCheck):
        raise ValidationError("recovery audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, version: str, boundary: str, recovery_id: str, transfer_id: str, chunk_count: int, action_count: int, check_count: int, passed: bool, checks: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAuditCheck], content_address: str) -> None:
        self.version = _text(version, "recovery audit version")
        self.boundary = _text(boundary, "recovery audit boundary")
        self.recovery_id = _label(recovery_id, "recovery audit ID")
        self.transfer_id = _label(transfer_id, "recovery audit transfer ID")
        self.chunk_count = recovery_model._count(chunk_count, "recovery audit chunk count", recovery_model.transfer_model.MAX_CHUNKS, positive=True)
        self.action_count = recovery_model._count(action_count, "recovery audit action count", recovery_model.MAX_ACTIONS)
        self.check_count = _count(check_count, "recovery audit check count", len(CHECK_IDS))
        if not isinstance(passed, bool):
            raise ValidationError("recovery audit acceptance must be boolean")
        self.passed = passed
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAuditCheck.from_mapping(item) for item in _sequence(checks, "recovery audit checks", len(CHECK_IDS)))
        self.content_address = _address(content_address, "recovery audit address", AUDIT_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("recovery audit does not replay its checks")
        if not _public(self.to_dict()):
            raise ValidationError("recovery audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("recovery audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "recovery_id": self.recovery_id, "transfer_id": self.transfer_id, "chunk_count": self.chunk_count, "action_count": self.action_count, "check_count": self.check_count, "passed": self.passed, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "recovery audit")
        _strict(value, set(cls.FIELDS), "recovery audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAudit):
        raise ValidationError("recovery audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any, evidence: Sequence[str], *, passed: bool | None = None):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAuditCheck(check_id, observed == expected if passed is None else passed, observed, expected, evidence, "pending:recovery-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAuditCheck(check_id, provisional.passed, observed, expected, evidence, address_check(provisional))


def _expected_actions(value):
    actions = []
    for item in value.actions:
        pending = recovery_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAction(item.index, item.offset, item.size, item.content_address, "pending:recovery-action")
        actions.append(recovery_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAction(pending.index, pending.offset, pending.size, pending.content_address, recovery_model.address_action(pending)).to_dict())
    return tuple(actions)


def audit_recovery(value):
    """Recompute recovery conservation, state, and addressed-action invariants."""
    if not isinstance(value, recovery_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecovery):
        raise ValidationError("recovery audit requires a typed recovery")
    value = recovery_model.recovery_from_mapping(value.to_dict())
    received = tuple(value.received_indices)
    missing = tuple(value.missing_indices)
    evidence = (value.content_address, value.transfer_address, value.archive_address)
    observed_actions = tuple(item.to_dict() for item in value.actions)
    expected_actions = _expected_actions(value)
    action_evidence = tuple(dict.fromkeys((value.content_address, *(item.action_address for item in value.actions))))
    checks = (
        _check("version", value.version, recovery_model.VERSION, evidence),
        _check("boundary", value.boundary, recovery_model.BOUNDARY, evidence),
        _check("recovery-address", recovery_model.address_recovery(value), value.content_address, (value.content_address,)),
        _check("transfer-linkage", value.transfer_address.startswith(recovery_model.transfer_model.TRANSFER_PREFIX + ":"), True, evidence),
        _check("archive-linkage", value.archive_address.startswith(recovery_model.transfer_model.archive_model.ARCHIVE_PREFIX + ":"), True, evidence),
        _check("index-conservation", (tuple(sorted(set(received) | set(missing))), bool(set(received) & set(missing))), (tuple(range(value.chunk_count)), False), evidence),
        _check("byte-conservation", value.received_bytes + value.remaining_bytes, value.archive_size, evidence),
        _check("action-coverage", tuple(item.index for item in value.actions), missing, action_evidence),
        _check("action-addresses", tuple(item.action_address for item in value.actions), tuple(item["action_address"] for item in expected_actions), action_evidence),
        _check("action-ranges", all(item.offset + item.size <= value.archive_size for item in value.actions), True, evidence),
        _check("state-replay", value.state, "complete" if not missing else "partial", evidence),
        _check("decision-replay", value.decision, "assemble" if not missing else "resume", evidence),
        _check("next-index", value.next_index, missing[0] if missing else -1, evidence),
        _check("checkpoint-type", isinstance(value.checkpointed, bool), True, evidence),
        _check("safety-state", value.safe_to_resume, True, evidence),
        _check("public-boundary", _public(value.to_dict()), True, (value.content_address,)),
        _check("mapping-round-trip", recovery_model.recovery_from_mapping(value.to_dict()).to_dict(), value.to_dict(), (value.content_address,)),
        _check("deterministic-plan", observed_actions, expected_actions, action_evidence),
    )
    body = {"version": VERSION, "boundary": BOUNDARY, "recovery_id": value.recovery_id, "transfer_id": value.transfer_id, "chunk_count": value.chunk_count, "action_count": value.action_count, "check_count": len(checks), "passed": all(item.passed for item in checks), "checks": checks}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAudit(**body, content_address="pending:recovery-audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAudit.from_mapping(value)


def verify_audit(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAudit):
        raise ValidationError("recovery audit verification requires a typed audit")
    result = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAudit.from_mapping(value.to_dict())
    if not result.passed:
        raise ValidationError("recovery audit contains failed checks")
    return result


def audit_json(value) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value) -> str:
    value = verify_audit(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        writer.writerow(check.to_dict() | {"observed": canonical_json(check.observed), "expected": canonical_json(check.expected), "evidence": canonical_json(check.evidence)})
    return stream.getvalue()


def render_audit_markdown(value) -> str:
    value = verify_audit(value)
    lines = ["# Execution-ledger history-diff archive transfer recovery audit", "", f"- Recovery: `{value.recovery_id}`", f"- Transfer: `{value.transfer_id}`", f"- Result: `{str(value.passed).lower()}`", f"- Checks: `{value.check_count}`", "", "| check | passed |", "| --- | ---: |"]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer recovery audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "evidence": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer recovery audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "recovery_id": {"type": "string"}, "transfer_id": {"type": "string"}, "chunk_count": {"type": "integer", "minimum": 1}, "action_count": {"type": "integer", "minimum": 0}, "check_count": {"type": "integer", "minimum": 0, "maximum": len(CHECK_IDS)}, "passed": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": len(CHECK_IDS), "operations": ["audit_recovery", "audit_from_mapping", "verify_audit", "audit_json", "audit_csv", "render_audit_markdown"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_recovery", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
