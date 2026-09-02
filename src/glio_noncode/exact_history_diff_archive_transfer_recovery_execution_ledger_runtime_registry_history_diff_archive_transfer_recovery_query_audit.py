"""Independent assurance for exact archive transfer recovery queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery as recovery_model
from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = recovery_model.RECOVERY_PREFIX + "-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "recovery-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "evidence", "content_address")
AUDIT_FIELDS = ("version", "boundary", "recovery_id", "query_id", "check_count", "passed", "checks", "content_address")


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


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, evidence: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "recovery query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("recovery query audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("recovery query audit result must be boolean")
        self.passed = passed
        self.observed = observed
        self.expected = expected
        self.evidence = tuple(_text(item, "recovery query audit evidence", 4096) for item in _sequence(evidence, "recovery query audit evidence", 12))
        if not self.evidence:
            raise ValidationError("recovery query audit check needs evidence")
        self.content_address = _address(content_address, "recovery query audit check address", CHECK_PREFIX, allow_pending=True)
        if not _public(self.to_dict()):
            raise ValidationError("recovery query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("recovery query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history diff archive transfer recovery query audit check")
        _strict(value, set(cls.FIELDS), "history diff archive transfer recovery query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAuditCheck):
        raise ValidationError("recovery query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, version: str, boundary: str, recovery_id: str, query_id: str, check_count: int, passed: bool, checks: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAuditCheck], content_address: str) -> None:
        self.version = _text(version, "recovery query audit version")
        self.boundary = _text(boundary, "recovery query audit boundary")
        self.recovery_id = _label(recovery_id, "recovery query audit recovery ID")
        self.query_id = _label(query_id, "recovery query audit query ID")
        self.check_count = _count(check_count, "recovery query audit check count", len(CHECK_IDS))
        if not isinstance(passed, bool):
            raise ValidationError("recovery query audit acceptance must be boolean")
        self.passed = passed
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "recovery query audit checks", len(CHECK_IDS)))
        self.content_address = _address(content_address, "recovery query audit address", AUDIT_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("recovery query audit does not replay its checks")
        if not _public(self.to_dict()):
            raise ValidationError("recovery query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("recovery query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "recovery_id": self.recovery_id, "query_id": self.query_id, "check_count": self.check_count, "passed": self.passed, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "recovery query audit")
        _strict(value, set(cls.FIELDS), "recovery query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAudit):
        raise ValidationError("recovery query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any, evidence: Sequence[str], *, passed: bool | None = None):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAuditCheck(check_id, observed == expected if passed is None else passed, observed, expected, evidence, "pending:recovery-query-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAuditCheck(check_id, provisional.passed, observed, expected, evidence, address_check(provisional))


def _row_signature(row):
    return (row.ordinal, row.resource, row.key, canonical_json(row.value), row.address, row.row_address)


def audit_query(value: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQuery, recovery: recovery_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecovery):
    """Replay filters, pagination, row addresses, and recovery linkage."""
    if not isinstance(value, query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQuery) or not isinstance(recovery, recovery_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecovery):
        raise ValidationError("recovery query audit requires typed query and recovery")
    value = query_model.query_from_mapping(value.to_dict())
    recovery = recovery_model.recovery_from_mapping(recovery.to_dict())
    replayed = query_model.query_recovery(recovery, query_id=value.query_id, resources=value.resources, key=value.key, text=value.text, offset=value.offset, limit=value.limit)
    evidence = (value.content_address, value.recovery_address, value.transfer_address, value.archive_address)
    observed_semantics = tuple(sorted((row.resource, row.key, canonical_json(row.value)) for row in value.rows))
    expected_semantics = tuple(sorted((row.resource, row.key, canonical_json(row.value)) for row in replayed.rows))
    checks = (
        _check("version", value.version, query_model.VERSION, evidence),
        _check("boundary", value.boundary, query_model.BOUNDARY, evidence),
        _check("resource-order", value.resources, tuple(item for item in query_model.RESOURCES if item in value.resources), evidence),
        _check("filter-replay", (value.resources, value.key, value.text, value.offset, value.limit), (replayed.resources, replayed.key, replayed.text, replayed.offset, replayed.limit), evidence),
        _check("count-replay", (value.total_count, value.returned_count, value.truncated), (replayed.total_count, replayed.returned_count, replayed.truncated), evidence),
        _check("row-order", tuple(row.ordinal for row in value.rows), tuple(range(value.offset, value.offset + value.returned_count)), evidence),
        _check("row-addresses", tuple(row.row_address for row in value.rows), tuple(query_model.address_row(query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryRow(row.ordinal, row.resource, row.key, row.value, row.address, "pending:row")) for row in value.rows), evidence),
        _check("row-membership", tuple(_row_signature(row) for row in value.rows), tuple(_row_signature(row) for row in replayed.rows), evidence),
        _check("resource-semantics", observed_semantics, expected_semantics, evidence),
        _check("recovery-linkage", (value.recovery_address, value.transfer_address, value.archive_address), (recovery.content_address, recovery.transfer_address, recovery.archive_address), evidence),
        _check("public-boundary", _public(value.to_dict()), True, (value.content_address,)),
        _check("mapping-round-trip", query_model.query_from_mapping(value.to_dict()).to_dict(), value.to_dict(), (value.content_address,)),
    )
    body = {"version": VERSION, "boundary": BOUNDARY, "recovery_id": recovery.recovery_id, "query_id": value.query_id, "check_count": len(checks), "passed": all(item.passed for item in checks), "checks": checks}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAudit(**body, content_address="pending:recovery-query-audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAudit.from_mapping(value)


def verify_audit(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAudit):
        raise ValidationError("recovery query audit verification requires a typed audit")
    result = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAudit.from_mapping(value.to_dict())
    if not result.passed:
        raise ValidationError("recovery query audit contains failed checks")
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
    lines = ["# Execution-ledger history-diff archive transfer recovery query audit", "", f"- Recovery: `{value.recovery_id}`", f"- Query: `{value.query_id}`", f"- Result: `{str(value.passed).lower()}`", f"- Checks: `{value.check_count}`", "", "| check | passed |", "| --- | ---: |"]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer recovery query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "evidence": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer recovery query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "recovery_id": {"type": "string"}, "query_id": {"type": "string"}, "check_count": {"type": "integer", "minimum": 0, "maximum": len(CHECK_IDS)}, "passed": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": len(CHECK_IDS), "operations": ["audit_query", "audit_from_mapping", "verify_audit", "audit_json", "audit_csv", "render_audit_markdown"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferRecoveryQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "audit_query", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
