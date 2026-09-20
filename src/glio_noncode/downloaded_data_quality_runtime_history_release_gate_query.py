"""Bounded public queries over downloaded-data quality release gates."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_runtime_history_release_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = gate_model.VERSION + "-query-v1"
BOUNDARY = gate_model.BOUNDARY + "_query"
QUERY_PREFIX = gate_model.GATE_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "policy", "checks", "readiness", "counters", "addresses", "bounds")
STATES = ("",) + gate_model.STATES
SEVERITIES = ("",) + gate_model.SEVERITIES
MAX_ROWS = 64
MAX_LIMIT = 64
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "passed", "severity", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "gate_id", "history_id", "resources", "state_filter", "passed_filter", "severity_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096, required=True)
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool_or_none(value: Any, field: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean or null")
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


def _display(value: Any) -> str:
    return canonical_json(value)


class QueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, passed: bool | None, severity: str, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release gate query row ordinal", MAX_ROWS, lower=1)
        if resource not in RESOURCES:
            raise ValidationError("release gate query row resource is unsupported")
        self.resource = resource
        self.item_id = _label(item_id, "release gate query row item ID")
        self.key = _label(key, "release gate query row key")
        if state not in gate_model.STATES and state != "":
            raise ValidationError("release gate query row state is unsupported")
        self.state = state
        self.passed = _bool_or_none(passed, "release gate query row result")
        if severity not in gate_model.SEVERITIES and severity != "":
            raise ValidationError("release gate query row severity is unsupported")
        self.severity = severity
        self.value = _text(value, "release gate query row value", 4096, required=True)
        self.text = _text(text, "release gate query row text", 4096, required=True)
        self.content_address = _address(content_address, "release gate query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.content_address.startswith("pending:") and content_hash(self.to_dict() | {"content_address": None}, prefix=ROW_PREFIX) != self.content_address:
            raise ValidationError("release gate query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> QueryRow:
        value = _mapping(value, "release gate query row")
        _strict(value, set(cls.FIELDS), "release gate query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: QueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class GateQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, gate_id: str, history_id: str, resources: Sequence[str], state_filter: str, passed_filter: bool | None, severity_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[QueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "release gate query ID")
        self.gate_id = _label(gate_id, "release gate query gate ID")
        self.history_id = _label(history_id, "release gate query history ID")
        self.resources = tuple(_label(item, "release gate query resource") for item in _sequence(resources, "release gate query resources", len(RESOURCES)))
        if any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources):
            raise ValidationError("release gate query resources are invalid")
        if state_filter not in STATES:
            raise ValidationError("release gate query state filter is invalid")
        self.state_filter = state_filter
        self.passed_filter = _bool_or_none(passed_filter, "release gate query result filter")
        if severity_filter not in SEVERITIES:
            raise ValidationError("release gate query severity filter is invalid")
        self.severity_filter = severity_filter
        self.text_filter = _text(text_filter, "release gate query text filter")
        self.offset = _count(offset, "release gate query offset", MAX_ROWS)
        self.limit = _count(limit, "release gate query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "release gate query total count", MAX_ROWS)
        self.returned_count = _count(returned_count, "release gate query returned count", MAX_LIMIT)
        self.truncated = bool(truncated) if isinstance(truncated, bool) else (_bool_or_none(truncated, "release gate query truncation") is True)
        self.rows = tuple(item if isinstance(item, QueryRow) else QueryRow.from_mapping(item) for item in _sequence(rows, "release gate query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "release gate query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.returned_count > self.total_count:
            raise ValidationError("release gate query counts do not replay")
        if self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("release gate query truncation does not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("release gate query row pagination does not replay")
        if not self.content_address.startswith("pending:") and address_query(self) != self.content_address:
            raise ValidationError("release gate query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "gate_id": self.gate_id, "history_id": self.history_id, "resources": list(self.resources), "state_filter": self.state_filter, "passed_filter": self.passed_filter, "severity_filter": self.severity_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> GateQuery:
        value = _mapping(value, "release gate query")
        _strict(value, set(cls.FIELDS), "release gate query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: GateQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(ordinal: int, resource: str, key: str, value: Any, *, state: str = "", passed: bool | None = None, severity: str = "", text: str = "") -> QueryRow:
    item = QueryRow(ordinal, resource, key, key, state, passed, severity, _display(value), text or key, f"pending:{ROW_PREFIX}")
    item.content_address = address_row(item)
    item._validate()
    return item


def _all_rows(gate: gate_model.ReleaseGate, resources: Sequence[str]) -> tuple[QueryRow, ...]:
    rows: list[QueryRow] = []
    if "summary" in resources:
        rows.append(_row(len(rows) + 1, "summary", "decision", gate.state, state=gate.state, passed=gate.release_ready, text="release decision"))
    if "policy" in resources:
        for key in ("minimum_entries", "maximum_regressed", "maximum_blocked", "require_latest_ready", "require_latest_accepted", "allow_unchanged"):
            rows.append(_row(len(rows) + 1, "policy", key, getattr(gate.policy, key), text="policy " + key))
    if "checks" in resources:
        for item in gate.checks:
            rows.append(_row(len(rows) + 1, "checks", item.check_id, item.actual, state=gate.state, passed=item.passed, severity=item.severity, text=item.detail))
    if "readiness" in resources:
        for key in ("release_ready", "state", "latest_state", "latest_accepted"):
            value = getattr(gate, key)
            rows.append(_row(len(rows) + 1, "readiness", key, value, state=gate.state, passed=value if isinstance(value, bool) else None, text="readiness " + key))
    if "counters" in resources:
        for key in ("check_count", "passed_count", "failed_count", "entry_count", "regressed_count", "blocked_count"):
            rows.append(_row(len(rows) + 1, "counters", key, getattr(gate, key), state=gate.state, text="counter " + key))
    if "addresses" in resources:
        for key in ("gate_address", "history_address", "policy_address", "summary_address"):
            value = gate.content_address if key == "gate_address" else gate.history_address if key == "history_address" else gate.policy.content_address if key == "policy_address" else gate.summary.content_address
            rows.append(_row(len(rows) + 1, "addresses", key, value, state=gate.state, text="address " + key))
    if "bounds" in resources:
        for key, value in (("max_checks", gate_model.MAX_CHECKS), ("max_history_entries", gate_model.history_model.MAX_ENTRIES), ("max_gate_bytes", gate_model.MAX_GATE_BYTES)):
            rows.append(_row(len(rows) + 1, "bounds", key, value, text="bound " + key))
    return tuple(rows)


def query_gate(gate: gate_model.ReleaseGate, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] | None = None, state_filter: str = "", passed_filter: bool | None = None, severity_filter: str = "", text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> GateQuery:
    gate_model.verify_gate(gate)
    selected = tuple(resources) if resources is not None else RESOURCES
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected):
        raise ValidationError("release gate query resources are invalid")
    _count(offset, "release gate query offset", MAX_ROWS)
    _count(limit, "release gate query limit", MAX_LIMIT, lower=1)
    text_filter = _text(text_filter, "release gate query text filter")
    selected_rows = tuple(item for item in _all_rows(gate, selected) if (not state_filter or item.state == state_filter) and (passed_filter is None or item.passed == passed_filter) and (not severity_filter or item.severity == severity_filter) and (not text_filter or text_filter.casefold() in (item.key + " " + item.value + " " + item.text).casefold()))
    page = selected_rows[offset : offset + limit]
    rows = tuple(QueryRow(index + 1, item.resource, item.item_id, item.key, item.state, item.passed, item.severity, item.value, item.text, item.content_address) for index, item in enumerate(page, offset))
    result = GateQuery(query_id, gate.gate_id, gate.history_id, selected, state_filter, passed_filter, severity_filter, text_filter, offset, limit, len(selected_rows), len(rows), offset + len(rows) < len(selected_rows), rows, f"pending:{QUERY_PREFIX}")
    result.content_address = address_query(result)
    result._validate()
    return result


def query_from_mapping(value: Mapping[str, Any]) -> GateQuery:
    return GateQuery.from_mapping(value)


def query_json(value: GateQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: GateQuery) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in GateQuery.from_mapping(value.to_dict()).rows)
    return output.getvalue()


def render_query_markdown(value: GateQuery) -> str:
    value = GateQuery.from_mapping(value.to_dict())
    lines = [f"# Release gate query {value.query_id}", "", f"- Rows: {value.returned_count}/{value.total_count}", "", "| # | resource | key | state | passed | value |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.resource} | {item.key} | {item.state} | {item.passed} | {item.value} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer"}, "resource": {"enum": list(RESOURCES)}, "item_id": {"type": "string"}, "key": {"type": "string"}, "state": {"enum": list(gate_model.STATES) + [""]}, "passed": {"type": ["boolean", "null"]}, "severity": {"enum": list(gate_model.SEVERITIES) + [""]}, "value": {"type": "string"}, "text": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "gate_id": {"type": "string"}, "history_id": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "state_filter": {"enum": list(STATES)}, "passed_filter": {"type": ["boolean", "null"]}, "severity_filter": {"enum": list(SEVERITIES)}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("summary policy check readiness counter address and bound resources", "state result severity and text filters", "deterministic pagination", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "SEVERITIES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "QueryRow", "GateQuery", "address_row", "address_query", "query_gate", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
