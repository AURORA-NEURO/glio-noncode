"""Independent audit receipts for recovery execution plans."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution as execution_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = execution_model.VERSION + "-audit-v1"
BOUNDARY = execution_model.BOUNDARY + "_audit"
AUDIT_PREFIX = execution_model.EXECUTION_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "execution-address",
    "recovery-linkage",
    "transfer-linkage",
    "plan-conservation",
    "current-index-conservation",
    "outcome-order",
    "outcome-addresses",
    "status-conservation",
    "byte-conservation",
    "state-replay",
    "decision-replay",
    "safety-replay",
    "checkpoint-replay",
    "public-boundary",
    "mapping-round-trip",
    "deterministic-outcomes",
)
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "content_address")
AUDIT_FIELDS = ("execution_address", "execution_id", "version", "boundary", "checks", "check_count", "passed", "content_address")
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


class RecoveryExecutionAuditCheck:
    """One independently recomputed execution invariant."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, content_address: str) -> None:
        self.check_id = _label(check_id, "execution audit check ID")
        self.passed = _bool(passed, "execution audit check result")
        self.observed = observed
        self.expected = expected
        self.content_address = _address(content_address, "execution audit check address", CHECK_PREFIX, allow_pending=True)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("execution audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("execution audit check address does not replay")
        if not execution_model.transfer_model._public(self.to_dict()):
            raise ValidationError("execution audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryExecutionAuditCheck:
        value = _mapping(value, "execution audit check")
        _strict(value, set(cls.FIELDS), "execution audit check")
        return cls(value["check_id"], value["passed"], value["observed"], value["expected"], value["content_address"])


class RecoveryExecutionAudit:
    """Canonical audit receipt for a recovery execution snapshot."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, execution_address: str, execution_id: str, version: str, boundary: str, checks: Sequence[RecoveryExecutionAuditCheck], check_count: int, passed: bool, content_address: str) -> None:
        self.execution_address = _address(execution_address, "execution audit execution address", execution_model.EXECUTION_PREFIX)
        self.execution_id = _label(execution_id, "execution audit execution ID")
        self.version = _text(version, "execution audit version", 2048)
        self.boundary = _text(boundary, "execution audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, RecoveryExecutionAuditCheck) else RecoveryExecutionAuditCheck.from_mapping(item) for item in _sequence(checks, "execution audit checks", MAX_CHECKS))
        if isinstance(check_count, bool) or not isinstance(check_count, int) or check_count != len(self.checks) or check_count != MAX_CHECKS:
            raise ValidationError("execution audit check count is inconsistent")
        self.check_count = check_count
        self.passed = _bool(passed, "execution audit result")
        self.content_address = _address(content_address, "execution audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("execution audit checks are incomplete or inconsistent")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("execution audit address does not replay")
        if not execution_model.transfer_model._public(self.to_dict()):
            raise ValidationError("execution audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"execution_address": self.execution_address, "execution_id": self.execution_id, "version": self.version, "boundary": self.boundary, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed": self.passed, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryExecutionAudit:
        value = _mapping(value, "execution audit")
        _strict(value, set(cls.FIELDS), "execution audit")
        return cls(value["execution_address"], value["execution_id"], value["version"], value["boundary"], tuple(RecoveryExecutionAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "execution audit checks", MAX_CHECKS)), value["check_count"], value["passed"], value["content_address"])


def address_check(value: RecoveryExecutionAuditCheck) -> str:
    if not isinstance(value, RecoveryExecutionAuditCheck):
        raise ValidationError("execution audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: RecoveryExecutionAudit) -> str:
    if not isinstance(value, RecoveryExecutionAudit):
        raise ValidationError("execution audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any) -> RecoveryExecutionAuditCheck:
    pending = RecoveryExecutionAuditCheck(check_id, observed == expected, observed, expected, "pending:execution-audit-check")
    return RecoveryExecutionAuditCheck(check_id, pending.passed, observed, expected, address_check(pending))


def _expected_outcome_addresses(value: execution_model.RecoveryExecution) -> tuple[str, ...]:
    result = []
    for item in value.outcomes:
        pending = execution_model.RecoveryExecutionOutcome(item.index, item.action_address, item.content_address, item.offset, item.size, item.status, item.reason, "pending:execution-outcome")
        result.append(execution_model.address_outcome(pending))
    return tuple(result)


def audit_execution(value: execution_model.RecoveryExecution) -> RecoveryExecutionAudit:
    if not isinstance(value, execution_model.RecoveryExecution):
        raise ValidationError("execution audit requires a typed execution")
    value = execution_model.execution_from_mapping(value.to_dict())
    base = tuple(value.base_received_indices)
    planned = tuple(value.planned_indices)
    applied = set(value.applied_indices)
    pending = set(value.pending_indices)
    rejected = set(value.rejected_indices)
    universe = tuple(range(value.chunk_count))
    checks = (
        _check("version", value.version, execution_model.VERSION),
        _check("boundary", value.boundary, execution_model.BOUNDARY),
        _check("execution-address", execution_model.address_execution(value), value.content_address),
        _check("recovery-linkage", (value.recovery_address.startswith(execution_model.recovery_model.RECOVERY_PREFIX + ":"), value.recovery_id != ""), (True, True)),
        _check("transfer-linkage", (value.transfer_address.startswith( execution_model.transfer_model.TRANSFER_PREFIX + ":"), value.archive_address.startswith(execution_model.transfer_model.archive_model.ARCHIVE_PREFIX + ":")), (True, True)),
        _check("plan-conservation", (base, planned, tuple(sorted(set(base) | set(planned)))), (base, planned, universe)),
        _check("current-index-conservation", (value.current_received_indices, value.current_missing_indices, tuple(sorted(set(value.current_received_indices) | set(value.current_missing_indices)))), (value.current_received_indices, value.current_missing_indices, universe)),
        _check("outcome-order", tuple(item.index for item in value.outcomes), planned),
        _check("outcome-addresses", tuple(item.outcome_address for item in value.outcomes), _expected_outcome_addresses(value)),
        _check("status-conservation", (tuple(sorted(applied)), tuple(sorted(pending)), tuple(sorted(rejected)), (value.applied_count, value.pending_count, value.rejected_count)), (value.applied_indices, value.pending_indices, value.rejected_indices, (len(applied), len(pending), len(rejected)))),
        _check("byte-conservation", (value.planned_bytes, value.applied_bytes + value.pending_bytes + value.rejected_bytes, value.current_received_bytes + value.current_remaining_bytes), (value.planned_bytes, value.planned_bytes, value.archive_size)),
        _check("state-replay", value.state, "blocked" if rejected else "complete" if not pending else "in_progress" if applied else "planned"),
        _check("decision-replay", value.decision, "block" if rejected else "assemble" if not pending else "resume"),
        _check("safety-replay", (value.safe_to_continue, value.safe_to_assemble), (not rejected, not pending and not rejected)),
        _check("checkpoint-replay", value.checkpointed, value.checkpointed),
        _check("public-boundary", execution_model.transfer_model._public(value.to_dict()), True),
        _check("mapping-round-trip", execution_model.execution_from_mapping(value.to_dict()).to_dict(), value.to_dict()),
        _check("deterministic-outcomes", tuple(item.to_dict() for item in value.outcomes), tuple(item.to_dict() for item in execution_model.execution_from_mapping(value.to_dict()).outcomes)),
    )
    provisional = RecoveryExecutionAudit(value.content_address, value.execution_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), "pending:execution-audit")
    return RecoveryExecutionAudit(value.content_address, value.execution_id, VERSION, BOUNDARY, checks, len(checks), provisional.passed, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionAudit:
    return RecoveryExecutionAudit.from_mapping(value)


def audit_json(value: RecoveryExecutionAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: RecoveryExecutionAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict() | {"observed": json.dumps(item.observed, sort_keys=True, separators=(",", ":")), "expected": json.dumps(item.expected, sort_keys=True, separators=(",", ":"))})
    return stream.getvalue()


def render_audit_markdown(value: RecoveryExecutionAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# History observatory archive transfer recovery execution audit", "", f"- Execution: `{value.execution_id}`", f"- Result: `{'passed' if value.passed else 'failed'}`", f"- Checks: `{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | observed | expected |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "History observatory archive transfer recovery execution audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "History observatory archive transfer recovery execution audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"execution_address": {"type": "string", "pattern": "^" + execution_model.EXECUTION_PREFIX + ":"}, "execution_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "check_count": {"const": MAX_CHECKS}, "passed": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "features": ["independent plan and outcome replay", "index and byte conservation", "state and safety recomputation", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "RecoveryExecutionAudit", "RecoveryExecutionAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_execution", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]

