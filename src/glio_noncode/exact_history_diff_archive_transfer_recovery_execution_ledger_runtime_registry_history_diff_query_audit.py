"""Independent replay audit for history-diff inspection queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff as diff_model
from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_query as query_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "diff-linkage", "public-boundary", "query-address", "mapping-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "evidence", "content_address")
AUDIT_FIELDS = ("version", "boundary", "query_id", "diff_id", "row_count", "check_count", "passed", "checks", "content_address")


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


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
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


def _public(value: Any) -> bool:
    return query_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, evidence: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "registry history diff query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("registry history diff query audit check ID is unsupported")
        self.passed = _bool(passed, "registry history diff query audit result")
        self.observed = observed
        self.expected = expected
        self.evidence = tuple(_text(item, "registry history diff query audit evidence", 2048) for item in _sequence(evidence, "registry history diff query audit evidence", 8))
        self.content_address = _address(content_address, "registry history diff query audit check address", CHECK_PREFIX, allow_pending=True)
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("registry history diff query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff query audit check")
        _strict(value, set(cls.FIELDS), "registry history diff query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, version: str, boundary: str, query_id: str, diff_id: str, row_count: int, check_count: int, passed: bool, checks: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAuditCheck], content_address: str) -> None:
        self.version = _text(version, "registry history diff query audit version", 1024)
        self.boundary = _text(boundary, "registry history diff query audit boundary", 1024)
        self.query_id = _label(query_id, "registry history diff query audit query ID")
        self.diff_id = _label(diff_id, "registry history diff query audit diff ID")
        self.row_count = _count(row_count, "registry history diff query audit row count", query_model.MAX_QUERY_ITEMS)
        self.check_count = _count(check_count, "registry history diff query audit check count", len(CHECK_IDS))
        self.passed = _bool(passed, "registry history diff query audit passed")
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "registry history diff query audit checks", len(CHECK_IDS)))
        self.content_address = _address(content_address, "registry history diff query audit address", AUDIT_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or tuple(item.check_id for item in self.checks) != CHECK_IDS or not self.checks or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("registry history diff query audit does not replay its checks")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("registry history diff query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "query_id": self.query_id, "diff_id": self.diff_id, "row_count": self.row_count, "check_count": self.check_count, "passed": self.passed, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff query audit")
        _strict(value, set(cls.FIELDS), "registry history diff query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any, evidence: Sequence[str]):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAuditCheck(check_id, observed == expected, observed, expected, evidence, CHECK_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAuditCheck(check_id, provisional.passed, observed, expected, evidence, address_check(provisional))


def _same_json(left: Any, right: Any) -> bool:
    return canonical_json(left) == canonical_json(right)


def _semantic_rows(query: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQuery, diff: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff) -> tuple[bool, ...]:
    valid: list[bool] = []
    summary = diff.summary.to_dict()
    by_identity = {item.identity: item for item in diff.items}
    for row in query.rows:
        if row.resource == "summary":
            valid.append(row.key in diff_model.SUMMARY_FIELDS and _same_json(row.value, summary.get(row.key)))
        elif row.resource == "items" or row.resource in diff_model.CHANGES:
            item = by_identity.get(row.key)
            valid.append(item is not None and _same_json(item.to_dict(), row.value) and item.change == row.change)
        elif row.resource == "addresses":
            valid.append(row.key in {"diff", "baseline", "candidate", "items", "summary", "manifest"} and isinstance(row.value, str))
        elif row.resource == "bounds":
            valid.append(row.key in {"item-count", "max-items", "added-count", "removed-count", "changed-count", "unchanged-count"})
        elif row.resource == "latest":
            valid.append(row.key in {"ordinal", "change", "left-entry-address", "right-entry-address", "direction"})
        else:
            valid.append(False)
    return tuple(valid)


def audit_query(value: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQuery, diff: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff):
    value = query_model.verify_query(value)
    diff = diff_model.verify_diff(diff)
    expected = query_model.query_history_diff(diff, resources=value.resources, change=value.change, key=value.key, text=value.text, offset=value.offset, limit=value.limit, query_id=value.query_id)
    checks = (
        _check("version", value.version, query_model.VERSION, (value.content_address,)),
        _check("boundary", value.boundary, query_model.BOUNDARY, (value.content_address,)),
        _check("resource-order", value.resources, tuple(item for item in query_model.RESOURCES if item in value.resources), (value.content_address,)),
        _check("filter-replay", (value.change, value.key, value.text, value.offset, value.limit), (expected.change, expected.key, expected.text, expected.offset, expected.limit), (expected.content_address,)),
        _check("count-replay", (value.total_count, value.returned_count, value.truncated), (expected.total_count, expected.returned_count, expected.truncated), (expected.content_address,)),
        _check("row-order", tuple(row.ordinal for row in value.rows), tuple(row.ordinal for row in expected.rows), (value.content_address,)),
        _check("row-addresses", tuple(query_model.address_row(row) for row in value.rows), tuple(row.row_address for row in value.rows), (value.content_address,)),
        _check("row-membership", tuple(canonical_json(row.to_dict()) for row in value.rows), tuple(canonical_json(row.to_dict()) for row in expected.rows), (expected.content_address,)),
        _check("resource-semantics", _semantic_rows(value, diff), tuple(True for _ in value.rows), (value.diff_address,)),
        _check("diff-linkage", (value.diff_id, value.diff_address), (diff.diff_id, diff.content_address), (diff.content_address,)),
        _check("public-boundary", _public(value.to_dict()), True, (value.content_address,)),
        _check("query-address", query_model.address_query(value), value.content_address, (value.content_address,)),
        _check("mapping-round-trip", query_model.query_json(query_model.query_from_mapping(value.to_dict())), query_model.query_json(value), (value.content_address,)),
    )
    body = {"version": VERSION, "boundary": BOUNDARY, "query_id": value.query_id, "diff_id": value.diff_id, "row_count": value.returned_count, "check_count": len(checks), "passed": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAudit(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def verify_audit(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAudit):
        raise ValidationError("registry history diff query audit verification requires a typed audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAudit.from_mapping(value)


def audit_json(value) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value) -> str:
    value = verify_audit(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return output.getvalue()


def render_audit_markdown(value) -> str:
    value = verify_audit(value)
    lines = ["# Execution-ledger runtime registry history diff query audit", "", f"- Query: {value.query_id}", f"- Diff: {value.diff_id}", f"- Passed: {value.passed}", f"- Address: {value.content_address}", "", "| check | passed | observed | expected |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {item.passed} | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "evidence": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "query_id": {"type": "string"}, "diff_id": {"type": "string"}, "row_count": {"type": "integer", "minimum": 0}, "check_count": {"const": len(CHECK_IDS)}, "passed": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": len(CHECK_IDS), "operations": ("audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAuditCheck", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffQueryAudit", "address_check", "address_audit", "audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
