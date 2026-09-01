"""Bounded path-free queries over exact execution ledgers."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger as ledger_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = ledger_model.VERSION + "-query-v1"
BOUNDARY = ledger_model.BOUNDARY + "_query"
QUERY_PREFIX = ledger_model.LEDGER_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
MAX_LIMIT = 256
MAX_QUERY_ITEMS = ledger_model.MAX_ENTRIES * 7 + 2
RESOURCES = ("summary", "entries", "transitions", "states", "decisions", "bytes", "latest")
ROW_FIELDS = (
    "resource", "ordinal", "ledger_id", "recovery_id", "execution_id", "execution_address", "transition",
    "state", "decision", "accepted", "applied_count", "pending_count", "rejected_count",
    "current_received_bytes", "current_remaining_bytes", "checkpointed", "previous_execution_address",
    "previous_entry_address", "head_address", "value", "row_address",
)
QUERY_FIELDS = (
    "query_id", "version", "boundary", "ledger_address", "ledger_id", "resources", "transition_filter",
    "state_filter", "decision_filter", "text_filter", "offset", "limit", "total_count", "returned_count",
    "truncated", "rows", "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str = "ledger query label") -> str:
    value = _text(value, field, 512, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = False, allow_pending: bool = False) -> str:
    value = _text(value, field, 4096, required=required)
    if allow_pending and value.startswith("pending:"):
        return value
    if not value:
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


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow:
    """One bounded, value-free ledger query row."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, ledger_id: str, recovery_id: str, execution_id: str, execution_address: str, transition: str, state: str, decision: str, accepted: bool, applied_count: int, pending_count: int, rejected_count: int, current_received_bytes: int, current_remaining_bytes: int, checkpointed: bool, previous_execution_address: str, previous_entry_address: str, head_address: str, value: str, row_address: str) -> None:
        if resource not in RESOURCES:
            raise ValidationError("ledger query resource is unsupported")
        self.resource = resource
        self.ordinal = _count(ordinal, "ledger query row ordinal", MAX_QUERY_ITEMS)
        self.ledger_id = _label(ledger_id)
        self.recovery_id = _text(recovery_id, "ledger query row recovery ID", 512)
        self.execution_id = _text(execution_id, "ledger query row execution ID", 512)
        self.execution_address = _address(execution_address, "ledger query row execution address")
        self.transition = _text(transition, "ledger query row transition", 32)
        self.state = _text(state, "ledger query row state", 32)
        self.decision = _text(decision, "ledger query row decision", 32)
        self.accepted = _bool(accepted, "ledger query row acceptance")
        self.applied_count = _count(applied_count, "ledger query row applied count", ledger_model.MAX_ENTRIES)
        self.pending_count = _count(pending_count, "ledger query row pending count", ledger_model.MAX_ENTRIES)
        self.rejected_count = _count(rejected_count, "ledger query row rejected count", ledger_model.MAX_ENTRIES)
        self.current_received_bytes = _count(current_received_bytes, "ledger query row received bytes", ledger_model.MAX_LEDGER_BYTES)
        self.current_remaining_bytes = _count(current_remaining_bytes, "ledger query row remaining bytes", ledger_model.MAX_LEDGER_BYTES)
        self.checkpointed = _bool(checkpointed, "ledger query row checkpoint")
        self.previous_execution_address = _address(previous_execution_address, "ledger query row previous execution address")
        self.previous_entry_address = _address(previous_entry_address, "ledger query row previous entry address")
        self.head_address = _address(head_address, "ledger query row head address", required=True)
        self.value = _text(value, "ledger query row value", 4096)
        self.row_address = _address(row_address, "ledger query row address", ROW_PREFIX, allow_pending=True)
        if not self.row_address.startswith("pending:") and address_row(self) != self.row_address:
            raise ValidationError("ledger query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow":
        value = _mapping(value, "ledger query row")
        _strict(value, set(cls.FIELDS), "ledger query row")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery:
    """A deterministic bounded ledger query result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, version: str, boundary: str, ledger_address: str, ledger_id: str, resources: Sequence[str], transition_filter: str, state_filter: str, decision_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow], content_address: str) -> None:
        self.query_id = _label(query_id)
        self.version = _text(version, "ledger query version", 2048, required=True)
        self.boundary = _text(boundary, "ledger query boundary", 1024, required=True)
        self.ledger_address = _address(ledger_address, "ledger query ledger address", ledger_model.LEDGER_PREFIX, required=True)
        self.ledger_id = _label(ledger_id)
        self.resources = tuple(_text(item, "ledger query resource", 64, required=True) for item in _sequence(resources, "ledger query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or self.resources != tuple(item for item in RESOURCES if item in self.resources):
            raise ValidationError("ledger query resources are not canonical")
        self.transition_filter = _text(transition_filter, "ledger query transition filter", 32)
        self.state_filter = _text(state_filter, "ledger query state filter", 32)
        self.decision_filter = _text(decision_filter, "ledger query decision filter", 32)
        self.text_filter = _text(text_filter, "ledger query text filter", 256).casefold()
        self.offset = _count(offset, "ledger query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "ledger query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "ledger query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "ledger query returned count", MAX_QUERY_ITEMS)
        self.truncated = _bool(truncated, "ledger query truncation")
        self.rows = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow.from_mapping(item) for item in _sequence(rows, "ledger query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "ledger query address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger query version or boundary is not current")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.offset + self.returned_count > self.total_count + self.offset:
            raise ValidationError("ledger query counts do not replay")
        if self.truncated != (self.offset + self.returned_count < self.offset + self.total_count):
            raise ValidationError("ledger query truncation does not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset, self.offset + self.returned_count)):
            raise ValidationError("ledger query row order does not replay")
        if not self.content_address.startswith("pending:") and address_query(self) != self.content_address:
            raise ValidationError("ledger query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "version": self.version, "boundary": self.boundary, "ledger_address": self.ledger_address, "ledger_id": self.ledger_id, "resources": self.resources, "transition_filter": self.transition_filter, "state_filter": self.state_filter, "decision_filter": self.decision_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery":
        value = _mapping(value, "ledger query")
        _strict(value, set(cls.FIELDS), "ledger query")
        return cls(value["query_id"], value["version"], value["boundary"], value["ledger_address"], value["ledger_id"], value["resources"], value["transition_filter"], value["state_filter"], value["decision_filter"], value["text_filter"], value["offset"], value["limit"], value["total_count"], value["returned_count"], value["truncated"], tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow.from_mapping(item) for item in _sequence(value["rows"], "ledger query rows", MAX_LIMIT)), value["content_address"])


def address_row(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow):
        raise ValidationError("ledger query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


def address_query(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery):
        raise ValidationError("ledger query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _renumber(row: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow, ordinal: int) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "row_address": "pending:ledger-query-row"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow(**body | {"row_address": address_row(provisional)})


def _row(resource: str, ordinal: int, *, ledger: ledger_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedger, entry: ledger_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry | None = None, value: str = "") -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow:
    if entry is None:
        body = {"resource": resource, "ordinal": ordinal, "ledger_id": ledger.ledger_id, "recovery_id": ledger.recovery_id, "execution_id": ledger.latest_execution_id, "execution_address": ledger.latest_execution_address, "transition": "", "state": ledger.state, "decision": ledger.latest_decision, "accepted": ledger.accepted, "applied_count": 0, "pending_count": 0, "rejected_count": 0, "current_received_bytes": ledger.archive_size if ledger.state == "complete" else 0, "current_remaining_bytes": 0 if ledger.state == "complete" else ledger.archive_size, "checkpointed": False, "previous_execution_address": "", "previous_entry_address": "", "head_address": ledger.head_address, "value": value}
    else:
        body = {"resource": resource, "ordinal": ordinal, "ledger_id": ledger.ledger_id, "recovery_id": entry.recovery_id, "execution_id": entry.execution_id, "execution_address": entry.execution_address, "transition": entry.transition, "state": entry.state, "decision": entry.decision, "accepted": entry.accepted, "applied_count": entry.applied_count, "pending_count": entry.pending_count, "rejected_count": entry.rejected_count, "current_received_bytes": entry.current_received_bytes, "current_remaining_bytes": entry.current_remaining_bytes, "checkpointed": entry.checkpointed, "previous_execution_address": entry.previous_execution_address, "previous_entry_address": entry.previous_entry_address, "head_address": ledger.head_address, "value": value}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow(**body, row_address="pending:ledger-query-row")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow(**body, row_address=address_row(provisional))


def _all_rows(value: ledger_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> tuple[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow, ...]:
    rows: list[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow] = [_row("summary", 0, ledger=value, value=value.state)]
    for resource in RESOURCES[1:-1]:
        for ordinal, entry in enumerate(value.entries, 0):
            row_value = entry.execution_address if resource == "entries" else entry.transition if resource == "transitions" else entry.state if resource == "states" else entry.decision if resource == "decisions" else f"{entry.current_received_bytes}/{entry.current_remaining_bytes}"
            rows.append(_row(resource, ordinal, ledger=value, entry=entry, value=row_value))
    if value.entries:
        rows.append(_row("latest", 0, ledger=value, entry=value.entries[-1], value=value.entries[-1].execution_address))
    return tuple(rows)


def _matches(row: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow, *, transition: str, state: str, decision: str, text: str) -> bool:
    if transition and row.transition != transition or state and row.state != state or decision and row.decision != decision:
        return False
    return not text or text in " ".join(str(row.to_dict().get(field, "")) for field in ROW_FIELDS).casefold()


def query_ledger(value: ledger_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedger, *, query_id: str = "runtime-registry-history-diff-archive-transfer-recovery-execution-ledger-query", resources: Sequence[str] | None = None, transition: str = "", state: str = "", decision: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery:
    value = ledger_model.verify_ledger(value)
    selected = tuple(RESOURCES if resources is None else resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected) or selected != tuple(item for item in RESOURCES if item in selected):
        raise ValidationError("ledger query resources are not supported")
    if transition and transition not in ledger_model.TRANSITIONS or state and state not in ledger_model.STATES or decision and decision not in ledger_model.DECISIONS:
        raise ValidationError("ledger query filter is unsupported")
    offset = _count(offset, "ledger query offset", MAX_QUERY_ITEMS)
    limit = _count(limit, "ledger query limit", MAX_LIMIT, lower=1)
    filtered = tuple(row for row in _all_rows(value) if row.resource in selected and _matches(row, transition=transition, state=state, decision=decision, text=text.casefold()))
    page = filtered[offset:offset + limit]
    rows = tuple(_renumber(row, offset + index) for index, row in enumerate(page))
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery(query_id, VERSION, BOUNDARY, value.content_address, value.ledger_id, selected, transition, state, decision, text, offset, limit, len(filtered), len(rows), offset + len(rows) < offset + len(filtered), rows, "pending:ledger-query")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery(query_id, VERSION, BOUNDARY, value.content_address, value.ledger_id, selected, transition, state, decision, text, offset, limit, len(filtered), len(rows), offset + len(rows) < offset + len(filtered), rows, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery.from_mapping(value)


def query_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_query_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Exact archive-transfer recovery execution ledger query", "", f"- Ledger: `{value.ledger_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.total_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | execution | transition | state | decision | value |", "| ---: | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.execution_id}` | `{item.transition}` | `{item.state}` | `{item.decision}` | `{item.value}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {field: {} for field in ROW_FIELDS}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "ledger_address": {"type": "string", "pattern": "^" + ledger_model.LEDGER_PREFIX + ":"}, "ledger_id": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "transition_filter": {"type": "string"}, "state_filter": {"type": "string"}, "decision_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "max_limit": MAX_LIMIT, "features": ("bounded resource projections", "transition state and decision filters", "stable pagination", "deterministic row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQuery", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_ledger", "query_schema", "render_query_markdown", "row_schema"]
