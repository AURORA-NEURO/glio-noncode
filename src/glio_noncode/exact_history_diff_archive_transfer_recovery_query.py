from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery as recovery_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = recovery_model.VERSION + "-query-v1"
BOUNDARY = recovery_model.BOUNDARY + "_query"
QUERY_PREFIX = recovery_model.RECOVERY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "actions", "received", "missing", "state", "progress", "bounds")
MAX_LIMIT = 128
MAX_QUERY_ITEMS = (3 * recovery_model.MAX_ACTIONS) + len(RESOURCES)
ROW_FIELDS = ("resource", "ordinal", "recovery_id", "transfer_id", "recovery_address", "archive_address", "archive_size", "chunk_count", "chunk_index", "chunk_offset", "chunk_size", "chunk_address", "action_address", "received", "missing", "state", "decision", "safe_to_resume", "checkpointed", "next_index", "remaining_bytes", "content_address")
QUERY_FIELDS = ("recovery_address", "recovery_id", "version", "boundary", "resources", "index", "state_filter", "received_filter", "text_filter", "offset", "limit", "rows", "row_count", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 1024)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False, optional: bool = False) -> str:
    value = _text(value, field, 8192, required=not optional)
    if optional and value == "":
        return value
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or value.startswith(("/", "\\")) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _index(value: Any, field: str, maximum: int, *, allow_minus_one: bool = False) -> int:
    return _count(value, field, maximum, lower=-1 if allow_minus_one else 0)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _nullable_bool(value: Any, field: str) -> bool | None:
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


