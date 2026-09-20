"""Independent replay audit for release-evidence history queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_runtime_history_release_evidence_history as history_model
from . import downloaded_data_quality_runtime_history_release_evidence_history_query as query_model
from . import downloaded_data_quality_runtime_history_release_evidence as evidence_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-query-audit-v1"
BOUNDARY = history_model.BOUNDARY + "_query_audit"
AUDIT_PREFIX = history_model.HISTORY_PREFIX + "-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("identity_link", "history_link", "resource_set", "filter_replay", "total_count", "returned_count", "pagination", "row_order", "row_addresses", "query_address", "projection_replay", "public_boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("query_id", "history_id", "gate_id", "source_history_id", "query_address", "history_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _public(value: Any) -> bool:
    return evidence_model.gate_model.history_model._public(value)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "evidence history query audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "evidence history query audit check ID")
        self.passed = _bool(passed, "evidence history query audit check result")
        self.actual = _text(actual, "evidence history query audit actual", 32768)
        self.expected = _text(expected, "evidence history query audit expected", 32768)
        self.detail = _text(detail, "evidence history query audit detail", 4096)
        self.content_address = _address(content_address, "evidence history query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("evidence history query audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("evidence history query audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence history query audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "evidence history query audit check")
        _strict(value, set(cls.FIELDS), "evidence history query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("evidence history query audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class HistoryQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_id: str, history_id: str, gate_id: str, source_history_id: str, query_address: str, history_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_id = _label(query_id, "evidence history query audit query ID")
        self.history_id = _label(history_id, "evidence history query audit history ID")
        self.gate_id = _label(gate_id, "evidence history query audit gate ID")
        self.source_history_id = _label(source_history_id, "evidence history query audit source history ID")
        self.query_address = _address(query_address, "evidence history query audit query address", query_model.QUERY_PREFIX)
        self.history_address = _address(history_address, "evidence history query audit history address", history_model.HISTORY_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "evidence history query audit check")) for item in _sequence(checks, "evidence history query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "evidence history query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "evidence history query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "evidence history query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "evidence history query audit acceptance")
        self.content_address = _address(content_address, "evidence history query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("evidence history query audit checks are incomplete or out of order")
        if (self.passed_count, self.failed_count) != (sum(item.passed for item in self.checks), sum(not item.passed for item in self.checks)):
            raise ValidationError("evidence history query audit counters do not replay")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("evidence history query audit acceptance does not replay")
        if any(item.content_address != address_check(item) for item in self.checks):
            raise ValidationError("evidence history query audit check address does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("evidence history query audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence history query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryQueryAudit":
        value = _mapping(value, "evidence history query audit")
        _strict(value, set(cls.FIELDS), "evidence history query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: HistoryQueryAudit) -> str:
    if not isinstance(value, HistoryQueryAudit):
        raise ValidationError("evidence history query audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    return AuditCheck(ordinal, check_id, passed, canonical_json(actual), canonical_json(expected), detail, f"pending:{CHECK_PREFIX}")


def audit_query(query: query_model.HistoryQuery, history: history_model.EvidenceHistory) -> HistoryQueryAudit:
    if not isinstance(query, query_model.HistoryQuery) or not isinstance(history, history_model.EvidenceHistory):
        raise ValidationError("evidence history query audit requires typed query and history")
    history_model.verify_history(history)
    query._validate()
    replay = query_model.query_history(history, query_id=query.query_id, resources=query.resources, state_filter=query.state_filter, transition_filter=query.transition_filter, readiness_filter=query.readiness_filter, text_filter=query.text_filter, offset=query.offset, limit=query.limit)
    checks = (
        _finding(1, "identity_link", (query.query_id, query.history_id, query.gate_id, query.source_history_id) == (replay.query_id, history.history_id, history.gate_id, history.source_history_id), (query.query_id, query.history_id, query.gate_id, query.source_history_id), (replay.query_id, history.history_id, history.gate_id, history.source_history_id), "query identity must link history"),
        _finding(2, "history_link", query.history_id == history.history_id and query.gate_id == history.gate_id, (query.history_id, query.gate_id), (history.history_id, history.gate_id), "query must identify its history"),
        _finding(3, "resource_set", query.resources == replay.resources, query.resources, replay.resources, "query resource selection must replay"),
        _finding(4, "filter_replay", (query.state_filter, query.transition_filter, query.readiness_filter, query.text_filter) == (replay.state_filter, replay.transition_filter, replay.readiness_filter, replay.text_filter), (query.state_filter, query.transition_filter, query.readiness_filter, query.text_filter), (replay.state_filter, replay.transition_filter, replay.readiness_filter, replay.text_filter), "query filters must replay"),
        _finding(5, "total_count", query.total_count == replay.total_count, query.total_count, replay.total_count, "total row count must replay"),
        _finding(6, "returned_count", query.returned_count == replay.returned_count, query.returned_count, replay.returned_count, "returned row count must replay"),
        _finding(7, "pagination", (query.offset, query.limit, query.truncated) == (replay.offset, replay.limit, replay.truncated), (query.offset, query.limit, query.truncated), (replay.offset, replay.limit, replay.truncated), "pagination must replay"),
        _finding(8, "row_order", tuple(item.ordinal for item in query.rows) == tuple(item.ordinal for item in replay.rows), tuple(item.ordinal for item in query.rows), tuple(item.ordinal for item in replay.rows), "row ordinals must replay"),
        _finding(9, "row_addresses", tuple(item.content_address for item in query.rows) == tuple(item.content_address for item in replay.rows), tuple(item.content_address for item in query.rows), tuple(item.content_address for item in replay.rows), "row addresses must replay"),
        _finding(10, "query_address", query.content_address == query_model.address_query(query), query.content_address, query_model.address_query(query), "query address must replay"),
        _finding(11, "projection_replay", query.to_dict() == replay.to_dict(), (query.content_address, query.returned_count, query.total_count), (replay.content_address, replay.returned_count, replay.total_count), "query projection must be deterministic"),
        _finding(12, "public_boundary", _public(query.to_dict()) and _public(history.to_dict()), True, True, "query audit output must remain value-only and path-free"),
    )
    checks = tuple(_seal(item, address_check) for item in checks)
    passed = sum(item.passed for item in checks)
    return _seal(HistoryQueryAudit(query.query_id, history.history_id, history.gate_id, history.source_history_id, query.content_address, history.content_address, checks, len(checks), passed, len(checks) - passed, passed == len(checks), f"pending:{AUDIT_PREFIX}"), address_audit)


def verify_audit(value: HistoryQueryAudit) -> HistoryQueryAudit:
    if not isinstance(value, HistoryQueryAudit):
        raise ValidationError("evidence history query audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> HistoryQueryAudit:
    return HistoryQueryAudit.from_mapping(value)


def audit_json(value: HistoryQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: HistoryQueryAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: HistoryQueryAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Downloaded-data quality release-evidence history query audit {value.query_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceHistoryQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "actual": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("deterministic history query replay", "pagination and filter audit", "row address audit", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "HistoryQueryAudit", "address_check", "address_audit", "audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
