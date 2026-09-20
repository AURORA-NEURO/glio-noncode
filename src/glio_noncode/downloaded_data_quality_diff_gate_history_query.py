"""Bounded deterministic queries over downloaded-data quality gate history."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-history-query-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_history_query"
QUERY_PREFIX = "glio-noncode-download-quality-diff-gate-history-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "entries", "promote", "hold", "block", "improved", "regressed", "unchanged", "changed", "latest")
MAX_LIMIT = 1000
MAX_TOTAL_COUNT = history_model.MAX_ENTRIES * (len(RESOURCES) - 1) + 1
ROW_FIELDS = ("ordinal", "resource", "snapshot_id", "decision", "state", "transition", "release_ready", "gate_address", "runtime_address", "policy_address", "entry_address", "content_address")
QUERY_FIELDS = ("history_address", "version", "boundary", "resources", "decision", "state", "transition", "snapshot_id", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, optional: bool = False) -> str:
    if optional and value == "":
        return ""
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
    namespace, digest = value.split(":", 1)
    if not namespace or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValidationError(f"{field} must be a canonical content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataQualityDiffGateHistoryQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, snapshot_id: str, decision: str, state: str, transition: str, release_ready: bool, gate_address: str, runtime_address: str, policy_address: str, entry_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality gate history query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "quality gate history query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("quality gate history query row resource is unsupported")
        self.snapshot_id = _text(snapshot_id, "quality gate history query row snapshot ID")
        self.decision = _label(decision, "quality gate history query row decision", required=False)
        self.state = _label(state, "quality gate history query row state", required=False)
        self.transition = _label(transition, "quality gate history query row transition", required=False)
        self.release_ready = _bool(release_ready, "quality gate history query row release readiness")
        self.gate_address = _address(gate_address, "quality gate history query row gate address", optional=True)
        self.runtime_address = _address(runtime_address, "quality gate history query row runtime address", optional=True)
        self.policy_address = _address(policy_address, "quality gate history query row policy address", optional=True)
        self.entry_address = _address(entry_address, "quality gate history query row entry address", history_model.ENTRY_PREFIX, optional=True)
        self.content_address = _address(content_address, "quality gate history query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality gate history query row address")
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and self.entry_address:
            raise ValidationError("summary history query row cannot retain an entry address")
        if self.resource != "summary" and not self.entry_address:
            raise ValidationError("history query finding row must retain an entry address")
        if not _public(self.to_dict()):
            raise ValidationError("quality gate history query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("quality gate history query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateHistoryQueryRow":
        value = _mapping(value, "quality gate history query row")
        _strict(value, set(cls.FIELDS), "quality gate history query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataQualityDiffGateHistoryQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataQualityDiffGateHistoryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, history_address: str, version: str, boundary: str, resources: Sequence[str], decision: str, state: str, transition: str, snapshot_id: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataQualityDiffGateHistoryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.history_address = _address(history_address, "quality gate history query history address", history_model.HISTORY_PREFIX)
        self.version = _text(version, "quality gate history query version")
        self.boundary = _text(boundary, "quality gate history query boundary", 512)
        self.resources = tuple(_label(item, "quality gate history query resource") for item in _sequence(resources, "quality gate history query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(sorted(self.resources, key=RESOURCES.index)):
            raise ValidationError("quality gate history query resources are unsupported, duplicated, or unordered")
        self.decision = _label(decision, "quality gate history query decision", required=False)
        self.state = _label(state, "quality gate history query state", required=False)
        self.transition = _label(transition, "quality gate history query transition", required=False)
        self.snapshot_id = _text(snapshot_id, "quality gate history query snapshot ID")
        self.text = _text(text, "quality gate history query text", 1024)
        self.offset = _count(offset, "quality gate history query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "quality gate history query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "quality gate history query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "quality gate history query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "quality gate history query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "quality gate history query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "quality gate history query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataQualityDiffGateHistoryQueryRow) else DownloadedDataQualityDiffGateHistoryQueryRow.from_mapping(item) for item in _sequence(rows, "quality gate history query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "quality gate history query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality gate history query address")
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.matched_count or self.matched_count < self.returned_count or self.returned_count != len(self.rows) or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.offset + self.matched_count) or tuple(row.ordinal for row in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("quality gate history query pagination does not replay")
        if any(row.resource not in self.resources and row.resource != "summary" for row in self.rows):
            raise ValidationError("quality gate history query row resource is outside the request")
        if self.version != VERSION or self.boundary != BOUNDARY or not _public(self.to_dict()):
            raise ValidationError("quality gate history query version, boundary, or public projection failed")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("quality gate history query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "decision": self.decision, "state": self.state, "transition": self.transition, "snapshot_id": self.snapshot_id, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(row.to_dict() for row in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateHistoryQuery":
        value = _mapping(value, "quality gate history query")
        _strict(value, set(cls.FIELDS), "quality gate history query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataQualityDiffGateHistoryQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(ordinal: int, resource: str, entry: history_model.DownloadedDataQualityDiffGateHistoryEntry | None, history: history_model.DownloadedDataQualityDiffGateHistory) -> DownloadedDataQualityDiffGateHistoryQueryRow:
    if resource == "summary":
        body = {"ordinal": ordinal, "resource": "summary", "snapshot_id": "summary", "decision": "", "state": history.state if history.state != "empty" else "", "transition": "", "release_ready": history.release_ready, "gate_address": "", "runtime_address": "", "policy_address": "", "entry_address": ""}
    else:
        if entry is None:
            raise ValidationError("history query entry row requires an entry")
        body = {"ordinal": ordinal, "resource": resource, "snapshot_id": entry.snapshot_id, "decision": entry.decision, "state": entry.state, "transition": entry.transition, "release_ready": entry.release_ready, "gate_address": entry.gate_address, "runtime_address": entry.runtime_address, "policy_address": entry.policy_address, "entry_address": entry.content_address}
    provisional = DownloadedDataQualityDiffGateHistoryQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateHistoryQueryRow(**body, content_address=address_row(provisional))


def query_history(value: history_model.DownloadedDataQualityDiffGateHistory, *, resources: Sequence[str] = RESOURCES, decision: str = "", state: str = "", transition: str = "", snapshot_id: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataQualityDiffGateHistoryQuery:
    if not isinstance(value, history_model.DownloadedDataQualityDiffGateHistory):
        raise ValidationError("quality gate history query requires a typed history")
    requested = tuple(_label(item, "quality gate history query resource") for item in resources)
    if not requested or len(set(requested)) != len(requested) or any(item not in RESOURCES for item in requested) or requested != tuple(sorted(requested, key=RESOURCES.index)):
        raise ValidationError("quality gate history query resources are unsupported, duplicated, or unordered")
    decision = _label(decision, "quality gate history query decision", required=False)
    state = _label(state, "quality gate history query state", required=False)
    transition = _label(transition, "quality gate history query transition", required=False)
    snapshot_id = _text(snapshot_id, "quality gate history query snapshot ID")
    text = _text(text, "quality gate history query text", 1024)
    offset = _count(offset, "quality gate history query offset", MAX_TOTAL_COUNT)
    limit = _count(limit, "quality gate history query limit", MAX_LIMIT, positive=True)
    if decision and decision not in ("promote", "hold", "block") or state and state not in history_model.STATES or transition and transition not in history_model.TRANSITIONS:
        raise ValidationError("quality gate history query filter is unsupported")
    candidates: list[tuple[str, history_model.DownloadedDataQualityDiffGateHistoryEntry | None]] = []
    for resource in requested:
        if resource == "summary":
            candidates.append((resource, None))
            continue
        for entry in value.entries:
            include = resource == "entries" or resource == entry.decision or resource == entry.transition or resource == "latest" and entry.ordinal == value.entry_count
            if include:
                candidates.append((resource, entry))
    filtered: list[tuple[str, history_model.DownloadedDataQualityDiffGateHistoryEntry | None]] = []
    for resource, entry in candidates:
        if entry is not None:
            if decision and entry.decision != decision or state and entry.state != state or transition and entry.transition != transition or snapshot_id and snapshot_id not in entry.snapshot_id or text and text.casefold() not in canonical_json(entry.to_dict()).casefold():
                continue
        elif decision or state or transition or snapshot_id or text:
            continue
        filtered.append((resource, entry))
    total_count = len(candidates)
    matched_count = len(filtered)
    page = filtered[offset:offset + limit]
    rows = tuple(_row(offset + ordinal, resource, entry, value) for ordinal, (resource, entry) in enumerate(page, 1))
    body = {"history_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": requested, "decision": decision, "state": state, "transition": transition, "snapshot_id": snapshot_id, "text": text, "offset": offset, "limit": limit, "total_count": total_count, "matched_count": matched_count, "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < offset + matched_count, "rows": rows}
    provisional = DownloadedDataQualityDiffGateHistoryQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateHistoryQuery(**body, content_address=address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateHistoryQuery:
    return DownloadedDataQualityDiffGateHistoryQuery.from_mapping(value)


def query_json(value: DownloadedDataQualityDiffGateHistoryQuery) -> str:
    return canonical_json(DownloadedDataQualityDiffGateHistoryQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataQualityDiffGateHistoryQuery) -> str:
    value = DownloadedDataQualityDiffGateHistoryQuery.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(row.to_dict()[field] for field in ROW_FIELDS) for row in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataQualityDiffGateHistoryQuery) -> str:
    value = DownloadedDataQualityDiffGateHistoryQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate History Query", "", f"- Resources: `{', '.join(value.resources)}`", f"- Returned: `{value.returned_count}` of `{value.matched_count}`", f"- Truncated: `{value.truncated}`", f"- Address: `{value.content_address}`", "", "| # | resource | snapshot | decision | state | transition | release ready |", "| ---: | --- | --- | --- | --- | --- | :---: |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.snapshot_id}` | `{row.decision}` | `{row.state}` | `{row.transition}` | {row.release_ready} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate history query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "snapshot_id": {"type": "string"}, "decision": {"type": "string"}, "state": {"type": "string"}, "transition": {"type": "string"}, "release_ready": {"type": "boolean"}, "gate_address": {"type": "string"}, "runtime_address": {"type": "string"}, "policy_address": {"type": "string"}, "entry_address": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate history query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"history_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "decision": {"type": "string"}, "state": {"type": "string"}, "transition": {"type": "string"}, "snapshot_id": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "operations": ("query_history", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_limit": MAX_LIMIT, "max_total_count": MAX_TOTAL_COUNT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "DownloadedDataQualityDiffGateHistoryQuery", "DownloadedDataQualityDiffGateHistoryQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_history", "query_json", "query_schema", "render_query_markdown", "row_schema"]
