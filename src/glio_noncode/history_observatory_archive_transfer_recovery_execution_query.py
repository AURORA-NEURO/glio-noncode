"""Bounded public queries over recovery execution receipts."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution as execution_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = execution_model.VERSION + "-query-v1"
BOUNDARY = execution_model.BOUNDARY + "_query"
QUERY_PREFIX = execution_model.EXECUTION_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
MAX_LIMIT = 256
MAX_QUERY_ITEMS = execution_model.MAX_OUTCOMES + 16
RESOURCES = ("summary", "outcomes", "applied", "pending", "rejected", "state", "bounds")
ROW_FIELDS = ("resource", "ordinal", "index", "action_address", "content_address", "offset", "size", "status", "reason", "outcome_address", "state", "decision", "row_address")
QUERY_FIELDS = ("query_id", "version", "boundary", "execution_address", "execution_id", "resources", "status_filter", "index_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, optional: bool = False, allow_pending: bool = False) -> str:
    value = _text(value, field, required=not optional)
    if optional and value == "":
        return value
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


class RecoveryExecutionQueryRow:
    """One value-free row from an execution query."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, index: int, action_address: str, content_address: str, offset: int, size: int, status: str, reason: str, outcome_address: str, state: str, decision: str, row_address: str) -> None:
        if resource not in RESOURCES:
            raise ValidationError("execution query row resource is unsupported")
        self.resource = resource
        self.ordinal = _count(ordinal, "execution query row ordinal", MAX_QUERY_ITEMS - 1)
        self.index = _count(index + 1, "execution query row index", execution_model.transfer_model.MAX_CHUNKS) - 1
        self.action_address = _address(action_address, "execution query action address", execution_model.recovery_model.ACTION_PREFIX, optional=True)
        self.content_address = _address(content_address, "execution query chunk address", execution_model.transfer_model.CHUNK_PREFIX, optional=True)
        self.offset = _count(offset, "execution query row offset", execution_model.transfer_model.MAX_TRANSFER_BYTES)
        self.size = _count(size, "execution query row size", execution_model.transfer_model.MAX_CHUNK_SIZE)
        if status not in ("",) + execution_model.STATUSES:
            raise ValidationError("execution query row status is unsupported")
        if reason and not isinstance(reason, str):
            raise ValidationError("execution query row reason is invalid")
        self.status = status
        self.reason = _text(reason, "execution query row reason", 512)
        self.outcome_address = _address(outcome_address, "execution query outcome address", execution_model.OUTCOME_PREFIX, optional=True)
        if state not in ("",) + execution_model.STATES:
            raise ValidationError("execution query row state is unsupported")
        if decision not in ("",) + execution_model.DECISIONS:
            raise ValidationError("execution query row decision is unsupported")
        self.state = state
        self.decision = decision
        self.row_address = _address(row_address, "execution query row address", ROW_PREFIX, allow_pending=True)
        if not self.row_address.startswith("pending:") and address_row(self) != self.row_address:
            raise ValidationError("execution query row address does not replay")
        if not execution_model.transfer_model._public(self.to_dict()):
            raise ValidationError("execution query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionQueryRow":
        value = _mapping(value, "execution query row")
        _strict(value, set(cls.FIELDS), "execution query row")
        return cls(*(value[field] for field in cls.FIELDS))


class RecoveryExecutionQuery:
    """A deterministic, bounded execution query result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, version: str, boundary: str, execution_address: str, execution_id: str, resources: Sequence[str], status_filter: str, index_filter: int, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[RecoveryExecutionQueryRow], content_address: str) -> None:
        self.query_id = _label(query_id, "execution query ID")
        self.version = _text(version, "execution query version", 2048, required=True)
        self.boundary = _text(boundary, "execution query boundary", 1024, required=True)
        self.execution_address = _address(execution_address, "execution query execution address", execution_model.EXECUTION_PREFIX)
        self.execution_id = _label(execution_id, "execution query execution ID")
        selected = tuple(resources)
        if not selected or any(resource not in RESOURCES for resource in selected) or len(set(selected)) != len(selected) or selected != tuple(resource for resource in RESOURCES if resource in selected):
            raise ValidationError("execution query resources are not canonical")
        self.resources = selected
        if status_filter not in ("",) + execution_model.STATUSES:
            raise ValidationError("execution query status filter is unsupported")
        self.status_filter = status_filter
        self.index_filter = _count(index_filter + 1, "execution query index filter", execution_model.transfer_model.MAX_CHUNKS) - 1
        self.text_filter = _text(text_filter, "execution query text filter", 512)
        self.offset = _count(offset, "execution query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "execution query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "execution query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "execution query returned count", self.limit)
        self.truncated = _bool(truncated, "execution query truncation")
        self.rows = tuple(item if isinstance(item, RecoveryExecutionQueryRow) else RecoveryExecutionQueryRow.from_mapping(item) for item in _sequence(rows, "execution query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "execution query address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.returned_count != len(self.rows) or tuple(item.ordinal for item in self.rows) != tuple(range(self.returned_count)) or any(item.resource not in self.resources for item in self.rows):
            raise ValidationError("execution query rows are inconsistent")
        if self.total_count < self.returned_count or self.offset + self.returned_count > self.total_count and not self.truncated:
            raise ValidationError("execution query counts are inconsistent")
        if self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("execution query truncation does not replay")
        if not execution_model.transfer_model._public(self.to_dict()):
            raise ValidationError("execution query crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_query(self) != self.content_address:
            raise ValidationError("execution query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "version": self.version, "boundary": self.boundary, "execution_address": self.execution_address, "execution_id": self.execution_id, "resources": self.resources, "status_filter": self.status_filter, "index_filter": self.index_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionQuery":
        value = _mapping(value, "execution query")
        _strict(value, set(cls.FIELDS), "execution query")
        return cls(value["query_id"], value["version"], value["boundary"], value["execution_address"], value["execution_id"], value["resources"], value["status_filter"], value["index_filter"], value["text_filter"], value["offset"], value["limit"], value["total_count"], value["returned_count"], value["truncated"], tuple(RecoveryExecutionQueryRow.from_mapping(item) for item in _sequence(value["rows"], "execution query rows", MAX_LIMIT)), value["content_address"])


def address_row(value: RecoveryExecutionQueryRow) -> str:
    if not isinstance(value, RecoveryExecutionQueryRow):
        raise ValidationError("execution query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


def address_query(value: RecoveryExecutionQuery) -> str:
    if not isinstance(value, RecoveryExecutionQuery):
        raise ValidationError("execution query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, *, index: int = -1, action_address: str = "", content_address: str = "", offset: int = 0, size: int = 0, status: str = "", reason: str = "", outcome_address: str = "", state: str = "", decision: str = "") -> RecoveryExecutionQueryRow:
    pending = RecoveryExecutionQueryRow(resource, ordinal, index, action_address, content_address, offset, size, status, reason, outcome_address, state, decision, "pending:execution-query-row")
    return RecoveryExecutionQueryRow(resource, ordinal, index, action_address, content_address, offset, size, status, reason, outcome_address, state, decision, address_row(pending))


def _all_rows(value: execution_model.RecoveryExecution) -> tuple[RecoveryExecutionQueryRow, ...]:
    rows: list[RecoveryExecutionQueryRow] = []
    rows.append(_row("summary", 0, reason="execution-summary", state=value.state, decision=value.decision, offset=value.current_received_bytes, size=value.current_remaining_bytes))
    for item in value.outcomes:
        rows.append(_row("outcomes", len(rows), index=item.index, action_address=item.action_address, content_address=item.content_address, offset=item.offset, size=item.size, status=item.status, reason=item.reason, outcome_address=item.outcome_address))
    for resource, status in (("applied", "applied"), ("pending", "pending"), ("rejected", "rejected")):
        for item in value.outcomes:
            if item.status == status:
                rows.append(_row(resource, len(rows), index=item.index, action_address=item.action_address, content_address=item.content_address, offset=item.offset, size=item.size, status=item.status, reason=item.reason, outcome_address=item.outcome_address))
    rows.append(_row("state", len(rows), reason="execution-state", status="", state=value.state, decision=value.decision))
    rows.append(_row("bounds", len(rows), reason="archive-bounds", offset=value.current_received_bytes, size=value.current_remaining_bytes, state=value.state, decision=value.decision))
    return tuple(rows)


def _matches(row: RecoveryExecutionQueryRow, *, status: str, index: int, text: str) -> bool:
    if status and row.status != status:
        return False
    if index >= 0 and row.index != index:
        return False
    if text:
        haystack = canonical_json(row.to_dict()).casefold()
        if text.casefold() not in haystack:
            return False
    return True


def query_execution(value: execution_model.RecoveryExecution, *, query_id: str = "comparison-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-query", resources: Sequence[str] | None = None, status: str = "", index: int = -1, text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> RecoveryExecutionQuery:
    if not isinstance(value, execution_model.RecoveryExecution):
        raise ValidationError("execution query requires a typed execution")
    selected = tuple(resource for resource in RESOURCES if resources is None or resource in tuple(resources))
    if not selected:
        raise ValidationError("execution query requires at least one resource")
    index = _count(index + 1, "execution query index", value.chunk_count) - 1
    rows = tuple(item for item in _all_rows(value) if item.resource in selected and _matches(item, status=status, index=index, text=text))
    offset = _count(offset, "execution query offset", MAX_QUERY_ITEMS)
    limit = _count(limit, "execution query limit", MAX_LIMIT, lower=1)
    page = rows[offset:offset + limit]
    page_rows = []
    for ordinal, item in enumerate(page):
        pending = RecoveryExecutionQueryRow(item.resource, ordinal, item.index, item.action_address, item.content_address, item.offset, item.size, item.status, item.reason, item.outcome_address, item.state, item.decision, "pending:execution-query-row")
        page_rows.append(RecoveryExecutionQueryRow(item.resource, ordinal, item.index, item.action_address, item.content_address, item.offset, item.size, item.status, item.reason, item.outcome_address, item.state, item.decision, address_row(pending)))
    page = tuple(page_rows)
    result = RecoveryExecutionQuery(query_id, VERSION, BOUNDARY, value.content_address, value.execution_id, selected, status, index, text, offset, limit, len(rows), len(page), offset + len(page) < len(rows), page, "pending:execution-query")
    return RecoveryExecutionQuery(query_id, VERSION, BOUNDARY, value.content_address, value.execution_id, selected, status, index, text, offset, limit, len(rows), len(page), offset + len(page) < len(rows), page, address_query(result))


def query_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionQuery:
    return RecoveryExecutionQuery.from_mapping(value)


def query_json(value: RecoveryExecutionQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: RecoveryExecutionQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_query_markdown(value: RecoveryExecutionQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# History observatory archive transfer recovery execution query", "", f"- Execution: `{value.execution_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.total_count}`", f"- Address: `{value.content_address}`", "", "| resource | ordinal | index | status | state | decision | reason | row address |", "| --- | ---: | ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.resource} | {item.ordinal} | {item.index} | {item.status} | {item.state} | {item.decision} | {item.reason} | {item.row_address} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "History observatory archive transfer recovery execution query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 0}, "index": {"type": "integer", "minimum": -1}, "action_address": {"type": "string"}, "content_address": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "size": {"type": "integer", "minimum": 0}, "status": {"type": "string"}, "reason": {"type": "string"}, "outcome_address": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "row_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "History observatory archive transfer recovery execution query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "execution_address": {"type": "string", "pattern": "^" + execution_model.EXECUTION_PREFIX + ":"}, "execution_id": {"type": "string"}, "resources": {"type": "array", "items": {"type": "string", "enum": list(RESOURCES)}}, "status_filter": {"type": "string"}, "index_filter": {"type": "integer", "minimum": -1}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "max_limit": MAX_LIMIT, "features": ["summary outcome and status resources", "index status and text filters", "deterministic pagination", "row and query addresses", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "RecoveryExecutionQuery", "RecoveryExecutionQueryRow", "VERSION", "address_query", "address_row", "capabilities", "query_csv", "query_execution", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
