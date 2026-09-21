"""Bounded query projections over D477 release batches."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d477_release_batch as batch_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = batch_model.VERSION + "-query-v1"
BOUNDARY = batch_model.BOUNDARY + "_query"
QUERY_PREFIX = batch_model.BATCH_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "policy", "items", "checks", "readiness", "addresses", "bounds")
STATES = batch_model.STATES
SEVERITIES = batch_model.SEVERITIES
MAX_ROWS = batch_model.MAX_CHECKS * 10
MAX_LIMIT = 256
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "passed", "severity", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "batch_id", "batch_address", "resources", "state_filter", "passed_filter", "severity_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


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
    return batch_model.runtime_model.diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class BatchQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, passed: bool | None, severity: str, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release batch query row ordinal", MAX_ROWS, lower=1)
        self.resource = _label(resource, "release batch query resource")
        self.item_id = _label(item_id, "release batch query item ID")
        self.key = _label(key, "release batch query key")
        if state not in STATES:
            raise ValidationError("release batch query row state is unsupported")
        self.state = state
        self.passed = _optional_bool(passed, "release batch query row result")
        if severity not in SEVERITIES and severity != "":
            raise ValidationError("release batch query row severity is unsupported")
        self.severity = severity
        self.value = _text(value, "release batch query row value", 32768)
        self.text = _text(text, "release batch query row text", 32768)
        self.content_address = _address(content_address, "release batch query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES:
            raise ValidationError("release batch query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address:
            raise ValidationError("release batch query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchQueryRow":
        value = _mapping(value, "release batch query row")
        _strict(value, set(cls.FIELDS), "release batch query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: BatchQueryRow) -> str:
    if not isinstance(value, BatchQueryRow):
        raise ValidationError("release batch query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class BatchQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, batch_id: str, batch_address: str, resources: Sequence[str], state_filter: str, passed_filter: bool | None, severity_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[BatchQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "release batch query ID")
        self.batch_id = _label(batch_id, "release batch query batch ID")
        self.batch_address = _address(batch_address, "release batch query batch address", batch_model.BATCH_PREFIX)
        self.resources = tuple(_label(item, "release batch query resource") for item in _sequence(resources, "release batch query resources", len(RESOURCES)))
        self.state_filter = _text(state_filter, "release batch query state filter", 64, required=False)
        self.passed_filter = _optional_bool(passed_filter, "release batch query result filter")
        self.severity_filter = _text(severity_filter, "release batch query severity filter", 64, required=False)
        self.text_filter = _text(text_filter, "release batch query text filter", 512, required=False)
        self.offset = _count(offset, "release batch query offset", MAX_ROWS)
        self.limit = _count(limit, "release batch query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "release batch query total count", MAX_ROWS)
        self.returned_count = _count(returned_count, "release batch query returned count", MAX_ROWS)
        self.truncated = _bool(truncated, "release batch query truncation")
        self.rows = tuple(item if isinstance(item, BatchQueryRow) else BatchQueryRow.from_mapping(_mapping(item, "release batch query row")) for item in _sequence(rows, "release batch query rows", MAX_ROWS))
        self.content_address = _address(content_address, "release batch query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources):
            raise ValidationError("release batch query resources are unsupported or duplicated")
        if self.state_filter and self.state_filter not in STATES or self.severity_filter and self.severity_filter not in SEVERITIES:
            raise ValidationError("release batch query filters are unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count or self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("release batch query counters do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)) or any(item.content_address != address_row(item) for item in self.rows):
            raise ValidationError("release batch query row order or addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address:
            raise ValidationError("release batch query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchQuery":
        value = _mapping(value, "release batch query")
        _strict(value, set(cls.FIELDS), "release batch query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: BatchQuery) -> str:
    if not isinstance(value, BatchQuery):
        raise ValidationError("release batch query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)


def _row(ordinal: int, resource: str, key: str, value: Any, *, state: str, passed: bool | None = None, severity: str = "") -> BatchQueryRow:
    rendered = canonical_json(value)
    return BatchQueryRow(ordinal, resource, f"{resource}:{key}", key, state, passed, severity, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")


def _rows(value: batch_model.ReleaseBatch) -> tuple[BatchQueryRow, ...]:
    raw: list[tuple[str, str, Any, str, bool | None, str]] = []

    def add(resource: str, key: str, item: Any, *, passed: bool | None = None, severity: str = "") -> None:
        raw.append((resource, key, item, value.state, passed, severity))

    for key in ("batch_id", "item_count", "ready_count", "blocked_count", "audited_count", "accepted_count", "accepted", "release_ready", "state"):
        item = getattr(value, key)
        add("summary", key, item, passed=item if isinstance(item, bool) else None)
    for key in ("policy_id", "minimum_runtimes", "minimum_ready", "maximum_blocked", "require_same_diff", "require_audited", "require_release_ready", "allow_mixed_policies"):
        item = getattr(value.policy, key)
        add("policy", key, item, passed=item if isinstance(item, bool) else None)
    for item in value.items:
        add("items", item.runtime_id, item.to_dict(), passed=item.accepted)
    for item in value.checks:
        add("checks", item.check_id, item.to_dict(), passed=item.passed, severity=item.severity)
    for key, item in (("release_ready", value.release_ready), ("state", value.state), ("accepted", value.accepted), ("ready_count", value.ready_count), ("blocked_count", value.blocked_count), ("audited_count", value.audited_count)):
        add("readiness", key, item, passed=item if isinstance(item, bool) else None)
    for key, item in (("batch_address", value.content_address), ("policy_address", value.policy.content_address), ("manifest_address", value.manifest.content_address), ("summary_address", value.summary.content_address), ("items_address", batch_model.address_items(value.items)), ("checks_address", batch_model.address_checks(value.checks))):
        add("addresses", key, item)
    for key, item in (("max_items", batch_model.MAX_ITEMS), ("max_checks", batch_model.MAX_CHECKS), ("max_rows", MAX_ROWS), ("item_count", value.item_count)):
        add("bounds", key, item)
    return tuple(_row(index, resource, key, item, state=state, passed=passed, severity=severity) for index, (resource, key, item, state, passed, severity) in enumerate(raw, 1))


def query_batch(value: batch_model.ReleaseBatch, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, state_filter: str = "", passed_filter: bool | None = None, severity_filter: str = "", text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> BatchQuery:
    batch_model.verify_batch(value)
    selected = tuple(resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected):
        raise ValidationError("release batch query resources are unsupported or duplicated")
    if state_filter and state_filter not in STATES or severity_filter and severity_filter not in SEVERITIES:
        raise ValidationError("release batch query filters are unsupported")
    offset = _count(offset, "release batch query offset", MAX_ROWS)
    limit = _count(limit, "release batch query limit", MAX_LIMIT, lower=1)
    rows = tuple(item for item in _rows(value) if item.resource in selected and (not state_filter or item.state == state_filter) and (passed_filter is None or item.passed == passed_filter) and (not severity_filter or item.severity == severity_filter) and (not text_filter or text_filter.casefold() in item.text.casefold()))
    page = rows[offset:offset + limit]
    typed = tuple(_seal(BatchQueryRow(index + 1, item.resource, item.item_id, item.key, item.state, item.passed, item.severity, item.value, item.text, f"pending:{ROW_PREFIX}"), address_row) for index, item in enumerate(page, offset))
    provisional = BatchQuery(query_id, value.batch_id, value.content_address, selected, state_filter, passed_filter, severity_filter, text_filter, offset, limit, len(rows), len(typed), offset + len(typed) < len(rows), typed, f"pending:{QUERY_PREFIX}")
    return _seal(provisional, address_query)


def query_from_mapping(value: Mapping[str, Any]) -> BatchQuery:
    return BatchQuery.from_mapping(value)


def verify_query(value: BatchQuery) -> BatchQuery:
    if not isinstance(value, BatchQuery):
        raise ValidationError("release batch query verification requires a typed query")
    value._validate()
    return value


def query_json(value: BatchQuery) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: BatchQuery) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_query(value).rows)
    return output.getvalue()


def render_query_markdown(value: BatchQuery) -> str:
    value = verify_query(value)
    lines = [f"# Release batch query {value.query_id}", "", f"- Batch: {value.batch_id}", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Resource | Key | State | Passed | Value |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.resource} | {item.key} | {item.state} | {item.passed} | {item.value} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in ROW_FIELDS}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {field: {"type": "array" if field in ("resources", "rows") else "integer" if field.endswith("count") or field in ("offset", "limit") else "boolean" if field in ("passed_filter", "truncated") else "string"} for field in QUERY_FIELDS}, "$defs": {"row": row_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "severities": SEVERITIES, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("summary policy item check and readiness projections", "state result severity and text filters", "bounded pagination", "canonical row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "SEVERITIES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "BatchQueryRow", "BatchQuery", "address_row", "address_query", "query_batch", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
