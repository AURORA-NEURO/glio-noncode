from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery as recovery_model
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
    "public-boundary",
    "mapping-round-trip",
    "deterministic-plan",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("recovery_address", "recovery_id", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or value.startswith(("/", "\\")) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 1024)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
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


class ExactHistoryDiffArchiveTransferRecoveryAuditCheck:
    """One independently addressed recovery assertion."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "recovery audit ordinal", MAX_CHECKS, positive=True)
        if check_id not in CHECK_IDS or CHECK_IDS[self.ordinal - 1] != check_id:
            raise ValidationError("recovery audit check identity or order is invalid")
        self.check_id = check_id
        if not isinstance(passed, bool):
            raise ValidationError("recovery audit result must be boolean")
        self.passed = passed
        self.detail = _text(detail, "recovery audit detail")
        self.evidence_addresses = tuple(_address(item, "recovery audit evidence address") for item in _sequence(evidence_addresses, "recovery audit evidence", 16))
        if not self.evidence_addresses:
            raise ValidationError("recovery audit check needs evidence")
        self.content_address = _address(content_address, "recovery audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("recovery audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("recovery audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryAuditCheck:
        value = _mapping(value, "history diff archive transfer recovery audit check")
        _strict(value, set(cls.FIELDS), "history diff archive transfer recovery audit check")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryAudit:
    """Independent audit receipt for a path-free recovery plan."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, recovery_address: str, recovery_id: str, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.recovery_address = _address(recovery_address, "recovery audit recovery address", recovery_model.RECOVERY_PREFIX)
        self.recovery_id = _label(recovery_id, "recovery audit recovery ID")
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryAuditCheck.from_mapping(item) for item in _sequence(checks, "recovery audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "recovery audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "recovery audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "recovery audit failed count", MAX_CHECKS)
        if not isinstance(accepted, bool):
            raise ValidationError("recovery audit acceptance must be boolean")
        self.accepted = accepted
        self.content_address = _address(content_address, "recovery audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("recovery audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("recovery audit counters do not replay")
        if any(self.recovery_address not in item.evidence_addresses for item in self.checks):
            raise ValidationError("recovery audit evidence does not retain the recovery address")
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("recovery audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("recovery audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"recovery_address": self.recovery_address, "recovery_id": self.recovery_id, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryAudit:
        value = _mapping(value, "history diff archive transfer recovery audit")
        _strict(value, set(cls.FIELDS), "history diff archive transfer recovery audit")
        return cls(value["recovery_address"], value["recovery_id"], tuple(ExactHistoryDiffArchiveTransferRecoveryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "recovery audit checks", MAX_CHECKS)), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryAuditCheck):
        raise ValidationError("recovery audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryAudit):
        raise ValidationError("recovery audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> ExactHistoryDiffArchiveTransferRecoveryAuditCheck:
    pending = ExactHistoryDiffArchiveTransferRecoveryAuditCheck(ordinal, check_id, bool(passed), detail, evidence, "pending:recovery-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryAuditCheck(ordinal, check_id, bool(passed), detail, evidence, address_check(pending))


def _expected_actions(value: recovery_model.ExactHistoryDiffArchiveTransferRecovery) -> tuple[dict[str, Any], ...]:
    actions = []
    for item in value.actions:
        pending = recovery_model.ExactHistoryDiffArchiveTransferRecoveryAction(item.index, item.offset, item.size, item.content_address, "pending:recovery-action")
        actions.append(recovery_model.ExactHistoryDiffArchiveTransferRecoveryAction(pending.index, pending.offset, pending.size, pending.content_address, recovery_model.address_action(pending)).to_dict())
    return tuple(actions)


def audit_recovery(value: recovery_model.ExactHistoryDiffArchiveTransferRecovery) -> ExactHistoryDiffArchiveTransferRecoveryAudit:
    """Recompute all recovery conservation and action-plan invariants."""
    if not isinstance(value, recovery_model.ExactHistoryDiffArchiveTransferRecovery):
        raise ValidationError("recovery audit requires a typed recovery")
    value = recovery_model.recovery_from_mapping(value.to_dict())
    received = tuple(value.received_indices)
    missing = tuple(value.missing_indices)
    evidence = (value.content_address, value.transfer_address, value.archive_address)
    expected_actions = _expected_actions(value)
    observed_actions = tuple(item.to_dict() for item in value.actions)
    action_evidence = tuple(dict.fromkeys((value.content_address, *(item.action_address for item in value.actions))))
    checks = (
        _check(1, "version", value.version == recovery_model.VERSION, "recovery version derives from the transfer contract", evidence),
        _check(2, "boundary", value.boundary == recovery_model.BOUNDARY, "recovery boundary derives from the transfer contract", evidence),
        _check(3, "recovery-address", recovery_model.address_recovery(value) == value.content_address, "recovery address replays from the public snapshot", evidence),
        _check(4, "transfer-linkage", value.transfer_address.startswith(recovery_model.transfer_model.TRANSFER_PREFIX + ":"), "recovery retains the transfer address", evidence),
        _check(5, "archive-linkage", value.archive_address.startswith(recovery_model.transfer_model.archive_model.ARCHIVE_PREFIX + ":"), "recovery retains the anchored archive address", evidence),
        _check(6, "index-conservation", tuple(sorted(set(received) | set(missing))) == tuple(range(value.chunk_count)) and not set(received) & set(missing), "received and missing indices partition the transfer", evidence),
        _check(7, "byte-conservation", value.received_bytes + value.remaining_bytes == value.archive_size, "received and remaining bytes conserve the archive", evidence),
        _check(8, "action-coverage", tuple(item.index for item in value.actions) == missing, "one action exists for every missing chunk", action_evidence),
        _check(9, "action-addresses", tuple(item.action_address for item in value.actions) == tuple(recovery_model.address_action(recovery_model.ExactHistoryDiffArchiveTransferRecoveryAction(item.index, item.offset, item.size, item.content_address, "pending:recovery-action")) for item in value.actions), "action addresses replay independently", action_evidence),
        _check(10, "action-ranges", all(item.offset + item.size <= value.archive_size for item in value.actions), "missing-chunk actions remain inside the archive", evidence),
        _check(11, "state-replay", value.state == ("complete" if not missing else "partial"), "state follows the missing-chunk partition", evidence),
        _check(12, "decision-replay", value.decision == ("assemble" if not missing else "resume"), "decision follows recovery completeness", evidence),
        _check(13, "next-index", value.next_index == (missing[0] if missing else -1), "next index selects the first missing chunk", evidence),
        _check(14, "checkpoint-type", isinstance(value.checkpointed, bool), "checkpoint state is an explicit boolean", evidence),
        _check(15, "public-boundary", recovery_model.transfer_model._public(value.to_dict()), "recovery contains only bounded public values", evidence),
        _check(16, "mapping-round-trip", recovery_model.recovery_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "recovery mapping round-trips exactly", evidence),
        _check(17, "deterministic-plan", observed_actions == expected_actions, "missing-chunk action addresses are deterministic", action_evidence),
    )
    body = {"recovery_address": value.content_address, "recovery_id": value.recovery_id, "checks": checks, "check_count": MAX_CHECKS, "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = ExactHistoryDiffArchiveTransferRecoveryAudit(**body, content_address="pending:recovery-audit")
    return ExactHistoryDiffArchiveTransferRecoveryAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryAudit.from_mapping(value)


def verify_audit(value: ExactHistoryDiffArchiveTransferRecoveryAudit) -> ExactHistoryDiffArchiveTransferRecoveryAudit:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryAudit):
        raise ValidationError("recovery audit verification requires a typed audit")
    value._validate()
    if not value.accepted:
        raise ValidationError("recovery audit contains failed checks")
    return value


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict() | {"evidence_addresses": canonical_json(item.evidence_addresses)})
    return stream.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Exact runtime-registry history-diff archive transfer recovery audit", "", f"- Recovery: `{value.recovery_id}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact runtime-registry history-diff archive transfer recovery audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact runtime-registry history-diff archive transfer recovery audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"recovery_address": {"type": "string", "pattern": "^" + recovery_model.RECOVERY_PREFIX + ":"}, "recovery_id": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_count": MAX_CHECKS, "checks": list(CHECK_IDS), "features": ["independent transfer linkage", "index and byte conservation", "deterministic missing-action replay", "state and decision replay", "checkpoint type verification", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "ExactHistoryDiffArchiveTransferRecoveryAudit", "ExactHistoryDiffArchiveTransferRecoveryAuditCheck", "MAX_CHECKS", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_recovery", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
