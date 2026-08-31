"""Bounded query projections for the comparison-query history observatory."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = observatory_model.VERSION + "-query-v1"
BOUNDARY = observatory_model.BOUNDARY + "_query"
QUERY_PREFIX = observatory_model.OBSERVATORY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "members", "empty", "ready", "blocked", "mixed", "transitions", "initial", "improved", "regressed", "unchanged", "changed", "stable")
MAX_LIMIT = 128
MAX_TOTAL_COUNT = 1 + observatory_model.MAX_MEMBERS * (1 + len(observatory_model.STATES) + len(observatory_model.TRENDS)) + observatory_model.MAX_TRANSITIONS
ROW_FIELDS = (
    "resource", "ordinal", "member_ordinal", "history_id", "registry_id",
    "history_address", "snapshot_ordinal", "registry_address", "snapshot_count",
    "entry_count", "ready_count", "blocked_count", "accepted_count",
    "rejected_count", "total_query_rows", "matched_query_rows",
    "returned_query_rows", "state", "accepted", "transition", "trend",
    "content_address",
)
QUERY_FIELDS = (
    "observatory_address", "resources", "history_id_filter", "registry_id_filter",
    "state_filter", "accepted_filter", "transition_filter", "trend_filter",
    "address_filter", "text_filter", "offset", "limit", "total_count",
    "matched_count", "returned_count", "rows", "content_address",
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
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, member_ordinal: int, history_id: str, registry_id: str, history_address: str, snapshot_ordinal: int, registry_address: str, snapshot_count: int, entry_count: int, ready_count: int, blocked_count: int, accepted_count: int, rejected_count: int, total_query_rows: int, matched_query_rows: int, returned_query_rows: int, state: str, accepted: bool | None, transition: str, trend: str, content_address: str) -> None:
        self.resource = _label(resource, "observatory query row resource", required=True)
        if self.resource not in RESOURCES:
            raise ValidationError("observatory query row resource is unsupported")
        self.ordinal = _count(ordinal, "observatory query row ordinal", MAX_TOTAL_COUNT)
        if self.ordinal < 1:
            raise ValidationError("observatory query row ordinal must be positive")
        self.member_ordinal = _count(member_ordinal, "observatory query row member ordinal", observatory_model.MAX_MEMBERS)
        self.history_id = _label(history_id, "observatory query row history ID")
        self.registry_id = _label(registry_id, "observatory query row registry ID")
        self.history_address = _address(history_address, "observatory query row history address")
        self.snapshot_ordinal = _count(snapshot_ordinal, "observatory query row snapshot ordinal", observatory_model.history_model.MAX_ENTRIES)
        self.registry_address = _address(registry_address, "observatory query row registry address")
        for field in ("snapshot_count", "entry_count", "ready_count", "blocked_count", "accepted_count", "rejected_count"):
            setattr(self, field, _count(locals()[field], f"observatory query row {field}", observatory_model.history_model.MAX_ENTRIES))
        for field in ("total_query_rows", "matched_query_rows", "returned_query_rows"):
            setattr(self, field, _count(locals()[field], f"observatory query row {field}", observatory_model.MAX_TOTAL_ROWS))
        self.state = _label(state, "observatory query row state", required=True)
        if self.state not in observatory_model.STATES:
            raise ValidationError("observatory query row state is unsupported")
        self.accepted = _bool_or_none(accepted, "observatory query row acceptance")
        self.transition = _label(transition, "observatory query row transition")
        if self.transition and self.transition not in observatory_model.TRANSITIONS:
            raise ValidationError("observatory query row transition is unsupported")
        self.trend = _label(trend, "observatory query row trend")
        if self.trend and self.trend not in observatory_model.TRENDS:
            raise ValidationError("observatory query row trend is unsupported")
        self.content_address = _address(content_address, "observatory query row content address", ROW_PREFIX)
        if not _public(self.to_dict()):
            raise ValidationError("observatory query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("observatory query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory query row")
        _strict(value, set(cls.FIELDS), "observatory query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: Any) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryRow):
        raise ValidationError("observatory query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, observatory_address: str, resources: Sequence[str], history_id_filter: str, registry_id_filter: str, state_filter: str, accepted_filter: bool | None, transition_filter: str, trend_filter: str, address_filter: str, text_filter: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, rows: Sequence[Any], content_address: str) -> None:
        self.observatory_address = _address(observatory_address, "observatory query address", observatory_model.OBSERVATORY_PREFIX)
        selected = _sequence(resources, "observatory query resources", len(RESOURCES))
        if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected):
            raise ValidationError("observatory query resources are invalid")
        self.resources = tuple(item for item in RESOURCES if item in selected)
        self.history_id_filter = _label(history_id_filter, "observatory query history filter")
        self.registry_id_filter = _label(registry_id_filter, "observatory query registry filter")
        self.state_filter = _label(state_filter, "observatory query state filter")
        self.accepted_filter = _bool_or_none(accepted_filter, "observatory query acceptance filter")
        self.transition_filter = _label(transition_filter, "observatory query transition filter")
        self.trend_filter = _label(trend_filter, "observatory query trend filter")
        self.address_filter = _address(address_filter, "observatory query address filter")
        self.text_filter = _text(text_filter, "observatory query text filter", 1024)
        self.offset = _count(offset, "observatory query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "observatory query limit", MAX_LIMIT)
        if self.limit < 1:
            raise ValidationError("observatory query limit must be positive")
        self.total_count = _count(total_count, "observatory query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "observatory query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "observatory query returned count", MAX_LIMIT)
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryRow.from_mapping(item) for item in _sequence(rows, "observatory query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "observatory query content address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.returned_count > max(0, self.matched_count - self.offset) or tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("observatory query counts or pagination do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("observatory query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"observatory_address": self.observatory_address, "resources": self.resources, "history_id_filter": self.history_id_filter, "registry_id_filter": self.registry_id_filter, "state_filter": self.state_filter, "accepted_filter": self.accepted_filter, "transition_filter": self.transition_filter, "trend_filter": self.trend_filter, "address_filter": self.address_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory query")
        _strict(value, set(cls.FIELDS), "observatory query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: Any) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQuery):
        raise ValidationError("observatory query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, *, member: Any | None = None, transition: Any | None = None, summary: Any | None = None):
    body = {"resource": resource, "ordinal": ordinal, "member_ordinal": 0, "history_id": "", "registry_id": "", "history_address": "", "snapshot_ordinal": 0, "registry_address": "", "snapshot_count": 0, "entry_count": 0, "ready_count": 0, "blocked_count": 0, "accepted_count": 0, "rejected_count": 0, "total_query_rows": 0, "matched_query_rows": 0, "returned_query_rows": 0, "state": "empty", "accepted": False, "transition": "", "trend": "", "content_address": ROW_PREFIX + ":pending"}
    if member is not None:
        body.update({"member_ordinal": member.ordinal, "history_id": member.history_id, "registry_id": member.registry_id, "history_address": member.history_address, "snapshot_count": member.snapshot_count, "entry_count": member.latest_entry_count, "ready_count": member.latest_ready_count, "blocked_count": member.latest_blocked_count, "accepted_count": member.latest_accepted_count, "rejected_count": member.latest_rejected_count, "total_query_rows": member.latest_total_query_rows, "matched_query_rows": member.latest_matched_query_rows, "returned_query_rows": member.latest_returned_query_rows, "state": member.latest_state, "accepted": member.latest_accepted, "trend": member.trend})
    if transition is not None:
        body.update({"member_ordinal": transition.member_ordinal, "history_id": transition.history_id, "registry_id": transition.registry_id, "history_address": transition.history_address, "snapshot_ordinal": transition.snapshot_ordinal, "registry_address": transition.registry_address, "entry_count": transition.entry_count, "ready_count": transition.ready_count, "blocked_count": transition.blocked_count, "accepted_count": transition.accepted_count, "rejected_count": transition.rejected_count, "total_query_rows": transition.total_query_rows, "matched_query_rows": transition.matched_query_rows, "returned_query_rows": transition.returned_query_rows, "state": transition.state, "accepted": transition.accepted, "transition": transition.transition})
    if summary is not None:
        body.update({"history_address": summary.latest_history_address, "snapshot_count": summary.transition_count, "entry_count": summary.member_count, "ready_count": summary.ready_count, "blocked_count": summary.blocked_count, "accepted": summary.accepted, "total_query_rows": summary.total_query_rows, "matched_query_rows": summary.matched_query_rows, "returned_query_rows": summary.returned_query_rows, "state": summary.state})
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryRow(**(body | {"content_address": address_row(provisional)}))


def _renumber_row(value: Any, ordinal: int):
    body = value.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryRow(**(body | {"content_address": address_row(provisional)}))


def _all_rows(value: Any) -> tuple[Any, ...]:
    rows: list[Any] = [_row("summary", 1, summary=value.summary)]
    ordinal = 2
    for resource in ("members", "empty", "ready", "blocked", "mixed", "stable", "improved", "regressed", "changed"):
        for member in value.members:
            if resource == "members" or resource == member.latest_state or resource == member.trend:
                rows.append(_row(resource, ordinal, member=member))
                ordinal += 1
    rows.extend(_row("transitions", ordinal + index, transition=transition) for index, transition in enumerate(value.transitions))
    rows.extend(_row(transition.transition, ordinal + len(value.transitions) + index, transition=transition) for index, transition in enumerate(value.transitions) if transition.transition in {"initial", "improved", "regressed", "unchanged", "changed"})
    return tuple(rows)


def _matches(row: Any, *, history_id: str, registry_id: str, state: str, accepted: bool | None, transition: str, trend: str, address: str, text: str) -> bool:
    if history_id and row.history_id != history_id or registry_id and row.registry_id != registry_id or state and row.state != state or accepted is not None and row.accepted != accepted or transition and row.transition != transition or trend and row.trend != trend:
        return False
    if address and address not in {row.content_address, row.history_address, row.registry_address}:
        return False
    if text:
        haystack = " ".join(str(row.to_dict()[field]) for field in ROW_FIELDS if field != "content_address").casefold()
        if text.casefold() not in haystack:
            return False
    return True


def query_observatory(value: Any, *, resources: Sequence[str] | None = None, history_id: str = "", registry_id: str = "", state: str = "", accepted: bool | None = None, transition: str = "", trend: str = "", address: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT):
    if not isinstance(value, observatory_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatory):
        raise ValidationError("observatory query requires a typed observatory")
    value = observatory_model.observatory_from_mapping(value.to_dict())
    selected = tuple(RESOURCES if resources is None else _sequence(resources, "observatory query resources", len(RESOURCES)))
    if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected):
        raise ValidationError("observatory query resources are invalid")
    if state and state not in observatory_model.STATES or transition and transition not in observatory_model.TRANSITIONS or trend and trend not in observatory_model.TRENDS:
        raise ValidationError("observatory query filter value is unsupported")
    _label(history_id, "observatory query history filter")
    _label(registry_id, "observatory query registry filter")
    _label(text, "observatory query text filter") if not text else _text(text, "observatory query text filter", 1024)
    _address(address, "observatory query address filter")
    _count(offset, "observatory query offset", MAX_TOTAL_COUNT)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("observatory query limit is outside its bound")
    all_rows = _all_rows(value)
    selected_rows = tuple(row for row in all_rows if row.resource in selected)
    matched = tuple(row for row in selected_rows if _matches(row, history_id=history_id, registry_id=registry_id, state=state, accepted=accepted, transition=transition, trend=trend, address=address, text=text))
    page = tuple(_renumber_row(row, index) for index, row in enumerate(matched[offset:offset + limit], offset + 1))
    body = {"observatory_address": value.content_address, "resources": tuple(item for item in RESOURCES if item in selected), "history_id_filter": history_id, "registry_id_filter": registry_id, "state_filter": state, "accepted_filter": accepted, "transition_filter": transition, "trend_filter": trend, "address_filter": address, "text_filter": text, "offset": offset, "limit": limit, "total_count": len(selected_rows), "matched_count": len(matched), "returned_count": len(page), "rows": page, "content_address": QUERY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQuery.from_mapping(value)


def query_json(value: Any) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: Any) -> str:
    value = query_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_query_markdown(value: Any) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Comparison Query Snapshot Registry History Observatory Query", "", f"Observatory: {value.observatory_address}", f"Resources: {', '.join(value.resources)}", f"Rows: {value.returned_count} of {value.matched_count}", f"Address: {value.content_address}", "", "| # | resource | history | state | accepted | transition | trend |", "| ---: | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.resource} | {item.history_id} | {item.state} | {item.accepted} | {item.transition} | {item.trend} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    integer_fields = {"ordinal", "member_ordinal", "snapshot_ordinal", "snapshot_count", "entry_count", "ready_count", "blocked_count", "accepted_count", "rejected_count", "total_query_rows", "matched_query_rows", "returned_query_rows"}
    properties = {field: {"type": "integer", "minimum": 0} if field in integer_fields else {"type": ["boolean", "null"]} if field == "accepted" else {"enum": list(RESOURCES)} if field == "resource" else {"enum": list(observatory_model.STATES)} if field == "state" else {"enum": list(observatory_model.TRANSITIONS)} if field == "transition" else {"enum": list(observatory_model.TRENDS)} if field == "trend" else {"type": "string"} for field in ROW_FIELDS}
    properties["ordinal"]["minimum"] = 1
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": properties}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"observatory_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "history_id_filter": {"type": "string"}, "registry_id_filter": {"type": "string"}, "state_filter": {"type": "string"}, "accepted_filter": {"type": ["boolean", "null"]}, "transition_filter": {"type": "string"}, "trend_filter": {"type": "string"}, "address_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": list(RESOURCES), "max_limit": MAX_LIMIT, "max_total_count": MAX_TOTAL_COUNT, "features": ["summary and member resources", "state and trend partitions", "transition-kind partitions", "bounded identity and address filters", "deterministic pagination", "row content addresses", "JSON CSV and Markdown projections"]}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_observatory", "query_schema", "render_query_markdown", "row_schema"]

