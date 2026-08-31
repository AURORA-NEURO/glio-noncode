"""Independent assurance checks for history-diff recovery runtime registry queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry as registry_model
from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-membership", "resource-semantics", "registry-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "registry_address", "query_id", "registry_id", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
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


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck:
    """One addressed query assurance finding."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "history-diff runtime registry query audit ordinal", MAX_CHECKS, lower=1)
        if check_id not in CHECK_IDS:
            raise ValidationError("history-diff runtime registry query audit check is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "history-diff runtime registry query audit result")
        self.detail = _text(detail, "history-diff runtime registry query audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "history-diff runtime registry query audit evidence address") for item in _sequence(evidence_addresses, "history-diff runtime registry query audit evidence", 16))
        self.content_address = _address(content_address, "history-diff runtime registry query audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("history-diff runtime registry query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("history-diff runtime registry query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck:
        value = _mapping(value, "history-diff runtime registry query audit check")
        _strict(value, set(cls.FIELDS), "history-diff runtime registry query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck):
        raise ValidationError("history-diff runtime registry query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit:
    """A fixed-size independently recomputed query assurance result."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, registry_address: str, query_id: str, registry_id: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.query_address = _address(query_address, "history-diff runtime registry query audit query address", query_model.QUERY_PREFIX)
        self.registry_address = _address(registry_address, "history-diff runtime registry query audit registry address", registry_model.REGISTRY_PREFIX)
        self.query_id = _label(query_id, "history-diff runtime registry query audit query ID")
        self.registry_id = _label(registry_id, "history-diff runtime registry query audit registry ID")
        self.version = _text(version, "history-diff runtime registry query audit version", 1024)
        self.boundary = _text(boundary, "history-diff runtime registry query audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck) else HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "history-diff runtime registry query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "history-diff runtime registry query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "history-diff runtime registry query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history-diff runtime registry query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "history-diff runtime registry query audit acceptance")
        self.content_address = _address(content_address, "history-diff runtime registry query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        expected_passed = sum(item.passed for item in self.checks)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history-diff runtime registry query audit version or boundary is not current")
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count != expected_passed or self.failed_count != self.check_count - expected_passed:
            raise ValidationError("history-diff runtime registry query audit counts do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("history-diff runtime registry query audit checks are not ordered")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("history-diff runtime registry query audit acceptance does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history-diff runtime registry query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("history-diff runtime registry query audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "registry_address": self.registry_address, "query_id": self.query_id, "registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("query_address", "registry_address", "query_id", "registry_id", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit:
        value = _mapping(value, "history-diff runtime registry query audit")
        _strict(value, set(cls.FIELDS), "history-diff runtime registry query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit):
        raise ValidationError("history-diff runtime registry query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def value_model_version(value: query_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery) -> str:
    """Read the version through the typed query without broadening its fields."""
    if not isinstance(value, query_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery):
        raise ValidationError("history-diff runtime registry query audit requires a typed query")
    return query_model.VERSION


def audit_query(value: query_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQuery, registry: registry_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistry) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit:
    registry = registry_model.verify_registry(registry)
    value = query_model.query_from_mapping(value.to_dict())
    replay = query_model.query_registry(registry, resources=value.resources, state=value.state_filter, key=value.key_filter, text=value.text_filter, offset=value.offset, limit=value.limit, query_id=value.query_id)
    checks: list[HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck] = []

    def add(check_id: str, passed: bool, detail: str, evidence: Sequence[str] = ()) -> None:
        body = {"ordinal": len(checks) + 1, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:16], "content_address": CHECK_PREFIX + ":pending"}
        provisional = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck(**body)
        checks.append(HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck(**(body | {"content_address": address_check(provisional)})))

    canonical_resources = tuple(item for item in query_model.RESOURCES if item in value.resources)
    add("version", value_model_version(value) == query_model.VERSION, "query version is current", (value.content_address,))
    add("boundary", _public(value.to_dict()), "query boundary is public and value-free", (value.content_address,))
    add("resource-order", value.resources == canonical_resources, "query resources retain canonical order", (value.content_address,))
    add("filter-replay", replay.content_address == value.content_address, "query filters replay to the same addressed page", (value.content_address, replay.content_address))
    add("count-replay", (value.total_count, value.returned_count, value.truncated) == (replay.total_count, replay.returned_count, replay.truncated), "query counts and pagination replay", (value.content_address,))
    add("row-order", tuple(item.ordinal for item in value.rows) == tuple(range(1, len(value.rows) + 1)), "query row ordinals retain page order", tuple(item.row_address for item in value.rows))
    add("row-addresses", all(query_model.address_row(item) == item.row_address for item in value.rows), "query row addresses replay", tuple(item.row_address for item in value.rows))
    add("row-membership", tuple(item.to_dict() for item in value.rows) == tuple(item.to_dict() for item in replay.rows), "query rows match the recomputed page", tuple(item.row_address for item in value.rows))
    add("resource-semantics", all(item.resource in query_model.RESOURCES and item.key for item in value.rows), "query rows retain known resource semantics", tuple(item.row_address for item in value.rows))
    add("registry-linkage", value.registry_id == registry.registry_id and value.registry_address == registry.content_address, "query retains the exact registry link", (value.registry_address, registry.content_address))
    add("public-boundary", _public(value.to_dict()), "query contains no forbidden public metadata", (value.content_address,))
    add("mapping-round-trip", query_model.query_from_mapping(value.to_dict()).content_address == value.content_address, "query mapping round-trips to the same address", (value.content_address,))
    body = {"query_address": value.content_address, "registry_address": registry.content_address, "query_id": value.query_id, "registry_id": registry.registry_id, "version": VERSION, "boundary": BOUNDARY, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit(**body)
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def verify_audit(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit):
        raise ValidationError("history-diff runtime registry query audit verification requires a typed audit")
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit:
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit.from_mapping(value)


def audit_json(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit) -> str:
    value = verify_audit(value)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address"))
    for item in value.checks:
        writer.writerow((item.ordinal, item.check_id, item.passed, item.detail, json.dumps(item.evidence_addresses, ensure_ascii=False), item.content_address))
    return output.getvalue()


def render_audit_markdown(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# History-Diff Recovery Execution Runtime Registry Query Audit", "", f"- Query: `{value.query_id}`", f"- Registry: `{value.registry_id}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "registry_address": {"type": "string"}, "query_id": {"type": "string"}, "registry_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": MAX_CHECKS, "operations": ("audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAuditCheck", "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryQueryAudit", "address_check", "address_audit", "audit_query", "value_model_version", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
