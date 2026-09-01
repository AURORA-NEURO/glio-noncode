"""Independent audits for exact execution-ledger query results."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger as ledger_model
from . import exact_history_diff_archive_transfer_recovery_execution_ledger_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "ledger-linkage", "public-boundary", "mapping-round-trip")
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck:
    """One independently recomputed ledger query check."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, content_address: str) -> None:
        if check_id not in CHECK_IDS:
            raise ValidationError("ledger query audit check is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "ledger query audit check result")
        self.observed = observed
        self.expected = expected
        self.content_address = _address(content_address, "ledger query audit check address", CHECK_PREFIX, allow_pending=True)
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("ledger query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck":
        value = _mapping(value, "ledger query audit check")
        _strict(value, set(cls.FIELDS), "ledger query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit:
    """A fixed-size audit of a bounded ledger query."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, query_id: str, version: str, boundary: str, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck], check_count: int, passed: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "ledger query audit query address", query_model.QUERY_PREFIX)
        self.query_id = _label(query_id, "ledger query audit ID")
        self.version = _text(version, "ledger query audit version", 2048)
        self.boundary = _text(boundary, "ledger query audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "ledger query audit checks", MAX_CHECKS))
        if isinstance(check_count, bool) or not isinstance(check_count, int) or check_count < 0 or check_count > MAX_CHECKS:
            raise ValidationError("ledger query audit check count is outside its bound")
        self.check_count = check_count
        self.passed = _bool(passed, "ledger query audit result")
        self.content_address = _address(content_address, "ledger query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger query audit version or boundary is not current")
        if self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("ledger query audit checks do not replay")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("ledger query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "query_id": self.query_id, "version": self.version, "boundary": self.boundary, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed": self.passed, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit":
        value = _mapping(value, "ledger query audit")
        _strict(value, set(cls.FIELDS), "ledger query audit")
        return cls(value["query_address"], value["query_id"], value["version"], value["boundary"], tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "ledger query audit checks", MAX_CHECKS)), value["check_count"], value["passed"], value["content_address"])


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck):
        raise ValidationError("ledger query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit):
        raise ValidationError("ledger query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck:
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck(check_id, observed == expected, observed, expected, "pending:ledger-query-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck(check_id, provisional.passed, observed, expected, address_check(provisional))


def audit_query(value: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery, ledger: ledger_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit:
    if not isinstance(value, query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery) or not isinstance(ledger, ledger_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedger):
        raise ValidationError("ledger query audit requires typed query and ledger")
    value = query_model.query_from_mapping(value.to_dict())
    ledger = ledger_model.verify_ledger(ledger)
    expected = query_model.query_ledger(ledger, query_id=value.query_id, resources=value.resources, transition=value.transition_filter, state=value.state_filter, decision=value.decision_filter, text=value.text_filter, offset=value.offset, limit=value.limit)
    checks = (
        _check("version", value.version, query_model.VERSION),
        _check("boundary", value.boundary, query_model.BOUNDARY),
        _check("resource-order", value.resources, tuple(item for item in query_model.RESOURCES if item in value.resources)),
        _check("filter-replay", (value.transition_filter, value.state_filter, value.decision_filter, value.text_filter, value.offset, value.limit), (expected.transition_filter, expected.state_filter, expected.decision_filter, expected.text_filter, expected.offset, expected.limit)),
        _check("count-replay", (value.total_count, value.returned_count, value.truncated), (expected.total_count, expected.returned_count, expected.truncated)),
        _check("row-order", tuple(item.ordinal for item in value.rows), tuple(range(value.offset, value.offset + value.returned_count))),
        _check("row-addresses", tuple(item.row_address for item in value.rows), tuple(item.row_address for item in expected.rows)),
        _check("row-membership", tuple(item.to_dict() for item in value.rows), tuple(item.to_dict() for item in expected.rows)),
        _check("resource-semantics", tuple(item.resource for item in value.rows), tuple(item.resource for item in expected.rows)),
        _check("ledger-linkage", (value.ledger_id, value.ledger_address), (ledger.ledger_id, ledger.content_address)),
        _check("public-boundary", ledger_model._public(value.to_dict()), True),
        _check("mapping-round-trip", query_model.query_from_mapping(value.to_dict()).content_address, value.content_address),
    )
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit(value.content_address, value.query_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), "pending:ledger-query-audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit(value.content_address, value.query_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit.from_mapping(value)


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Exact archive-transfer recovery execution ledger query audit", "", f"- Query: `{value.query_id}`", f"- Checks: `{value.check_count}`", f"- Passed: `{str(value.passed).lower()}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | observed | expected |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {index} | `{item.check_id}` | `{str(item.passed).lower()}` | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for index, item in enumerate(value.checks, 1))
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "query_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": MAX_CHECKS, "operations": ("audit_query", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
