from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery as recovery_model
from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "recovery-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("recovery_address", "query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or value.startswith(("/", "\\")) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 1024)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
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


class ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck:
    """One independently addressed recovery-query assertion."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "query audit ordinal", MAX_CHECKS, positive=True)
        if check_id not in CHECK_IDS or CHECK_IDS[self.ordinal - 1] != check_id:
            raise ValidationError("query audit check identity or order is invalid")
        self.check_id = check_id
        if not isinstance(passed, bool):
            raise ValidationError("query audit result must be boolean")
        self.passed = passed
        self.detail = _text(detail, "query audit detail")
        self.evidence_addresses = tuple(_address(item, "query audit evidence address") for item in _sequence(evidence_addresses, "query audit evidence", 16))
        if not self.evidence_addresses:
            raise ValidationError("query audit check needs evidence")
        self.content_address = _address(content_address, "query audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck:
        value = _mapping(value, "history diff archive transfer recovery query audit check")
        _strict(value, set(cls.FIELDS), "history diff archive transfer recovery query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryQueryAudit:
    """Independent audit receipt for a bounded recovery query."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, recovery_address: str, query_address: str, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.recovery_address = _address(recovery_address, "query audit recovery address", recovery_model.RECOVERY_PREFIX)
        self.query_address = _address(query_address, "query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "query audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "query audit failed count", MAX_CHECKS)
        if not isinstance(accepted, bool):
            raise ValidationError("query audit acceptance must be boolean")
        self.accepted = accepted
        self.content_address = _address(content_address, "query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("query audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("query audit counters do not replay")
        if any(self.recovery_address not in item.evidence_addresses for item in self.checks):
            raise ValidationError("query audit evidence does not retain the recovery address")
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("query audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"recovery_address": self.recovery_address, "query_address": self.query_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryQueryAudit:
        value = _mapping(value, "history diff archive transfer recovery query audit")
        _strict(value, set(cls.FIELDS), "history diff archive transfer recovery query audit")
        return cls(value["recovery_address"], value["query_address"], tuple(ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "query audit checks", MAX_CHECKS)), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck):
        raise ValidationError("query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryQueryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryQueryAudit):
        raise ValidationError("query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck:
    pending = ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck(ordinal, check_id, bool(passed), detail, evidence, "pending:query-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck(ordinal, check_id, bool(passed), detail, evidence, address_check(pending))


def _row_key(row: query_model.ExactHistoryDiffArchiveTransferRecoveryQueryRow) -> tuple[Any, ...]:
    return (row.resource, row.ordinal, row.chunk_index, row.content_address)


def _semantics(rows: Sequence[query_model.ExactHistoryDiffArchiveTransferRecoveryQueryRow]) -> tuple[bool, ...]:
    values = []
    for row in rows:
        if row.resource in {"actions", "missing"}:
            values.append(row.chunk_index >= 0 and row.missing and not row.received and bool(row.chunk_address))
        elif row.resource == "received":
            values.append(row.chunk_index >= 0 and row.received and not row.missing)
        else:
            values.append(row.chunk_index == -1 and row.received and not row.missing)
    return tuple(values)


def audit_query(query: query_model.ExactHistoryDiffArchiveTransferRecoveryQuery, recovery: recovery_model.ExactHistoryDiffArchiveTransferRecovery) -> ExactHistoryDiffArchiveTransferRecoveryQueryAudit:
    """Recompute the requested page and receipt every visible query invariant."""
    if not isinstance(query, query_model.ExactHistoryDiffArchiveTransferRecoveryQuery) or not isinstance(recovery, recovery_model.ExactHistoryDiffArchiveTransferRecovery):
        raise ValidationError("recovery query audit requires typed query and recovery")
    query = query_model.query_from_mapping(query.to_dict())
    recovery = recovery_model.recovery_from_mapping(recovery.to_dict())
    expected = query_model.query_recovery(recovery, resources=query.resources, index=None if query.index < 0 else query.index, state=query.state_filter, received=query.received_filter, text=query.text_filter, offset=query.offset, limit=query.limit)
    evidence = (recovery.content_address, query.content_address, *(item.content_address for item in query.rows[:8]))
    checks = (
        _check(1, "version", query.version == query_model.VERSION, "query version derives from the recovery contract", evidence),
        _check(2, "boundary", query.boundary == query_model.BOUNDARY, "query boundary derives from the recovery contract", evidence),
        _check(3, "resource-order", query.resources == tuple(sorted(query.resources, key=query_model.RESOURCES.index)), "query resources retain canonical order", evidence),
        _check(4, "filter-replay", (query.index, query.state_filter, query.received_filter, query.text_filter, query.offset, query.limit) == (expected.index, expected.state_filter, expected.received_filter, expected.text_filter, expected.offset, expected.limit), "query filters replay", evidence),
        _check(5, "count-replay", query.row_count == expected.row_count, "query row count replays", evidence),
        _check(6, "row-order", tuple(_row_key(item) for item in query.rows) == tuple(_row_key(item) for item in expected.rows), "query rows retain page order", evidence),
        _check(7, "row-addresses", tuple(item.content_address for item in query.rows) == tuple(item.content_address for item in expected.rows), "query row addresses replay", evidence),
        _check(8, "row-membership", tuple(item.to_dict() for item in query.rows) == tuple(item.to_dict() for item in expected.rows), "query rows equal the independently recomputed page", evidence),
        _check(9, "resource-semantics", _semantics(query.rows) == tuple(True for _ in query.rows), "query rows retain resource and receiver semantics", evidence),
        _check(10, "recovery-linkage", query.recovery_address == recovery.content_address and all(item.recovery_address == recovery.content_address and item.recovery_id == recovery.recovery_id for item in query.rows), "query links to the exact recovery snapshot", evidence),
        _check(11, "public-boundary", recovery_model.transfer_model._public(query.to_dict()), "query is bounded and value-free", evidence),
        _check(12, "mapping-round-trip", query_model.query_from_mapping(query.to_dict()).to_dict() == query.to_dict(), "query mapping round-trips exactly", evidence),
    )
    body = {"recovery_address": recovery.content_address, "query_address": query.content_address, "checks": checks, "check_count": MAX_CHECKS, "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = ExactHistoryDiffArchiveTransferRecoveryQueryAudit(**body, content_address="pending:query-audit")
    return ExactHistoryDiffArchiveTransferRecoveryQueryAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryQueryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryQueryAudit.from_mapping(value)


def verify_audit(value: ExactHistoryDiffArchiveTransferRecoveryQueryAudit) -> ExactHistoryDiffArchiveTransferRecoveryQueryAudit:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryQueryAudit):
        raise ValidationError("query audit verification requires a typed audit")
    value._validate()
    if not value.accepted:
        raise ValidationError("query audit contains failed checks")
    return value


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict() | {"evidence_addresses": canonical_json(item.evidence_addresses)})
    return stream.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Exact runtime-registry history-diff archive transfer recovery query audit", "", f"- Recovery: `{value.recovery_address}`", f"- Query: `{value.query_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact runtime-registry history-diff archive transfer recovery query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact runtime-registry history-diff archive transfer recovery query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"recovery_address": {"type": "string", "pattern": "^" + recovery_model.RECOVERY_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_count": MAX_CHECKS, "checks": list(CHECK_IDS), "features": ["independent query recomputation", "row order and address replay", "resource semantics", "recovery linkage", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "ExactHistoryDiffArchiveTransferRecoveryQueryAudit", "ExactHistoryDiffArchiveTransferRecoveryQueryAuditCheck", "MAX_CHECKS", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
