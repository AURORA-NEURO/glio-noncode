"""Independent audit receipts for recovery-execution queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution as execution_model
from . import exact_history_diff_archive_transfer_recovery_execution_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "execution-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "content_address")
AUDIT_FIELDS = ("query_address", "query_id", "version", "boundary", "checks", "check_count", "passed", "content_address")
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


class ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck:
    """One independently recomputed query invariant."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, content_address: str) -> None:
        self.check_id = _label(check_id, "execution query audit check ID")
        self.passed = _bool(passed, "execution query audit check result")
        self.observed = observed
        self.expected = expected
        self.content_address = _address(content_address, "execution query audit check address", CHECK_PREFIX, allow_pending=True)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("execution query audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("execution query audit check address does not replay")
        if not execution_model.transfer_model._public(self.to_dict()):
            raise ValidationError("execution query audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck:
        value = _mapping(value, "execution query audit check")
        _strict(value, set(cls.FIELDS), "execution query audit check")
        return cls(value["check_id"], value["passed"], value["observed"], value["expected"], value["content_address"])


class ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit:
    """Canonical audit receipt for a recovery-execution query."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, query_id: str, version: str, boundary: str, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck], check_count: int, passed: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "execution query audit query address", query_model.QUERY_PREFIX)
        self.query_id = _label(query_id, "execution query audit query ID")
        self.version = _text(version, "execution query audit version", 2048)
        self.boundary = _text(boundary, "execution query audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "execution query audit checks", MAX_CHECKS))
        if isinstance(check_count, bool) or not isinstance(check_count, int) or check_count != len(self.checks) or check_count != MAX_CHECKS:
            raise ValidationError("execution query audit check count is inconsistent")
        self.check_count = check_count
        self.passed = _bool(passed, "execution query audit result")
        self.content_address = _address(content_address, "execution query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("execution query audit checks are incomplete or inconsistent")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("execution query audit address does not replay")
        if not execution_model.transfer_model._public(self.to_dict()):
            raise ValidationError("execution query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "query_id": self.query_id, "version": self.version, "boundary": self.boundary, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed": self.passed, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit:
        value = _mapping(value, "execution query audit")
        _strict(value, set(cls.FIELDS), "execution query audit")
        return cls(value["query_address"], value["query_id"], value["version"], value["boundary"], tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "execution query audit checks", MAX_CHECKS)), value["check_count"], value["passed"], value["content_address"])


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck):
        raise ValidationError("execution query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit):
        raise ValidationError("execution query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any) -> ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck:
    pending = ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck(check_id, observed == expected, observed, expected, "pending:execution-query-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck(check_id, pending.passed, observed, expected, address_check(pending))


def audit_query(value: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionQuery, execution: execution_model.ExactHistoryDiffArchiveTransferRecoveryExecution) -> ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit:
    if not isinstance(value, query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionQuery) or not isinstance(execution, execution_model.ExactHistoryDiffArchiveTransferRecoveryExecution):
        raise ValidationError("execution query audit requires typed query and execution")
    value = query_model.query_from_mapping(value.to_dict())
    execution = execution_model.execution_from_mapping(execution.to_dict())
    expected = query_model.query_execution(execution, query_id=value.query_id, resources=value.resources, status=value.status_filter, index=value.index_filter, text=value.text_filter, offset=value.offset, limit=value.limit)
    rows = tuple(item.to_dict() for item in value.rows)
    expected_rows = tuple(item.to_dict() for item in expected.rows)
    checks = (
        _check("version", value.version, query_model.VERSION),
        _check("boundary", value.boundary, query_model.BOUNDARY),
        _check("resource-order", value.resources, tuple(resource for resource in query_model.RESOURCES if resource in value.resources)),
        _check("filter-replay", (value.status_filter, value.index_filter, value.text_filter, value.offset, value.limit), (expected.status_filter, expected.index_filter, expected.text_filter, expected.offset, expected.limit)),
        _check("count-replay", (value.total_count, value.returned_count, value.truncated), (expected.total_count, expected.returned_count, expected.truncated)),
        _check("row-order", tuple(item.ordinal for item in value.rows), tuple(range(value.returned_count))),
        _check("row-addresses", tuple(item.row_address for item in value.rows), tuple(item.row_address for item in expected.rows)),
        _check("row-membership", rows, expected_rows),
        _check("resource-semantics", all(item.resource in query_model.RESOURCES and item.resource in value.resources for item in value.rows), True),
        _check("execution-linkage", (value.execution_address, value.execution_id), (execution.content_address, execution.execution_id)),
        _check("public-boundary", execution_model.transfer_model._public(value.to_dict()), True),
        _check("mapping-round-trip", query_model.query_from_mapping(value.to_dict()).to_dict(), value.to_dict()),
    )
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit(value.content_address, value.query_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), "pending:execution-query-audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit(value.content_address, value.query_id, VERSION, BOUNDARY, checks, len(checks), provisional.passed, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit.from_mapping(value)


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict() | {"observed": json.dumps(item.observed, sort_keys=True, separators=(",", ":")), "expected": json.dumps(item.expected, sort_keys=True, separators=(",", ":"))})
    return stream.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Exact runtime-registry history-diff archive transfer recovery execution query audit", "", f"- Query: `{value.query_id}`", f"- Result: `{'passed' if value.passed else 'failed'}`", f"- Checks: `{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | observed | expected |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact runtime-registry history-diff archive transfer recovery execution query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact runtime-registry history-diff archive transfer recovery execution query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "query_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "check_count": {"const": MAX_CHECKS}, "passed": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "features": ["independent query regeneration", "resource and filter replay", "row address and membership replay", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionQueryAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
