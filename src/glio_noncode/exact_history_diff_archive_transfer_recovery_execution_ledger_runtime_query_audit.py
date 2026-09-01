"""Independent audits for exact execution-ledger runtime query results."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime as runtime_model
from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "runtime-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "content_address")
AUDIT_FIELDS = ("query_address", "query_id", "version", "boundary", "checks", "check_count", "passed", "content_address")
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
    if allow_pending and value.startswith("pending:"):
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


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck:
    """One independently recomputed runtime query check."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, content_address: str) -> None:
        if check_id not in CHECK_IDS:
            raise ValidationError("ledger runtime query audit check is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "ledger runtime query audit check result")
        self.observed = observed
        self.expected = expected
        self.content_address = _address(content_address, "ledger runtime query audit check address", CHECK_PREFIX, allow_pending=True)
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("ledger runtime query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck":
        value = _mapping(value, "ledger runtime query audit check")
        _strict(value, set(cls.FIELDS), "ledger runtime query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit:
    """A fixed-size, value-free audit of a runtime query."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, query_id: str, version: str, boundary: str, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck], check_count: int, passed: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "ledger runtime query audit query address", query_model.QUERY_PREFIX)
        self.query_id = _label(query_id, "ledger runtime query audit query ID")
        self.version = _text(version, "ledger runtime query audit version", 2048)
        self.boundary = _text(boundary, "ledger runtime query audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "ledger runtime query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "ledger runtime query audit check count", MAX_CHECKS)
        self.passed = _bool(passed, "ledger runtime query audit result")
        self.content_address = _address(content_address, "ledger runtime query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger runtime query audit version or boundary is not current")
        if self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("ledger runtime query audit checks do not replay")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("ledger runtime query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "query_id": self.query_id, "version": self.version, "boundary": self.boundary, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed": self.passed, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit":
        value = _mapping(value, "ledger runtime query audit")
        _strict(value, set(cls.FIELDS), "ledger runtime query audit")
        return cls(value["query_address"], value["query_id"], value["version"], value["boundary"], tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "ledger runtime query audit checks", MAX_CHECKS)), value["check_count"], value["passed"], value["content_address"])


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck):
        raise ValidationError("ledger runtime query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit):
        raise ValidationError("ledger runtime query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck:
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck(check_id, observed == expected, observed, expected, "pending:ledger-runtime-query-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck(check_id, provisional.passed, observed, expected, address_check(provisional))


def audit_query(value: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQuery, runtime: runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit:
    if not isinstance(value, query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQuery) or not isinstance(runtime, runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime):
        raise ValidationError("ledger runtime query audit requires typed query and runtime")
    value = query_model.query_from_mapping(value.to_dict())
    runtime = runtime_model.verify_runtime(runtime)
    expected = query_model.query_runtime(runtime, query_id=value.query_id, resources=value.resources, state=value.state_filter, key=value.key_filter, text=value.text_filter, offset=value.offset, limit=value.limit)
    checks = (
        _check("version", value.version, query_model.VERSION),
        _check("boundary", value.boundary, query_model.BOUNDARY),
        _check("resource-order", value.resources, tuple(item for item in query_model.RESOURCES if item in value.resources)),
        _check("filter-replay", (value.state_filter, value.key_filter, value.text_filter, value.offset, value.limit), (expected.state_filter, expected.key_filter, expected.text_filter, expected.offset, expected.limit)),
        _check("count-replay", (value.total_count, value.returned_count, value.truncated), (expected.total_count, expected.returned_count, expected.truncated)),
        _check("row-order", tuple(item.ordinal for item in value.rows), tuple(range(value.returned_count))),
        _check("row-addresses", tuple(item.row_address for item in value.rows), tuple(item.row_address for item in expected.rows)),
        _check("row-membership", tuple(item.to_dict() for item in value.rows), tuple(item.to_dict() for item in expected.rows)),
        _check("resource-semantics", tuple(item.resource for item in value.rows), tuple(item.resource for item in expected.rows)),
        _check("runtime-linkage", (value.runtime_address, value.runtime_id, value.ledger_id), (runtime.content_address, runtime.runtime_id, runtime.ledger_id)),
        _check("public-boundary", runtime_model._public(value.to_dict()), True),
        _check("mapping-round-trip", query_model.query_from_mapping(value.to_dict()).content_address, value.content_address),
    )
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit(value.content_address, value.query_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), "pending:ledger-runtime-query-audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit(value.content_address, value.query_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit.from_mapping(value)


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Exact execution ledger runtime query audit", "", f"- Query: `{value.query_id}`", f"- Checks: `{value.check_count}`", f"- Passed: `{value.passed}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | observed | expected |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {index} | `{item.check_id}` | `{item.passed}` | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for index, item in enumerate(value.checks, 1))
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "query_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": MAX_CHECKS, "operations": ("audit_query", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeQueryAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
