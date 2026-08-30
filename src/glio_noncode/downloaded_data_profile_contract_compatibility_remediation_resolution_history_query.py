"""Bounded queries over value-free remediation-resolution history."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history as history_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "entries")
QUERY_FIELDS = ("history_address", "version", "boundary", "resources", "state", "decision", "transition", "release_ready", "plan_id", "resolution_id", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")
ROW_FIELDS = ("ordinal", "resource", "resolution_id", "plan_id", "resolution_address", "required_open_count", "state", "decision", "release_ready", "transition", "previous_resolution_address", "resolution_entry_address", "content_address")
MAX_TOTAL_COUNT = history_model.MAX_ENTRIES + 1
MAX_LIMIT = 100


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
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


def _ordered_labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not labels or len(set(labels)) != len(labels) or any(item not in allowed for item in labels) or tuple(sorted(labels, key=allowed.index)) != labels:
        raise ValidationError(f"{field} contains unsupported or unordered labels")
    return labels


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, resolution_id: str, plan_id: str, resolution_address: str, required_open_count: int, state: str, decision: str, release_ready: bool, transition: str, previous_resolution_address: str, resolution_entry_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "history query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("history query row resource is unsupported")
        self.resolution_id = _label(resolution_id, "history query row resolution ID")
        self.plan_id = _label(plan_id, "history query row plan ID")
        self.resolution_address = _address(resolution_address, "history query row resolution address", "glio-noncode-download-profile-contract-compatibility-remediation-resolution", required=False)
        self.required_open_count = _count(required_open_count, "history query row open count", history_model.MAX_ENTRIES)
        self.state = _label(state, "history query row state")
        if self.state not in history_model.STATES:
            raise ValidationError("history query row state is unsupported")
        self.decision = _label(decision, "history query row decision")
        if self.decision not in history_model.DECISIONS:
            raise ValidationError("history query row decision is unsupported")
        self.release_ready = _bool(release_ready, "history query row release readiness")
        self.transition = _label(transition, "history query row transition")
        if self.transition not in history_model.TRANSITIONS:
            raise ValidationError("history query row transition is unsupported")
        self.previous_resolution_address = _address(previous_resolution_address, "history query row previous resolution address", "glio-noncode-download-profile-contract-compatibility-remediation-resolution", required=False)
        self.resolution_entry_address = _address(resolution_entry_address, "history query row entry address", history_model.ENTRY_PREFIX, required=False)
        self.content_address = _address(content_address, "history query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and any((self.resolution_address, self.previous_resolution_address, self.resolution_entry_address)):
            raise ValidationError("history summary row contains entry linkage fields")
        if self.resource == "entries" and (not self.resolution_address or not self.resolution_entry_address):
            raise ValidationError("history entry row is incomplete")
        if not _public(self.to_dict()):
            raise ValidationError("history query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("history query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow:
        value = _mapping(value, "history query row")
        _strict(value, set(cls.FIELDS), "history query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow):
        raise ValidationError("history query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, history_address: str, version: str, boundary: str, resources: Sequence[str], state: str, decision: str, transition: str, release_ready: bool, plan_id: str, resolution_id: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.history_address = _address(history_address, "history query history address", history_model.HISTORY_PREFIX)
        self.version = _text(version, "history query version")
        self.boundary = _text(boundary, "history query boundary", 512)
        self.resources = _ordered_labels(resources, "history query resources", RESOURCES)
        self.state = _label(state, "history query state", required=False)
        if self.state and self.state not in history_model.STATES:
            raise ValidationError("history query state is unsupported")
        self.decision = _label(decision, "history query decision", required=False)
        if self.decision and self.decision not in history_model.DECISIONS:
            raise ValidationError("history query decision is unsupported")
        self.transition = _label(transition, "history query transition", required=False)
        if self.transition and self.transition not in history_model.TRANSITIONS:
            raise ValidationError("history query transition is unsupported")
        self.release_ready = _bool(release_ready, "history query release readiness")
        self.plan_id = _label(plan_id, "history query plan ID", required=False)
        self.resolution_id = _label(resolution_id, "history query resolution ID", required=False)
        self.text = _text(text, "history query text", 1024, required=False)
        self.offset = _count(offset, "history query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "history query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "history query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "history query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "history query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "history query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "history query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow.from_mapping(item) for item in _sequence(rows, "history query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "history query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history query version or boundary is not current")
        if len(self.rows) != self.returned_count or self.returned_count > self.limit or tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("history query row order does not replay")
        if self.matched_count > self.total_count or self.returned_count > self.matched_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("history query counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("history query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "state": self.state, "decision": self.decision, "transition": self.transition, "release_ready": self.release_ready, "plan_id": self.plan_id, "resolution_id": self.resolution_id, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery:
        value = _mapping(value, "history query")
        _strict(value, set(cls.FIELDS), "history query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery):
        raise ValidationError("history query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _summary_row(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow:
    body = {"ordinal": 1, "resource": "summary", "resolution_id": "history-summary", "plan_id": value.history_id, "resolution_address": "", "required_open_count": value.latest_required_open_count, "state": value.state, "decision": value.decision, "release_ready": value.release_ready, "transition": "initial", "previous_resolution_address": "", "resolution_entry_address": "", "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow(**(body | {"content_address": address_row(provisional)}))


def _entry_row(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow:
    body = {"ordinal": ordinal, "resource": "entries", "resolution_id": value.resolution_id, "plan_id": value.plan_id, "resolution_address": value.resolution_address, "required_open_count": value.required_open_count, "state": value.state, "decision": value.decision, "release_ready": value.release_ready, "transition": value.transition, "previous_resolution_address": value.previous_resolution_address, "resolution_entry_address": value.content_address, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow(**(body | {"content_address": address_row(provisional)}))


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow, query: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery) -> bool:
    if row.resource == "summary":
        return not any((query.state, query.decision, query.transition, query.plan_id, query.resolution_id, query.text)) and not query.release_ready
    if query.state and row.state != query.state:
        return False
    if query.decision and row.decision != query.decision:
        return False
    if query.transition and row.transition != query.transition:
        return False
    if query.release_ready and not row.release_ready:
        return False
    if query.plan_id and row.plan_id != query.plan_id:
        return False
    if query.resolution_id and query.resolution_id.casefold() not in row.resolution_id.casefold():
        return False
    haystack = " ".join((row.resolution_id, row.plan_id, row.resolution_address, row.state, row.decision, row.transition, row.previous_resolution_address, row.resolution_entry_address)).casefold()
    return not query.text or query.text.casefold() in haystack


def query_history(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory, *, resources: Sequence[str] = RESOURCES, state: str = "", decision: str = "", transition: str = "", release_ready: bool = False, plan_id: str = "", resolution_id: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery:
    if not isinstance(value, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory):
        raise ValidationError("history query requires a typed history")
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery(value.content_address, VERSION, BOUNDARY, resources, state, decision, transition, release_ready, plan_id, resolution_id, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    rows = tuple([_summary_row(value)] if "summary" in provisional.resources else []) + tuple(_entry_row(item, ordinal) for ordinal, item in enumerate(value.entries, 2) if "entries" in provisional.resources)
    matched = tuple(item for item in rows if _matches(item, provisional))
    selected = tuple(_readdress(item, ordinal) for ordinal, item in enumerate(matched[offset : offset + limit], 1))
    body = {"history_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": provisional.resources, "state": provisional.state, "decision": provisional.decision, "transition": provisional.transition, "release_ready": provisional.release_ready, "plan_id": provisional.plan_id, "resolution_id": provisional.resolution_id, "text": provisional.text, "offset": provisional.offset, "limit": provisional.limit, "total_count": len(rows), "matched_count": len(matched), "returned_count": len(selected), "next_offset": provisional.offset + len(selected), "truncated": provisional.offset + len(selected) < len(matched), "rows": selected, "content_address": QUERY_PREFIX + ":pending"}
    provisional_result = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery(**(body | {"content_address": address_query(provisional_result)}))


def _readdress(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in ROW_FIELDS) for item in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Query", "", f"- History: `{value.history_address}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", f"- Address: `{value.content_address}`", "", "| # | resource | snapshot | open | transition | state |", "| ---: | --- | --- | ---: | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.resolution_id}` | `{row.required_open_count}` | `{row.transition}` | `{row.state}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "resolution_id": {"type": "string"}, "plan_id": {"type": "string"}, "resolution_address": {"type": "string"}, "required_open_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(history_model.STATES)}, "decision": {"enum": list(history_model.DECISIONS)}, "release_ready": {"type": "boolean"}, "transition": {"enum": list(history_model.TRANSITIONS)}, "previous_resolution_address": {"type": "string"}, "resolution_entry_address": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"history_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "state": {"type": "string"}, "decision": {"type": "string"}, "transition": {"type": "string"}, "release_ready": {"type": "boolean"}, "plan_id": {"type": "string"}, "resolution_id": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "states": history_model.STATES, "decisions": history_model.DECISIONS, "transitions": history_model.TRANSITIONS, "operations": ("query_history", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_history", "query_json", "query_schema", "render_query_markdown", "row_schema"]
