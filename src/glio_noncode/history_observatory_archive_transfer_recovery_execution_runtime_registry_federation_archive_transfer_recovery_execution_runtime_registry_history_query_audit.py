"""Independent assurance for registry-history query projections."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history as history_model
from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "resource-order",
    "filter-replay",
    "count-replay",
    "row-order",
    "row-addresses",
    "row-membership",
    "resource-semantics",
    "history-linkage",
    "public-boundary",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "history_address", "history_id", "query_id", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
MAX_CHECKS = len(CHECK_IDS)


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
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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
    return history_model._public(value)


class RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck:
    """One independently addressed query assurance finding."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history query audit ordinal", MAX_CHECKS, lower=1)
        if check_id not in CHECK_IDS:
            raise ValidationError("runtime registry history query audit check is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "runtime registry history query audit result")
        self.detail = _text(detail, "runtime registry history query audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "runtime registry history query audit evidence address") for item in _sequence(evidence_addresses, "runtime registry history query audit evidence", 128))
        self.content_address = _address(content_address, "runtime registry history query audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime registry history query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck:
        value = _mapping(value, "runtime registry history query audit check")
        _strict(value, set(cls.FIELDS), "runtime registry history query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck):
        raise ValidationError("runtime registry history query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RecoveryExecutionRuntimeRegistryHistoryQueryAudit:
    """A fixed-size independently recomputed query audit."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, history_address: str, history_id: str, query_id: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.query_address = _address(query_address, "runtime registry history query audit query address", query_model.QUERY_PREFIX)
        self.history_address = _address(history_address, "runtime registry history query audit history address", history_model.HISTORY_PREFIX)
        self.history_id = _label(history_id, "runtime registry history query audit history ID")
        self.query_id = _label(query_id, "runtime registry history query audit query ID")
        self.version = _text(version, "runtime registry history query audit version", 1024)
        self.boundary = _text(boundary, "runtime registry history query audit boundary", 1024)
        self.check_count = _count(check_count, "runtime registry history query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry history query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry history query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry history query audit acceptance")
        self.checks = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck) else RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime registry history query audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "runtime registry history query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry history query audit does not replay checks")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime registry history query audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "history_address": self.history_address, "history_id": self.history_id, "query_id": self.query_id, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryHistoryQueryAudit:
        value = _mapping(value, "runtime registry history query audit")
        _strict(value, set(cls.FIELDS), "runtime registry history query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: RecoveryExecutionRuntimeRegistryHistoryQueryAudit) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryHistoryQueryAudit):
        raise ValidationError("runtime registry history query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck:
    body = {"ordinal": CHECK_IDS.index(check_id) + 1, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence) or (query_model.QUERY_PREFIX + ":empty",), "content_address": CHECK_PREFIX + ":pending"}
    provisional = RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck(**body)
    return RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_query(value: query_model.RecoveryExecutionRuntimeRegistryHistoryQuery, history: history_model.RecoveryExecutionRuntimeRegistryHistory) -> RecoveryExecutionRuntimeRegistryHistoryQueryAudit:
    history = history_model.verify_history(history)
    value = query_model.query_from_mapping(value.to_dict())
    replay = query_model.query_history(history, resources=value.resources, state=value.state_filter, key=value.key_filter, transition=value.transition_filter, text=value.text_filter, offset=value.offset, limit=value.limit, query_id=value.query_id)
    evidence = tuple(item.row_address for item in value.rows) or (value.content_address,)
    resource_semantics = all(item.resource in query_model.RESOURCES and item.state in query_model.STATES and (not item.transition or item.transition in query_model.TRANSITIONS) for item in value.rows)
    checks = (
        _check("version", query_model.VERSION == history_model.VERSION + "-query-v1", "query version is current", (value.content_address,)),
        _check("boundary", query_model.BOUNDARY == history_model.BOUNDARY + "_query", "query boundary is public and value-free", (value.content_address,)),
        _check("resource-order", value.resources == tuple(item for item in query_model.RESOURCES if item in value.resources) and len(value.resources) == len(set(value.resources)), "query resources retain canonical order", (value.content_address,)),
        _check("filter-replay", replay.content_address == value.content_address, "query filters replay to the same addressed page", (value.content_address, replay.content_address)),
        _check("count-replay", (value.total_count, value.returned_count, value.truncated) == (replay.total_count, replay.returned_count, replay.truncated), "query counts and pagination replay", (value.content_address,)),
        _check("row-order", tuple(item.ordinal for item in value.rows) == tuple(range(1, len(value.rows) + 1)), "query rows retain page order", evidence),
        _check("row-addresses", len({item.row_address for item in value.rows}) == len(value.rows) and all(query_model.address_row(item) == item.row_address for item in value.rows), "query row addresses replay", evidence),
        _check("row-membership", tuple(item.to_dict() for item in value.rows) == tuple(item.to_dict() for item in replay.rows), "query rows match the recomputed page", evidence),
        _check("resource-semantics", resource_semantics, "query rows retain known resource semantics", evidence),
        _check("history-linkage", value.history_id == history.history_id and value.history_address == history.content_address, "query retains the exact history linkage", (value.history_address, history.content_address)),
        _check("public-boundary", _public(value.to_dict()), "query contains only public value-free fields", (value.content_address,)),
        _check("mapping-round-trip", query_model.query_from_mapping(value.to_dict()).content_address == value.content_address, "query mapping round-trips to the same address", (value.content_address,)),
    )
    body = {"query_address": value.content_address, "history_address": history.content_address, "history_id": history.history_id, "query_id": value.query_id, "version": VERSION, "boundary": BOUNDARY, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = RecoveryExecutionRuntimeRegistryHistoryQueryAudit(**body)
    return RecoveryExecutionRuntimeRegistryHistoryQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def verify_audit(value: RecoveryExecutionRuntimeRegistryHistoryQueryAudit) -> RecoveryExecutionRuntimeRegistryHistoryQueryAudit:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryHistoryQueryAudit):
        raise ValidationError("runtime registry history query audit verification requires a typed audit")
    return RecoveryExecutionRuntimeRegistryHistoryQueryAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryHistoryQueryAudit:
    return RecoveryExecutionRuntimeRegistryHistoryQueryAudit.from_mapping(value)


def audit_json(value: RecoveryExecutionRuntimeRegistryHistoryQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RecoveryExecutionRuntimeRegistryHistoryQueryAudit) -> str:
    value = verify_audit(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    for item in value.checks:
        writer.writerow((item.ordinal, item.check_id, item.passed, item.detail, json.dumps(item.evidence_addresses, ensure_ascii=False), item.content_address))
    return output.getvalue()


def render_audit_markdown(value: RecoveryExecutionRuntimeRegistryHistoryQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Federation archive recovery execution runtime registry history query audit", "", f"Query: {value.query_id}", f"History: {value.history_id}", f"Passed: {value.passed_count}/{value.check_count}", f"Accepted: {value.accepted}", f"Address: {value.content_address}", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryHistoryQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "history_address": {"type": "string"}, "history_id": {"type": "string"}, "query_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": MAX_CHECKS, "operations": ("audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "RecoveryExecutionRuntimeRegistryHistoryQueryAuditCheck", "RecoveryExecutionRuntimeRegistryHistoryQueryAudit", "address_check", "address_audit", "audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
