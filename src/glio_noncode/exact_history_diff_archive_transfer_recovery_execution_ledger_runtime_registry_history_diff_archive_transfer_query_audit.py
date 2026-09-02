"""Independent audit for transfer query projections."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer as transfer_model
from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_query as query_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = transfer_model.TRANSFER_PREFIX + "-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "transfer-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "evidence", "content_address")
AUDIT_FIELDS = ("version", "boundary", "query_id", "transfer_id", "archive_id", "row_count", "check_count", "passed", "checks", "content_address")


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
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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
    return query_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, evidence: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "transfer query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("transfer query audit check ID is unsupported")
        self.passed = bool(passed)
        self.observed = observed
        self.expected = expected
        self.evidence = tuple(_text(item, "transfer query audit evidence", 2048) for item in _sequence(evidence, "transfer query audit evidence", 8))
        self.content_address = _address(content_address, "transfer query audit check address", CHECK_PREFIX, allow_pending=True)
        if not _public(self.to_dict()):
            raise ValidationError("transfer query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("transfer query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "transfer query audit check")
        _strict(value, set(cls.FIELDS), "transfer query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value):
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, version: str, boundary: str, query_id: str, transfer_id: str, archive_id: str, row_count: int, check_count: int, passed: bool, checks: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAuditCheck], content_address: str) -> None:
        self.version = _text(version, "transfer query audit version")
        self.boundary = _text(boundary, "transfer query audit boundary")
        self.query_id = _label(query_id, "transfer query audit query ID")
        self.transfer_id = _label(transfer_id, "transfer query audit transfer ID")
        self.archive_id = _label(archive_id, "transfer query audit archive ID")
        self.row_count = query_model._count(row_count, "transfer query audit row count", query_model.MAX_LIMIT)
        self.check_count = query_model._count(check_count, "transfer query audit check count", len(CHECK_IDS))
        self.passed = bool(passed)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "transfer query audit checks", len(CHECK_IDS)))
        self.content_address = _address(content_address, "transfer query audit address", AUDIT_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("transfer query audit does not replay its checks")
        if not _public(self.to_dict()):
            raise ValidationError("transfer query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("transfer query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "query_id": self.query_id, "transfer_id": self.transfer_id, "archive_id": self.archive_id, "row_count": self.row_count, "check_count": self.check_count, "passed": self.passed, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "transfer query audit")
        _strict(value, set(cls.FIELDS), "transfer query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value):
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any, evidence: Sequence[str], *, passed: bool | None = None):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAuditCheck(check_id, observed == expected if passed is None else passed, observed, expected, evidence, CHECK_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAuditCheck(check_id, provisional.passed, observed, expected, evidence, address_check(provisional))


def audit_query(value: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQuery, transfer: transfer_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransfer):
    value = query_model.verify_query(value)
    transfer = transfer_model.verify_transfer(transfer)
    expected = query_model.query_transfer(transfer, resources=value.resources, key=value.key, text=value.text, offset=value.offset, limit=value.limit, query_id=value.query_id)
    observed_rows = tuple((row.resource, row.key, canonical_json(row.value), row.address) for row in value.rows)
    expected_rows = tuple((row.resource, row.key, canonical_json(row.value), row.address) for row in expected.rows)
    observed_membership = tuple((row.resource, row.key) for row in value.rows)
    expected_membership = tuple((row.resource, row.key) for row in expected.rows)
    observed_semantics = tuple(sorted((row.resource, row.key, canonical_json(row.value)) for row in value.rows))
    expected_semantics = tuple(sorted((row.resource, row.key, canonical_json(row.value)) for row in expected.rows))
    checks = (
        _check("version", value.version, query_model.VERSION, (value.content_address,)),
        _check("boundary", value.boundary, query_model.BOUNDARY, (value.content_address,)),
        _check("resource-order", value.resources, expected.resources, (value.transfer_address,)),
        _check("filter-replay", (value.key, value.text, value.offset, value.limit), (expected.key, expected.text, expected.offset, expected.limit), (value.content_address,)),
        _check("count-replay", (value.total_count, value.returned_count, value.truncated), (expected.total_count, expected.returned_count, expected.truncated), (value.content_address,)),
        _check("row-order", tuple(row.ordinal for row in value.rows), tuple(row.ordinal for row in expected.rows), (value.content_address,)),
        _check("row-addresses", tuple(row.row_address for row in value.rows), tuple(row.row_address for row in expected.rows), (value.content_address,)),
        _check("row-membership", observed_membership, expected_membership, (value.content_address,)),
        _check("resource-semantics", observed_semantics, expected_semantics, (value.transfer_address,)),
        _check("transfer-linkage", (value.transfer_id, value.archive_id, value.transfer_address, value.archive_address), (transfer.transfer_id, transfer.archive_id, transfer.content_address, transfer.archive_address), (transfer.content_address,)),
        _check("public-boundary", _public(value.to_dict()), True, (value.content_address,)),
        _check("mapping-round-trip", query_model.query_from_mapping(value.to_dict()).content_address, value.content_address, (value.content_address,)),
    )
    body = {"version": VERSION, "boundary": BOUNDARY, "query_id": value.query_id, "transfer_id": value.transfer_id, "archive_id": value.archive_id, "row_count": value.returned_count, "check_count": len(checks), "passed": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAudit(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAudit.from_mapping(value)


def verify_audit(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAudit):
        raise ValidationError("transfer query audit verification requires a typed audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAudit.from_mapping(value.to_dict())


def audit_json(value) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value) -> str:
    value = verify_audit(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(check.to_dict() for check in value.checks)
    return stream.getvalue()


def render_audit_markdown(value) -> str:
    value = verify_audit(value)
    lines = ["# Execution-ledger history-diff archive transfer query audit", "", f"- Transfer: `{value.transfer_id}`", f"- Archive: `{value.archive_id}`", f"- Query: `{value.query_id}`", f"- Result: `{value.passed}`", f"- Checks: `{value.check_count}`", "", "| check | passed |", "| --- | ---: |"]
    lines.extend(f"| `{check.check_id}` | `{check.passed}` |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "evidence": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "query_id": {"type": "string"}, "transfer_id": {"type": "string"}, "archive_id": {"type": "string"}, "row_count": {"type": "integer", "minimum": 0}, "check_count": {"type": "integer", "minimum": 0, "maximum": len(CHECK_IDS)}, "passed": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": len(CHECK_IDS), "operations": ["audit_query", "audit_from_mapping", "verify_audit", "audit_json", "audit_csv", "render_audit_markdown"], "public_boundary": {"source_paths": False, "source_records": False, "chunk_bytes": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
