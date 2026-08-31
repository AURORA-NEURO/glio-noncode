"""Bounded inspection queries over comparison-query snapshot registries."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = registry_model.VERSION + "-query-v1"
BOUNDARY = registry_model.BOUNDARY + "_query"
QUERY_PREFIX = registry_model.REGISTRY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "entries", "ready", "blocked", "accepted", "rejected", "diffs", "queries")
MAX_LIMIT = 128
MAX_TOTAL_COUNT = 1 + (registry_model.MAX_ENTRIES * 7)
ROW_FIELDS = (
    "resource",
    "ordinal",
    "entry_ordinal",
    "snapshot_id",
    "snapshot_address",
    "diff_id",
    "diff_address",
    "query_address",
    "query_audit_address",
    "state",
    "accepted",
    "query_total_count",
    "query_matched_count",
    "query_returned_count",
    "resources",
    "field_filter",
    "direction_filter",
    "content_address",
)
QUERY_FIELDS = (
    "registry_address",
    "resources",
    "snapshot_id_filter",
    "diff_id_filter",
    "state_filter",
    "accepted_filter",
    "field_filter",
    "direction_filter",
    "text_filter",
    "offset",
    "limit",
    "total_count",
    "matched_count",
    "returned_count",
    "rows",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = False) -> str:
    value = _text(value, field, 4096, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool_or_none(value: Any, field: str) -> bool | None:
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, entry_ordinal: int, snapshot_id: str, snapshot_address: str, diff_id: str, diff_address: str, query_address: str, query_audit_address: str, state: str, accepted: bool, query_total_count: int, query_matched_count: int, query_returned_count: int, resources: Sequence[str], field_filter: str, direction_filter: str, content_address: str) -> None:
        self.resource = _label(resource, "registry query row resource", required=True)
        if self.resource not in RESOURCES:
            raise ValidationError("registry query row resource is unsupported")
        self.ordinal = _count(ordinal, "registry query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.entry_ordinal = _count(entry_ordinal, "registry query row entry ordinal", registry_model.MAX_ENTRIES)
        self.snapshot_id = _label(snapshot_id, "registry query row snapshot ID")
        self.snapshot_address = _address(snapshot_address, "registry query row snapshot address", registry_model.snapshot_model.SNAPSHOT_PREFIX)
        self.diff_id = _label(diff_id, "registry query row diff ID")
        self.diff_address = _address(diff_address, "registry query row diff address")
        self.query_address = _address(query_address, "registry query row query address")
        self.query_audit_address = _address(query_audit_address, "registry query row query audit address")
        self.state = _label(state, "registry query row state", required=True)
        if self.state not in registry_model.STATES and self.state not in registry_model.snapshot_model.STATES:
            raise ValidationError("registry query row state is unsupported")
        if self.resource == "summary":
            self.snapshot_id = _label(snapshot_id, "registry query summary snapshot ID")
        self.accepted = _bool_or_none(accepted, "registry query row acceptance")
        if self.accepted is None:
            raise ValidationError("registry query row acceptance must be boolean")
        self.query_total_count = _count(query_total_count, "registry query row total count", registry_model.MAX_TOTAL_ROWS)
        self.query_matched_count = _count(query_matched_count, "registry query row matched count", registry_model.MAX_TOTAL_ROWS)
        self.query_returned_count = _count(query_returned_count, "registry query row returned count", registry_model.MAX_TOTAL_ROWS)
        self.resources = tuple(_label(item, "registry query row resource member", required=True) for item in _sequence(resources, "registry query row resources", 64))
        self.field_filter = _text(field_filter, "registry query row field filter", 1024)
        self.direction_filter = _text(direction_filter, "registry query row direction filter", 1024)
        self.content_address = _address(content_address, "registry query row content address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.query_matched_count > self.query_total_count or self.query_returned_count > self.query_matched_count:
            raise ValidationError("registry query row counts are not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("registry query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("registry query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry query row")
        _strict(value, set(cls.FIELDS), "registry query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow):
        raise ValidationError("registry query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, registry_address: str, resources: Sequence[str], snapshot_id_filter: str, diff_id_filter: str, state_filter: str, accepted_filter: bool | None, field_filter: str, direction_filter: str, text_filter: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, rows: Sequence[Any], content_address: str) -> None:
        self.registry_address = _address(registry_address, "registry query registry address", registry_model.REGISTRY_PREFIX, required=True)
        resources = _sequence(resources, "registry query resources", len(RESOURCES))
        if not resources or len(set(resources)) != len(resources) or any(item not in RESOURCES for item in resources):
            raise ValidationError("registry query resources are invalid")
        self.resources = tuple(item for item in RESOURCES if item in resources)
        self.snapshot_id_filter = _label(snapshot_id_filter, "registry query snapshot ID filter")
        self.diff_id_filter = _label(diff_id_filter, "registry query diff ID filter")
        self.state_filter = _label(state_filter, "registry query state filter")
        if self.state_filter and self.state_filter not in registry_model.STATES and self.state_filter not in registry_model.snapshot_model.STATES:
            raise ValidationError("registry query state filter is unsupported")
        self.accepted_filter = _bool_or_none(accepted_filter, "registry query acceptance filter")
        self.field_filter = _text(field_filter, "registry query field filter", 1024)
        self.direction_filter = _text(direction_filter, "registry query direction filter", 1024)
        self.text_filter = _text(text_filter, "registry query text filter", 1024)
        self.offset = _count(offset, "registry query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "registry query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "registry query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "registry query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "registry query returned count", MAX_LIMIT)
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow.from_mapping(item) for item in _sequence(rows, "registry query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "registry query content address", QUERY_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.returned_count > max(0, self.matched_count - self.offset):
            raise ValidationError("registry query counts or pagination do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("registry query row ordinals are not page ordinals")
        if not _public(self.to_dict()):
            raise ValidationError("registry query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("registry query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "resources": self.resources, "snapshot_id_filter": self.snapshot_id_filter, "diff_id_filter": self.diff_id_filter, "state_filter": self.state_filter, "accepted_filter": self.accepted_filter, "field_filter": self.field_filter, "direction_filter": self.direction_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry query")
        _strict(value, set(cls.FIELDS), "registry query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQuery):
        raise ValidationError("registry query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, entry: Any | None = None, summary: Any | None = None) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow:
    body = {"resource": resource, "ordinal": ordinal, "entry_ordinal": 0, "snapshot_id": "", "snapshot_address": "", "diff_id": "", "diff_address": "", "query_address": "", "query_audit_address": "", "state": "empty", "accepted": False, "query_total_count": 0, "query_matched_count": 0, "query_returned_count": 0, "resources": (), "field_filter": "", "direction_filter": "", "content_address": ROW_PREFIX + ":pending"}
    if entry is not None:
        body.update({"entry_ordinal": entry.ordinal, "snapshot_id": entry.snapshot_id, "snapshot_address": entry.snapshot_address, "diff_id": entry.diff_id, "diff_address": entry.diff_address, "query_address": entry.query_address, "query_audit_address": entry.query_audit_address, "state": entry.state, "accepted": entry.accepted, "query_total_count": entry.query_total_count, "query_matched_count": entry.query_matched_count, "query_returned_count": entry.query_returned_count, "resources": entry.resources, "field_filter": entry.field_filter, "direction_filter": entry.direction_filter})
    if summary is not None:
        body.update({"snapshot_id": summary.latest_snapshot_id, "snapshot_address": summary.latest_snapshot_address, "state": summary.state, "accepted": summary.accepted, "query_total_count": summary.total_query_rows, "query_matched_count": summary.matched_query_rows, "query_returned_count": summary.returned_query_rows})
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow(**(body | {"content_address": address_row(provisional)}))


def _renumber_row(value: Any, ordinal: int):
    body = value.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow(**(body | {"content_address": address_row(provisional)}))


def _all_rows(value: Any) -> tuple[Any, ...]:
    rows = []
    ordinal = 1
    rows.append(_row("summary", ordinal, summary=value.summary))
    ordinal += 1
    for resource in ("entries", "ready", "blocked", "accepted", "rejected"):
        for entry in value.entries.entries:
            include = resource == "entries" or resource == entry.state or resource == "accepted" and entry.accepted or resource == "rejected" and not entry.accepted
            if include:
                rows.append(_row(resource, ordinal, entry=entry))
                ordinal += 1
    seen_diffs: set[str] = set()
    seen_queries: set[str] = set()
    for entry in value.entries.entries:
        if entry.diff_id not in seen_diffs:
            rows.append(_row("diffs", ordinal, entry=entry))
            ordinal += 1
            seen_diffs.add(entry.diff_id)
        if entry.query_address not in seen_queries:
            rows.append(_row("queries", ordinal, entry=entry))
            ordinal += 1
            seen_queries.add(entry.query_address)
    return tuple(rows)


def _matches(row: Any, *, snapshot_id: str, diff_id: str, state: str, accepted: bool | None, field: str, direction: str, text: str) -> bool:
    if snapshot_id and row.snapshot_id != snapshot_id or diff_id and row.diff_id != diff_id or state and row.state != state or accepted is not None and row.accepted != accepted or field and row.field_filter != field or direction and row.direction_filter != direction:
        return False
    if text:
        haystack = " ".join(str(row.to_dict()[name]) for name in ROW_FIELDS if name != "content_address").casefold()
        return text.casefold() in haystack
    return True


def query_registry(value: Any, *, resources: Sequence[str] | None = None, snapshot_id: str = "", diff_id: str = "", state: str = "", accepted: bool | None = None, field: str = "", direction: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT):
    value = registry_model.verify_registry(value)
    selected = tuple(RESOURCES if resources is None else _sequence(resources, "registry query resources", len(RESOURCES)))
    if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected):
        raise ValidationError("registry query resources are invalid")
    _label(snapshot_id, "registry query snapshot ID filter")
    _label(diff_id, "registry query diff ID filter")
    _label(state, "registry query state filter")
    _text(field, "registry query field filter", 1024)
    _text(direction, "registry query direction filter", 1024)
    _text(text, "registry query text filter", 1024)
    _count(offset, "registry query offset", MAX_TOTAL_COUNT)
    _count(limit, "registry query limit", MAX_LIMIT, positive=True)
    all_rows = _all_rows(value)
    selected_rows = tuple(row for row in all_rows if row.resource in selected)
    matched = tuple(row for row in selected_rows if _matches(row, snapshot_id=snapshot_id, diff_id=diff_id, state=state, accepted=accepted, field=field, direction=direction, text=text))
    page = tuple(_renumber_row(row, ordinal) for ordinal, row in enumerate(matched[offset:offset + limit], offset + 1))
    body = {"registry_address": value.content_address, "resources": tuple(item for item in RESOURCES if item in selected), "snapshot_id_filter": snapshot_id, "diff_id_filter": diff_id, "state_filter": state, "accepted_filter": accepted, "field_filter": field, "direction_filter": direction, "text_filter": text, "offset": offset, "limit": limit, "total_count": len(selected_rows), "matched_count": len(matched), "returned_count": len(page), "rows": page, "content_address": QUERY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQuery.from_mapping(value)


def query_json(value) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value) -> str:
    value = query_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_query_markdown(value) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Comparison Query Snapshot Registry Query", "", f"- Registry: `{value.registry_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}` of `{value.matched_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | snapshot | diff | state | accepted |", "| ---: | --- | --- | --- | :---: | :---: |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.snapshot_id}` | `{item.diff_id}` | `{item.state}` | `{str(item.accepted).lower()}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot registry query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 1}, "entry_ordinal": {"type": "integer", "minimum": 0}, "snapshot_id": {"type": "string"}, "snapshot_address": {"type": "string"}, "diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "state": {"type": "string"}, "accepted": {"type": "boolean"}, "query_total_count": {"type": "integer", "minimum": 0}, "query_matched_count": {"type": "integer", "minimum": 0}, "query_returned_count": {"type": "integer", "minimum": 0}, "resources": {"type": "array"}, "field_filter": {"type": "string"}, "direction_filter": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot registry query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"registry_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "snapshot_id_filter": {"type": "string"}, "diff_id_filter": {"type": "string"}, "state_filter": {"type": "string"}, "accepted_filter": {"type": ["boolean", "null"]}, "field_filter": {"type": "string"}, "direction_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "value_free": True, "resources": list(RESOURCES), "max_limit": MAX_LIMIT, "features": ["summary and entry projections", "ready blocked accepted and rejected partitions", "distinct diff and query projections", "exact identity and state filters", "bounded text filters", "deterministic pagination", "row content addresses", "JSON CSV and Markdown projections"]}


__all__ = [
    "BOUNDARY",
    "MAX_LIMIT",
    "MAX_TOTAL_COUNT",
    "QUERY_FIELDS",
    "QUERY_PREFIX",
    "RESOURCES",
    "ROW_FIELDS",
    "ROW_PREFIX",
    "VERSION",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQuery",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryRow",
    "address_query",
    "address_row",
    "capabilities",
    "query_csv",
    "query_from_mapping",
    "query_json",
    "query_registry",
    "query_schema",
    "render_query_markdown",
    "row_schema",
]
