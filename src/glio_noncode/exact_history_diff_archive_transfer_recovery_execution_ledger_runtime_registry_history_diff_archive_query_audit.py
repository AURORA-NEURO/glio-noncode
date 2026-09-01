"""Independent replay audit for history-diff archive queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive as archive_model
from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "archive-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "evidence", "content_address")
AUDIT_FIELDS = ("version", "boundary", "query_id", "archive_id", "row_count", "check_count", "passed", "checks", "content_address")


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
    value = _text(value, field, 4096)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return archive_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, evidence: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "history diff archive query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("history diff archive query audit check ID is unsupported")
        self.passed = bool(passed)
        self.observed = observed
        self.expected = expected
        self.evidence = tuple(_text(item, "history diff archive query audit evidence", 2048) for item in _sequence(evidence, "history diff archive query audit evidence", 8))
        self.content_address = _address(content_address, "history diff archive query audit check address", CHECK_PREFIX, allow_pending=True)
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("history diff archive query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history diff archive query audit check")
        _strict(value, set(cls.FIELDS), "history diff archive query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value):
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, version: str, boundary: str, query_id: str, archive_id: str, row_count: int, check_count: int, passed: bool, checks: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAuditCheck], content_address: str) -> None:
        self.version = _text(version, "history diff archive query audit version", 2048)
        self.boundary = _text(boundary, "history diff archive query audit boundary", 2048)
        self.query_id = _label(query_id, "history diff archive query audit query ID")
        self.archive_id = _label(archive_id, "history diff archive query audit archive ID")
        self.row_count = _count(row_count, "history diff archive query audit row count", query_model.MAX_QUERY_ITEMS)
        self.check_count = _count(check_count, "history diff archive query audit check count", len(CHECK_IDS))
        self.passed = bool(passed)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "history diff archive query audit checks", len(CHECK_IDS)))
        self.content_address = _address(content_address, "history diff archive query audit address", AUDIT_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or tuple(item.check_id for item in self.checks) != CHECK_IDS or not self.checks or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("history diff archive query audit does not replay its checks")
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("history diff archive query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "query_id": self.query_id, "archive_id": self.archive_id, "row_count": self.row_count, "check_count": self.check_count, "passed": self.passed, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history diff archive query audit")
        _strict(value, set(cls.FIELDS), "history diff archive query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value):
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any, evidence: Sequence[str]):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAuditCheck(check_id, observed == expected, observed, expected, evidence, CHECK_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAuditCheck(check_id, provisional.passed, observed, expected, evidence, address_check(provisional))


def _same_json(left: Any, right: Any) -> bool:
    return canonical_json(left) == canonical_json(right)


def audit_query(value: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQuery, archive: archive_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive):
    value = query_model.verify_query(value)
    archive = archive_model.verify_archive(archive)
    expected = query_model.query_archive(archive, resources=value.resources, key=value.key, text=value.text, offset=value.offset, limit=value.limit, query_id=value.query_id)
    semantic = []
    rows = {(row.resource, row.key): row for row in query_model._all_rows(archive)}
    for row in value.rows:
        expected_row = rows.get((row.resource, row.key))
        semantic.append(expected_row is not None and _same_json(expected_row.value, row.value))
    checks = (
        _check("version", value.version, query_model.VERSION, (value.content_address,)),
        _check("boundary", value.boundary, query_model.BOUNDARY, (value.content_address,)),
        _check("resource-order", value.resources, tuple(item for item in query_model.RESOURCES if item in value.resources), (value.content_address,)),
        _check("filter-replay", (value.key, value.text, value.offset, value.limit), (expected.key, expected.text, expected.offset, expected.limit), (expected.content_address,)),
        _check("count-replay", (value.total_count, value.returned_count, value.truncated), (expected.total_count, expected.returned_count, expected.truncated), (expected.content_address,)),
        _check("row-order", tuple(row.ordinal for row in value.rows), tuple(row.ordinal for row in expected.rows), (value.content_address,)),
        _check("row-addresses", tuple(query_model.address_row(row) for row in value.rows), tuple(row.row_address for row in value.rows), (value.content_address,)),
        _check("row-membership", tuple(canonical_json(row.to_dict()) for row in value.rows), tuple(canonical_json(row.to_dict()) for row in expected.rows), (expected.content_address,)),
        _check("resource-semantics", tuple(semantic), tuple(True for _ in value.rows), (value.archive_address,)),
        _check("archive-linkage", (value.archive_id, value.archive_address), (archive.archive_id, archive.content_address), (archive.content_address,)),
        _check("public-boundary", _public(value.to_dict()), True, (value.content_address,)),
        _check("mapping-round-trip", query_model.query_json(query_model.query_from_mapping(value.to_dict())), query_model.query_json(value), (value.content_address,)),
    )
    body = {"version": VERSION, "boundary": BOUNDARY, "query_id": value.query_id, "archive_id": value.archive_id, "row_count": value.returned_count, "check_count": len(checks), "passed": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAudit(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def verify_audit(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAudit):
        raise ValidationError("history diff archive query audit verification requires a typed audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAudit.from_mapping(value)


def audit_json(value) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value) -> str:
    value = verify_audit(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value) -> str:
    value = verify_audit(value)
    lines = ["# Execution-ledger registry history diff archive query audit", "", f"- Archive: `{value.archive_id}`", f"- Query: `{value.query_id}`", f"- Checks: `{value.check_count}`", f"- Passed: `{value.passed}`", f"- Address: `{value.content_address}`", "", "| # | check | passed |", "| ---: | --- | --- |"]
    lines.extend(f"| {index} | `{item.check_id}` | `{item.passed}` |" for index, item in enumerate(value.checks, 1))
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "evidence": {"type": "array", "items": {"type": "string"}, "maxItems": 8}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "query_id": {"type": "string"}, "archive_id": {"type": "string"}, "row_count": {"type": "integer", "minimum": 0}, "check_count": {"type": "integer", "const": len(CHECK_IDS)}, "passed": {"type": "boolean"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS), "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "features": ["independent filter replay", "canonical row replay", "archive linkage verification", "mapping round-trip"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveQueryAuditCheck", "VERSION", "address_audit", "address_check", "audit_archive", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
