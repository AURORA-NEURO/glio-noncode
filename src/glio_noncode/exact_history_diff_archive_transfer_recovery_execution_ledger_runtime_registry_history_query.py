"""Bounded path-free queries over exact runtime-registry histories."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = history_model.VERSION + "-query-v1"
BOUNDARY = history_model.BOUNDARY + "_query"
QUERY_PREFIX = history_model.HISTORY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = "ledger-runtime-registry-history-query"
MAX_LIMIT = 256
MAX_QUERY_ITEMS = history_model.MAX_ENTRIES * 6 + 64
RESOURCES = ("summary", "snapshots", "transitions", "states", "readiness", "addresses", "bounds", "latest")
ROW_FIELDS = ("ordinal", "resource", "key", "value", "address", "state", "accepted", "transition", "row_address")
QUERY_FIELDS = ("query_id", "version", "boundary", "history_address", "history_id", "resources", "state_filter", "key_filter", "transition_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong public address namespace")
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


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow:
    """One stable row in a bounded history query."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, key: str, value: Any, address: str, state: str, accepted: bool, transition: str, row_address: str) -> None:
        if resource not in RESOURCES:
            raise ValidationError("ledger runtime registry history query row resource is unsupported")
        self.ordinal = _count(ordinal, "ledger runtime registry history query row ordinal", MAX_QUERY_ITEMS)
        self.resource = resource
        self.key = _text(key, "ledger runtime registry history query row key", 512, required=True)
        self.value = value
        self.address = _address(address, "ledger runtime registry history query row address")
        self.state = _text(state, "ledger runtime registry history query row state", 128, required=True)
        self.accepted = _bool(accepted, "ledger runtime registry history query row acceptance")
        self.transition = _text(transition, "ledger runtime registry history query row transition", 128, required=True)
        self.row_address = _address(row_address, "ledger runtime registry history query row content address", ROW_PREFIX, allow_pending=True)
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("ledger runtime registry history query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow":
        value = _mapping(value, "ledger runtime registry history query row")
        _strict(value, set(cls.FIELDS), "ledger runtime registry history query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow):
        raise ValidationError("ledger runtime registry history query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery:
    """A deterministic, bounded, value-free history query result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, version: str, boundary: str, history_address: str, history_id: str, resources: Sequence[str], state_filter: str, key_filter: str, transition_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "ledger runtime registry history query ID")
        self.version = _text(version, "ledger runtime registry history query version", 2048)
        self.boundary = _text(boundary, "ledger runtime registry history query boundary", 1024)
        self.history_address = _address(history_address, "ledger runtime registry history query history address", history_model.HISTORY_PREFIX)
        self.history_id = _label(history_id, "ledger runtime registry history query history ID")
        self.resources = tuple(resources)
        if not self.resources or tuple(item for item in RESOURCES if item in self.resources) != self.resources or any(item not in RESOURCES for item in self.resources):
            raise ValidationError("ledger runtime registry history query resources are not canonical")
        self.state_filter = _text(state_filter, "ledger runtime registry history query state filter", 128)
        self.key_filter = _text(key_filter, "ledger runtime registry history query key filter", 512)
        self.transition_filter = _text(transition_filter, "ledger runtime registry history query transition filter", 128)
        self.text_filter = _text(text_filter, "ledger runtime registry history query text filter", 4096)
        self.offset = _count(offset, "ledger runtime registry history query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "ledger runtime registry history query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "ledger runtime registry history query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "ledger runtime registry history query returned count", MAX_LIMIT)
        self.truncated = _bool(truncated, "ledger runtime registry history query truncation")
        self.rows = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow.from_mapping(item) for item in _sequence(rows, "ledger runtime registry history query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "ledger runtime registry history query address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger runtime registry history query version or boundary is not current")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or tuple(item.ordinal for item in self.rows) != tuple(range(self.returned_count)):
            raise ValidationError("ledger runtime registry history query page does not replay")
        if self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("ledger runtime registry history query truncation does not replay")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("ledger runtime registry history query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "version": self.version, "boundary": self.boundary, "history_address": self.history_address, "history_id": self.history_id, "resources": self.resources, "state_filter": self.state_filter, "key_filter": self.key_filter, "transition_filter": self.transition_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "returned_count": self.returned_count, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery":
        value = _mapping(value, "ledger runtime registry history query")
        _strict(value, set(cls.FIELDS), "ledger runtime registry history query")
        return cls(value["query_id"], value["version"], value["boundary"], value["history_address"], value["history_id"], tuple(_sequence(value["resources"], "ledger runtime registry history query resources", len(RESOURCES))), value["state_filter"], value["key_filter"], value["transition_filter"], value["text_filter"], value["offset"], value["limit"], value["total_count"], value["returned_count"], value["truncated"], tuple(value["rows"]), value["content_address"])


def address_query(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery):
        raise ValidationError("ledger runtime registry history query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, key: str, value: Any, address: str, state: str, accepted: bool, transition: str) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow:
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow(ordinal, resource, key, value, address, state, accepted, transition, "pending:ledger-runtime-registry-history-query-row")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow(ordinal, resource, key, value, address, state, accepted, transition, address_row(provisional))


def _all_rows(value: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory) -> tuple[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow, ...]:
    rows: list[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow] = []
    summary = value.to_dict()
    summary_fields = ("history_id", "registry_id", "version", "boundary", "entry_count", "latest_registry_address", "latest_entry_count", "latest_accepted_count", "latest_ready_count", "latest_blocked_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "state", "accepted", "content_address")
    for field in summary_fields:
        rows.append(_row("summary", len(rows), field, summary[field], value.content_address, value.state, value.accepted, "summary"))
    for item in value.entries:
        rows.append(_row("snapshots", len(rows), str(item.ordinal), item.to_dict(), item.registry_address, item.state, item.accepted, item.transition))
    for transition in history_model.TRANSITIONS:
        rows.append(_row("transitions", len(rows), transition, sum(item.transition == transition for item in value.entries), value.summary.content_address, value.state, value.accepted, transition))
    for key, item in (("empty", value.state == "empty"), ("ready", value.state == "ready"), ("blocked", value.state == "blocked")):
        rows.append(_row("states", len(rows), key, item, value.summary.content_address, value.state, value.accepted, "state"))
    for key, item in (("accepted", value.accepted), ("latest-accepted", value.entries[-1].accepted if value.entries else False), ("ready-count", value.latest_ready_count), ("blocked-count", value.latest_blocked_count)):
        rows.append(_row("readiness", len(rows), key, item, value.summary.content_address, value.state, value.accepted, "readiness"))
    for key, item in (("history", value.content_address), ("entries", value.entries and value.entries[-1].content_address or value.content_address), ("summary", value.summary.content_address), ("manifest", value.manifest.manifest_address)):
        rows.append(_row("addresses", len(rows), key, item, value.content_address, value.state, value.accepted, "address"))
    for key, item in (("entry-count", value.entry_count), ("max-entries", history_model.MAX_ENTRIES), ("artifact-count", len(history_model.ARTIFACT_FILES))):
        rows.append(_row("bounds", len(rows), key, item, value.summary.content_address, value.state, value.accepted, "bounds"))
    latest = value.entries[-1] if value.entries else None
    for key, item in (("ordinal", latest.ordinal if latest else 0), ("registry-address", latest.registry_address if latest else ""), ("state", latest.state if latest else value.state), ("accepted", latest.accepted if latest else value.accepted), ("transition", latest.transition if latest else "")):
        rows.append(_row("latest", len(rows), key, item, latest.registry_address if latest else value.content_address, value.state, value.accepted, latest.transition if latest else "latest"))
    return tuple(rows)


def _matches(row: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow, *, state: str, key: str, transition: str, text: str) -> bool:
    if state and row.state != state:
        return False
    if key and row.key != key:
        return False
    if transition and row.transition != transition:
        return False
    if text and text.casefold() not in canonical_json(row.to_dict()).casefold():
        return False
    return True


def query_history(value: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory, *, resources: Sequence[str] | None = None, state: str = "", key: str = "", transition: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT, query_id: str = DEFAULT_QUERY_ID) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery:
    if not isinstance(value, history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistory):
        raise ValidationError("ledger runtime registry history query requires a typed history")
    value = history_model.verify_history(value)
    selected = tuple(resource for resource in RESOURCES if resources is None or resource in tuple(resources))
    if not selected:
        raise ValidationError("ledger runtime registry history query requires at least one resource")
    offset = _count(offset, "ledger runtime registry history query offset", MAX_QUERY_ITEMS)
    limit = _count(limit, "ledger runtime registry history query limit", MAX_LIMIT, lower=1)
    state = _text(state, "ledger runtime registry history query state filter", 128)
    key = _text(key, "ledger runtime registry history query key filter", 512)
    transition = _text(transition, "ledger runtime registry history query transition filter", 128)
    text = _text(text, "ledger runtime registry history query text filter", 4096)
    rows = tuple(item for item in _all_rows(value) if item.resource in selected and _matches(item, state=state, key=key, transition=transition, text=text))
    page = rows[offset:offset + limit]
    page_rows = tuple(_row(item.resource, ordinal, item.key, item.value, item.address, item.state, item.accepted, item.transition) for ordinal, item in enumerate(page))
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery(query_id, VERSION, BOUNDARY, value.content_address, value.history_id, selected, state, key, transition, text, offset, limit, len(rows), len(page_rows), offset + len(page_rows) < len(rows), page_rows, "pending:ledger-runtime-registry-history-query")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery(query_id, VERSION, BOUNDARY, value.content_address, value.history_id, selected, state, key, transition, text, offset, limit, len(rows), len(page_rows), offset + len(page_rows) < len(rows), page_rows, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery.from_mapping(value)


def query_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_query_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Exact execution ledger runtime registry history query", "", f"- History: `{value.history_id}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}/{value.total_count}`", f"- Address: `{value.content_address}`", "", "| resource | ordinal | key | state | accepted | transition | address |", "| --- | ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.resource} | {item.ordinal} | `{item.key}` | `{item.state}` | `{item.accepted}` | `{item.transition}` | `{item.address}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry history query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 0}, "resource": {"type": "string", "enum": list(RESOURCES)}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "state": {"type": "string"}, "accepted": {"type": "boolean"}, "transition": {"type": "string"}, "row_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry history query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "history_address": {"type": "string", "pattern": "^" + history_model.HISTORY_PREFIX + ":"}, "history_id": {"type": "string"}, "resources": {"type": "array", "items": {"type": "string", "enum": list(RESOURCES)}}, "state_filter": {"type": "string"}, "key_filter": {"type": "string"}, "transition_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "transitions": history_model.TRANSITIONS, "states": history_model.STATES, "max_query_items": MAX_QUERY_ITEMS, "max_limit": MAX_LIMIT, "features": ("summary snapshot transition state readiness address bounds and latest resources", "state key transition and text filters", "deterministic pagination", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["BOUNDARY", "DEFAULT_QUERY_ID", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQuery", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryQueryRow", "VERSION", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_history", "query_json", "query_schema", "render_query_markdown", "row_schema"]
