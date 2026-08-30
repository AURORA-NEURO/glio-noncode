"""Bounded inspection projections for policy registry observatory archives.

The query reads the addressed archive envelope and its fixed ZIP receipts
without requiring extraction.  Loaded archives additionally expose their
nested observatory members and transitions.  Every returned row is ordered,
bounded, value-free, and independently addressable so a receiving system can
inspect a handoff before accepting it into a larger workflow.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory as observatory_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = archive_model.VERSION + "-query-v1"
BOUNDARY = archive_model.BOUNDARY + "_query"
QUERY_PREFIX = archive_model.ARCHIVE_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
FILE_HASH_PREFIX = archive_model.ARTIFACT_PREFIX + "-file"
RESOURCES = ("summary", "manifest", "artifacts", "files", "observatory", "members", "transitions")
MAX_LIMIT = 128
MAX_TOTAL_COUNT = 2 + len(archive_model.FILES) + 1 + observatory_model.MAX_MEMBERS + observatory_model.MAX_TRANSITIONS
ROW_FIELDS = ("resource", "ordinal", "artifact_ordinal", "name", "size", "hash", "archive_id", "version", "boundary", "observatory_id", "observatory_address", "archive_size", "member_ordinal", "history_id", "registry_id", "transition_ordinal", "transition", "state", "decision", "accepted", "release_ready", "trend", "content_address")
QUERY_FIELDS = ("archive_address", "resources", "name_filter", "hash_filter", "observatory_id_filter", "history_id_filter", "state_filter", "decision_filter", "accepted_filter", "release_ready_filter", "transition_filter", "trend_filter", "text_filter", "offset", "limit", "total_count", "matched_count", "returned_count", "rows", "content_address")


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
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _state(value: Any, field: str) -> str:
    value = _label(value, field)
    if value and value not in set(observatory_model.STATES) | set(observatory_model.history_model.STATES):
        raise ValidationError(f"{field} is unsupported")
    return value


def _decision(value: Any, field: str) -> str:
    value = _label(value, field)
    if value and value not in set(observatory_model.DECISIONS) | set(observatory_model.history_model.DECISIONS):
        raise ValidationError(f"{field} is unsupported")
    return value


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow:
    """One addressed row in an archive query result."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, artifact_ordinal: int, name: str, size: int, hash: str, archive_id: str, version: str, boundary: str, observatory_id: str, observatory_address: str, archive_size: int, member_ordinal: int, history_id: str, registry_id: str, transition_ordinal: int, transition: str, state: str, decision: str, accepted: bool | None, release_ready: bool | None, trend: str, content_address: str) -> None:
        self.resource = _label(resource, "archive query row resource", required=True)
        if self.resource not in RESOURCES:
            raise ValidationError("archive query row resource is unsupported")
        self.ordinal = _count(ordinal, "archive query row ordinal", MAX_TOTAL_COUNT)
        if self.ordinal < 1:
            raise ValidationError("archive query row ordinal must be positive")
        self.artifact_ordinal = _count(artifact_ordinal, "archive query row artifact ordinal", len(archive_model.ARCHIVE_PAYLOAD_FILES))
        self.name = _text(name, "archive query row name", 256)
        if self.name and self.name not in archive_model.FILES:
            raise ValidationError("archive query row name is not an archive member")
        self.size = _count(size, "archive query row size", archive_model.MAX_ARCHIVE_BYTES)
        self.hash = _address(hash, "archive query row hash", required=False)
        self.archive_id = _label(archive_id, "archive query row archive ID")
        self.version = _text(version, "archive query row version")
        self.boundary = _label(boundary, "archive query row boundary")
        self.observatory_id = _label(observatory_id, "archive query row observatory ID")
        self.observatory_address = _address(observatory_address, "archive query row observatory address", observatory_model.OBSERVATORY_PREFIX)
        self.archive_size = _count(archive_size, "archive query row archive size", archive_model.MAX_ARCHIVE_BYTES)
        self.member_ordinal = _count(member_ordinal, "archive query row member ordinal", observatory_model.MAX_MEMBERS)
        self.history_id = _label(history_id, "archive query row history ID")
        self.registry_id = _label(registry_id, "archive query row registry ID")
        self.transition_ordinal = _count(transition_ordinal, "archive query row transition ordinal", observatory_model.MAX_TRANSITIONS)
        self.transition = _label(transition, "archive query row transition")
        if self.transition and self.transition not in observatory_model.TRANSITIONS:
            raise ValidationError("archive query row transition is unsupported")
        self.state = _state(state, "archive query row state")
        self.decision = _decision(decision, "archive query row decision")
        self.accepted = _bool_or_none(accepted, "archive query row acceptance")
        self.release_ready = _bool_or_none(release_ready, "archive query row readiness")
        self.trend = _label(trend, "archive query row trend")
        if self.trend and self.trend not in observatory_model.TRENDS:
            raise ValidationError("archive query row trend is unsupported")
        self.content_address = _address(content_address, "archive query row address", ROW_PREFIX)
        if not _public(self.to_dict()):
            raise ValidationError("archive query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("archive query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "archive query row")
        _strict(value, set(cls.FIELDS), "archive query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow):
        raise ValidationError("archive query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery:
    """A bounded, addressed archive query result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, archive_address: str, resources: Sequence[str], name_filter: str, hash_filter: str, observatory_id_filter: str, history_id_filter: str, state_filter: str, decision_filter: str, accepted_filter: bool | None, release_ready_filter: bool | None, transition_filter: str, trend_filter: str, text_filter: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, rows: Sequence[Any], content_address: str) -> None:
        self.archive_address = _address(archive_address, "archive query archive address", archive_model.ARCHIVE_PREFIX, required=True)
        resources = _sequence(resources, "archive query resources", len(RESOURCES))
        if not resources or len(set(resources)) != len(resources) or any(item not in RESOURCES for item in resources):
            raise ValidationError("archive query resources are invalid")
        self.resources = tuple(item for item in RESOURCES if item in resources)
        self.name_filter = _text(name_filter, "archive query name filter", 256)
        if self.name_filter and self.name_filter not in archive_model.FILES:
            raise ValidationError("archive query name filter is unsupported")
        self.hash_filter = _address(hash_filter, "archive query hash filter", required=False)
        self.observatory_id_filter = _label(observatory_id_filter, "archive query observatory filter")
        self.history_id_filter = _label(history_id_filter, "archive query history filter")
        self.state_filter = _state(state_filter, "archive query state filter")
        self.decision_filter = _decision(decision_filter, "archive query decision filter")
        self.accepted_filter = _bool_or_none(accepted_filter, "archive query acceptance filter")
        self.release_ready_filter = _bool_or_none(release_ready_filter, "archive query readiness filter")
        self.transition_filter = _label(transition_filter, "archive query transition filter")
        if self.transition_filter and self.transition_filter not in observatory_model.TRANSITIONS:
            raise ValidationError("archive query transition filter is unsupported")
        self.trend_filter = _label(trend_filter, "archive query trend filter")
        if self.trend_filter and self.trend_filter not in observatory_model.TRENDS:
            raise ValidationError("archive query trend filter is unsupported")
        self.text_filter = _text(text_filter, "archive query text filter", 1024)
        self.offset = _count(offset, "archive query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "archive query limit", MAX_LIMIT)
        if self.limit < 1:
            raise ValidationError("archive query limit must be positive")
        self.total_count = _count(total_count, "archive query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "archive query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "archive query returned count", MAX_LIMIT)
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow.from_mapping(item) for item in _sequence(rows, "archive query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "archive query address", QUERY_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.returned_count > max(0, self.matched_count - self.offset) or tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("archive query counts or pagination do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("archive query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("archive query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_address": self.archive_address, "resources": self.resources, "name_filter": self.name_filter, "hash_filter": self.hash_filter, "observatory_id_filter": self.observatory_id_filter, "history_id_filter": self.history_id_filter, "state_filter": self.state_filter, "decision_filter": self.decision_filter, "accepted_filter": self.accepted_filter, "release_ready_filter": self.release_ready_filter, "transition_filter": self.transition_filter, "trend_filter": self.trend_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "archive query")
        _strict(value, set(cls.FIELDS), "archive query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery):
        raise ValidationError("archive query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(resource: str, ordinal: int, archive: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive, **updates: Any) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow:
    body = {"resource": resource, "ordinal": ordinal, "artifact_ordinal": 0, "name": "", "size": 0, "hash": "", "archive_id": archive.archive_id, "version": archive.version, "boundary": archive.boundary, "observatory_id": archive.observatory_id, "observatory_address": archive.observatory_address, "archive_size": archive.archive_size, "member_ordinal": 0, "history_id": "", "registry_id": "", "transition_ordinal": 0, "transition": "", "state": "", "decision": "", "accepted": None, "release_ready": None, "trend": "", "content_address": ROW_PREFIX + ":pending"}
    body.update(updates)
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow(**(body | {"content_address": address_row(provisional)}))


def _renumber_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow:
    body = value.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow(**(body | {"content_address": address_row(provisional)}))


def _file_receipts(value: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> tuple[tuple[str, int, str], ...]:
    manifest = canonical_bytes(archive_model.manifest_document(value))
    rows = [(archive_model.ARCHIVE_MANIFEST_NAME, len(manifest), hash_bytes(manifest, prefix=FILE_HASH_PREFIX))]
    rows.extend((item.name, item.size, item.hash) for item in value.artifacts)
    return tuple(rows)


def _all_rows(value: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow, ...]:
    rows: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow] = []
    ordinal = 1
    rows.append(_row("summary", ordinal, value))
    ordinal += 1
    manifest_name, manifest_size, manifest_hash = _file_receipts(value)[0]
    rows.append(_row("manifest", ordinal, value, artifact_ordinal=0, name=manifest_name, size=manifest_size, hash=manifest_hash))
    ordinal += 1
    for item in value.artifacts:
        rows.append(_row("artifacts", ordinal, value, artifact_ordinal=item.index + 1, name=item.name, size=item.size, hash=item.hash))
        ordinal += 1
    for index, (name, size, receipt) in enumerate(_file_receipts(value)):
        rows.append(_row("files", ordinal, value, artifact_ordinal=index if index else 0, name=name, size=size, hash=receipt))
        ordinal += 1
    nested = value.observatory
    if nested is not None:
        rows.append(_row("observatory", ordinal, value, state=nested.state, decision=nested.decision, accepted=nested.accepted, release_ready=nested.release_ready, trend="stable" if nested.changed_count == 0 else "changed"))
        ordinal += 1
        for item in nested.members:
            rows.append(_row("members", ordinal, value, member_ordinal=item.ordinal, history_id=item.history_id, registry_id=item.registry_id, state=item.latest_state, decision=item.latest_decision, accepted=item.latest_accepted, release_ready=item.latest_release_ready, trend=item.trend))
            ordinal += 1
        for item in nested.transitions:
            rows.append(_row("transitions", ordinal, value, artifact_ordinal=0, member_ordinal=item.member_ordinal, history_id=item.history_id, registry_id=item.registry_id, transition_ordinal=item.ordinal, transition=item.transition, state=item.state, decision=item.decision, accepted=item.accepted, release_ready=item.release_ready))
            ordinal += 1
    return tuple(rows)


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow, *, name: str, hash: str, observatory_id: str, history_id: str, state: str, decision: str, accepted: bool | None, release_ready: bool | None, transition: str, trend: str, text: str) -> bool:
    if name and row.name != name or hash and row.hash != hash or observatory_id and row.observatory_id != observatory_id or history_id and row.history_id != history_id or state and row.state != state or decision and row.decision != decision or accepted is not None and row.accepted != accepted or release_ready is not None and row.release_ready != release_ready or transition and row.transition != transition or trend and row.trend != trend:
        return False
    if text:
        haystack = " ".join(str(row.to_dict()[field]) for field in ROW_FIELDS if field != "content_address").casefold()
        return text.casefold() in haystack
    return True


def query_archive(value: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive, *, resources: Sequence[str] | None = None, name: str = "", hash: str = "", observatory_id: str = "", history_id: str = "", state: str = "", decision: str = "", accepted: bool | None = None, release_ready: bool | None = None, transition: str = "", trend: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery:
    if not isinstance(value, archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive):
        raise ValidationError("archive query requires a typed archive")
    value = archive_model.verify_archive(value)
    selected = tuple(RESOURCES if resources is None else _sequence(resources, "archive query resources", len(RESOURCES)))
    if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected):
        raise ValidationError("archive query resources are invalid")
    _text(name, "archive query name filter", 256)
    _address(hash, "archive query hash filter")
    _label(observatory_id, "archive query observatory filter")
    _label(history_id, "archive query history filter")
    _state(state, "archive query state filter")
    _decision(decision, "archive query decision filter")
    _label(transition, "archive query transition filter")
    _label(trend, "archive query trend filter")
    _text(text, "archive query text filter", 1024)
    _count(offset, "archive query offset", MAX_TOTAL_COUNT)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("archive query limit is outside its bound")
    all_rows = _all_rows(value)
    selected_rows = tuple(row for row in all_rows if row.resource in selected)
    matched = tuple(row for row in selected_rows if _matches(row, name=name, hash=hash, observatory_id=observatory_id, history_id=history_id, state=state, decision=decision, accepted=accepted, release_ready=release_ready, transition=transition, trend=trend, text=text))
    page = tuple(_renumber_row(row, index) for index, row in enumerate(matched[offset:offset + limit], offset + 1))
    body = {"archive_address": value.content_address, "resources": tuple(item for item in RESOURCES if item in selected), "name_filter": name, "hash_filter": hash, "observatory_id_filter": observatory_id, "history_id_filter": history_id, "state_filter": state, "decision_filter": decision, "accepted_filter": accepted, "release_ready_filter": release_ready, "transition_filter": transition, "trend_filter": trend, "text_filter": text, "offset": offset, "limit": limit, "total_count": len(selected_rows), "matched_count": len(matched), "returned_count": len(page), "rows": page, "content_address": QUERY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery) -> str:
    value = query_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Policy Package Registry Observatory Archive Query", "", f"- Archive: `{value.archive_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Rows: `{value.returned_count}` of `{value.matched_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | member | name | bytes | state | decision |", "| ---: | --- | ---: | --- | ---: | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.member_ordinal}` | `{item.name}` | `{item.size}` | `{item.state}` | `{item.decision}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 1}, "artifact_ordinal": {"type": "integer", "minimum": 0}, "name": {"type": "string"}, "size": {"type": "integer", "minimum": 0}, "hash": {"type": "string"}, "archive_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "observatory_id": {"type": "string"}, "observatory_address": {"type": "string"}, "archive_size": {"type": "integer", "minimum": 0}, "member_ordinal": {"type": "integer", "minimum": 0}, "history_id": {"type": "string"}, "registry_id": {"type": "string"}, "transition_ordinal": {"type": "integer", "minimum": 0}, "transition": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": ["boolean", "null"]}, "release_ready": {"type": ["boolean", "null"]}, "trend": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"archive_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "name_filter": {"type": "string"}, "hash_filter": {"type": "string"}, "observatory_id_filter": {"type": "string"}, "history_id_filter": {"type": "string"}, "state_filter": {"type": "string"}, "decision_filter": {"type": "string"}, "accepted_filter": {"type": ["boolean", "null"]}, "release_ready_filter": {"type": ["boolean", "null"]}, "transition_filter": {"type": "string"}, "trend_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": list(RESOURCES), "max_limit": MAX_LIMIT, "max_total_count": MAX_TOTAL_COUNT, "features": ["manifest-only archive inspection", "artifact and file byte receipts", "nested observatory member and transition projections", "bounded exact filters", "deterministic pagination", "row content addresses", "JSON CSV and Markdown projections"]}


__all__ = ["BOUNDARY", "FILE_HASH_PREFIX", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow", "address_query", "address_row", "capabilities", "query_archive", "query_csv", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
