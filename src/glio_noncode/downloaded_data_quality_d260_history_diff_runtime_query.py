"""Bounded query projections over runtime registry history diff runtimes."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d260_history_diff_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-query-v1"
BOUNDARY = runtime_model.BOUNDARY + "_query"
QUERY_PREFIX = runtime_model.RUNTIME_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "policy", "checks", "comparison", "readiness", "addresses", "bounds")
STATES = runtime_model.STATES
SEVERITIES = runtime_model.SEVERITIES
MAX_ROWS = runtime_model.MAX_CHECKS * 8
MAX_LIMIT = 128
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "passed", "severity", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "runtime_id", "diff_id", "runtime_address", "resources", "state_filter", "passed_filter", "severity_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


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
    return runtime_model.diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class RuntimeQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, passed: bool | None, severity: str, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff runtime query row ordinal", MAX_ROWS, lower=1)
        self.resource = _label(resource, "history diff runtime query resource")
        self.item_id = _label(item_id, "history diff runtime query row item ID")
        self.key = _label(key, "history diff runtime query row key")
        if state not in STATES:
            raise ValidationError("history diff runtime query row state is unsupported")
        self.state = state
        self.passed = _optional_bool(passed, "history diff runtime query row result")
        if severity not in SEVERITIES and severity != "":
            raise ValidationError("history diff runtime query row severity is unsupported")
        self.severity = severity
        self.value = _text(value, "history diff runtime query row value", 32768)
        self.text = _text(text, "history diff runtime query row text", 32768)
        self.content_address = _address(content_address, "history diff runtime query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES:
            raise ValidationError("history diff runtime query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address:
            raise ValidationError("history diff runtime query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff runtime query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeQueryRow":
        value = _mapping(value, "history diff runtime query row"); _strict(value, set(cls.FIELDS), "history diff runtime query row"); return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RuntimeQueryRow) -> str:
    if not isinstance(value, RuntimeQueryRow):
        raise ValidationError("history diff runtime query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class RuntimeQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, runtime_id: str, diff_id: str, runtime_address: str, resources: Sequence[str], state_filter: str, passed_filter: bool | None, severity_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[RuntimeQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "history diff runtime query ID")
        self.runtime_id = _label(runtime_id, "history diff runtime query runtime ID")
        self.diff_id = _label(diff_id, "history diff runtime query diff ID")
        self.runtime_address = _address(runtime_address, "history diff runtime query runtime address", runtime_model.RUNTIME_PREFIX)
        self.resources = tuple(_label(item, "history diff runtime query resource") for item in _sequence(resources, "history diff runtime query resources", len(RESOURCES)))
        self.state_filter = _text(state_filter, "history diff runtime query state filter", 64, required=False)
        self.passed_filter = _optional_bool(passed_filter, "history diff runtime query result filter")
        self.severity_filter = _text(severity_filter, "history diff runtime query severity filter", 64, required=False)
        self.text_filter = _text(text_filter, "history diff runtime query text filter", 512, required=False)
        self.offset = _count(offset, "history diff runtime query offset", MAX_ROWS)
        self.limit = _count(limit, "history diff runtime query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "history diff runtime query total count", MAX_ROWS)
        self.returned_count = _count(returned_count, "history diff runtime query returned count", MAX_ROWS)
        self.truncated = _bool(truncated, "history diff runtime query truncation")
        self.rows = tuple(item if isinstance(item, RuntimeQueryRow) else RuntimeQueryRow.from_mapping(_mapping(item, "history diff runtime query row")) for item in _sequence(rows, "history diff runtime query rows", MAX_ROWS))
        self.content_address = _address(content_address, "history diff runtime query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources):
            raise ValidationError("history diff runtime query resources are unsupported or duplicated")
        if self.state_filter and self.state_filter not in STATES or self.severity_filter and self.severity_filter not in SEVERITIES:
            raise ValidationError("history diff runtime query filters are unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count or self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("history diff runtime query counters do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)) or any(item.content_address != address_row(item) for item in self.rows):
            raise ValidationError("history diff runtime query row order or addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address:
            raise ValidationError("history diff runtime query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff runtime query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeQuery":
        value = _mapping(value, "history diff runtime query"); _strict(value, set(cls.FIELDS), "history diff runtime query"); return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RuntimeQuery) -> str:
    if not isinstance(value, RuntimeQuery):
        raise ValidationError("history diff runtime query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)


def _row(ordinal: int, resource: str, key: str, value: Any, *, state: str, passed: bool | None = None, severity: str = "") -> RuntimeQueryRow:
    rendered = canonical_json(value)
    return RuntimeQueryRow(ordinal, resource, f"{resource}:{key}", key, state, passed, severity, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")


def _rows(value: runtime_model.DiffRuntime) -> tuple[RuntimeQueryRow, ...]:
    raw: list[tuple[str, str, Any, str, bool | None, str]] = []
    def add(resource: str, key: str, item: Any, *, passed: bool | None = None, severity: str = "") -> None:
        raw.append((resource, key, item, value.state, passed, severity))
    for key in ("runtime_id", "diff_id", "check_count", "passed_count", "failed_count", "release_ready", "state", "direction", "state_transition", "item_count", "added_count", "removed_count", "changed_count", "accepted"):
        item = getattr(value, key); add("summary", key, item, passed=item if isinstance(item, bool) else None)
    for key in ("policy_id", "diff_id", "minimum_items", "maximum_added", "maximum_removed", "maximum_changed", "allowed_directions", "require_accepted", "require_state_change", "allow_unchanged"):
        add("policy", key, getattr(value.policy, key), passed=getattr(value.policy, key) if isinstance(getattr(value.policy, key), bool) else None)
    for item in value.checks:
        add("checks", item.check_id, item.to_dict(), passed=item.passed, severity=item.severity)
    for key, item in (("item_count", value.item_count), ("added_count", value.added_count), ("removed_count", value.removed_count), ("changed_count", value.changed_count), ("unchanged_count", value.item_count - value.added_count - value.removed_count - value.changed_count), ("direction", value.direction), ("state_transition", value.state_transition)):
        add("comparison", key, item)
    for key, item in (("release_ready", value.release_ready), ("state", value.state), ("accepted", value.accepted), ("passed_count", value.passed_count), ("failed_count", value.failed_count)):
        add("readiness", key, item, passed=item if isinstance(item, bool) else None)
    for key, item in (("runtime_address", value.content_address), ("diff_address", value.diff_address), ("policy_address", value.policy.content_address), ("summary_address", value.summary.content_address)):
        add("addresses", key, item)
    for key, item in (("max_checks", runtime_model.MAX_CHECKS), ("max_rows", MAX_ROWS), ("check_count", value.check_count)):
        add("bounds", key, item)
    return tuple(_row(index, resource, key, item, state=state, passed=passed, severity=severity) for index, (resource, key, item, state, passed, severity) in enumerate(raw, 1))


def query_runtime(value: runtime_model.DiffRuntime, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, state_filter: str = "", passed_filter: bool | None = None, severity_filter: str = "", text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> RuntimeQuery:
    runtime_model.verify_runtime(value); selected = tuple(resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected):
        raise ValidationError("history diff runtime query resources are unsupported or duplicated")
    if state_filter and state_filter not in STATES or severity_filter and severity_filter not in SEVERITIES:
        raise ValidationError("history diff runtime query filters are unsupported")
    rows = _rows(value); needle = text_filter.casefold()
    filtered = tuple(item for item in rows if item.resource in selected and (not state_filter or item.state == state_filter) and (passed_filter is None or item.passed == passed_filter) and (not severity_filter or item.severity == severity_filter) and (not needle or needle in item.text.casefold()))
    offset = _count(offset, "history diff runtime query offset", MAX_ROWS); limit = _count(limit, "history diff runtime query limit", MAX_LIMIT, lower=1); page = filtered[offset:offset + limit]
    page = tuple(_seal(RuntimeQueryRow(index, item.resource, item.item_id, item.key, item.state, item.passed, item.severity, item.value, item.text, f"pending:{ROW_PREFIX}"), address_row) for index, item in enumerate(page, offset + 1))
    return _seal(RuntimeQuery(query_id, value.runtime_id, value.diff_id, value.content_address, selected, state_filter, passed_filter, severity_filter, text_filter, offset, limit, len(filtered), len(page), offset + len(page) < len(filtered), page, f"pending:{QUERY_PREFIX}"), address_query)


def query_from_mapping(value: Mapping[str, Any]) -> RuntimeQuery:
    return RuntimeQuery.from_mapping(value)


def verify_query(value: RuntimeQuery) -> RuntimeQuery:
    if not isinstance(value, RuntimeQuery):
        raise ValidationError("history diff runtime query verification requires a typed query")
    value._validate(); return value


def query_json(value: RuntimeQuery) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: RuntimeQuery) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_query(value).rows); return output.getvalue()


def render_query_markdown(value: RuntimeQuery) -> str:
    value = verify_query(value); lines = [f"# Runtime registry history diff runtime query {value.query_id}", "", f"- Runtime: {value.runtime_id}", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Ordinal | Resource | Key | Result | Severity | Value |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.resource} | {item.key} | {item.passed if item.passed is not None else '—'} | {item.severity or '—'} | {item.value.replace('|', chr(92) + '|')} |" for item in value.rows); return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffRuntimeQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string" if field != "passed" else "boolean"} for field in ROW_FIELDS}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffRuntimeQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {field: {"type": "array" if field in ("resources", "rows") else "integer" if field.endswith("count") or field in ("offset", "limit") else "boolean" if field in ("passed_filter", "truncated") else "string"} for field in QUERY_FIELDS}, "$defs": {"row": row_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "severities": SEVERITIES, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("policy and comparison projections", "state result severity and text filters", "bounded pagination", "canonical row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "SEVERITIES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "RuntimeQueryRow", "RuntimeQuery", "address_row", "address_query", "query_runtime", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]













