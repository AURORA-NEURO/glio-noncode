"""Bounded query projections over runtime registry histories."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d426_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-query-v1"
BOUNDARY = history_model.BOUNDARY + "_query"
QUERY_PREFIX = history_model.HISTORY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "entries", "transitions", "state", "readiness", "addresses", "bounds")
STATES = history_model.STATES
TRANSITIONS = history_model.TRANSITIONS
MAX_ROWS = history_model.MAX_ENTRIES * 8
MAX_LIMIT = 128
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "transition", "release_ready", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "history_id", "registry_id", "history_address", "resources", "state_filter", "transition_filter", "readiness_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


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
        self.ordinal = _count(ordinal, "runtime registry history query row ordinal", MAX_ROWS, lower=1)
        self.resource = _label(resource, "runtime registry history query resource")
        self.item_id = _label(item_id, "runtime registry history query item ID")
        self.key = _label(key, "runtime registry history query key")
        if state not in STATES:
            raise ValidationError("runtime registry history query row state is unsupported")
        self.state = state
        if transition not in TRANSITIONS and transition != "":
            raise ValidationError("runtime registry history query row transition is unsupported")
        self.transition = transition
        self.release_ready = _optional_bool(release_ready, "runtime registry history query row readiness")
        self.value = _text(value, "runtime registry history query row value", 16384)
        self.text = _text(text, "runtime registry history query row text", 16384)
        self.content_address = _address(content_address, "runtime registry history query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES:
            raise ValidationError("runtime registry history query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryQueryRow":
        value = _mapping(value, "runtime registry history query row")
        _strict(value, set(cls.FIELDS), "runtime registry history query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: HistoryQueryRow) -> str:
    if not isinstance(value, HistoryQueryRow):
        raise ValidationError("runtime registry history query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class HistoryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, history_id: str, registry_id: str, history_address: str, resources: Sequence[str], state_filter: str, transition_filter: str, readiness_filter: bool | None, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[HistoryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "runtime registry history query ID")
        self.history_id = _label(history_id, "runtime registry history query history ID")
        self.registry_id = _label(registry_id, "runtime registry history query registry ID")
        self.history_address = _address(history_address, "runtime registry history query history address", history_model.HISTORY_PREFIX)
        self.resources = tuple(_label(item, "runtime registry history query resource") for item in _sequence(resources, "runtime registry history query resources", len(RESOURCES)))
        self.state_filter = _text(state_filter, "runtime registry history state filter", 64, required=False)
        self.transition_filter = _text(transition_filter, "runtime registry history transition filter", 64, required=False)
        self.readiness_filter = _optional_bool(readiness_filter, "runtime registry history readiness filter")
        self.text_filter = _text(text_filter, "runtime registry history text filter", 512, required=False)
        self.offset = _count(offset, "runtime registry history query offset", MAX_ROWS)
        self.limit = _count(limit, "runtime registry history query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "runtime registry history query total count", MAX_ROWS)
        self.returned_count = _count(returned_count, "runtime registry history query returned count", MAX_ROWS)
        self.truncated = _bool(truncated, "runtime registry history query truncation")
        self.rows = tuple(item if isinstance(item, HistoryQueryRow) else HistoryQueryRow.from_mapping(_mapping(item, "runtime registry history query row")) for item in _sequence(rows, "runtime registry history query rows", MAX_ROWS))
        self.content_address = _address(content_address, "runtime registry history query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources):
            raise ValidationError("runtime registry history query resources are unsupported or duplicated")
        if self.state_filter and self.state_filter not in STATES or self.transition_filter and self.transition_filter not in TRANSITIONS:
            raise ValidationError("runtime registry history query filters are unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count:
            raise ValidationError("runtime registry history query counters do not replay")
        if self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("runtime registry history query truncation does not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("runtime registry history query row ordinals do not replay")
        if any(item.content_address != address_row(item) for item in self.rows):
            raise ValidationError("runtime registry history query row addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryQuery":
        value = _mapping(value, "runtime registry history query")
        _strict(value, set(cls.FIELDS), "runtime registry history query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: HistoryQuery) -> str:
    if not isinstance(value, HistoryQuery):
        raise ValidationError("runtime registry history query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)


def _row(ordinal: int, resource: str, key: str, value: Any, state: str, transition: str = "", release_ready: bool | None = None) -> HistoryQueryRow:
    rendered = canonical_json(value)
    return HistoryQueryRow(ordinal, resource, f"{resource}:{key}", key, state, transition, release_ready, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")


def _rows(value: history_model.RegistryHistory) -> tuple[HistoryQueryRow, ...]:
    raw: list[tuple[str, str, Any, str, str, bool | None]] = []
    def add(resource: str, key: str, item: Any, state: str, transition: str = "", readiness: bool | None = None) -> None:
        raw.append((resource, key, item, state, transition, readiness))
    for key in ("entry_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "latest_state", "latest_release_ready", "accepted"):
        item = getattr(value.summary, key)
        add("summary", key, item, value.latest_state, readiness=item if isinstance(item, bool) else None)
    for item in value.entries:
        add("entries", item.snapshot_id, {"ordinal": item.ordinal, "registry_id": item.registry_id, "registry_address": item.registry_address, "state": item.state, "release_ready": item.release_ready, "entry_count": item.entry_count, "ready_count": item.ready_count, "blocked_count": item.blocked_count, "previous_address": item.previous_address}, item.state, item.transition, item.release_ready)
    for transition in TRANSITIONS:
        add("transitions", transition, sum(item.transition == transition for item in value.entries), value.latest_state, transition)
    for key, item in (("latest_state", value.latest_state), ("accepted", value.accepted), ("entry_count", value.entry_count)):
        add("state", key, item, value.latest_state, readiness=item if isinstance(item, bool) else None)
    for key, item in (("latest_release_ready", value.latest_release_ready), ("improved_count", value.improved_count), ("regressed_count", value.regressed_count)):
        add("readiness", key, item, value.latest_state, readiness=item if isinstance(item, bool) else None)
    for key, item in (("history_address", value.content_address), ("registry_id", value.registry_id), ("entries_address", value.manifest.artifact_addresses[0]), ("summary_address", value.summary.content_address), ("manifest_address", value.manifest.content_address)):
        add("addresses", key, item, value.latest_state)
    for key, item in (("max_entries", history_model.MAX_ENTRIES), ("max_rows", MAX_ROWS), ("entry_count", value.entry_count)):
        add("bounds", key, item, value.latest_state)
    return tuple(_row(index, resource, key, item, state, transition, readiness) for index, (resource, key, item, state, transition, readiness) in enumerate(raw, 1))


def query_history(value: history_model.RegistryHistory, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, state_filter: str = "", transition_filter: str = "", readiness_filter: bool | None = None, text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> HistoryQuery:
    history_model.verify_history(value)
    selected = tuple(resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected):
        raise ValidationError("runtime registry history query resources are unsupported or duplicated")
    rows = _rows(value)
    needle = text_filter.casefold()
    filtered = tuple(item for item in rows if item.resource in selected and (not state_filter or item.state == state_filter) and (not transition_filter or item.transition == transition_filter) and (readiness_filter is None or item.release_ready == readiness_filter) and (not needle or needle in item.text.casefold()))
    offset = _count(offset, "runtime registry history query offset", MAX_ROWS)
    limit = _count(limit, "runtime registry history query limit", MAX_LIMIT, lower=1)
    page = filtered[offset:offset + limit]
    page = tuple(_seal(HistoryQueryRow(index, item.resource, item.item_id, item.key, item.state, item.transition, item.release_ready, item.value, item.text, f"pending:{ROW_PREFIX}"), address_row) for index, item in enumerate(page, offset + 1))
    return _seal(HistoryQuery(query_id, value.history_id, value.registry_id, value.content_address, selected, state_filter, transition_filter, readiness_filter, text_filter, offset, limit, len(filtered), len(page), offset + len(page) < len(filtered), page, f"pending:{QUERY_PREFIX}"), address_query)


def query_from_mapping(value: Mapping[str, Any]) -> HistoryQuery:
    return HistoryQuery.from_mapping(value)


def verify_query(value: HistoryQuery) -> HistoryQuery:
    if not isinstance(value, HistoryQuery):
        raise ValidationError("runtime registry history query verification requires a typed query")
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
    lines = [f"# Runtime registry history query {value.query_id}", "", f"- History: {value.history_id}", f"- Results: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Resource | Key | State | Transition | Ready | Value |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.resource} | {item.key} | {item.state} | {item.transition} | {item.release_ready if item.release_ready is not None else ''} | {item.value} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    properties = {field: {"type": "integer" if field == "ordinal" else "string"} for field in ROW_FIELDS}
    properties["release_ready"] = {"type": ["boolean", "null"]}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistoryQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": properties}


def query_schema() -> dict[str, Any]:
    properties = {field: {"type": "array" if field in ("resources", "rows") else "integer" if field.endswith("count") or field in ("offset", "limit") else "boolean" if field == "truncated" else "string"} for field in QUERY_FIELDS}
    properties["readiness_filter"] = {"type": ["boolean", "null"]}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RegistryHistoryQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": properties, "$defs": {"row": row_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "transitions": TRANSITIONS, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("bounded history projections", "state transition and readiness filters", "text and pagination filters", "predecessor and address visibility", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "TRANSITIONS", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "HistoryQueryRow", "HistoryQuery", "address_row", "address_query", "query_history", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
