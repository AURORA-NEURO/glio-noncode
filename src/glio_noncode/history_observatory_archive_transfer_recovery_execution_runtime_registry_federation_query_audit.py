"""Independent assurance for runtime registry federation queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation as federation_model
from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = federation_model.FEDERATION_PREFIX + "-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
MAX_CHECKS = 12
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "federation-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "federation_address", "query_id", "federation_id", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
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
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValidationError(f"{field} must be a string-keyed object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("path", "payload", "agent", "language")) or not _public(item):
                return False
    elif isinstance(value, (tuple, list)):
        return all(_public(item) for item in value)
    return not isinstance(value, (bytes, bytearray))


class RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry federation query audit check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "runtime registry federation query audit check ID")
        self.passed = _bool(passed, "runtime registry federation query audit check result")
        self.detail = _text(detail, "runtime registry federation query audit check detail", 1024)
        self.evidence_addresses = tuple(_address(item, "runtime registry federation query audit evidence address") for item in _sequence(evidence_addresses, "runtime registry federation query audit evidence", 16))
        self.content_address = _address(content_address, "runtime registry federation query audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or not _public(self.to_dict()):
            raise ValidationError("runtime registry federation query audit check is invalid")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime registry federation query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck":
        value = _mapping(value, "runtime registry federation query audit check")
        _strict(value, set(cls.FIELDS), "runtime registry federation query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck):
        raise ValidationError("runtime registry federation query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RecoveryExecutionRuntimeRegistryFederationQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, federation_address: str, query_id: str, federation_id: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.query_address = _address(query_address, "runtime registry federation query audit query address", query_model.QUERY_PREFIX)
        self.federation_address = _address(federation_address, "runtime registry federation query audit federation address", federation_model.FEDERATION_PREFIX)
        self.query_id = _label(query_id, "runtime registry federation query audit query ID")
        self.federation_id = _label(federation_id, "runtime registry federation query audit federation ID")
        self.version = _text(version, "runtime registry federation query audit version", 1024)
        self.boundary = _text(boundary, "runtime registry federation query audit boundary", 1024)
        self.check_count = _count(check_count, "runtime registry federation query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry federation query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry federation query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry federation query audit acceptance")
        self.checks = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck) else RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime registry federation query audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "runtime registry federation query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        expected_passed = sum(item.passed for item in self.checks)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime registry federation query audit version or boundary is not current")
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count != expected_passed or self.failed_count != self.check_count - expected_passed:
            raise ValidationError("runtime registry federation query audit counts do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry federation query audit checks are not ordered")
        if self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("runtime registry federation query audit acceptance or public boundary is invalid")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime registry federation query audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "federation_address": self.federation_address, "query_id": self.query_id, "federation_id": self.federation_id, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationQueryAudit":
        value = _mapping(value, "runtime registry federation query audit")
        _strict(value, set(cls.FIELDS), "runtime registry federation query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RecoveryExecutionRuntimeRegistryFederationQueryAudit) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationQueryAudit):
        raise ValidationError("runtime registry federation query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def audit_query(value: query_model.RecoveryExecutionRuntimeRegistryFederationQuery, federation: federation_model.RecoveryExecutionRuntimeRegistryFederation) -> RecoveryExecutionRuntimeRegistryFederationQueryAudit:
    if not isinstance(value, query_model.RecoveryExecutionRuntimeRegistryFederationQuery) or not isinstance(federation, federation_model.RecoveryExecutionRuntimeRegistryFederation):
        raise ValidationError("runtime registry federation query audit requires typed query and federation")
    checks: list[RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck] = []

    def add(check_id: str, passed: bool, detail: str, evidence: Sequence[str] = ()) -> None:
        provisional = RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck(len(checks) + 1, check_id, bool(passed), detail, tuple(evidence)[:16], CHECK_PREFIX + ":pending")
        checks.append(RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional)))

    add("version", value_model_version(value) == query_model.VERSION, "query version matches the current contract", (value.content_address,))
    add("boundary", query_model.BOUNDARY == federation_model.BOUNDARY + "_query", "query boundary matches the current contract", (value.content_address,))
    add("resource-order", value.resources == tuple(item for item in query_model.RESOURCES if item in value.resources), "query resources use canonical order", (value.content_address,))
    try:
        replay = query_model.query_federation(federation, query_id=value.query_id, resources=value.resources, state=value.state_filter, key=value.key_filter, text=value.text_filter, offset=value.offset, limit=value.limit)
        replay_mapping = replay.to_dict()
    except (TypeError, ValueError, ValidationError):
        replay = None
        replay_mapping = None
    add("filter-replay", replay_mapping == value.to_dict() if replay_mapping is not None else False, "query filters replay the exact page", (value.content_address,))
    add("count-replay", value.total_count >= value.returned_count == len(value.rows) and value.truncated == (value.offset + value.returned_count < value.total_count), "query counts and truncation replay", (value.content_address,))
    add("row-order", tuple(item.ordinal for item in value.rows) == tuple(range(1, value.returned_count + 1)), "query row ordinals are contiguous", tuple(item.row_address for item in value.rows))
    add("row-addresses", all(query_model.address_row(item) == item.row_address for item in value.rows), "query row addresses replay", tuple(item.row_address for item in value.rows))
    expected_rows = tuple(replay.rows) if replay is not None else ()
    add("row-membership", tuple(item.to_dict() for item in value.rows) == tuple(item.to_dict() for item in expected_rows), "returned rows match the independently recomputed page", tuple(item.row_address for item in value.rows))
    add("resource-semantics", all(item.resource in query_model.RESOURCES and item.key and item.address and item.state in query_model.STATES for item in value.rows), "rows retain bounded resource semantics", tuple(item.row_address for item in value.rows))
    add("federation-linkage", value.federation_id == federation.federation_id and value.federation_address == federation.content_address, "query links to the requested federation", (value.federation_address, federation.content_address))
    add("public-boundary", _public(value.to_dict()), "query projection contains only public bounded fields", (value.content_address,))
    try:
        round_trip = query_model.query_from_mapping(json.loads(query_model.query_json(value))).content_address == value.content_address
    except (TypeError, ValueError, ValidationError):
        round_trip = False
    add("mapping-round-trip", round_trip, "canonical query mapping preserves its address", (value.content_address,))
    checks = tuple(checks)
    provisional = RecoveryExecutionRuntimeRegistryFederationQueryAudit(value.content_address, value.federation_address, value.query_id, value.federation_id, VERSION, BOUNDARY, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), checks, AUDIT_PREFIX + ":pending")
    return RecoveryExecutionRuntimeRegistryFederationQueryAudit(provisional.query_address, provisional.federation_address, provisional.query_id, provisional.federation_id, provisional.version, provisional.boundary, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, provisional.checks, address_audit(provisional))


def value_model_version(value: query_model.RecoveryExecutionRuntimeRegistryFederationQuery) -> str:
    if not isinstance(value, query_model.RecoveryExecutionRuntimeRegistryFederationQuery):
        raise ValidationError("query version requires a typed query")
    return query_model.VERSION


def verify_audit(value: RecoveryExecutionRuntimeRegistryFederationQueryAudit) -> RecoveryExecutionRuntimeRegistryFederationQueryAudit:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationQueryAudit):
        raise ValidationError("runtime registry federation query audit verification requires a typed audit")
    return RecoveryExecutionRuntimeRegistryFederationQueryAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryFederationQueryAudit:
    return RecoveryExecutionRuntimeRegistryFederationQueryAudit.from_mapping(value)


def audit_json(value: RecoveryExecutionRuntimeRegistryFederationQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RecoveryExecutionRuntimeRegistryFederationQueryAudit) -> str:
    value = verify_audit(value)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "check_id", "passed", "detail", "evidence_count", "content_address"))
    for item in value.checks:
        writer.writerow((item.ordinal, item.check_id, item.passed, item.detail, len(item.evidence_addresses), item.content_address))
    return output.getvalue()


def render_audit_markdown(value: RecoveryExecutionRuntimeRegistryFederationQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Recovery Execution Runtime Registry Federation Query Audit", "", f"- Federation: `{value.federation_id}`", f"- Query: `{value.query_id}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "maxItems": 16, "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederationQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "federation_address": {"type": "string"}, "query_id": {"type": "string"}, "federation_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_count": MAX_CHECKS, "check_ids": list(CHECK_IDS), "operations": ["audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"], "privacy": {"values": False, "source_paths": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "MAX_CHECKS", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "RecoveryExecutionRuntimeRegistryFederationQueryAuditCheck", "RecoveryExecutionRuntimeRegistryFederationQueryAudit", "address_check", "address_audit", "audit_query", "value_model_version", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
