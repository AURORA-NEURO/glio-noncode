"""Bounded query projections over policy-driven history runtimes."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_runtime_history_release_evidence_history as history_model
from . import downloaded_data_quality_runtime_history_release_evidence_history_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-query-v1"
BOUNDARY = runtime_model.BOUNDARY + "_query"
QUERY_PREFIX = runtime_model.RUNTIME_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "policy", "checks", "readiness", "counters", "addresses", "bounds")
STATES = runtime_model.STATES
SEVERITIES = runtime_model.SEVERITIES
MAX_ROWS = 128
MAX_LIMIT = 128
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "passed", "severity", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "runtime_id", "history_id", "history_address", "resources", "state_filter", "passed_filter", "severity_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


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


def _optional_bool(value: Any, field: str) -> bool | None:
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


def _public(value: Any) -> bool:
    return history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class QueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, passed: bool | None, severity: str, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime query row ordinal", MAX_ROWS, lower=1)
        self.resource = _label(resource, "runtime query resource")
        self.item_id = _label(item_id, "runtime query item ID")
        self.key = _label(key, "runtime query key")
        if state not in STATES:
            raise ValidationError("runtime query row state is unsupported")
        self.state = state
        self.passed = _optional_bool(passed, "runtime query row result")
        if severity not in SEVERITIES and severity != "":
            raise ValidationError("runtime query row severity is unsupported")
        self.severity = severity
        self.value = _text(value, "runtime query row value", 16384)
        self.text = _text(text, "runtime query row text", 16384)
        self.content_address = _address(content_address, "runtime query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES:
            raise ValidationError("runtime query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address:
            raise ValidationError("runtime query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryRow":
        value = _mapping(value, "runtime query row")
        _strict(value, set(cls.FIELDS), "runtime query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: QueryRow) -> str:
    if not isinstance(value, QueryRow):
        raise ValidationError("runtime query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class RuntimeQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, runtime_id: str, history_id: str, history_address: str, resources: Sequence[str], state_filter: str, passed_filter: bool | None, severity_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[QueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "runtime query ID")
        self.runtime_id = _label(runtime_id, "runtime query runtime ID")
        self.history_id = _label(history_id, "runtime query history ID")
        self.history_address = _address(history_address, "runtime query history address", history_model.HISTORY_PREFIX)
        self.resources = tuple(_label(item, "runtime query resource") for item in _sequence(resources, "runtime query resources", len(RESOURCES)))
        self.state_filter = _text(state_filter, "runtime query state filter", 64, required=False)
        self.passed_filter = _optional_bool(passed_filter, "runtime query result filter")
        self.severity_filter = _text(severity_filter, "runtime query severity filter", 64, required=False)
        self.text_filter = _text(text_filter, "runtime query text filter", 512, required=False)
        self.offset = _count(offset, "runtime query offset", MAX_ROWS)
        self.limit = _count(limit, "runtime query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "runtime query total count", MAX_ROWS)
        self.returned_count = _count(returned_count, "runtime query returned count", MAX_ROWS)
        self.truncated = _bool(truncated, "runtime query truncation")
        self.rows = tuple(item if isinstance(item, QueryRow) else QueryRow.from_mapping(_mapping(item, "runtime query row")) for item in _sequence(rows, "runtime query rows", MAX_ROWS))
        self.content_address = _address(content_address, "runtime query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources):
            raise ValidationError("runtime query resources are unsupported or duplicated")
        if self.state_filter and self.state_filter not in STATES or self.severity_filter and self.severity_filter not in SEVERITIES:
            raise ValidationError("runtime query filters are unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count:
            raise ValidationError("runtime query counters do not replay")
        if self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("runtime query truncation does not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("runtime query row ordinals do not replay")
        if any(item.content_address != address_row(item) for item in self.rows):
            raise ValidationError("runtime query row addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address:
            raise ValidationError("runtime query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeQuery":
        value = _mapping(value, "runtime query")
        _strict(value, set(cls.FIELDS), "runtime query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RuntimeQuery) -> str:
    if not isinstance(value, RuntimeQuery):
        raise ValidationError("runtime query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)


def _row(ordinal: int, resource: str, key: str, value: Any, state: str, passed: bool | None = None, severity: str = "") -> QueryRow:
    rendered = canonical_json(value)
    return QueryRow(ordinal, resource, f"{resource}:{key}", key, state, passed, severity, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")


def _rows(value: runtime_model.HistoryRuntime) -> tuple[QueryRow, ...]:
    raw: list[tuple[str, str, Any, bool | None, str]] = []
    def add(resource: str, key: str, item: Any, passed: bool | None = None, severity: str = "") -> None:
        raw.append((resource, key, item, passed, severity))
    for key in ("runtime_id", "history_id", "state", "release_ready", "latest_state", "latest_ready", "entry_count", "regressed_count", "blocked_count"):
        add("summary", key, getattr(value, key), getattr(value, key) if isinstance(getattr(value, key), bool) else None)
    for key in runtime_model.POLICY_FIELDS[:-1]:
        add("policy", key, getattr(value.policy, key))
    for item in value.checks:
        add("checks", item.check_id, {"ordinal": item.ordinal, "passed": item.passed, "severity": item.severity, "actual": item.actual, "expected": item.expected, "detail": item.detail}, item.passed, item.severity)
    for key in ("release_ready", "latest_ready"):
        add("readiness", key, getattr(value, key), getattr(value, key))
    for key in ("check_count", "passed_count", "failed_count", "entry_count", "regressed_count", "blocked_count"):
        add("counters", key, getattr(value, key))
    for key, item in (("history_address", value.history_address), ("policy_address", value.policy.content_address), ("runtime_address", value.content_address), ("manifest_address", value.manifest.content_address), ("summary_address", value.summary.content_address)):
        add("addresses", key, item)
    for key, item in (("minimum_entries", value.policy.minimum_entries), ("maximum_regressed", value.policy.maximum_regressed), ("maximum_blocked", value.policy.maximum_blocked), ("max_checks", runtime_model.MAX_CHECKS)):
        add("bounds", key, item)
    return tuple(_row(index, resource, key, item, value.state, passed, severity) for index, (resource, key, item, passed, severity) in enumerate(raw, 1))


def query_runtime(value: runtime_model.HistoryRuntime, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, state_filter: str = "", passed_filter: bool | None = None, severity_filter: str = "", text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> RuntimeQuery:
    runtime_model.verify_runtime(value)
    selected = tuple(resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected):
        raise ValidationError("runtime query resources are unsupported or duplicated")
    rows = _rows(value)
    text_value = text_filter.casefold()
    filtered = tuple(item for item in rows if item.resource in selected and (not state_filter or item.state == state_filter) and (passed_filter is None or item.passed == passed_filter) and (not severity_filter or item.severity == severity_filter) and (not text_value or text_value in item.text.casefold()))
    offset = _count(offset, "runtime query offset", MAX_ROWS)
    limit = _count(limit, "runtime query limit", MAX_LIMIT, lower=1)
    page = filtered[offset:offset + limit]
    page = tuple(_seal(QueryRow(index, item.resource, item.item_id, item.key, item.state, item.passed, item.severity, item.value, item.text, f"pending:{ROW_PREFIX}"), address_row) for index, item in enumerate(page, offset + 1))
    return _seal(RuntimeQuery(query_id, value.runtime_id, value.history_id, value.history_address, selected, state_filter, passed_filter, severity_filter, text_filter, offset, limit, len(filtered), len(page), offset + len(page) < len(filtered), page, f"pending:{QUERY_PREFIX}"), address_query)


def query_from_mapping(value: Mapping[str, Any]) -> RuntimeQuery:
    return RuntimeQuery.from_mapping(value)


def query_json(value: RuntimeQuery) -> str:
    return canonical_json(query_from_mapping(verify_query(value).to_dict()).to_dict())


def verify_query(value: RuntimeQuery) -> RuntimeQuery:
    if not isinstance(value, RuntimeQuery):
        raise ValidationError("runtime query verification requires a typed query")
    value._validate()
    return value


def query_csv(value: RuntimeQuery) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_query(value).rows)
    return output.getvalue()


def render_query_markdown(value: RuntimeQuery) -> str:
    value = verify_query(value)
    lines = [f"# Runtime query {value.query_id}", "", f"- Runtime: {value.runtime_id}", f"- Results: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Resource | Key | Result | Severity | Value |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.resource} | {item.key} | {item.passed if item.passed is not None else ''} | {item.severity} | {item.value} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    properties = {field: {"type": "integer" if field == "ordinal" else "string"} for field in ROW_FIELDS}
    properties["passed"] = {"type": ["boolean", "null"]}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": properties}


def query_schema() -> dict[str, Any]:
    properties = {field: {"type": "array" if field in ("resources", "rows") else "integer" if field.endswith("count") or field in ("offset", "limit") else "boolean" if field == "truncated" else "string"} for field in QUERY_FIELDS}
    properties["passed_filter"] = {"type": ["boolean", "null"]}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "severities": SEVERITIES, "max_rows": MAX_ROWS, "features": ("bounded resource projection", "stable filters and pagination", "canonical row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "SEVERITIES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "QueryRow", "RuntimeQuery", "address_row", "address_query", "query_runtime", "query_from_mapping", "query_json", "verify_query", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
