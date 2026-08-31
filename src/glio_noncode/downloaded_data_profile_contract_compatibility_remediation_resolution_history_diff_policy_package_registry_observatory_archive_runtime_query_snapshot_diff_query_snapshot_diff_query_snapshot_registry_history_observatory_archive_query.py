"""Bounded queries over comparison-query history-observatory archives."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = archive_model.VERSION + "-query-v1"
BOUNDARY = archive_model.BOUNDARY + "_query"
QUERY_PREFIX = archive_model.ARCHIVE_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "archive", "artifacts", "observatory", "members", "histories", "transitions", "states", "trends")
MAX_LIMIT = 128
MAX_MEMBERS = observatory_model.MAX_MEMBERS
MAX_TRANSITIONS = observatory_model.MAX_TRANSITIONS
MAX_QUERY_ITEMS = 2 + len(archive_model.ARCHIVE_PAYLOAD_FILES) + 1 + (4 * MAX_MEMBERS) + MAX_TRANSITIONS
ROW_FIELDS = (
    "resource", "ordinal", "archive_id", "archive_address", "archive_size",
    "artifact_ordinal", "artifact_name", "artifact_size", "artifact_hash",
    "observatory_id", "observatory_address", "member_ordinal", "history_id",
    "registry_id", "snapshot_ordinal", "transition", "state", "accepted",
    "trend", "registry_address", "previous_registry_address", "entry_count",
    "ready_count", "blocked_count", "total_query_rows", "content_address",
)
QUERY_FIELDS = (
    "archive_address", "resources", "name_filter", "hash_filter",
    "observatory_id_filter", "history_id_filter", "registry_id_filter",
    "state_filter", "accepted_filter", "transition_filter", "trend_filter",
    "address_filter", "text_filter", "offset", "limit", "total_count",
    "matched_count", "returned_count", "rows", "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = False) -> str:
    value = _text(value, field, 4096, required=required)
    if value and (":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} must be a public address")
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
    private_markers = ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\")
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return not any(marker in value.casefold() for marker in private_markers)
    return value is None or isinstance(value, (bool, int, float))


def _resources(value: Any) -> tuple[str, ...]:
    values = tuple(_label(item, "query resource", required=True) for item in _sequence(value, "query resources", len(RESOURCES)))
    if not values or len(set(values)) != len(values) or any(item not in RESOURCES for item in values) or tuple(sorted(values, key=RESOURCES.index)) != values:
        raise ValidationError("query resources must be a unique canonical subsequence")
    return values


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow:
    """One addressed archive inspection row."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, archive_id: str, archive_address: str, archive_size: int, artifact_ordinal: int, artifact_name: str, artifact_size: int, artifact_hash: str, observatory_id: str, observatory_address: str, member_ordinal: int, history_id: str, registry_id: str, snapshot_ordinal: int, transition: str, state: str, accepted: bool | None, trend: str, registry_address: str, previous_registry_address: str, entry_count: int, ready_count: int, blocked_count: int, total_query_rows: int, content_address: str) -> None:
        self.resource = _label(resource, "query row resource", required=True)
        if self.resource not in RESOURCES:
            raise ValidationError("query row resource is unsupported")
        self.ordinal = _count(ordinal, "query row ordinal", MAX_QUERY_ITEMS)
        if self.ordinal == 0:
            raise ValidationError("query row ordinal must be positive")
        self.archive_id = _label(archive_id, "query archive ID", required=True)
        self.archive_address = _address(archive_address, "query archive address", archive_model.ARCHIVE_PREFIX, required=True)
        self.archive_size = _count(archive_size, "query archive size", archive_model.MAX_ARCHIVE_BYTES)
        self.artifact_ordinal = _count(artifact_ordinal, "query artifact ordinal", len(archive_model.FILES))
        self.artifact_name = _text(artifact_name, "query artifact name", 256)
        if self.artifact_name and self.artifact_name not in archive_model.ARCHIVE_PAYLOAD_FILES:
            raise ValidationError("query artifact name is unsupported")
        self.artifact_size = _count(artifact_size, "query artifact size", archive_model.MAX_ARCHIVE_BYTES)
        self.artifact_hash = _address(artifact_hash, "query artifact hash", archive_model.ARTIFACT_PREFIX)
        self.observatory_id = _label(observatory_id, "query observatory ID")
        self.observatory_address = _address(observatory_address, "query observatory address", observatory_model.OBSERVATORY_PREFIX)
        self.member_ordinal = _count(member_ordinal, "query member ordinal", MAX_MEMBERS)
        self.history_id = _label(history_id, "query history ID")
        self.registry_id = _label(registry_id, "query registry ID")
        self.snapshot_ordinal = _count(snapshot_ordinal, "query snapshot ordinal", MAX_TRANSITIONS)
        self.transition = _label(transition, "query transition")
        if self.transition and self.transition not in observatory_model.TRANSITIONS:
            raise ValidationError("query transition is unsupported")
        self.state = _label(state, "query state")
        if self.state and self.state not in observatory_model.STATES:
            raise ValidationError("query state is unsupported")
        self.accepted = _bool_or_none(accepted, "query acceptance")
        self.trend = _label(trend, "query trend")
        if self.trend and self.trend not in observatory_model.TRENDS:
            raise ValidationError("query trend is unsupported")
        self.registry_address = _address(registry_address, "query registry address", observatory_model.history_model.registry_model.REGISTRY_PREFIX)
        self.previous_registry_address = _address(previous_registry_address, "query previous registry address", observatory_model.history_model.registry_model.REGISTRY_PREFIX)
        self.entry_count = _count(entry_count, "query entry count", MAX_TRANSITIONS)
        self.ready_count = _count(ready_count, "query ready count", MAX_TRANSITIONS)
        self.blocked_count = _count(blocked_count, "query blocked count", MAX_TRANSITIONS)
        self.total_query_rows = _count(total_query_rows, "query total rows", observatory_model.MAX_TOTAL_ROWS)
        self.content_address = _address(content_address, "query row address", ROW_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "archive query row")
        _strict(value, set(cls.FIELDS), "archive query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow):
        raise ValidationError("query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQuery:
    """A bounded, replayable query over archive and nested observatory rows."""

    FIELDS = QUERY_FIELDS

    def __init__(self, archive_address: str, resources: Sequence[str], name_filter: str, hash_filter: str, observatory_id_filter: str, history_id_filter: str, registry_id_filter: str, state_filter: str, accepted_filter: bool | None, transition_filter: str, trend_filter: str, address_filter: str, text_filter: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, rows: Sequence[Any], content_address: str) -> None:
        self.archive_address = _address(archive_address, "query archive address", archive_model.ARCHIVE_PREFIX, required=True)
        self.resources = _resources(resources)
        for attribute, value in (("name_filter", name_filter), ("hash_filter", hash_filter), ("observatory_id_filter", observatory_id_filter), ("history_id_filter", history_id_filter), ("registry_id_filter", registry_id_filter), ("state_filter", state_filter), ("transition_filter", transition_filter), ("trend_filter", trend_filter), ("address_filter", address_filter), ("text_filter", text_filter)):
            setattr(self, attribute, _text(value, attribute, 4096))
        self.accepted_filter = _bool_or_none(accepted_filter, "accepted filter")
        self.offset = _count(offset, "query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "query limit", MAX_LIMIT)
        if self.limit == 0:
            raise ValidationError("query limit must be positive")
        self.total_count = _count(total_count, "query total count", MAX_QUERY_ITEMS)
        self.matched_count = _count(matched_count, "query matched count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "query returned count", MAX_LIMIT)
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow.from_mapping(item) for item in _sequence(rows, "query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "query content address", QUERY_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.offset > self.total_count:
            raise ValidationError("query counts do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("query row ordinals are not contiguous")
        if any(item.resource not in self.resources or item.archive_address != self.archive_address for item in self.rows):
            raise ValidationError("query rows do not belong to the query")
        if not _public(self.to_dict()):
            raise ValidationError("query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_address": self.archive_address, "resources": self.resources, "name_filter": self.name_filter, "hash_filter": self.hash_filter, "observatory_id_filter": self.observatory_id_filter, "history_id_filter": self.history_id_filter, "registry_id_filter": self.registry_id_filter, "state_filter": self.state_filter, "accepted_filter": self.accepted_filter, "transition_filter": self.transition_filter, "trend_filter": self.trend_filter, "address_filter": self.address_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "archive query")
        _strict(value, set(cls.FIELDS), "archive query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQuery):
        raise ValidationError("query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, archive: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchive, **updates: Any):
    if archive.observatory is None:
        raise ValidationError("archive payload is required for nested observatory queries")
    observatory = archive.observatory
    body = {
        "resource": resource, "ordinal": ordinal, "archive_id": archive.archive_id,
        "archive_address": archive.content_address, "archive_size": archive.archive_size,
        "artifact_ordinal": 0, "artifact_name": "", "artifact_size": 0, "artifact_hash": "",
        "observatory_id": observatory.observatory_id, "observatory_address": observatory.content_address,
        "member_ordinal": 0, "history_id": "", "registry_id": "", "snapshot_ordinal": 0,
        "transition": "", "state": observatory.state, "accepted": observatory.accepted,
        "trend": "", "registry_address": "", "previous_registry_address": "",
        "entry_count": observatory.total_snapshot_count, "ready_count": observatory.ready_count,
        "blocked_count": observatory.blocked_count, "total_query_rows": observatory.total_query_rows,
        "content_address": ROW_PREFIX + ":pending",
    }
    body.update(updates)
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow(**(body | {"content_address": address_row(provisional)}))


def _member_row(resource: str, ordinal: int, archive: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchive, member: Any):
    return _row(resource, ordinal, archive, member_ordinal=member.ordinal, history_id=member.history_id, registry_id=member.registry_id, state=member.latest_state, accepted=member.latest_accepted, trend=member.trend, registry_address=member.latest_registry_address, entry_count=member.latest_entry_count, ready_count=member.latest_ready_count, blocked_count=member.latest_blocked_count, total_query_rows=member.latest_total_query_rows)


def _transition_row(ordinal: int, archive: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchive, transition: Any):
    return _row("transitions", ordinal, archive, member_ordinal=transition.member_ordinal, history_id=transition.history_id, registry_id=transition.registry_id, snapshot_ordinal=transition.snapshot_ordinal, transition=transition.transition, state=transition.state, accepted=transition.accepted, registry_address=transition.registry_address, previous_registry_address=transition.previous_registry_address, entry_count=transition.entry_count, ready_count=transition.ready_count, blocked_count=transition.blocked_count, total_query_rows=transition.total_query_rows)


def _all_rows(value: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchive, resources: Sequence[str]) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow, ...]:
    if value.observatory is None:
        raise ValidationError("archive payload is required for nested observatory queries")
    rows: list[Any] = []
    for resource in resources:
        if resource == "summary":
            rows.append(_row(resource, len(rows) + 1, value))
        elif resource == "archive":
            rows.append(_row(resource, len(rows) + 1, value))
        elif resource == "artifacts":
            for index, item in enumerate(value.artifacts):
                rows.append(_row(resource, len(rows) + 1, value, artifact_ordinal=index, artifact_name=item.name, artifact_size=item.size, artifact_hash=item.hash))
        elif resource == "observatory":
            rows.append(_row(resource, len(rows) + 1, value, entry_count=value.observatory.total_snapshot_count, ready_count=value.observatory.ready_count, blocked_count=value.observatory.blocked_count, total_query_rows=value.observatory.total_query_rows))
        elif resource in {"members", "histories", "states", "trends"}:
            for member in value.observatory.members:
                rows.append(_member_row(resource, len(rows) + 1, value, member))
        elif resource == "transitions":
            for transition in value.observatory.transitions:
                rows.append(_transition_row(len(rows) + 1, value, transition))
    return tuple(rows)


def _renumber(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow, ordinal: int):
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow(**(body | {"content_address": address_row(provisional)}))


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow, *, name: str, hash: str, observatory_id: str, history_id: str, registry_id: str, state: str, accepted: bool | None, transition: str, trend: str, address: str, text: str) -> bool:
    if name and row.artifact_name != name:
        return False
    if hash and row.artifact_hash != hash:
        return False
    if observatory_id and row.observatory_id != observatory_id:
        return False
    if history_id and row.history_id != history_id:
        return False
    if registry_id and row.registry_id != registry_id:
        return False
    if state and row.state != state:
        return False
    if accepted is not None and row.accepted != accepted:
        return False
    if transition and row.transition != transition:
        return False
    if trend and row.trend != trend:
        return False
    if address and address not in {row.content_address, row.archive_address, row.observatory_address, row.artifact_hash, row.registry_address, row.previous_registry_address}:
        return False
    return not text or text.casefold() in canonical_json(row.to_dict()).casefold()


def query_archive(value: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchive, *, resources: Sequence[str] | None = None, name: str = "", hash: str = "", observatory_id: str = "", history_id: str = "", registry_id: str = "", state: str = "", accepted: bool | None = None, transition: str = "", trend: str = "", address: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT):
    if not isinstance(value, archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchive):
        raise ValidationError("archive query requires a typed archive")
    archive_model.verify_archive(value)
    selected = _resources(RESOURCES if resources is None else resources)
    rows = _all_rows(value, selected)
    filtered = tuple(item for item in rows if _matches(item, name=name, hash=hash, observatory_id=observatory_id, history_id=history_id, registry_id=registry_id, state=state, accepted=accepted, transition=transition, trend=trend, address=address, text=text))
    page = tuple(_renumber(item, index + 1) for index, item in enumerate(filtered[offset:offset + limit]))
    body = {"archive_address": value.content_address, "resources": selected, "name_filter": name, "hash_filter": hash, "observatory_id_filter": observatory_id, "history_id_filter": history_id, "registry_id_filter": registry_id, "state_filter": state, "accepted_filter": accepted, "transition_filter": transition, "trend_filter": trend, "address_filter": address, "text_filter": text, "offset": offset, "limit": limit, "total_count": len(rows), "matched_count": len(filtered), "returned_count": len(page), "rows": page}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQuery.from_mapping(value)


def query_json(value) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow(row.to_dict())
    return stream.getvalue()


def render_query_markdown(value) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Comparison-query history observatory archive query", "", f"- Archive: {value.archive_address}", f"- Resources: {', '.join(value.resources)}", f"- Rows: {value.returned_count}/{value.matched_count}", f"- Query address: {value.content_address}", "", "| # | resource | history | transition | state | accepted | trend | address |", "| ---: | --- | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | {row.resource} | {row.history_id} | {row.transition} | {row.state} | {row.accepted} | {row.trend} | {row.content_address} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory archive query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 1}, "archive_id": {"type": "string"}, "archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "archive_size": {"type": "integer", "minimum": 0}, "artifact_ordinal": {"type": "integer", "minimum": 0}, "artifact_name": {"type": "string"}, "artifact_size": {"type": "integer", "minimum": 0}, "artifact_hash": {"type": "string"}, "observatory_id": {"type": "string"}, "observatory_address": {"type": "string"}, "member_ordinal": {"type": "integer", "minimum": 0}, "history_id": {"type": "string"}, "registry_id": {"type": "string"}, "snapshot_ordinal": {"type": "integer", "minimum": 0}, "transition": {"type": "string"}, "state": {"type": "string"}, "accepted": {"type": ["boolean", "null"]}, "trend": {"type": "string"}, "registry_address": {"type": "string"}, "previous_registry_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "ready_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "total_query_rows": {"type": "integer", "minimum": 0}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    properties = {"archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "resources": {"type": "array", "items": {"type": "string", "enum": list(RESOURCES)}, "minItems": 1, "maxItems": len(RESOURCES)}, "name_filter": {"type": "string"}, "hash_filter": {"type": "string"}, "observatory_id_filter": {"type": "string"}, "history_id_filter": {"type": "string"}, "registry_id_filter": {"type": "string"}, "state_filter": {"type": "string"}, "accepted_filter": {"type": ["boolean", "null"]}, "transition_filter": {"type": "string"}, "trend_filter": {"type": "string"}, "address_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "matched_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_LIMIT}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory archive query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "filters": ["artifact name", "artifact hash", "observatory ID", "history ID", "registry ID", "state", "accepted", "transition", "trend", "address", "text", "offset", "limit"], "features": ["archive envelope rows", "embedded artifact rows", "nested observatory rows", "member and history partitions", "transition rows", "state and trend partitions", "deterministic row addresses", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "MAX_MEMBERS", "MAX_QUERY_ITEMS", "MAX_TRANSITIONS", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryRow", "VERSION", "address_query", "address_row", "capabilities", "query_archive", "query_csv", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
