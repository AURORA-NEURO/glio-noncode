"""Bounded query projections over D491 registry histories."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d491_ledger_diff_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = history_model.VERSION + "-query-v1"
BOUNDARY = history_model.BOUNDARY + "_query"
QUERY_PREFIX = history_model.HISTORY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "entries", "transitions", "readiness", "addresses", "bounds")
STATES = history_model.STATES
TRANSITIONS = history_model.TRANSITIONS
MAX_ROWS = history_model.MAX_ENTRIES * 8 + 64
MAX_LIMIT = 256
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "transition", "release_ready", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "history_id", "history_address", "resources", "state_filter", "transition_filter", "ready_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


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


class HistoryQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, transition: str, release_ready: bool | None, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff runtime registry history query row ordinal", MAX_ROWS, lower=1)
        self.resource = _label(resource, "ledger diff runtime registry history query resource")
        self.item_id = _label(item_id, "ledger diff runtime registry history query item ID")
        self.key = _label(key, "ledger diff runtime registry history query key")
        if state not in STATES:
            raise ValidationError("ledger diff runtime registry history query row state is unsupported")
        self.state = state
        if transition not in TRANSITIONS and transition != "":
            raise ValidationError("ledger diff runtime registry history query row transition is unsupported")
        self.transition = transition
        self.release_ready = _optional_bool(release_ready, "ledger diff runtime registry history query row readiness")
        self.value = _text(value, "ledger diff runtime registry history query row value", 32768)
        self.text = _text(text, "ledger diff runtime registry history query row text", 32768)
        self.content_address = _address(content_address, "ledger diff runtime registry history query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES:
            raise ValidationError("ledger diff runtime registry history query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry history query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry history query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryQueryRow":
        value = _mapping(value, "ledger diff runtime registry history query row")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry history query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: HistoryQueryRow) -> str:
    if not isinstance(value, HistoryQueryRow):
        raise ValidationError("ledger diff runtime registry history query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class HistoryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, history_id: str, history_address: str, resources: Sequence[str], state_filter: str, transition_filter: str, ready_filter: bool | None, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[HistoryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "ledger diff runtime registry history query ID")
        self.history_id = _label(history_id, "ledger diff runtime registry history query history ID")
        self.history_address = _address(history_address, "ledger diff runtime registry history query history address", history_model.HISTORY_PREFIX)
        self.resources = tuple(_label(item, "ledger diff runtime registry history query resource") for item in _sequence(resources, "ledger diff runtime registry history query resources", len(RESOURCES)))
        self.state_filter = _text(state_filter, "ledger diff runtime registry history query state filter", 64, required=False)
        self.transition_filter = _text(transition_filter, "ledger diff runtime registry history query transition filter", 64, required=False)
        self.ready_filter = _optional_bool(ready_filter, "ledger diff runtime registry history query readiness filter")
        self.text_filter = _text(text_filter, "ledger diff runtime registry history query text filter", 512, required=False)
        self.offset = _count(offset, "ledger diff runtime registry history query offset", MAX_ROWS)
        self.limit = _count(limit, "ledger diff runtime registry history query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "ledger diff runtime registry history query total count", MAX_ROWS)
        self.returned_count = _count(returned_count, "ledger diff runtime registry history query returned count", MAX_ROWS)
        self.truncated = _bool(truncated, "ledger diff runtime registry history query truncation")
        self.rows = tuple(item if isinstance(item, HistoryQueryRow) else HistoryQueryRow.from_mapping(_mapping(item, "ledger diff runtime registry history query row")) for item in _sequence(rows, "ledger diff runtime registry history query rows", MAX_ROWS))
        self.content_address = _address(content_address, "ledger diff runtime registry history query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources):
            raise ValidationError("ledger diff runtime registry history query resources are unsupported or duplicated")
        if (self.state_filter and self.state_filter not in STATES) or (self.transition_filter and self.transition_filter not in TRANSITIONS):
            raise ValidationError("ledger diff runtime registry history query filters are unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count or self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("ledger diff runtime registry history query counters do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)) or any(item.content_address != address_row(item) for item in self.rows):
            raise ValidationError("ledger diff runtime registry history query row order or addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry history query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry history query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryQuery":
        value = _mapping(value, "ledger diff runtime registry history query")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry history query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: HistoryQuery) -> str:
    if not isinstance(value, HistoryQuery):
        raise ValidationError("ledger diff runtime registry history query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)


def _row(ordinal: int, resource: str, key: str, value: Any, *, state: str, transition: str = "", release_ready: bool | None = None) -> HistoryQueryRow:
    rendered = canonical_json(value)
    return HistoryQueryRow(ordinal, resource, f"{resource}:{key}", key, state, transition, release_ready, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")


def _rows(value: history_model.RuntimeRegistryHistory) -> tuple[HistoryQueryRow, ...]:
    raw: list[tuple[str, str, Any, str, str, bool | None]] = []

    def add(resource: str, key: str, item: Any, state: str, transition: str = "", ready: bool | None = None) -> None:
        raw.append((resource, key, item, state, transition, ready))

    for key in ("history_id", "entry_count", "initial_count", "promoted_count", "regressed_count", "unchanged_count", "changed_count", "latest_state", "latest_release_ready", "latest_accepted", "accepted"):
        item = getattr(value, key)
        add("summary", key, item, value.latest_state, "", item if isinstance(item, bool) else None)
    for item in value.entries:
        add("entries", item.snapshot_id, item.to_dict(), item.state, item.transition, item.release_ready)
    for item in value.entries:
        add("transitions", item.snapshot_id, item.transition, item.state, item.transition, item.release_ready)
    for key, item in (("latest_state", value.latest_state), ("latest_release_ready", value.latest_release_ready), ("latest_accepted", value.latest_accepted), ("entry_count", value.entry_count), ("promoted_count", value.promoted_count), ("regressed_count", value.regressed_count)):
        add("readiness", key, item, value.latest_state, "", item if isinstance(item, bool) else None)
    for key, item in (("history_address", value.content_address), ("manifest_address", value.manifest.content_address), ("entries_address", history_model.address_entries(value.entries)), ("summary_address", value.summary.content_address)):
        add("addresses", key, item, value.latest_state)
    for key, item in (("max_entries", history_model.MAX_ENTRIES), ("max_history_bytes", history_model.MAX_HISTORY_BYTES), ("max_rows", MAX_ROWS), ("entry_count", value.entry_count)):
        add("bounds", key, item, value.latest_state)
    return tuple(_row(index, resource, key, item, state=state, transition=transition, release_ready=ready) for index, (resource, key, item, state, transition, ready) in enumerate(raw, 1))


def query_history(value: history_model.RuntimeRegistryHistory, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, state_filter: str = "", transition_filter: str = "", ready_filter: bool | None = None, text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> HistoryQuery:
    history_model.verify_history(value)
    selected = tuple(resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected):
        raise ValidationError("ledger diff runtime registry history query resources are unsupported or duplicated")
    if (state_filter and state_filter not in STATES) or (transition_filter and transition_filter not in TRANSITIONS):
        raise ValidationError("ledger diff runtime registry history query filters are unsupported")
    offset = _count(offset, "ledger diff runtime registry history query offset", MAX_ROWS)
    limit = _count(limit, "ledger diff runtime registry history query limit", MAX_LIMIT, lower=1)
    needle = text_filter.casefold()
    rows = tuple(item for item in _rows(value) if item.resource in selected and (not state_filter or item.state == state_filter) and (not transition_filter or item.transition == transition_filter) and (ready_filter is None or item.release_ready == ready_filter) and (not needle or needle in item.text.casefold()))
    page = rows[offset:offset + limit]
    typed = tuple(_seal(HistoryQueryRow(index + 1, item.resource, item.item_id, item.key, item.state, item.transition, item.release_ready, item.value, item.text, f"pending:{ROW_PREFIX}"), address_row) for index, item in enumerate(page, offset))
    return _seal(HistoryQuery(query_id, value.history_id, value.content_address, selected, state_filter, transition_filter, ready_filter, text_filter, offset, limit, len(rows), len(typed), offset + len(typed) < len(rows), typed, f"pending:{QUERY_PREFIX}"), address_query)


def query_from_mapping(value: Mapping[str, Any]) -> HistoryQuery:
    return HistoryQuery.from_mapping(value)


def verify_query(value: HistoryQuery) -> HistoryQuery:
    if not isinstance(value, HistoryQuery):
        raise ValidationError("ledger diff runtime registry history query verification requires a typed query")
    value._validate()
    return value


def query_json(value: HistoryQuery) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: HistoryQuery) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_query(value).rows)
    return output.getvalue()


def render_query_markdown(value: HistoryQuery) -> str:
    value = verify_query(value)
    lines = [f"# Ledger diff runtime registry history query {value.query_id}", "", f"- History: {value.history_id}", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Resource | Key | State | Transition | Ready | Value |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.resource} | {item.key} | {item.state} | {item.transition} | {item.release_ready} | {item.value} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "release_ready" else "string"} for field in ROW_FIELDS}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {field: {"type": "array" if field in ("resources", "rows") else "integer" if field.endswith("count") or field in ("offset", "limit") else "boolean" if field in ("ready_filter", "truncated") else "string"} for field in QUERY_FIELDS}, "$defs": {"row": row_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "transitions": TRANSITIONS, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("summary entry transition readiness address and bounds projections", "state transition readiness and text filters", "bounded pagination", "canonical row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "TRANSITIONS", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "HistoryQueryRow", "HistoryQuery", "address_row", "address_query", "query_history", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
