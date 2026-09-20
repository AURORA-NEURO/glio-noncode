"""Bounded query projections over release-evidence histories."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_runtime_history_release_evidence_history as history_model
from . import downloaded_data_quality_runtime_history_release_evidence as evidence_model
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
MAX_ROWS = 128
MAX_LIMIT = 128
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "transition", "evidence_ready", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "history_id", "gate_id", "source_history_id", "resources", "state_filter", "transition_filter", "readiness_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


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
    return evidence_model.gate_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class QueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, transition: str, evidence_ready: bool | None, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "evidence history query row ordinal", MAX_ROWS, lower=1)
        self.resource = _label(resource, "evidence history query resource")
        self.item_id = _label(item_id, "evidence history query item ID")
        self.key = _label(key, "evidence history query key")
        if state not in STATES:
            raise ValidationError("evidence history query row state is unsupported")
        self.state = state
        if transition not in TRANSITIONS and transition != "":
            raise ValidationError("evidence history query row transition is unsupported")
        self.transition = transition
        self.evidence_ready = _optional_bool(evidence_ready, "evidence history query row readiness")
        self.value = _text(value, "evidence history query row value", 8192)
        self.text = _text(text, "evidence history query row text", 8192)
        self.content_address = _address(content_address, "evidence history query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES:
            raise ValidationError("evidence history query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address:
            raise ValidationError("evidence history query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence history query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryRow":
        value = _mapping(value, "evidence history query row")
        _strict(value, set(cls.FIELDS), "evidence history query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: QueryRow) -> str:
    if not isinstance(value, QueryRow):
        raise ValidationError("evidence history query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class HistoryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, history_id: str, gate_id: str, source_history_id: str, resources: Sequence[str], state_filter: str, transition_filter: str, readiness_filter: bool | None, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[QueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "evidence history query ID")
        self.history_id = _label(history_id, "evidence history query history ID")
        self.gate_id = _label(gate_id, "evidence history query gate ID")
        self.source_history_id = _label(source_history_id, "evidence history query source history ID")
        self.resources = tuple(_label(item, "evidence history query resource") for item in _sequence(resources, "evidence history query resources", len(RESOURCES)))
        self.state_filter = _text(state_filter, "evidence history query state filter", 64, required=False)
        self.transition_filter = _text(transition_filter, "evidence history query transition filter", 64, required=False)
        self.readiness_filter = _optional_bool(readiness_filter, "evidence history query readiness filter")
        self.text_filter = _text(text_filter, "evidence history query text filter", 512, required=False)
        self.offset = _count(offset, "evidence history query offset", MAX_ROWS)
        self.limit = _count(limit, "evidence history query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "evidence history query total count", MAX_ROWS)
        self.returned_count = _count(returned_count, "evidence history query returned count", MAX_ROWS)
        self.truncated = _bool(truncated, "evidence history query truncation")
        self.rows = tuple(item if isinstance(item, QueryRow) else QueryRow.from_mapping(_mapping(item, "evidence history query row")) for item in _sequence(rows, "evidence history query rows", MAX_ROWS))
        self.content_address = _address(content_address, "evidence history query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources):
            raise ValidationError("evidence history query resources are unsupported or duplicated")
        if self.state_filter and self.state_filter not in STATES or self.transition_filter and self.transition_filter not in TRANSITIONS:
            raise ValidationError("evidence history query filters are unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count:
            raise ValidationError("evidence history query counters do not replay")
        if self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("evidence history query truncation does not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("evidence history query row ordinals do not replay")
        if any(item.content_address != address_row(item) for item in self.rows):
            raise ValidationError("evidence history query row addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address:
            raise ValidationError("evidence history query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence history query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryQuery":
        value = _mapping(value, "evidence history query")
        _strict(value, set(cls.FIELDS), "evidence history query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: HistoryQuery) -> str:
    if not isinstance(value, HistoryQuery):
        raise ValidationError("evidence history query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)


def _row(ordinal: int, resource: str, key: str, value: Any, state: str, transition: str = "", evidence_ready: bool | None = None) -> QueryRow:
    rendered = canonical_json(value)
    return QueryRow(ordinal, resource, f"{resource}:{key}", key, state, transition, evidence_ready, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")


def _rows(value: history_model.EvidenceHistory) -> tuple[QueryRow, ...]:
    state = value.latest_state
    raw: list[tuple[str, str, Any, str, bool | None]] = []
    def add(resource: str, key: str, item: Any, transition: str = "", evidence_ready: bool | None = None) -> None:
        raw.append((resource, key, item, transition, evidence_ready))
    for key in ("entry_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "latest_state", "latest_ready", "accepted"):
        item = getattr(value.summary, key)
        add("summary", key, item, evidence_ready=item if isinstance(item, bool) else None)
    for item in value.entries:
        add("entries", item.snapshot_id, {"ordinal": item.ordinal, "evidence_id": item.evidence_id, "evidence_address": item.evidence_address, "transition": item.transition, "state": item.state, "evidence_ready": item.evidence_ready, "check_count": item.check_count, "passed_count": item.passed_count, "row_count": item.row_count, "total_row_count": item.total_row_count}, item.transition, item.evidence_ready)
    for transition in TRANSITIONS:
        add("transitions", transition, sum(item.transition == transition for item in value.entries), transition)
    for current_state in STATES:
        add("state", current_state, sum(item.state == current_state for item in value.entries))
    for key, item in (("latest_state", value.latest_state), ("latest_ready", value.latest_ready)):
        add("readiness", key, item, evidence_ready=item if isinstance(item, bool) else None)
    for key, item in (("history", value.content_address), ("manifest", value.manifest.content_address), ("summary", value.summary.content_address), ("entries", history_model.address_entries(value.entries)), ("head", value.entries[-1].content_address)):
        add("addresses", key, item)
    for key, item in (("max_entries", history_model.MAX_ENTRIES), ("entry_count", value.entry_count), ("query_max_rows", MAX_ROWS)):
        add("bounds", key, item)
    rows = tuple(_row(index, resource, key, item, state, transition, ready) for index, (resource, key, item, transition, ready) in enumerate(raw, 1))
    if len(rows) > MAX_ROWS:
        raise ValidationError("evidence history query projection exceeds its row bound")
    return tuple(_seal(item, address_row) for item in rows)


def query_history(value: history_model.EvidenceHistory, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] | None = None, state_filter: str = "", transition_filter: str = "", readiness_filter: bool | None = None, text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> HistoryQuery:
    history_model.verify_history(value)
    selected = tuple(resources or RESOURCES)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected):
        raise ValidationError("evidence history query resources are unsupported or duplicated")
    if state_filter and state_filter not in STATES or transition_filter and transition_filter not in TRANSITIONS:
        raise ValidationError("evidence history query filters are unsupported")
    offset = _count(offset, "evidence history query offset", MAX_ROWS)
    limit = _count(limit, "evidence history query limit", MAX_LIMIT, lower=1)
    text_filter = _text(text_filter, "evidence history query text filter", 512, required=False)
    rows = tuple(item for item in _rows(value) if item.resource in selected and (not state_filter or item.state == state_filter) and (not transition_filter or item.transition == transition_filter) and (readiness_filter is None or item.evidence_ready == readiness_filter) and (not text_filter or text_filter.casefold() in item.text.casefold()))
    page = rows[offset:offset + limit]
    page = tuple(QueryRow(index + 1, item.resource, item.item_id, item.key, item.state, item.transition, item.evidence_ready, item.value, item.text, f"pending:{ROW_PREFIX}") for index, item in enumerate(page, offset))
    page = tuple(_seal(item, address_row) for item in page)
    return _seal(HistoryQuery(query_id, value.history_id, value.gate_id, value.source_history_id, selected, state_filter, transition_filter, readiness_filter, text_filter, offset, limit, len(rows), len(page), offset + len(page) < len(rows), page, f"pending:{QUERY_PREFIX}"), address_query)


def query_from_mapping(value: Mapping[str, Any]) -> HistoryQuery:
    return HistoryQuery.from_mapping(value)


def query_json(value: HistoryQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: HistoryQuery) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in query_from_mapping(value.to_dict()).rows)
    return output.getvalue()


def render_query_markdown(value: HistoryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = [f"# Downloaded-data quality release-evidence history query {value.query_id}", "", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Resource | Key | State | Transition | Ready | Value |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.resource} | {item.key} | {item.state} | {item.transition} | {item.evidence_ready} | {item.value} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceHistoryQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer"}, "resource": {"type": "string", "enum": list(RESOURCES)}, "item_id": {"type": "string"}, "key": {"type": "string"}, "state": {"type": "string", "enum": list(STATES)}, "transition": {"type": "string", "enum": list(TRANSITIONS) + [""]}, "evidence_ready": {"type": ["boolean", "null"]}, "value": {"type": "string"}, "text": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {field: {"type": "array" if field in ("resources", "rows") else "integer" if field in ("offset", "limit", "total_count", "returned_count") else "boolean" if field == "truncated" else "string"} for field in QUERY_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "transitions": TRANSITIONS, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("summary entry transition state readiness address and bounds resources", "state transition readiness and text filters", "deterministic pagination", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "TRANSITIONS", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "QueryRow", "HistoryQuery", "address_row", "address_query", "query_history", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
