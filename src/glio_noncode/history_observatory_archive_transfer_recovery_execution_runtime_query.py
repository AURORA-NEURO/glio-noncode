"""Bounded offline queries over recovery execution runtime handoffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = runtime_model.VERSION + "-query-v1"
BOUNDARY = runtime_model.BOUNDARY + "_query"
QUERY_PREFIX = runtime_model.RUNTIME_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "stages", "artifacts", "components", "outcomes", "status", "bounds")
MAX_QUERY_ITEMS = 512
MAX_LIMIT = 128
ROW_FIELDS = ("resource", "ordinal", "key", "value", "address", "state", "accepted", "row_address")
QUERY_FIELDS = ("query_id", "version", "boundary", "runtime_address", "runtime_id", "execution_id", "resources", "state_filter", "key_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, required=True)
    if allow_pending and value.startswith("pending:"):
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
    return runtime_model._public(value)


class RecoveryExecutionRuntimeQueryRow:
    """One value-free row from a runtime query."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, key: str, value: Any, address: str, state: str, accepted: bool, row_address: str) -> None:
        if resource not in RESOURCES:
            raise ValidationError("runtime query row resource is unsupported")
        self.resource = resource
        self.ordinal = _count(ordinal, "runtime query row ordinal", MAX_QUERY_ITEMS - 1)
        self.key = _text(key, "runtime query row key", 512, required=True)
        self.value = value
        if len(canonical_json(value).encode("utf-8")) > 8192 or not _public(value):
            raise ValidationError("runtime query row value is not bounded and public")
        self.address = _address(address, "runtime query row address")
        if state not in ("",) + runtime_model.STATES:
            raise ValidationError("runtime query row state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime query row acceptance")
        self.row_address = _address(row_address, "runtime query row address receipt", ROW_PREFIX, allow_pending=True)
        if not self.row_address.startswith("pending:") and address_row(self) != self.row_address:
            raise ValidationError("runtime query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeQueryRow":
        value = _mapping(value, "runtime query row")
        _strict(value, set(cls.FIELDS), "runtime query row")
        return cls(*(value[field] for field in cls.FIELDS))


class RecoveryExecutionRuntimeQuery:
    """A deterministic, bounded runtime inspection query."""

    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, version: str, boundary: str, runtime_address: str, runtime_id: str, execution_id: str, resources: Sequence[str], state_filter: str, key_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[RecoveryExecutionRuntimeQueryRow], content_address: str) -> None:
        self.query_id = _label(query_id, "runtime query ID")
        self.version = _text(version, "runtime query version", 2048, required=True)
        self.boundary = _text(boundary, "runtime query boundary", 1024, required=True)
        self.runtime_address = _address(runtime_address, "runtime query runtime address", runtime_model.RUNTIME_PREFIX)
        self.runtime_id = _label(runtime_id, "runtime query runtime ID")
        self.execution_id = _label(execution_id, "runtime query execution ID")
        selected = tuple(resources)
        if not selected or any(resource not in RESOURCES for resource in selected) or len(set(selected)) != len(selected) or selected != tuple(resource for resource in RESOURCES if resource in selected):
            raise ValidationError("runtime query resources are not canonical")
        self.resources = selected
        if state_filter not in ("",) + runtime_model.STATES:
            raise ValidationError("runtime query state filter is unsupported")
        self.state_filter = state_filter
        self.key_filter = _text(key_filter, "runtime query key filter", 512)
        self.text_filter = _text(text_filter, "runtime query text filter", 512)
        self.offset = _count(offset, "runtime query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "runtime query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "runtime query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "runtime query returned count", self.limit)
        self.truncated = _bool(truncated, "runtime query truncation")
        self.rows = tuple(item if isinstance(item, RecoveryExecutionRuntimeQueryRow) else RecoveryExecutionRuntimeQueryRow.from_mapping(item) for item in _sequence(rows, "runtime query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "runtime query content address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.returned_count != len(self.rows) or tuple(item.ordinal for item in self.rows) != tuple(range(self.returned_count)) or any(item.resource not in self.resources for item in self.rows):
            raise ValidationError("runtime query rows are inconsistent")
        if self.total_count < self.returned_count or self.offset + self.returned_count > self.total_count and not self.truncated:
            raise ValidationError("runtime query counts are inconsistent")
        if self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("runtime query truncation does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime query crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_query(self) != self.content_address:
            raise ValidationError("runtime query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "version": self.version, "boundary": self.boundary, "runtime_address": self.runtime_address, "runtime_id": self.runtime_id, "execution_id": self.execution_id, "resources": self.resources, "state_filter": self.state_filter, "key_filter": self.key_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeQuery":
        value = _mapping(value, "recovery execution runtime query")
        _strict(value, set(cls.FIELDS), "recovery execution runtime query")
        return cls(value["query_id"], value["version"], value["boundary"], value["runtime_address"], value["runtime_id"], value["execution_id"], value["resources"], value["state_filter"], value["key_filter"], value["text_filter"], value["offset"], value["limit"], value["total_count"], value["returned_count"], value["truncated"], tuple(RecoveryExecutionRuntimeQueryRow.from_mapping(item) for item in _sequence(value["rows"], "runtime query rows", MAX_LIMIT)), value["content_address"])


def address_row(value: RecoveryExecutionRuntimeQueryRow) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeQueryRow):
        raise ValidationError("runtime query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


def address_query(value: RecoveryExecutionRuntimeQuery) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeQuery):
        raise ValidationError("runtime query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, key: str, value: Any, address: str, state: str, accepted: bool) -> RecoveryExecutionRuntimeQueryRow:
    pending = RecoveryExecutionRuntimeQueryRow(resource, ordinal, key, value, address, state, accepted, "pending:runtime-query-row")
    return RecoveryExecutionRuntimeQueryRow(resource, ordinal, key, value, address, state, accepted, address_row(pending))


def _all_rows(value: runtime_model.RecoveryExecutionRuntime) -> tuple[RecoveryExecutionRuntimeQueryRow, ...]:
    rows: list[RecoveryExecutionRuntimeQueryRow] = []
    for field in runtime_model.RUNTIME_FIELDS:
        if field != "stages":
            rows.append(_row("summary", len(rows), field, value.to_dict()[field], value.content_address, value.state, value.accepted))
    for item in value.stages:
        rows.append(_row("stages", len(rows), item.stage, item.state, item.address, item.state, item.accepted))
    for item in runtime_model.manifest_document(value)["artifacts"]:
        rows.append(_row("artifacts", len(rows), item["name"], {"size": item["size"], "hash": item["hash"]}, item["content_address"], value.state, value.accepted))
    components = (("execution", value.execution_address), ("execution-audit", value.execution_audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address))
    for key, address in components:
        rows.append(_row("components", len(rows), key, address, address, value.state, value.accepted))
    for item in value.execution.outcomes:
        rows.append(_row("outcomes", len(rows), str(item.index), item.status, item.outcome_address, value.state, item.status == "applied"))
    for key, item in (("state", value.state), ("accepted", value.accepted), ("execution-decision", value.execution.decision)):
        rows.append(_row("status", len(rows), key, item, value.content_address, value.state, value.accepted))
    bounds = (("archive-size", value.execution.archive_size), ("chunk-count", value.execution.chunk_count), ("action-count", value.execution.action_count), ("applied-count", value.execution.applied_count), ("pending-count", value.execution.pending_count), ("rejected-count", value.execution.rejected_count))
    for key, item in bounds:
        rows.append(_row("bounds", len(rows), key, item, value.content_address, value.state, value.accepted))
    return tuple(rows)


def _matches(row: RecoveryExecutionRuntimeQueryRow, *, state: str, key: str, text: str) -> bool:
    if state and row.state != state:
        return False
    if key and row.key != key:
        return False
    if text and text.casefold() not in canonical_json(row.to_dict()).casefold():
        return False
    return True


def query_runtime(value: runtime_model.RecoveryExecutionRuntime, *, query_id: str = "comparison-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-query", resources: Sequence[str] | None = None, state: str = "", key: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> RecoveryExecutionRuntimeQuery:
    if not isinstance(value, runtime_model.RecoveryExecutionRuntime):
        raise ValidationError("runtime query requires a typed runtime")
    value = runtime_model.verify_runtime(value)
    selected = tuple(resource for resource in RESOURCES if resources is None or resource in tuple(resources))
    if not selected:
        raise ValidationError("runtime query requires at least one resource")
    rows = tuple(item for item in _all_rows(value) if item.resource in selected and _matches(item, state=state, key=key, text=text))
    offset = _count(offset, "runtime query offset", MAX_QUERY_ITEMS)
    limit = _count(limit, "runtime query limit", MAX_LIMIT, lower=1)
    page = rows[offset:offset + limit]
    page_rows = tuple(_row(item.resource, ordinal, item.key, item.value, item.address, item.state, item.accepted) for ordinal, item in enumerate(page))
    provisional = RecoveryExecutionRuntimeQuery(query_id, VERSION, BOUNDARY, value.content_address, value.runtime_id, value.execution_id, selected, state, key, text, offset, limit, len(rows), len(page_rows), offset + len(page_rows) < len(rows), page_rows, "pending:runtime-query")
    return RecoveryExecutionRuntimeQuery(query_id, VERSION, BOUNDARY, value.content_address, value.runtime_id, value.execution_id, selected, state, key, text, offset, limit, len(rows), len(page_rows), offset + len(page_rows) < len(rows), page_rows, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntimeQuery:
    return RecoveryExecutionRuntimeQuery.from_mapping(value)


def query_json(value: RecoveryExecutionRuntimeQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: RecoveryExecutionRuntimeQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_query_markdown(value: RecoveryExecutionRuntimeQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Archive transfer recovery execution runtime query", "", f"- Runtime: `{value.runtime_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.total_count}`", f"- Address: `{value.content_address}`", "", "| resource | ordinal | key | state | accepted | address |", "| --- | ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.resource} | {item.ordinal} | `{item.key}` | `{item.state}` | `{item.accepted}` | `{item.address}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 0}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "state": {"type": "string"}, "accepted": {"type": "boolean"}, "row_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "runtime_address": {"type": "string", "pattern": "^" + runtime_model.RUNTIME_PREFIX + ":"}, "runtime_id": {"type": "string"}, "execution_id": {"type": "string"}, "resources": {"type": "array", "items": {"type": "string", "enum": list(RESOURCES)}}, "state_filter": {"type": "string"}, "key_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "max_query_items": MAX_QUERY_ITEMS, "max_limit": MAX_LIMIT, "features": ("summary stage artifact component outcome status and bounds resources", "state key and text filters", "deterministic pagination", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "RecoveryExecutionRuntimeQuery", "RecoveryExecutionRuntimeQueryRow", "VERSION", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_runtime", "query_schema", "render_query_markdown", "row_schema"]
