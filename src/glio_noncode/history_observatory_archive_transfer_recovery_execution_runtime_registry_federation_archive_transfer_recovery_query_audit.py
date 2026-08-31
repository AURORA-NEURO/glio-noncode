"""Independent audit receipts for recovery query results."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery as recovery_model
from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "recovery-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "content_address")
AUDIT_FIELDS = ("query_address", "recovery_address", "recovery_id", "version", "boundary", "checks", "check_count", "passed", "content_address")
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


class RecoveryQueryAuditCheck:
    """One independently recomputed query invariant."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, content_address: str) -> None:
        self.check_id = _label(check_id, "query audit check ID")
        self.passed = _bool(passed, "query audit check result")
        self.observed = observed
        self.expected = expected
        self.content_address = _address(content_address, "query audit check address", CHECK_PREFIX, allow_pending=True)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("query audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("query audit check address does not replay")
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("query audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryQueryAuditCheck:
        value = _mapping(value, "query audit check")
        _strict(value, set(cls.FIELDS), "query audit check")
        return cls(value["check_id"], value["passed"], value["observed"], value["expected"], value["content_address"])


class RecoveryQueryAudit:
    """Canonical audit receipt for a bounded recovery query."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, recovery_address: str, recovery_id: str, version: str, boundary: str, checks: Sequence[RecoveryQueryAuditCheck], check_count: int, passed: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "query audit query address", query_model.QUERY_PREFIX)
        self.recovery_address = _address(recovery_address, "query audit recovery address", recovery_model.RECOVERY_PREFIX)
        self.recovery_id = _label(recovery_id, "query audit recovery ID")
        self.version = _text(version, "query audit version", 2048)
        self.boundary = _text(boundary, "query audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, RecoveryQueryAuditCheck) else RecoveryQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "query audit checks", MAX_CHECKS))
        if isinstance(check_count, bool) or not isinstance(check_count, int) or check_count != len(self.checks) or check_count != MAX_CHECKS:
            raise ValidationError("query audit check count is inconsistent")
        self.check_count = check_count
        self.passed = _bool(passed, "query audit result")
        self.content_address = _address(content_address, "query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("query audit checks are incomplete or inconsistent")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("query audit address does not replay")
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "recovery_address": self.recovery_address, "recovery_id": self.recovery_id, "version": self.version, "boundary": self.boundary, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed": self.passed, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryQueryAudit:
        value = _mapping(value, "query audit")
        _strict(value, set(cls.FIELDS), "query audit")
        return cls(value["query_address"], value["recovery_address"], value["recovery_id"], value["version"], value["boundary"], tuple(RecoveryQueryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "query audit checks", MAX_CHECKS)), value["check_count"], value["passed"], value["content_address"])


def address_check(value: RecoveryQueryAuditCheck) -> str:
    if not isinstance(value, RecoveryQueryAuditCheck):
        raise ValidationError("query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: RecoveryQueryAudit) -> str:
    if not isinstance(value, RecoveryQueryAudit):
        raise ValidationError("query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any) -> RecoveryQueryAuditCheck:
    pending = RecoveryQueryAuditCheck(check_id, observed == expected, observed, expected, "pending:recovery-query-audit-check")
    return RecoveryQueryAuditCheck(check_id, pending.passed, observed, expected, address_check(pending))


def _row_key(row: query_model.RecoveryQueryRow) -> tuple[Any, ...]:
    return (row.resource, row.ordinal, row.chunk_index)


def _semantics(rows: Sequence[query_model.RecoveryQueryRow]) -> tuple[bool, ...]:
    values = []
    for row in rows:
        values.append((row.resource in ("actions", "missing") and row.missing and not row.received) or (row.resource == "received" and row.received and not row.missing) or (row.resource in ("summary", "state", "bounds") and row.chunk_index == -1))
    return tuple(values)


def audit_query(value: query_model.RecoveryQuery, recovery: recovery_model.TransferRecovery) -> RecoveryQueryAudit:
    """Recompute the requested page and receipt every visible query invariant."""
    if not isinstance(value, query_model.RecoveryQuery) or not isinstance(recovery, recovery_model.TransferRecovery):
        raise ValidationError("query audit requires typed query and recovery")
    value = query_model.query_from_mapping(value.to_dict())
    recovery = recovery_model.recovery_from_mapping(recovery.to_dict())
    expected = query_model.query_recovery(recovery, resources=value.resources, index=value.index, state=value.state_filter, received=value.received_filter, text=value.text_filter, offset=value.offset, limit=value.limit)
    observed_rows = tuple(item.to_dict() for item in value.rows)
    expected_rows = tuple(item.to_dict() for item in expected.rows)
    checks = (
        _check("version", value.version, query_model.VERSION),
        _check("boundary", value.boundary, query_model.BOUNDARY),
        _check("resource-order", value.resources, expected.resources),
        _check("filter-replay", (value.index, value.state_filter, value.received_filter, value.text_filter, value.offset, value.limit), (expected.index, expected.state_filter, expected.received_filter, expected.text_filter, expected.offset, expected.limit)),
        _check("count-replay", value.row_count, expected.row_count),
        _check("row-order", tuple(_row_key(item) for item in value.rows), tuple(_row_key(item) for item in expected.rows)),
        _check("row-addresses", tuple(item.content_address for item in value.rows), tuple(item.content_address for item in expected.rows)),
        _check("row-membership", observed_rows, expected_rows),
        _check("resource-semantics", _semantics(value.rows), tuple(True for _ in value.rows)),
        _check("recovery-linkage", tuple((item.recovery_id, item.recovery_address) for item in value.rows), tuple((recovery.recovery_id, recovery.content_address) for _ in value.rows)),
        _check("public-boundary", recovery_model.transfer_model._public(value.to_dict()), True),
        _check("mapping-round-trip", query_model.query_from_mapping(value.to_dict()).to_dict(), value.to_dict()),
    )
    provisional = RecoveryQueryAudit(value.content_address, recovery.content_address, recovery.recovery_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), "pending:recovery-query-audit")
    return RecoveryQueryAudit(value.content_address, recovery.content_address, recovery.recovery_id, VERSION, BOUNDARY, checks, len(checks), provisional.passed, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RecoveryQueryAudit:
    return RecoveryQueryAudit.from_mapping(value)


def audit_json(value: RecoveryQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: RecoveryQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict() | {"observed": canonical_json(item.observed), "expected": canonical_json(item.expected)})
    return stream.getvalue()


def render_audit_markdown(value: RecoveryQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# History observatory federation archive transfer recovery query audit", "", f"- Recovery: `{value.recovery_id}`", f"- Result: `{'passed' if value.passed else 'failed'}`", f"- Checks: `{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed |", "| --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "History observatory federation archive transfer recovery query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "History observatory federation archive transfer recovery query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "recovery_address": {"type": "string", "pattern": "^" + recovery_model.RECOVERY_PREFIX + ":"}, "recovery_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "check_count": {"const": MAX_CHECKS}, "passed": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "features": ["query specification replay", "row order and address replay", "resource semantics", "recovery linkage", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "RecoveryQueryAudit", "RecoveryQueryAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
