"""Bounded inspection queries for comparison-query snapshot registry histories."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = history_model.VERSION + "-query-v1"
BOUNDARY = history_model.BOUNDARY + "_query"
QUERY_PREFIX = history_model.HISTORY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "entries", "initial", "improved", "regressed", "unchanged", "changed", "accepted", "rejected", "ready", "blocked", "transitions")
STATES = history_model.STATES
TRANSITIONS = history_model.TRANSITIONS
QUERY_FIELDS = (
    "history_address",
    "version",
    "boundary",
    "resources",
    "resource",
    "registry_id",
    "state",
    "accepted",
    "transition",
    "address_filter",
    "text_filter",
    "offset",
    "limit",
    "total_count",
    "matched_count",
    "returned_count",
    "next_offset",
    "truncated",
    "rows",
    "content_address",
)
ROW_FIELDS = (
    "ordinal",
    "resource",
    "identity",
    "history_id",
    "history_address",
    "registry_id",
    "registry_address",
    "entry_count",
    "ready_count",
    "blocked_count",
    "accepted_count",
    "rejected_count",
    "total_query_rows",
    "matched_query_rows",
    "returned_query_rows",
    "state",
    "accepted",
    "transition",
    "previous_registry_address",
    "detail",
    "content_address",
)
MAX_TOTAL_COUNT = 1 + len(RESOURCES) * history_model.MAX_ENTRIES
MAX_LIMIT = 128


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


def _optional_bool(value: Any, field: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean or null")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _ordered_resources(value: Any) -> tuple[str, ...]:
    resources = tuple(_label(item, "history query resource") for item in _sequence(value, "history query resources", len(RESOURCES)))
    if not resources or len(set(resources)) != len(resources) or any(item not in RESOURCES for item in resources) or resources != tuple(item for item in RESOURCES if item in resources):
        raise ValidationError("history query resources must be a non-empty canonical subset")
    return resources


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _entry_summary(entry: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry) -> dict[str, Any]:
    return {"registry_id": entry.registry_id, "registry_address": entry.registry_address, "entry_count": entry.entry_count, "ready_count": entry.ready_count, "blocked_count": entry.blocked_count, "accepted_count": entry.accepted_count, "rejected_count": entry.rejected_count, "total_query_rows": entry.total_query_rows, "matched_query_rows": entry.matched_query_rows, "returned_query_rows": entry.returned_query_rows, "state": entry.state, "accepted": entry.accepted, "transition": entry.transition, "previous_registry_address": entry.previous_registry_address}


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, history_id: str, history_address: str, registry_id: str, registry_address: str, entry_count: int, ready_count: int, blocked_count: int, accepted_count: int, rejected_count: int, total_query_rows: int, matched_query_rows: int, returned_query_rows: int, state: str, accepted: bool, transition: str, previous_registry_address: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "history query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("history query row resource is unsupported")
        self.identity = _label(identity, "history query row identity")
        self.history_id = _label(history_id, "history query row history ID")
        self.history_address = _address(history_address, "history query row history address", history_model.HISTORY_PREFIX)
        self.registry_id = _label(registry_id, "history query row registry ID", required=False)
        self.registry_address = _address(registry_address, "history query row registry address", history_model.registry_model.REGISTRY_PREFIX, required=False)
        self.entry_count = _count(entry_count, "history query row entry count", history_model.MAX_ENTRIES)
        self.ready_count = _count(ready_count, "history query row ready count", history_model.MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "history query row blocked count", history_model.MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "history query row accepted count", history_model.MAX_ENTRIES)
        self.rejected_count = _count(rejected_count, "history query row rejected count", history_model.MAX_ENTRIES)
        self.total_query_rows = _count(total_query_rows, "history query row total query rows", history_model.MAX_TOTAL_ROWS)
        self.matched_query_rows = _count(matched_query_rows, "history query row matched query rows", history_model.MAX_TOTAL_ROWS)
        self.returned_query_rows = _count(returned_query_rows, "history query row returned query rows", history_model.MAX_TOTAL_ROWS)
        self.state = _label(state, "history query row state")
        if self.state not in STATES:
            raise ValidationError("history query row state is unsupported")
        self.accepted = _bool(accepted, "history query row acceptance")
        self.transition = _label(transition, "history query row transition")
        if self.transition not in TRANSITIONS:
            raise ValidationError("history query row transition is unsupported")
        self.previous_registry_address = _address(previous_registry_address, "history query row predecessor", history_model.registry_model.REGISTRY_PREFIX, required=False)
        self.detail = _text(detail, "history query row detail", 4096)
        self.content_address = _address(content_address, "history query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.ready_count + self.blocked_count != self.entry_count or self.accepted_count + self.rejected_count != self.entry_count or self.returned_query_rows > self.matched_query_rows or self.matched_query_rows > self.total_query_rows:
            raise ValidationError("history query row counts are not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("history query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("history query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history query row")
        _strict(value, set(cls.FIELDS), "history query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow):
        raise ValidationError("history query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, history_address: str, version: str, boundary: str, resources: Sequence[str], resource: str, registry_id: str, state: str, accepted: bool | None, transition: str, address_filter: str, text_filter: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.history_address = _address(history_address, "history query history address", history_model.HISTORY_PREFIX)
        self.version = _text(version, "history query version", 4096)
        self.boundary = _text(boundary, "history query boundary", 4096)
        self.resources = _ordered_resources(resources)
        self.resource = _label(resource, "history query resource filter", required=False)
        if self.resource and self.resource not in RESOURCES:
            raise ValidationError("history query resource filter is unsupported")
        self.registry_id = _label(registry_id, "history query registry ID", required=False)
        self.state = _label(state, "history query state filter", required=False)
        if self.state and self.state not in STATES:
            raise ValidationError("history query state filter is unsupported")
        self.accepted = _optional_bool(accepted, "history query acceptance filter")
        self.transition = _label(transition, "history query transition filter", required=False)
        if self.transition and self.transition not in TRANSITIONS:
            raise ValidationError("history query transition filter is unsupported")
        self.address_filter = _text(address_filter, "history query address filter", 2048, required=False)
        self.text_filter = _text(text_filter, "history query text filter", 1024, required=False)
        self.offset = _count(offset, "history query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "history query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "history query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "history query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "history query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "history query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "history query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow.from_mapping(item) for item in _sequence(rows, "history query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "history query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history query version or boundary is unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.matched_count or self.matched_count > self.total_count or self.returned_count > self.limit or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.offset + self.matched_count):
            raise ValidationError("history query pagination does not replay")
        if tuple(row.ordinal for row in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("history query row ordinals do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("history query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "resource": self.resource, "registry_id": self.registry_id, "state": self.state, "accepted": self.accepted, "transition": self.transition, "address_filter": self.address_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": [row.to_dict() for row in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history query")
        _strict(value, set(cls.FIELDS), "history query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery):
        raise ValidationError("history query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(ordinal: int, resource: str, identity: str, history: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, summary: Mapping[str, Any], detail: str) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "identity": identity, "history_id": history.history_id, "history_address": history.content_address, "registry_id": summary["registry_id"], "registry_address": summary["registry_address"], "entry_count": summary["entry_count"], "ready_count": summary["ready_count"], "blocked_count": summary["blocked_count"], "accepted_count": summary["accepted_count"], "rejected_count": summary["rejected_count"], "total_query_rows": summary["total_query_rows"], "matched_query_rows": summary["matched_query_rows"], "returned_query_rows": summary["returned_query_rows"], "state": summary["state"], "accepted": summary["accepted"], "transition": summary["transition"], "previous_registry_address": summary["previous_registry_address"], "detail": detail, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow(**(body | {"content_address": address_row(provisional)}))


def _rows(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, resources: Sequence[str]) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow, ...]:
    rows: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow] = []
    latest = value.entries.entries[-1] if value.entries.entries else None
    summary = {"registry_id": value.registry_id, "registry_address": value.latest_registry_address, "entry_count": value.latest_entry_count, "ready_count": value.latest_ready_count, "blocked_count": value.latest_blocked_count, "accepted_count": value.latest_accepted_count, "rejected_count": value.latest_rejected_count, "total_query_rows": value.latest_total_query_rows, "matched_query_rows": value.latest_matched_query_rows, "returned_query_rows": value.latest_returned_query_rows, "state": value.state, "accepted": value.accepted, "transition": latest.transition if latest else "initial", "previous_registry_address": latest.previous_registry_address if latest else ""}
    ordinal = 1
    if "summary" in resources:
        rows.append(_row(ordinal, "summary", "history-summary", value, summary, "aggregate history summary"))
        ordinal += 1
    for entry in value.entries.entries:
        entry_summary = _entry_summary(entry)
        for resource in resources:
            include = resource == "entries" or resource == entry.transition or resource == "transitions" or resource == ("accepted" if entry.accepted else "rejected") or resource == entry.state
            if include and resource != "summary":
                rows.append(_row(ordinal, resource, f"ordinal-{entry.ordinal}", value, entry_summary, f"registry history entry {entry.ordinal}"))
                ordinal += 1
    return tuple(rows)


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow, query: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery) -> bool:
    if query.resource and row.resource != query.resource:
        return False
    if query.registry_id and row.registry_id != query.registry_id:
        return False
    if query.state and row.state != query.state:
        return False
    if query.accepted is not None and row.accepted != query.accepted:
        return False
    if query.transition and row.transition != query.transition:
        return False
    if query.address_filter and query.address_filter not in " ".join((row.history_address, row.registry_address, row.previous_registry_address, row.content_address)):
        return False
    if query.text_filter and query.text_filter.casefold() not in json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True).casefold():
        return False
    return True


def query_history(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, *, resources: Sequence[str] = RESOURCES, resource: str = "", registry_id: str = "", state: str = "", accepted: bool | None = None, transition: str = "", address: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT):
    if not isinstance(value, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
        raise ValidationError("history query requires a typed history")
    selected = _ordered_resources(resources)
    resource = _label(resource, "history query resource filter", required=False)
    registry_id = _label(registry_id, "history query registry ID", required=False)
    state = _label(state, "history query state filter", required=False)
    transition = _label(transition, "history query transition filter", required=False)
    address = _text(address, "history query address filter", 2048, required=False)
    text = _text(text, "history query text filter", 1024, required=False)
    offset = _count(offset, "history query offset", MAX_TOTAL_COUNT)
    limit = _count(limit, "history query limit", MAX_LIMIT, positive=True)
    if resource and resource not in RESOURCES or state and state not in STATES or transition and transition not in TRANSITIONS:
        raise ValidationError("history query filter is unsupported")
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery(value.content_address, VERSION, BOUNDARY, selected, resource, registry_id, state, accepted, transition, address, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    candidates = _rows(value, selected)
    matched = tuple(row for row in candidates if _matches(row, provisional))
    page = matched[offset:offset + limit]
    body = {"history_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": selected, "resource": resource, "registry_id": registry_id, "state": state, "accepted": accepted, "transition": transition, "address_filter": address, "text_filter": text, "offset": offset, "limit": limit, "total_count": len(candidates), "matched_count": len(matched), "returned_count": len(page), "next_offset": offset + len(page), "truncated": offset + len(page) < offset + len(matched), "rows": page, "content_address": QUERY_PREFIX + ":pending"}
    final = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery(**(body | {"content_address": address_query(final)}))


def query_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery.from_mapping(value)


def query_json(value) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value) -> str:
    typed = query_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for row in typed.rows:
        body = row.to_dict()
        writer.writerow(json.dumps(body[field], ensure_ascii=False, sort_keys=True) if isinstance(body[field], (tuple, list, dict)) else body[field] for field in ROW_FIELDS)
    return output.getvalue()


def render_query_markdown(value) -> str:
    typed = query_from_mapping(value.to_dict())
    lines = ["# Comparison-Query Snapshot Registry History Query", "", f"- History: `{typed.history_address}`", f"- Resources: `{', '.join(typed.resources)}`", f"- Matched: `{typed.matched_count}`", f"- Returned: `{typed.returned_count}`", f"- Address: `{typed.content_address}`", "", "| # | resource | identity | state | accepted | transition | detail |", "| ---: | --- | --- | --- | ---: | --- | --- |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.identity}` | `{row.state}` | `{row.accepted}` | `{row.transition}` | {row.detail} |" for row in typed.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "history_id": {"type": "string"}, "history_address": {"type": "string"}, "registry_id": {"type": "string"}, "registry_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "ready_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "rejected_count": {"type": "integer", "minimum": 0}, "total_query_rows": {"type": "integer", "minimum": 0}, "matched_query_rows": {"type": "integer", "minimum": 0}, "returned_query_rows": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "transition": {"enum": list(TRANSITIONS)}, "previous_registry_address": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"history_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "resource": {"type": "string"}, "registry_id": {"type": "string"}, "state": {"type": "string"}, "accepted": {"type": ["boolean", "null"]}, "transition": {"type": "string"}, "address_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": list(RESOURCES), "states": list(STATES), "transitions": list(TRANSITIONS), "max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT, "value_free": True, "operations": ["query", "json", "csv", "markdown", "schema"]}
