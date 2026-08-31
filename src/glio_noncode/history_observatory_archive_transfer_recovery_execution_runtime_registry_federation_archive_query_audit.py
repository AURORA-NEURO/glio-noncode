"""Independent assurance for runtime-registry federation archive queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive as archive_model
from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
MAX_CHECKS = 12
CHECK_IDS = ("version", "boundary", "query-address", "archive-linkage", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_id", "archive_id", "archive_address", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
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
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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


class RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "archive query audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "archive query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("archive query audit check ID is unsupported")
        self.passed = _bool(passed, "archive query audit check result")
        self.detail = _text(detail, "archive query audit check detail", 2048)
        self.evidence_addresses = tuple(_address(item, "archive query audit evidence address", allow_pending=True) for item in _sequence(evidence_addresses, "archive query audit evidence addresses", 64))
        self.content_address = _address(content_address, "archive query audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("archive query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("archive query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck":
        value = _mapping(value, "archive query audit check")
        _strict(value, set(cls.FIELDS), "archive query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck):
        raise ValidationError("archive query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_id: str, archive_id: str, archive_address: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "archive query audit query ID")
        self.archive_id = _label(archive_id, "archive query audit archive ID")
        self.archive_address = _address(archive_address, "archive query audit archive address", archive_model.ARCHIVE_PREFIX)
        self.version = _text(version, "archive query audit version", 2048)
        self.boundary = _text(boundary, "archive query audit boundary", 2048)
        self.check_count = _count(check_count, "archive query audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "archive query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "archive query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "archive query audit acceptance")
        self.checks = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck) else RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "archive query audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "archive query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("archive query audit conservation or ordering does not replay")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks):
            raise ValidationError("archive query audit result counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("archive query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("archive query audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "archive_id": self.archive_id, "archive_address": self.archive_address, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("query_id", "archive_id", "archive_address", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit":
        value = _mapping(value, "archive query audit")
        _strict(value, set(cls.FIELDS), "archive query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit):
        raise ValidationError("archive query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def audit_query(query: query_model.RecoveryExecutionRuntimeRegistryFederationArchiveQuery, archive: archive_model.RecoveryExecutionRuntimeRegistryFederationArchive) -> RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit:
    if not isinstance(query, query_model.RecoveryExecutionRuntimeRegistryFederationArchiveQuery) or not isinstance(archive, archive_model.RecoveryExecutionRuntimeRegistryFederationArchive):
        raise ValidationError("archive query audit requires typed query and archive")
    checks: list[RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck] = []

    def add(check_id: str, passed: bool, detail: str, evidence: Sequence[str] = ()) -> None:
        provisional = RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck(len(checks) + 1, check_id, bool(passed), detail, evidence, CHECK_PREFIX + ":pending")
        checks.append(RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional)))

    recomputed = None
    try:
        recomputed = query_model.query_archive(archive, query_id=query.query_id, resources=query.resources, state=query.state_filter, key=query.key_filter, text=query.text_filter, offset=query.offset, limit=query.limit)
    except ValidationError:
        recomputed = None
    add("version", query_model.VERSION == archive_model.VERSION + "-query-v1", "query version derives from the archive contract", (query.content_address,))
    add("boundary", query_model.BOUNDARY == archive_model.BOUNDARY + "_query", "query boundary derives from the archive contract", (query.content_address,))
    add("query-address", query_model.address_query(query) == query.content_address, "query address replays from its public projection", (query.content_address,))
    add("archive-linkage", query.archive_id == archive.archive_id and query.archive_address == archive.content_address, "query links to the inspected archive", (query.archive_address, archive.content_address))
    add("filter-replay", recomputed is not None and recomputed.resources == query.resources and recomputed.state_filter == query.state_filter and recomputed.key_filter == query.key_filter and recomputed.text_filter == query.text_filter and recomputed.offset == query.offset and recomputed.limit == query.limit, "query filters replay exactly", (query.content_address,))
    add("count-replay", recomputed is not None and recomputed.total_count == query.total_count and recomputed.returned_count == query.returned_count and recomputed.truncated == query.truncated, "query counts and truncation replay", (query.content_address,))
    add("row-order", tuple(item.ordinal for item in query.rows) == tuple(range(1, query.returned_count + 1)), "query rows are contiguous and page-local", tuple(item.row_address for item in query.rows))
    add("row-addresses", all(query_model.address_row(item) == item.row_address for item in query.rows), "every query row address replays", tuple(item.row_address for item in query.rows))
    add("row-membership", recomputed is not None and tuple(item.to_dict() for item in recomputed.rows) == tuple(item.to_dict() for item in query.rows), "every row belongs to the recomputed filtered page", (query.content_address,))
    add("resource-semantics", all(item.resource in query.resources and item.state in query_model.STATES for item in query.rows), "rows use only requested resources and valid states", tuple(item.row_address for item in query.rows))
    add("public-boundary", _public(query.to_dict()), "query projection contains only bounded public fields", (query.content_address,))
    mapping_ok = False
    try:
        mapping_ok = query_model.query_from_mapping(query.to_dict()).content_address == query.content_address
    except ValidationError:
        mapping_ok = False
    add("mapping-round-trip", mapping_ok, "public query mapping rehydrates to the same address", (query.content_address,))
    passed_count = sum(item.passed for item in checks)
    provisional = RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit(query.query_id, archive.archive_id, archive.content_address, VERSION, BOUNDARY, len(checks), passed_count, len(checks) - passed_count, passed_count == len(checks), checks, AUDIT_PREFIX + ":pending")
    return RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit(provisional.query_id, provisional.archive_id, provisional.archive_address, provisional.version, provisional.boundary, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, provisional.checks, address_audit(provisional))


def verify_audit(value: RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit) -> RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit):
        raise ValidationError("archive query audit verification requires a typed audit")
    value._validate()
    if not value.accepted:
        raise ValidationError("archive query audit contains failed checks")
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit:
    return verify_audit(RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit.from_mapping(value))


def audit_json(value: RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit) -> str:
    return canonical_json(RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit) -> str:
    value = RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit.from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address"))
    for item in value.checks:
        writer.writerow((item.ordinal, item.check_id, item.passed, item.detail, "|".join(item.evidence_addresses), item.content_address))
    return output.getvalue()


def render_audit_markdown(value: RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit) -> str:
    value = RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit.from_mapping(value.to_dict())
    lines = ["# Runtime Registry Federation Archive Query Audit", "", f"- Archive: `{value.archive_id}`", f"- Query: `{value.query_id}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime registry federation archive query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime registry federation archive query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_id": {"type": "string"}, "archive_id": {"type": "string"}, "archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_count": MAX_CHECKS, "check_ids": list(CHECK_IDS), "operations": ["audit_query", "verify_audit", "audit_json", "audit_csv", "render_audit_markdown"], "privacy": {"values": False, "source_paths": False, "embedded_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "MAX_CHECKS", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "RecoveryExecutionRuntimeRegistryFederationArchiveQueryAuditCheck", "RecoveryExecutionRuntimeRegistryFederationArchiveQueryAudit", "address_check", "address_audit", "audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
