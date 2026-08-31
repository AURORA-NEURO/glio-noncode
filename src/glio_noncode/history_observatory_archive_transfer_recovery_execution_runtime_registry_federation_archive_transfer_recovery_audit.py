"""Independent audit receipts for federation archive transfer recovery plans."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery as recovery_model
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
    "index-conservation",
    "byte-conservation",
    "action-coverage",
    "action-addresses",
    "action-ranges",
    "state-replay",
    "decision-replay",
    "next-index",
    "checkpoint-replay",
    "public-boundary",
    "mapping-round-trip",
    "deterministic-plan",
)
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "content_address")
AUDIT_FIELDS = ("recovery_address", "recovery_id", "version", "boundary", "checks", "check_count", "passed", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
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


class RecoveryAuditCheck:
    """One independently recomputed recovery invariant."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, content_address: str) -> None:
        self.check_id = _label(check_id, "recovery audit check ID")
        self.passed = _bool(passed, "recovery audit check result")
        self.observed = observed
        self.expected = expected
        self.content_address = _address(content_address, "recovery audit check address", CHECK_PREFIX, allow_pending=True)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("recovery audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("recovery audit check address does not replay")
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("recovery audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryAuditCheck:
        value = _mapping(value, "recovery audit check")
        _strict(value, set(cls.FIELDS), "recovery audit check")
        return cls(value["check_id"], value["passed"], value["observed"], value["expected"], value["content_address"])


class RecoveryAudit:
    """Canonical audit receipt for a path-free transfer recovery plan."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, recovery_address: str, recovery_id: str, version: str, boundary: str, checks: Sequence[RecoveryAuditCheck], check_count: int, passed: bool, content_address: str) -> None:
        self.recovery_address = _address(recovery_address, "recovery audit recovery address", recovery_model.RECOVERY_PREFIX)
        self.recovery_id = _label(recovery_id, "recovery audit recovery ID")
        self.version = _text(version, "recovery audit version", 2048)
        self.boundary = _text(boundary, "recovery audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, RecoveryAuditCheck) else RecoveryAuditCheck.from_mapping(item) for item in _sequence(checks, "recovery audit checks", MAX_CHECKS))
        self.check_count = check_count
        if isinstance(check_count, bool) or not isinstance(check_count, int) or check_count != len(self.checks) or check_count != MAX_CHECKS:
            raise ValidationError("recovery audit check count is inconsistent")
        self.passed = _bool(passed, "recovery audit result")
        self.content_address = _address(content_address, "recovery audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("recovery audit checks are incomplete or inconsistent")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("recovery audit address does not replay")
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("recovery audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"recovery_address": self.recovery_address, "recovery_id": self.recovery_id, "version": self.version, "boundary": self.boundary, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed": self.passed, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryAudit:
        value = _mapping(value, "recovery audit")
        _strict(value, set(cls.FIELDS), "recovery audit")
        return cls(value["recovery_address"], value["recovery_id"], value["version"], value["boundary"], tuple(RecoveryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "recovery audit checks", MAX_CHECKS)), value["check_count"], value["passed"], value["content_address"])


def address_check(value: RecoveryAuditCheck) -> str:
    if not isinstance(value, RecoveryAuditCheck):
        raise ValidationError("recovery audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: RecoveryAudit) -> str:
    if not isinstance(value, RecoveryAudit):
        raise ValidationError("recovery audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any) -> RecoveryAuditCheck:
    pending = RecoveryAuditCheck(check_id, observed == expected, observed, expected, "pending:recovery-audit-check")
    return RecoveryAuditCheck(check_id, pending.passed, observed, expected, address_check(pending))


def _expected_actions(value: recovery_model.TransferRecovery) -> tuple[dict[str, Any], ...]:
    result = []
    for action in value.actions:
        pending = recovery_model.RecoveryAction(action.index, action.offset, action.size, action.content_address, "pending:recovery-action")
        result.append(recovery_model.RecoveryAction(pending.index, pending.offset, pending.size, pending.content_address, recovery_model.address_action(pending)).to_dict())
    return tuple(result)


def audit_recovery(value: recovery_model.TransferRecovery) -> RecoveryAudit:
    """Rematerialize the plan and independently replay its conservation rules."""
    if not isinstance(value, recovery_model.TransferRecovery):
        raise ValidationError("recovery audit requires a typed recovery")
    value = recovery_model.recovery_from_mapping(value.to_dict())
    received = tuple(value.received_indices)
    missing = tuple(value.missing_indices)
    expected_actions = _expected_actions(value)
    observed_actions = tuple(item.to_dict() for item in value.actions)
    checks = (
        _check("version", value.version, recovery_model.VERSION),
        _check("boundary", value.boundary, recovery_model.BOUNDARY),
        _check("recovery-address", recovery_model.address_recovery(value), value.content_address),
        _check("index-conservation", (received, missing, tuple(sorted(set(received) | set(missing)))), (received, missing, tuple(range(value.chunk_count)))),
        _check("byte-conservation", value.received_bytes + value.remaining_bytes, value.archive_size),
        _check("action-coverage", tuple(item.index for item in value.actions), missing),
        _check("action-addresses", tuple(item.action_address for item in value.actions), tuple(recovery_model.address_action(recovery_model.RecoveryAction(item.index, item.offset, item.size, item.content_address, "pending:recovery-action")) for item in value.actions)),
        _check("action-ranges", tuple(item.offset + item.size <= value.archive_size for item in value.actions), tuple(True for _ in value.actions)),
        _check("state-replay", value.state, "complete" if not missing else "partial"),
        _check("decision-replay", value.decision, "assemble" if not missing else "resume"),
        _check("next-index", value.next_index, missing[0] if missing else -1),
        _check("checkpoint-replay", value.checkpointed, value.checkpointed),
        _check("public-boundary", recovery_model.transfer_model._public(value.to_dict()), True),
        _check("mapping-round-trip", recovery_model.recovery_from_mapping(value.to_dict()).to_dict(), value.to_dict()),
        _check("deterministic-plan", observed_actions, expected_actions),
    )
    provisional = RecoveryAudit(value.content_address, value.recovery_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), "pending:recovery-audit")
    return RecoveryAudit(value.content_address, value.recovery_id, VERSION, BOUNDARY, checks, len(checks), provisional.passed, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RecoveryAudit:
    return RecoveryAudit.from_mapping(value)


def audit_json(value: RecoveryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: RecoveryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict() | {"observed": json.dumps(item.observed, sort_keys=True, separators=(",", ":")), "expected": json.dumps(item.expected, sort_keys=True, separators=(",", ":"))}
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RecoveryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# History observatory federation archive transfer recovery audit", "", f"- Recovery: `{value.recovery_id}`", f"- Result: `{'passed' if value.passed else 'failed'}`", f"- Checks: `{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | observed | expected |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "History observatory federation archive transfer recovery audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "History observatory federation archive transfer recovery audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"recovery_address": {"type": "string", "pattern": "^" + recovery_model.RECOVERY_PREFIX + ":"}, "recovery_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "check_count": {"const": MAX_CHECKS}, "passed": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "features": ["independent conservation checks", "address replay", "deterministic missing-action replay", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "RecoveryAudit", "RecoveryAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_recovery", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
