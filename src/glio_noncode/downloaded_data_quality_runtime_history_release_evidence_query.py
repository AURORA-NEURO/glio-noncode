"""Bounded query projections over a downloaded-data quality release evidence package."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_runtime_history_release_evidence as evidence_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = evidence_model.VERSION + "-query-v1"
BOUNDARY = evidence_model.BOUNDARY + "_query"
QUERY_PREFIX = evidence_model.EVIDENCE_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "gate", "gate_audit", "query", "query_audit", "manifest", "addresses", "readiness", "counters", "files")
STATES = evidence_model.STATES
SEVERITIES = ("info", "error")
MAX_ROWS = 128
MAX_LIMIT = 128
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "passed", "severity", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "evidence_id", "gate_id", "history_id", "resources", "state_filter", "passed_filter", "severity_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


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

    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, passed: bool | None, severity: str, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "evidence query row ordinal", MAX_ROWS, lower=1)
        self.resource = _label(resource, "evidence query row resource")
        self.item_id = _label(item_id, "evidence query row item ID")
        self.key = _label(key, "evidence query row key")
        if state not in STATES:
            raise ValidationError("evidence query row state is unsupported")
        self.state = state
        self.passed = _optional_bool(passed, "evidence query row passed")
        if severity not in SEVERITIES:
            raise ValidationError("evidence query row severity is unsupported")
        self.severity = severity
        self.value = _text(value, "evidence query row value", 4096)
        self.text = _text(text, "evidence query row text", 8192)
        self.content_address = _address(content_address, "evidence query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES:
            raise ValidationError("evidence query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address:
            raise ValidationError("evidence query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryRow":
        value = _mapping(value, "evidence query row")
        _strict(value, set(cls.FIELDS), "evidence query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: QueryRow) -> str:
    if not isinstance(value, QueryRow):
        raise ValidationError("evidence query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class EvidenceQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, query_id: str, evidence_id: str, gate_id: str, history_id: str, resources: Sequence[str], state_filter: str, passed_filter: bool | None, severity_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[QueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "evidence query ID")
        self.evidence_id = _label(evidence_id, "evidence query evidence ID")
        self.gate_id = _label(gate_id, "evidence query gate ID")
        self.history_id = _label(history_id, "evidence query history ID")
        self.resources = tuple(_label(item, "evidence query resource") for item in _sequence(resources, "evidence query resources", len(RESOURCES)))
        self.state_filter = _text(state_filter, "evidence query state filter", 64, required=False)
        self.passed_filter = _optional_bool(passed_filter, "evidence query passed filter")
        self.severity_filter = _text(severity_filter, "evidence query severity filter", 64, required=False)
        self.text_filter = _text(text_filter, "evidence query text filter", 512, required=False)
        self.offset = _count(offset, "evidence query offset", MAX_ROWS)
        self.limit = _count(limit, "evidence query limit", MAX_LIMIT, lower=1)
        self.total_count = _count(total_count, "evidence query total count", MAX_ROWS)
        self.returned_count = _count(returned_count, "evidence query returned count", MAX_ROWS)
        self.truncated = _bool(truncated, "evidence query truncation")
        self.rows = tuple(item if isinstance(item, QueryRow) else QueryRow.from_mapping(_mapping(item, "evidence query row")) for item in _sequence(rows, "evidence query rows", MAX_ROWS))
        self.content_address = _address(content_address, "evidence query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources):
            raise ValidationError("evidence query resources are unsupported or duplicated")
        if self.state_filter and self.state_filter not in STATES or self.severity_filter and self.severity_filter not in SEVERITIES:
            raise ValidationError("evidence query filters are unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count:
            raise ValidationError("evidence query counters do not replay")
        if self.truncated != (self.offset + self.returned_count < self.total_count):
            raise ValidationError("evidence query truncation does not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("evidence query row ordinals do not replay")
        if any(item.content_address != address_row(item) for item in self.rows):
            raise ValidationError("evidence query row addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address:
            raise ValidationError("evidence query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceQuery":
        value = _mapping(value, "evidence query")
        _strict(value, set(cls.FIELDS), "evidence query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: EvidenceQuery) -> str:
    if not isinstance(value, EvidenceQuery):
        raise ValidationError("evidence query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)


def _row(ordinal: int, resource: str, key: str, value: Any, state: str, passed: bool | None = None) -> QueryRow:
    rendered = canonical_json(value)
    return QueryRow(ordinal, resource, f"{resource}:{key}", key, state, passed, "info", rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")


def _rows(value: evidence_model.ReleaseEvidence) -> tuple[QueryRow, ...]:
    state = value.gate.state
    raw: list[tuple[str, str, Any, bool | None]] = []
    def add(resource: str, key: str, item: Any, passed: bool | None = None) -> None:
        raw.append((resource, key, item, passed))
    add("summary", "gate_state", value.summary.gate_state)
    add("summary", "release_ready", value.summary.release_ready, value.summary.release_ready)
    add("summary", "gate_audit_accepted", value.summary.gate_audit_accepted, value.summary.gate_audit_accepted)
    add("summary", "query_audit_accepted", value.summary.query_audit_accepted, value.summary.query_audit_accepted)
    add("summary", "query_complete", value.summary.query_complete, value.summary.query_complete)
    add("summary", "evidence_ready", value.summary.evidence_ready, value.summary.evidence_ready)
    for key in ("gate_id", "history_id", "state", "release_ready", "check_count", "passed_count", "failed_count"):
        item = getattr(value.gate, key)
        add("gate", key, item, item if isinstance(item, bool) else None)
    for key in ("accepted", "check_count", "passed_count", "failed_count"):
        item = getattr(value.gate_audit, key)
        add("gate_audit", key, item, item if isinstance(item, bool) else None)
    for key in ("query_id", "total_count", "returned_count", "truncated", "offset", "limit"):
        item = getattr(value.query, key)
        add("query", key, item, item if isinstance(item, bool) else None)
    for key in ("accepted", "check_count", "passed_count", "failed_count"):
        item = getattr(value.query_audit, key)
        add("query_audit", key, item, item if isinstance(item, bool) else None)
    add("manifest", "version", value.manifest.version)
    add("manifest", "boundary", value.manifest.boundary)
    add("manifest", "files", value.manifest.files)
    add("manifest", "artifact_addresses", value.manifest.artifact_addresses)
    for key, item in (("evidence", value.content_address), ("gate", value.gate_address), ("gate_audit", value.gate_audit_address), ("query", value.query_address), ("query_audit", value.query_audit_address), ("manifest", value.manifest.content_address), ("summary", value.summary.content_address)):
        add("addresses", key, item)
    for key in ("gate_state", "release_ready", "gate_audit_accepted", "query_complete", "evidence_ready"):
        item = getattr(value.summary, key)
        add("readiness", key, item, item if isinstance(item, bool) else None)
    for key in ("check_count", "passed_count", "row_count", "total_row_count", "resource_count"):
        item = getattr(value.summary, key)
        add("counters", key, item)
    for item in evidence_model.FILES:
        add("files", item, True, True)
    rows = tuple(_row(index, resource, key, item, state, passed) for index, (resource, key, item, passed) in enumerate(raw, 1))
    return tuple(_seal(item, address_row) for item in rows)


def query_evidence(value: evidence_model.ReleaseEvidence, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] | None = None, state_filter: str = "", passed_filter: bool | None = None, severity_filter: str = "", text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> EvidenceQuery:
    evidence_model.verify_evidence(value)
    selected = tuple(resources or RESOURCES)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected):
        raise ValidationError("evidence query resources are unsupported or duplicated")
    if state_filter and state_filter not in STATES or severity_filter and severity_filter not in SEVERITIES:
        raise ValidationError("evidence query filters are unsupported")
    offset = _count(offset, "evidence query offset", MAX_ROWS)
    limit = _count(limit, "evidence query limit", MAX_LIMIT, lower=1)
    text_filter = _text(text_filter, "evidence query text filter", 512, required=False)
    rows = tuple(item for item in _rows(value) if item.resource in selected and (not state_filter or item.state == state_filter) and (passed_filter is None or item.passed == passed_filter) and (not severity_filter or item.severity == severity_filter) and (not text_filter or text_filter.casefold() in item.text.casefold()))
    page = rows[offset:offset + limit]
    page = tuple(QueryRow(index + 1, item.resource, item.item_id, item.key, item.state, item.passed, item.severity, item.value, item.text, f"pending:{ROW_PREFIX}") for index, item in enumerate(page, offset))
    page = tuple(_seal(item, address_row) for item in page)
    return _seal(EvidenceQuery(query_id, value.evidence_id, value.gate_id, value.history_id, selected, state_filter, passed_filter, severity_filter, text_filter, offset, limit, len(rows), len(page), offset + len(page) < len(rows), page, f"pending:{QUERY_PREFIX}"), address_query)


def query_from_mapping(value: Mapping[str, Any]) -> EvidenceQuery:
    return EvidenceQuery.from_mapping(value)


def query_json(value: EvidenceQuery) -> str:
    return canonical_json(value.to_dict())


def query_csv(value: EvidenceQuery) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in query_from_mapping(value.to_dict()).rows)
    return output.getvalue()


def render_query_markdown(value: EvidenceQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = [f"# Downloaded-data quality release evidence query {value.query_id}", "", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Resource | Key | State | Passed | Value |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.resource} | {item.key} | {item.state} | {item.passed} | {item.value} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer"}, "resource": {"type": "string", "enum": list(RESOURCES)}, "item_id": {"type": "string"}, "key": {"type": "string"}, "state": {"type": "string", "enum": list(STATES)}, "passed": {"type": ["boolean", "null"]}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "value": {"type": "string"}, "text": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"query_id": {"type": "string"}, "evidence_id": {"type": "string"}, "gate_id": {"type": "string"}, "history_id": {"type": "string"}, "resources": {"type": "array"}, "state_filter": {"type": "string"}, "passed_filter": {"type": ["boolean", "null"]}, "severity_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}, "total_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "truncated": {"type": "boolean"}, "rows": {"type": "array"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "severities": SEVERITIES, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("evidence summary and artifact resources", "state passed severity and text filters", "deterministic pagination", "canonical JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "SEVERITIES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "QueryRow", "EvidenceQuery", "address_row", "address_query", "query_evidence", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