class ExactHistoryDiffArchiveTransferRecoveryQueryRow:
    """One bounded public row from a recovery query."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, recovery_id: str, transfer_id: str, recovery_address: str, archive_address: str, archive_size: int, chunk_count: int, chunk_index: int, chunk_offset: int, chunk_size: int, chunk_address: str, action_address: str, received: bool, missing: bool, state: str, decision: str, safe_to_resume: bool, checkpointed: bool, next_index: int, remaining_bytes: int, content_address: str) -> None:
        if resource not in RESOURCES:
            raise ValidationError("recovery query resource is unsupported")
        self.resource = resource
        self.ordinal = _count(ordinal, "recovery query row ordinal", MAX_QUERY_ITEMS, lower=1)
        self.recovery_id = _label(recovery_id, "recovery query recovery ID")
        self.transfer_id = _label(transfer_id, "recovery query transfer ID")
        self.recovery_address = _address(recovery_address, "recovery query recovery address", recovery_model.RECOVERY_PREFIX)
        self.archive_address = _address(archive_address, "recovery query archive address", recovery_model.transfer_model.archive_model.ARCHIVE_PREFIX)
        self.archive_size = _count(archive_size, "recovery query archive size", recovery_model.transfer_model.MAX_TRANSFER_BYTES, lower=1)
        self.chunk_count = _count(chunk_count, "recovery query chunk count", recovery_model.MAX_ACTIONS, lower=1)
        self.chunk_index = _index(chunk_index, "recovery query chunk index", self.chunk_count - 1, allow_minus_one=True)
        self.chunk_offset = _count(chunk_offset, "recovery query chunk offset", recovery_model.transfer_model.MAX_TRANSFER_BYTES)
        self.chunk_size = _count(chunk_size, "recovery query chunk size", recovery_model.transfer_model.MAX_CHUNK_SIZE)
        self.chunk_address = _address(chunk_address, "recovery query chunk address", recovery_model.transfer_model.CHUNK_PREFIX, optional=True)
        self.action_address = _address(action_address, "recovery query action address", recovery_model.ACTION_PREFIX, optional=True)
        self.received = _bool(received, "recovery query received flag")
        self.missing = _bool(missing, "recovery query missing flag")
        if state not in recovery_model.STATES or decision not in recovery_model.DECISIONS or self.received == self.missing:
            raise ValidationError("recovery query row state flags are inconsistent")
        self.state = state
        self.decision = decision
        self.safe_to_resume = _bool(safe_to_resume, "recovery query safety flag")
        self.checkpointed = _bool(checkpointed, "recovery query checkpoint flag")
        self.next_index = _index(next_index, "recovery query next index", self.chunk_count - 1, allow_minus_one=True)
        self.remaining_bytes = _count(remaining_bytes, "recovery query remaining bytes", self.archive_size)
        self.content_address = _address(content_address, "recovery query row address", ROW_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.chunk_index == -1 and (self.chunk_offset != 0 or self.chunk_size != 0 or self.chunk_address or self.action_address):
            raise ValidationError("summary recovery query rows cannot carry chunk geometry")
        if self.chunk_index >= 0 and self.chunk_offset + self.chunk_size > self.archive_size:
            raise ValidationError("recovery query row range exceeds the archive")
        if self.resource == "actions" and (not self.missing or not self.chunk_address or not self.action_address):
            raise ValidationError("action query row is missing an addressed action")
        if self.resource == "missing" and (not self.missing or not self.chunk_address):
            raise ValidationError("missing query row is missing its chunk address")
        if self.resource == "received" and (not self.received or self.missing):
            raise ValidationError("received query row has invalid state flags")
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("recovery query row crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_row(self) != self.content_address:
            raise ValidationError("recovery query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryQueryRow:
        value = _mapping(value, "history diff archive transfer recovery query row")
        _strict(value, set(cls.FIELDS), "history diff archive transfer recovery query row")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryQuery:
    """A deterministic bounded query result over a recovery snapshot."""

    FIELDS = QUERY_FIELDS

    def __init__(self, recovery_address: str, recovery_id: str, version: str, boundary: str, resources: Sequence[str], index: int, state_filter: str, received_filter: bool | None, text_filter: str, offset: int, limit: int, rows: Sequence[ExactHistoryDiffArchiveTransferRecoveryQueryRow], row_count: int, content_address: str) -> None:
        self.recovery_address = _address(recovery_address, "recovery query recovery address", recovery_model.RECOVERY_PREFIX)
        self.recovery_id = _label(recovery_id, "recovery query recovery ID")
        self.version = _text(version, "recovery query version", 2048)
        self.boundary = _text(boundary, "recovery query boundary", 2048)
        self.resources = tuple(resources)
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources) or tuple(sorted(self.resources, key=RESOURCES.index)) != self.resources:
            raise ValidationError("recovery query resources are invalid or not canonical")
        self.index = _index(index, "recovery query index", recovery_model.MAX_ACTIONS - 1, allow_minus_one=True)
        self.state_filter = _text(state_filter, "recovery query state filter", 32, required=False)
        if self.state_filter and self.state_filter not in recovery_model.STATES:
            raise ValidationError("recovery query state filter is unsupported")
        self.received_filter = _nullable_bool(received_filter, "recovery query received filter")
        self.text_filter = _text(text_filter, "recovery query text filter", 512, required=False)
        self.offset = _count(offset, "recovery query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "recovery query limit", MAX_LIMIT, lower=1)
        self.rows = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryQueryRow) else ExactHistoryDiffArchiveTransferRecoveryQueryRow.from_mapping(item) for item in _sequence(rows, "recovery query rows", MAX_QUERY_ITEMS))
        self.row_count = _count(row_count, "recovery query row count", MAX_QUERY_ITEMS)
        if self.row_count != len(self.rows):
            raise ValidationError("recovery query row count is inconsistent")
        self.content_address = _address(content_address, "recovery query address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("recovery query version or boundary is not current")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.row_count + 1)):
            raise ValidationError("recovery query row order is not canonical")
        if any(item.recovery_address != self.recovery_address or item.recovery_id != self.recovery_id for item in self.rows):
            raise ValidationError("recovery query row linkage is inconsistent")
        if not self.content_address.startswith("pending:") and address_query(self) != self.content_address:
            raise ValidationError("recovery query address does not replay")
        if not recovery_model.transfer_model._public(self.to_dict()):
            raise ValidationError("recovery query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"recovery_address": self.recovery_address, "recovery_id": self.recovery_id, "version": self.version, "boundary": self.boundary, "resources": self.resources, "index": self.index, "state_filter": self.state_filter, "received_filter": self.received_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "rows": tuple(item.to_dict() for item in self.rows), "row_count": self.row_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryQuery:
        value = _mapping(value, "history diff archive transfer recovery query")
        _strict(value, set(cls.FIELDS), "history diff archive transfer recovery query")
        return cls(value["recovery_address"], value["recovery_id"], value["version"], value["boundary"], value["resources"], value["index"], value["state_filter"], value["received_filter"], value["text_filter"], value["offset"], value["limit"], tuple(ExactHistoryDiffArchiveTransferRecoveryQueryRow.from_mapping(item) for item in _sequence(value["rows"], "recovery query rows", MAX_QUERY_ITEMS)), value["row_count"], value["content_address"])


def address_row(value: ExactHistoryDiffArchiveTransferRecoveryQueryRow) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryQueryRow):
        raise ValidationError("recovery query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


def address_query(value: ExactHistoryDiffArchiveTransferRecoveryQuery) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryQuery):
        raise ValidationError("recovery query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(value: recovery_model.ExactHistoryDiffArchiveTransferRecovery, resource: str, ordinal: int, *, chunk_index: int = -1, chunk_offset: int = 0, chunk_size: int = 0, chunk_address: str = "", action_address: str = "", received: bool = True, missing: bool = False) -> ExactHistoryDiffArchiveTransferRecoveryQueryRow:
    pending = ExactHistoryDiffArchiveTransferRecoveryQueryRow(resource, ordinal, value.recovery_id, value.transfer_id, value.content_address, value.archive_address, value.archive_size, value.chunk_count, chunk_index, chunk_offset, chunk_size, chunk_address, action_address, received, missing, value.state, value.decision, value.safe_to_resume, value.checkpointed, value.next_index, value.remaining_bytes, "pending:recovery-query-row")
    return ExactHistoryDiffArchiveTransferRecoveryQueryRow(resource, ordinal, value.recovery_id, value.transfer_id, value.content_address, value.archive_address, value.archive_size, value.chunk_count, chunk_index, chunk_offset, chunk_size, chunk_address, action_address, received, missing, value.state, value.decision, value.safe_to_resume, value.checkpointed, value.next_index, value.remaining_bytes, address_row(pending))


def _matches(row: ExactHistoryDiffArchiveTransferRecoveryQueryRow, *, index: int, state: str, received: bool | None, text: str) -> bool:
    return (index < 0 or row.chunk_index == index) and (not state or row.state == state) and (received is None or row.received == received) and (not text or text.casefold() in canonical_json(row.to_dict()).casefold())


def query_recovery(value: recovery_model.ExactHistoryDiffArchiveTransferRecovery, *, resources: Sequence[str] | None = None, index: int | None = None, state: str = "", received: bool | None = None, text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> ExactHistoryDiffArchiveTransferRecoveryQuery:
    """Replay a bounded query over summary, action, and receiver-state resources."""
    if not isinstance(value, recovery_model.ExactHistoryDiffArchiveTransferRecovery):
        raise ValidationError("recovery query requires a typed recovery")
    value = recovery_model.recovery_from_mapping(value.to_dict())
    selected = tuple(RESOURCES if resources is None else resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected) or tuple(sorted(selected, key=RESOURCES.index)) != selected:
        raise ValidationError("recovery query resources are invalid or not canonical")
    query_index = -1 if index is None else _index(index, "recovery query index", value.chunk_count - 1)
    rows: list[ExactHistoryDiffArchiveTransferRecoveryQueryRow] = []
    for resource in selected:
        if resource in {"summary", "state", "progress", "bounds"}:
            rows.append(_row(value, resource, len(rows) + 1))
        elif resource == "actions":
            rows.extend(_row(value, resource, len(rows) + 1, chunk_index=item.index, chunk_offset=item.offset, chunk_size=item.size, chunk_address=item.content_address, action_address=item.action_address, received=False, missing=True) for item in value.actions)
        elif resource == "missing":
            rows.extend(_row(value, resource, len(rows) + 1, chunk_index=item.index, chunk_offset=item.offset, chunk_size=item.size, chunk_address=item.content_address, action_address=item.action_address, received=False, missing=True) for item in value.actions)
        elif resource == "received":
            rows.extend(_row(value, resource, len(rows) + 1, chunk_index=item, received=True, missing=False) for item in value.received_indices)
    filtered = tuple(row for row in rows if _matches(row, index=query_index, state=state, received=received, text=text))
    offset = _count(offset, "recovery query offset", MAX_QUERY_ITEMS)
    limit = _count(limit, "recovery query limit", MAX_LIMIT, lower=1)
    page = filtered[offset:offset + limit]
    normalized = []
    for ordinal, row in enumerate(page, 1):
        pending = ExactHistoryDiffArchiveTransferRecoveryQueryRow(row.resource, ordinal, row.recovery_id, row.transfer_id, row.recovery_address, row.archive_address, row.archive_size, row.chunk_count, row.chunk_index, row.chunk_offset, row.chunk_size, row.chunk_address, row.action_address, row.received, row.missing, row.state, row.decision, row.safe_to_resume, row.checkpointed, row.next_index, row.remaining_bytes, "pending:recovery-query-row")
        normalized.append(ExactHistoryDiffArchiveTransferRecoveryQueryRow(pending.resource, pending.ordinal, pending.recovery_id, pending.transfer_id, pending.recovery_address, pending.archive_address, pending.archive_size, pending.chunk_count, pending.chunk_index, pending.chunk_offset, pending.chunk_size, pending.chunk_address, pending.action_address, pending.received, pending.missing, pending.state, pending.decision, pending.safe_to_resume, pending.checkpointed, pending.next_index, pending.remaining_bytes, address_row(pending)))
    provisional = ExactHistoryDiffArchiveTransferRecoveryQuery(value.content_address, value.recovery_id, VERSION, BOUNDARY, selected, query_index, state, received, text, offset, limit, tuple(normalized), len(normalized), "pending:recovery-query")
    return ExactHistoryDiffArchiveTransferRecoveryQuery(value.content_address, value.recovery_id, VERSION, BOUNDARY, selected, query_index, state, received, text, offset, limit, tuple(normalized), len(normalized), address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryQuery:
    return ExactHistoryDiffArchiveTransferRecoveryQuery.from_mapping(value)


def query_json(value: ExactHistoryDiffArchiveTransferRecoveryQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: ExactHistoryDiffArchiveTransferRecoveryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow(row.to_dict())
    return stream.getvalue()


def render_query_markdown(value: ExactHistoryDiffArchiveTransferRecoveryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Exact runtime-registry history-diff archive transfer recovery query", "", f"- Recovery: `{value.recovery_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.row_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | chunk | received | missing | state | decision |", "| ---: | --- | ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.chunk_index}` | `{str(item.received).lower()}` | `{str(item.missing).lower()}` | `{item.state}` | `{item.decision}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact runtime-registry history-diff archive transfer recovery query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}, "recovery_id": {"type": "string"}, "transfer_id": {"type": "string"}, "recovery_address": {"type": "string", "pattern": "^" + recovery_model.RECOVERY_PREFIX + ":"}, "archive_address": {"type": "string", "pattern": "^" + recovery_model.transfer_model.archive_model.ARCHIVE_PREFIX + ":"}, "archive_size": {"type": "integer", "minimum": 1}, "chunk_count": {"type": "integer", "minimum": 1}, "chunk_index": {"type": "integer", "minimum": -1}, "chunk_offset": {"type": "integer", "minimum": 0}, "chunk_size": {"type": "integer", "minimum": 0}, "chunk_address": {"type": "string"}, "action_address": {"type": "string"}, "received": {"type": "boolean"}, "missing": {"type": "boolean"}, "state": {"type": "string", "enum": list(recovery_model.STATES)}, "decision": {"type": "string", "enum": list(recovery_model.DECISIONS)}, "safe_to_resume": {"type": "boolean"}, "checkpointed": {"type": "boolean"}, "next_index": {"type": "integer", "minimum": -1}, "remaining_bytes": {"type": "integer", "minimum": 0}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact runtime-registry history-diff archive transfer recovery query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"recovery_address": {"type": "string", "pattern": "^" + recovery_model.RECOVERY_PREFIX + ":"}, "recovery_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "resources": {"type": "array", "minItems": 1, "maxItems": len(RESOURCES), "items": {"type": "string", "enum": list(RESOURCES)}}, "index": {"type": "integer", "minimum": -1}, "state_filter": {"type": "string"}, "received_filter": {"type": ["boolean", "null"]}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_QUERY_ITEMS}, "row_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "features": ["bounded recovery resources", "addressed missing-action inspection", "received and missing state filters", "state and index filters", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "ExactHistoryDiffArchiveTransferRecoveryQuery", "ExactHistoryDiffArchiveTransferRecoveryQueryRow", "VERSION", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_recovery", "query_schema", "render_query_markdown", "row_schema"]
