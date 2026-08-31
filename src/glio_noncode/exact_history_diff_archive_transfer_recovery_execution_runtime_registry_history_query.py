"""Bounded inspection queries for runtime registry histories."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-query-v1"
BOUNDARY = history_model.BOUNDARY + "_query"
QUERY_PREFIX = history_model.HISTORY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = history_model.HISTORY_PREFIX + "-query"
RESOURCES = ("summary", "snapshots", "transitions", "states", "readiness", "addresses", "bounds")
STATES = history_model.STATES
TRANSITIONS = history_model.TRANSITIONS
MAX_LIMIT = 512
MAX_TEXT = 4096
ROW_FIELDS = ("ordinal", "resource", "key", "value", "address", "state", "accepted", "transition", "row_address")
QUERY_FIELDS = ("query_id", "history_id", "history_address", "resources", "state_filter", "key_filter", "transition_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, required=True)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
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


def _public(value: Any) -> bool:
    return history_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow:
    """One addressed row in a bounded history projection."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, key: str, value: Any, address: str, state: str, accepted: bool, transition: str, row_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history query row ordinal", MAX_LIMIT, lower=1)
        if resource not in RESOURCES:
            raise ValidationError("runtime registry history query row resource is unsupported")
        self.resource = resource
        self.key = _label(key, "runtime registry history query row key")
        if len(canonical_json(value).encode("utf-8")) > 16384:
            raise ValidationError("runtime registry history query row value is too large")
        self.value = value
        self.address = _address(address, "runtime registry history query row address")
        if state not in STATES:
            raise ValidationError("runtime registry history query row state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry history query row acceptance")
        if transition and transition not in TRANSITIONS:
            raise ValidationError("runtime registry history query row transition is unsupported")
        self.transition = _label(transition, "runtime registry history query row transition", required=False)
        self.row_address = _address(row_address, "runtime registry history query row address", ROW_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history query row crosses the public boundary")
        if not self.row_address.startswith("pending:") and not self.row_address.endswith(":pending") and address_row(self) != self.row_address:
            raise ValidationError("runtime registry history query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow:
        value = _mapping(value, "runtime registry history query row")
        _strict(value, set(cls.FIELDS), "runtime registry history query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow):
        raise ValidationError("runtime registry history query row address requires a typed row")
    return content_hash(value.to_dict() | {"row_address": None}, prefix=ROW_PREFIX)


def _row(resource: str, key: str, value: Any, address: str, state: str, accepted: bool, transition: str, ordinal: int) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "key": key, "value": value, "address": address, "state": state, "accepted": accepted, "transition": transition, "row_address": ROW_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow(**(body | {"row_address": address_row(provisional)}))


def _all_rows(value: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory) -> tuple[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow, ...]:
    value = history_model.verify_history(value)
    rows: list[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow] = []
    for field in history_model.SUMMARY_FIELDS:
        rows.append(_row("summary", field, getattr(value.summary, field), value.summary.content_address, value.state, value.accepted, "", len(rows) + 1))
    for item in value.entries:
        rows.append(_row("snapshots", str(item.ordinal), item.to_dict(), item.content_address, item.state, item.accepted, item.transition, len(rows) + 1))
    for transition in TRANSITIONS:
        rows.append(_row("transitions", transition, {"transition": transition, "count": sum(item.transition == transition for item in value.entries)}, value.summary.content_address, value.state, value.accepted, transition, len(rows) + 1))
    for state in STATES:
        rows.append(_row("states", state, {"state": state, "count": sum(item.state == state for item in value.entries)}, value.summary.content_address, state, state != "blocked", "", len(rows) + 1))
    for key, count in (("entry_count", value.entry_count), ("latest_entry_count", value.latest_entry_count), ("latest_accepted_count", value.latest_accepted_count), ("latest_ready_count", value.latest_ready_count), ("latest_blocked_count", value.latest_blocked_count)):
        rows.append(_row("readiness", key, {"key": key, "count": count}, value.summary.content_address, value.state, value.accepted, "", len(rows) + 1))
    addresses = (("history", value.content_address), ("manifest", value.manifest.content_address), ("entries", value.manifest.artifact_addresses[0]), ("summary", value.summary.content_address), ("latest", value.latest_registry_address))
    for key, address in addresses:
        rows.append(_row("addresses", key, {"address": address}, address or value.summary.content_address, value.state, value.accepted, "", len(rows) + 1))
    for key, bound in (("entry_count", value.entry_count), ("max_entries", history_model.MAX_ENTRIES), ("file_count", len(history_model.FILES)), ("files", list(history_model.FILES))):
        rows.append(_row("bounds", key, bound, value.manifest.content_address, value.state, value.accepted, "", len(rows) + 1))
    return tuple(rows)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery:
    """Deterministic, filterable, paginated history inspection result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, history_id: str, history_address: str, resources: Sequence[str], state_filter: str, key_filter: str, transition_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "runtime registry history query ID")
        self.history_id = _label(history_id, "runtime registry history query history ID")
        self.history_address = _address(history_address, "runtime registry history query history address", history_model.HISTORY_PREFIX)
        self.resources = tuple(_label(item, "runtime registry history query resource") for item in _sequence(resources, "runtime registry history query resources", len(RESOURCES)))
        if len(self.resources) != len(set(self.resources)) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(item for item in RESOURCES if item in self.resources):
            raise ValidationError("runtime registry history query resources are unsupported, duplicated, or unordered")
        self.state_filter = _text(state_filter, "runtime registry history query state filter")
        if self.state_filter not in ("",) + STATES:
            raise ValidationError("runtime registry history query state filter is unsupported")
        self.key_filter = _text(key_filter, "runtime registry history query key filter", 512)
        self.transition_filter = _text(transition_filter, "runtime registry history query transition filter")
        if self.transition_filter not in ("",) + TRANSITIONS:
            raise ValidationError("runtime registry history query transition filter is unsupported")
        self.text_filter = _text(text_filter, "runtime registry history query text filter")
        self.offset = _count(offset, "runtime registry history query offset", 1_000_000)
        self.limit = _count(limit, "runtime registry history query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "runtime registry history query total count", 1_000_000)
        self.returned_count = _count(returned_count, "runtime registry history query returned count", MAX_LIMIT)
        self.truncated = _bool(truncated, "runtime registry history query truncation")
        self.rows = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow.from_mapping(item) for item in _sequence(rows, "runtime registry history query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "runtime registry history query address", QUERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.returned_count or self.returned_count != len(self.rows) or self.truncated != (self.offset + self.returned_count < self.offset + self.total_count) or tuple(item.ordinal for item in self.rows) != tuple(range(1, len(self.rows) + 1)):
            raise ValidationError("runtime registry history query counts or ordinals do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history query crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("runtime registry history query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "history_id": self.history_id,
            "history_address": self.history_address,
            "resources": self.resources,
            "state_filter": self.state_filter,
            "key_filter": self.key_filter,
            "transition_filter": self.transition_filter,
            "text_filter": self.text_filter,
            "offset": self.offset,
            "limit": self.limit,
            "total_count": self.total_count,
            "returned_count": self.returned_count,
            "truncated": self.truncated,
            "rows": [item.to_dict() for item in self.rows],
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery:
        value = _mapping(value, "runtime registry history query")
        _strict(value, set(cls.FIELDS), "runtime registry history query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery):
        raise ValidationError("runtime registry history query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def query_history(value: history_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistory, *, resources: Sequence[str] | None = None, state: str = "", key: str = "", transition: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT, query_id: str = DEFAULT_QUERY_ID) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery:
    value = history_model.verify_history(value)
    selected_resources = tuple(resources if resources is not None else RESOURCES)
    if len(selected_resources) != len(set(selected_resources)) or any(item not in RESOURCES for item in selected_resources) or selected_resources != tuple(item for item in RESOURCES if item in selected_resources):
        raise ValidationError("runtime registry history query resources are unsupported, duplicated, or unordered")
    if state not in ("",) + STATES or transition not in ("",) + TRANSITIONS:
        raise ValidationError("runtime registry history query filter is unsupported")
    key = _text(key, "runtime registry history query key filter", 512)
    text = _text(text, "runtime registry history query text filter")
    offset = _count(offset, "runtime registry history query offset", 1_000_000)
    limit = _count(limit, "runtime registry history query limit", MAX_LIMIT, lower=1)
    selected = []
    for row in _all_rows(value):
        if row.resource not in selected_resources or (state and row.state != state) or (key and row.key != key) or (transition and row.transition != transition):
            continue
        if text and text.casefold() not in canonical_json(row.to_dict()).casefold():
            continue
        selected.append(row)
    total_count = len(selected)
    page = selected[offset:offset + limit]
    rows = tuple(_row(row.resource, row.key, row.value, row.address, row.state, row.accepted, row.transition, ordinal) for ordinal, row in enumerate(page, 1))
    body = {"query_id": query_id, "history_id": value.history_id, "history_address": value.content_address, "resources": selected_resources, "state_filter": state, "key_filter": key, "transition_filter": transition, "text_filter": text, "offset": offset, "limit": limit, "total_count": total_count, "returned_count": len(rows), "truncated": offset + len(rows) < total_count, "rows": rows, "content_address": QUERY_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery.from_mapping(value)


def query_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for row in value.rows:
        writer.writerow((row.ordinal, row.resource, row.key, json.dumps(row.value, ensure_ascii=False, sort_keys=True), row.address, row.state, row.accepted, row.transition, row.row_address))
    return output.getvalue()


def render_query_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# History-Diff Archive Transfer Recovery Execution Runtime Registry History query", "", f"History: {value.history_id}", f"Resources: {', '.join(value.resources)}", f"Rows: {value.returned_count}/{value.total_count}", f"Address: {value.content_address}", "", "| # | resource | key | state | accepted | transition |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | {row.resource} | {row.key} | {row.state} | {row.accepted} | {row.transition} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "key": {"type": "string"}, "value": {}, "address": {"type": "string"}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "transition": {"enum": ["", *TRANSITIONS]}, "row_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "history_id": {"type": "string"}, "history_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "state_filter": {"enum": ["", *STATES]}, "key_filter": {"type": "string"}, "transition_filter": {"enum": ["", *TRANSITIONS]}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": RESOURCES, "states": STATES, "transitions": TRANSITIONS, "max_limit": MAX_LIMIT, "features": ("summary snapshot transition state readiness address and bounds resources", "state key transition and text filters", "deterministic pagination", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "TRANSITIONS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQueryRow", "ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryQuery", "address_row", "address_query", "query_history", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
