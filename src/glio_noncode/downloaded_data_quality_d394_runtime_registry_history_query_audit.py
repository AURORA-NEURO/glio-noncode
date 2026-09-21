"""Independent replay audit for runtime registry history queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d394_runtime_registry_history as history_model
from . import downloaded_data_quality_d394_runtime_registry_history_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = history_model.HISTORY_PREFIX + "-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("query_identity", "history_link", "registry_link", "resource_set", "filter_replay", "counts", "pagination", "row_order", "row_addresses", "projection_replay", "query_address", "public_boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("query_id", "history_id", "registry_id", "query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"):
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


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history query audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "runtime registry history query audit check ID")
        self.passed = _bool(passed, "runtime registry history query audit result")
        self.actual = _text(actual, "runtime registry history query audit actual", 32768)
        self.expected = _text(expected, "runtime registry history query audit expected", 32768)
        self.detail = _text(detail, "runtime registry history query audit detail", 4096)
        self.content_address = _address(content_address, "runtime registry history query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("runtime registry history query audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history query audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history query audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "runtime registry history query audit check")
        _strict(value, set(cls.FIELDS), "runtime registry history query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("runtime registry history query audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class QueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_id: str, history_id: str, registry_id: str, query_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_id = _label(query_id, "runtime registry history query audit query ID")
        self.history_id = _label(history_id, "runtime registry history query audit history ID")
        self.registry_id = _label(registry_id, "runtime registry history query audit registry ID")
        self.query_address = _address(query_address, "runtime registry history query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "runtime registry history query audit check")) for item in _sequence(checks, "runtime registry history query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "runtime registry history query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry history query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry history query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry history query audit acceptance")
        self.content_address = _address(content_address, "runtime registry history query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry history query audit checks are incomplete or out of order")
        if (self.passed_count, self.failed_count) != (sum(item.passed for item in self.checks), sum(not item.passed for item in self.checks)):
            raise ValidationError("runtime registry history query audit counters do not replay")
        if self.accepted != (self.failed_count == 0) or any(item.content_address != address_check(item) for item in self.checks):
            raise ValidationError("runtime registry history query audit disposition or check addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history query audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryAudit":
        value = _mapping(value, "runtime registry history query audit")
        _strict(value, set(cls.FIELDS), "runtime registry history query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: QueryAudit) -> str:
    if not isinstance(value, QueryAudit):
        raise ValidationError("runtime registry history query audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    return AuditCheck(ordinal, check_id, passed, canonical_json(actual), canonical_json(expected), detail, f"pending:{CHECK_PREFIX}")


def audit_query(value: query_model.HistoryQuery, history: history_model.RegistryHistory) -> QueryAudit:
    query_model.verify_query(value)
    history_model.verify_history(history)
    replay = query_model.query_history(history, query_id=value.query_id, resources=value.resources, state_filter=value.state_filter, transition_filter=value.transition_filter, readiness_filter=value.readiness_filter, text_filter=value.text_filter, offset=value.offset, limit=value.limit)
    checks = (
        _finding(1, "query_identity", value.query_id == replay.query_id, value.query_id, replay.query_id, "query identity must replay"),
        _finding(2, "history_link", value.history_id == history.history_id and value.history_address == history.content_address, (value.history_id, value.history_address), (history.history_id, history.content_address), "query must target the history"),
        _finding(3, "registry_link", value.registry_id == history.registry_id, value.registry_id, history.registry_id, "query registry identity must replay"),
        _finding(4, "resource_set", value.resources == replay.resources, value.resources, replay.resources, "query resources must replay"),
        _finding(5, "filter_replay", (value.state_filter, value.transition_filter, value.readiness_filter, value.text_filter) == (replay.state_filter, replay.transition_filter, replay.readiness_filter, replay.text_filter), (value.state_filter, value.transition_filter, value.readiness_filter, value.text_filter), (replay.state_filter, replay.transition_filter, replay.readiness_filter, replay.text_filter), "query filters must replay"),
        _finding(6, "counts", (value.total_count, value.returned_count, value.truncated) == (replay.total_count, replay.returned_count, replay.truncated), (value.total_count, value.returned_count, value.truncated), (replay.total_count, replay.returned_count, replay.truncated), "query counts must replay"),
        _finding(7, "pagination", (value.offset, value.limit) == (replay.offset, replay.limit), (value.offset, value.limit), (replay.offset, replay.limit), "query pagination must replay"),
        _finding(8, "row_order", tuple(item.ordinal for item in value.rows) == tuple(range(value.offset + 1, value.offset + value.returned_count + 1)), tuple(item.ordinal for item in value.rows), "contiguous page", "query rows must be ordered"),
        _finding(9, "row_addresses", all(item.content_address == query_model.address_row(item) for item in value.rows), "replayed", "canonical", "query row addresses must replay"),
        _finding(10, "projection_replay", value.to_dict() == replay.to_dict(), value.content_address, replay.content_address, "query projection must replay from history"),
        _finding(11, "query_address", value.content_address == query_model.address_query(value), value.content_address, query_model.address_query(value), "query address must replay"),
        _finding(12, "public_boundary", _public(value.to_dict()), True, True, "query audit output must remain value-only and path-free"),
    )
    sealed = tuple(_seal(item, address_check) for item in checks)
    passed = sum(item.passed for item in sealed)
    return _seal(QueryAudit(value.query_id, value.history_id, value.registry_id, value.content_address, sealed, len(sealed), passed, len(sealed) - passed, passed == len(sealed), f"pending:{AUDIT_PREFIX}"), address_audit)


def verify_audit(value: QueryAudit) -> QueryAudit:
    if not isinstance(value, QueryAudit):
        raise ValidationError("runtime registry history query audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> QueryAudit:
    return QueryAudit.from_mapping(value)


def audit_json(value: QueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: QueryAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: QueryAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Runtime registry history query audit {value.query_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistoryQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistoryQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent history query replay", "filter and pagination verification", "canonical row-address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "QueryAudit", "address_check", "address_audit", "audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
