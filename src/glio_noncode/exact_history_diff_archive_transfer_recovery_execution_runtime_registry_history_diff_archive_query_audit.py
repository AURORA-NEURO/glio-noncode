"""Independent assurance for bounded history-diff archive queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff_archive as archive_model
from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
MAX_CHECKS = 13
CHECK_IDS = ("version", "boundary", "query-address", "archive-linkage", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "pagination-bounds", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_id", "archive_id", "archive_address", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 1024)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be a public content address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return archive_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff archive query audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "history diff archive query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("history diff archive query audit check ID is unsupported")
        self.passed = _bool(passed, "history diff archive query audit check result")
        self.detail = _text(detail, "history diff archive query audit check detail", 2048)
        self.evidence_addresses = tuple(_address(item, "history diff archive query audit evidence address", allow_pending=True) for item in _sequence(evidence_addresses, "history diff archive query audit evidence addresses", 64))
        self.content_address = _address(content_address, "history diff archive query audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("history diff archive query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck:
        value = _mapping(value, "history diff archive query audit check")
        _strict(value, set(cls.FIELDS), "history diff archive query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck):
        raise ValidationError("history diff archive query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_id: str, archive_id: str, archive_address: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "history diff archive query audit query ID")
        self.archive_id = _label(archive_id, "history diff archive query audit archive ID")
        self.archive_address = _address(archive_address, "history diff archive query audit archive address", archive_model.ARCHIVE_PREFIX)
        self.version = _text(version, "history diff archive query audit version", 2048)
        self.boundary = _text(boundary, "history diff archive query audit boundary", 2048)
        self.check_count = _count(check_count, "history diff archive query audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "history diff archive query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history diff archive query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "history diff archive query audit acceptance")
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "history diff archive query audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "history diff archive query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("history diff archive query audit conservation or ordering does not replay")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks):
            raise ValidationError("history diff archive query audit result counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("history diff archive query audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "archive_id": self.archive_id, "archive_address": self.archive_address, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit:
        value = _mapping(value, "history diff archive query audit")
        _strict(value, set(cls.FIELDS), "history diff archive query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit):
        raise ValidationError("history diff archive query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def audit_query(query: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery, archive: archive_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchive) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit:
    if not isinstance(query, query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery) or not isinstance(archive, archive_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchive):
        raise ValidationError("history diff archive query audit requires a typed query and archive")
    checks: list[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck] = []

    def add(check_id: str, passed: bool, detail: str, evidence: Sequence[str] = ()) -> None:
        provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck(len(checks) + 1, check_id, bool(passed), detail, evidence, CHECK_PREFIX + ":pending")
        checks.append(ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional)))

    expected: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQuery | None = None
    try:
        expected = query_model.query_archive(archive, query_id=query.query_id, resources=query.resources, key=query.key_filter, text=query.text_filter, offset=query.offset, limit=query.limit)
    except ValidationError:
        expected = None
    add("version", query_model.VERSION == query_model.VERSION and expected is not None, "query version is produced by the current contract", (query.content_address,))
    add("boundary", query_model.BOUNDARY == query_model.BOUNDARY and expected is not None, "query boundary is produced by the current contract", (query.content_address,))
    add("query-address", query_model.address_query(query) == query.content_address, "query address replays from the public query", (query.content_address,))
    add("archive-linkage", query.archive_id == archive.archive_id and query.archive_address == archive.content_address, "query links to the requested archive", (query.archive_address, archive.content_address))
    filter_ok = expected is not None and query.to_dict() | {"content_address": None} == expected.to_dict() | {"content_address": None}
    add("filter-replay", filter_ok, "resource and filter shape replays through the archive", (query.content_address, archive.content_address))
    count_ok = expected is not None and (query.total_count, query.returned_count, query.truncated) == (expected.total_count, expected.returned_count, expected.truncated)
    add("count-replay", count_ok, "filtered counts and truncation replay", (query.content_address,))
    order_ok = tuple(row.ordinal for row in query.rows) == tuple(range(query.offset + 1, query.offset + query.returned_count + 1))
    add("row-order", order_ok, "returned row ordinals are contiguous at the requested offset", tuple(row.row_address for row in query.rows))
    addresses_ok = all(query_model.address_row(row) == row.row_address for row in query.rows)
    add("row-addresses", addresses_ok, "every returned row address replays", tuple(row.row_address for row in query.rows))
    membership_ok = expected is not None and tuple(row.to_dict() for row in query.rows) == tuple(row.to_dict() for row in expected.rows)
    add("row-membership", membership_ok, "returned rows match the independently recomputed page", (query.content_address,))
    resource_ok = all(row.resource in query.resources for row in query.rows) and len(query.resources) == len(set(query.resources))
    add("resource-semantics", resource_ok, "every returned row belongs to a requested resource", (query.content_address,))
    pagination_ok = query.offset <= query_model.MAX_OFFSET and 1 <= query.limit <= query_model.MAX_LIMIT and query.returned_count <= query.limit and query.total_count <= query_model.MAX_ROWS
    add("pagination-bounds", pagination_ok, "offset, limit, row, and total bounds are enforced", (query.content_address,))
    add("public-boundary", _public(query.to_dict()), "query projection contains only bounded public fields", (query.content_address,))
    mapping_ok = False
    try:
        mapping_ok = query_model.query_from_mapping(query.to_dict()).content_address == query.content_address
    except ValidationError:
        mapping_ok = False
    add("mapping-round-trip", mapping_ok, "public query mapping rehydrates to the same address", (query.content_address,))
    passed_count = sum(item.passed for item in checks)
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit(query.query_id, query.archive_id, query.archive_address, VERSION, BOUNDARY, len(checks), passed_count, len(checks) - passed_count, passed_count == len(checks), checks, AUDIT_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit(provisional.query_id, provisional.archive_id, provisional.archive_address, provisional.version, provisional.boundary, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, provisional.checks, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit.from_mapping(value)


def verify_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit):
        raise ValidationError("history diff archive query audit verification requires a typed audit")
    value._validate()
    if not value.accepted:
        raise ValidationError("history diff archive query audit contains failed checks")
    return value


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    for item in value.checks:
        writer.writerow((item.ordinal, item.check_id, item.passed, item.detail, "|".join(item.evidence_addresses), item.content_address))
    return output.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Federation History-Diff Archive Query Audit", "", f"- Query: `{value.query_id}`", f"- Archive: `{value.archive_id}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationRuntimeRegistryHistoryDiffArchiveQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationRuntimeRegistryHistoryDiffArchiveQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_id": {"type": "string"}, "archive_id": {"type": "string"}, "archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_count": MAX_CHECKS, "check_ids": list(CHECK_IDS), "operations": ["audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"], "privacy": {"values": False, "source_paths": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "MAX_CHECKS", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAuditCheck", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffArchiveQueryAudit", "address_check", "address_audit", "audit_query", "audit_from_mapping", "verify_audit", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
