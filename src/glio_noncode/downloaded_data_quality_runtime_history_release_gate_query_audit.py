"""Independent audit of bounded release-gate query projections."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_quality_runtime_history_release_gate as gate_model
from . import downloaded_data_quality_runtime_history_release_gate_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
MAX_CHECKS = 12
CHECK_IDS = (
    "query_gate_link",
    "query_history_link",
    "resource_set",
    "state_filter",
    "passed_filter",
    "severity_filter",
    "text_filter",
    "row_addresses",
    "row_resources",
    "pagination",
    "counts",
    "public_boundary",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("query_id", "gate_id", "history_id", "query_address", "gate_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
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


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _display(value: Any) -> str:
    return canonical_json(value)


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release gate query audit ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("release gate query audit ordinal must be positive")
        self.check_id = _label(check_id, "release gate query audit check ID")
        self.passed = _bool(passed, "release gate query audit result")
        self.actual = _text(actual, "release gate query audit actual")
        self.expected = _text(expected, "release gate query audit expected")
        self.detail = _text(detail, "release gate query audit detail")
        self.content_address = _address(content_address, "release gate query audit finding address", FINDING_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.content_address.startswith("pending:") and content_hash(self.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX) != self.content_address:
            raise ValidationError("release gate query audit finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AuditCheck:
        value = _mapping(value, "release gate query audit check")
        _strict(value, set(cls.FIELDS), "release gate query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class QueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_id: str, gate_id: str, history_id: str, query_address: str, gate_address: str, checks: tuple[AuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_id = _label(query_id, "release gate query audit query ID")
        self.gate_id = _label(gate_id, "release gate query audit gate ID")
        self.history_id = _label(history_id, "release gate query audit history ID")
        self.query_address = _address(query_address, "release gate query audit query address", query_model.QUERY_PREFIX)
        self.gate_address = _address(gate_address, "release gate query audit gate address", gate_model.GATE_PREFIX)
        self.checks = tuple(checks)
        self.check_count = _count(check_count, "release gate query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "release gate query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "release gate query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "release gate query audit acceptance")
        self.content_address = _address(content_address, "release gate query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("release gate query audit checks do not replay")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("release gate query audit counters do not replay")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("release gate query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "gate_id": self.gate_id, "history_id": self.history_id, "query_address": self.query_address, "gate_address": self.gate_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> QueryAudit:
        value = _mapping(value, "release gate query audit")
        _strict(value, set(cls.FIELDS), "release gate query audit")
        return cls(value["query_id"], value["gate_id"], value["history_id"], value["query_address"], value["gate_address"], tuple(AuditCheck.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: QueryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    value = AuditCheck(ordinal, check_id, passed, _display(actual), _display(expected), detail, f"pending:{FINDING_PREFIX}")
    value.content_address = address_check(value)
    value._validate()
    return value


def audit_query(query: query_model.GateQuery, gate: gate_model.ReleaseGate) -> QueryAudit:
    if not isinstance(query, query_model.GateQuery) or not isinstance(gate, gate_model.ReleaseGate):
        raise ValidationError("release gate query audit requires typed query and gate")
    gate_model.verify_gate(gate)
    query_model.GateQuery.from_mapping(query.to_dict())
    all_rows = query_model._all_rows(gate, query.resources)
    selected_rows = tuple(item for item in all_rows if (not query.state_filter or item.state == query.state_filter) and (query.passed_filter is None or item.passed == query.passed_filter) and (not query.severity_filter or item.severity == query.severity_filter) and (not query.text_filter or query.text_filter.casefold() in (item.key + " " + item.value + " " + item.text).casefold()))
    expected_rows = selected_rows[query.offset : query.offset + query.limit]
    checks = (
        _finding(1, "query_gate_link", query.gate_id == gate.gate_id, query.gate_id, gate.gate_id, "query must target the supplied gate"),
        _finding(2, "query_history_link", query.history_id == gate.history_id, query.history_id, gate.history_id, "query must target the supplied history"),
        _finding(3, "resource_set", all(item in query_model.RESOURCES for item in query.resources), query.resources, query_model.RESOURCES, "resources must be canonical"),
        _finding(4, "state_filter", query.state_filter in query_model.STATES, query.state_filter, query_model.STATES, "state filter must be bounded"),
        _finding(5, "passed_filter", query.passed_filter is None or isinstance(query.passed_filter, bool), query.passed_filter, "boolean or null", "result filter must be bounded"),
        _finding(6, "severity_filter", query.severity_filter in query_model.SEVERITIES, query.severity_filter, query_model.SEVERITIES, "severity filter must be bounded"),
        _finding(7, "text_filter", len(query.text_filter) <= 4096, len(query.text_filter), "<= 4096", "text filter must be bounded"),
        _finding(8, "row_addresses", all(item.content_address == query_model.address_row(item) for item in query.rows), "replayed", "canonical", "each returned row address must replay"),
        _finding(9, "row_resources", all(item.resource in query.resources for item in query.rows), tuple(item.resource for item in query.rows), query.resources, "rows must belong to selected resources"),
        _finding(10, "pagination", tuple(item.to_dict() for item in query.rows) == tuple(item.to_dict() for item in expected_rows), query.returned_count, len(expected_rows), "returned rows must equal the deterministic page"),
        _finding(11, "counts", (query.total_count, query.returned_count, query.truncated) == (len(selected_rows), len(expected_rows), query.offset + len(expected_rows) < len(selected_rows)), (query.total_count, query.returned_count, query.truncated), (len(selected_rows), len(expected_rows), query.offset + len(expected_rows) < len(selected_rows)), "query counts and truncation must replay"),
        _finding(12, "public_boundary", all(gate_model.history_model._public(item.to_dict()) for item in query.rows), True, True, "query output must remain value-only and path-free"),
    )
    passed = sum(item.passed for item in checks)
    result = QueryAudit(query.query_id, gate.gate_id, gate.history_id, query.content_address, gate.content_address, checks, len(checks), passed, len(checks) - passed, passed == len(checks), f"pending:{AUDIT_PREFIX}")
    result.content_address = address_audit(result)
    result._validate()
    return result


def audit_from_mapping(value: Mapping[str, Any]) -> QueryAudit:
    return QueryAudit.from_mapping(value)


def verify_audit(value: QueryAudit) -> QueryAudit:
    if not isinstance(value, QueryAudit):
        raise ValidationError("release gate query audit verification requires a typed audit")
    value._validate()
    return value


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
    lines = [f"# Release gate query audit {value.query_id}", "", f"- Accepted: {value.accepted}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| # | check | passed | actual | expected |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.actual} | {item.expected} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "actual": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_id": {"type": "string"}, "gate_id": {"type": "string"}, "history_id": {"type": "string"}, "query_address": {"type": "string"}, "gate_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "features": ("independent filter and pagination replay", "query and gate linkage", "canonical row-address verification", "path-free query audit evidence", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "FINDING_PREFIX", "MAX_CHECKS", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "AuditCheck", "QueryAudit", "address_check", "address_audit", "audit_query", "audit_from_mapping", "verify_audit", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
