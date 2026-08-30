"""Bounded public queries over policy package registry histories."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry as registry_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history as history_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "entries", "ready", "decisions", "transitions")
STATES = history_model.STATES
DECISIONS = history_model.DECISIONS
TRANSITIONS = history_model.TRANSITIONS
QUERY_FIELDS = ("history_address", "version", "boundary", "resources", "resource", "registry_id", "state", "decision", "accepted", "release_ready", "transition", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")
ROW_FIELDS = ("ordinal", "resource", "identity", "registry_id", "registry_address", "entry_count", "accepted_count", "release_ready_count", "promote_count", "hold_count", "block_count", "state", "decision", "accepted", "release_ready", "transition", "detail", "content_address")
MAX_TOTAL_COUNT = 1 + 4 * history_model.MAX_ENTRIES
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


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _label(value, field)
    if ":" not in value or (prefix and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be an addressed public receipt")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} must be a bounded count")
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


def _ordered_labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not values or len(values) != len(set(values)) or any(item not in allowed for item in values) or values != tuple(sorted(values, key=allowed.index)):
        raise ValidationError(f"{field} must contain unique values in canonical order")
    return values


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, registry_id: str, registry_address: str, entry_count: int, accepted_count: int, release_ready_count: int, promote_count: int, hold_count: int, block_count: int, state: str, decision: str, accepted: bool, release_ready: bool, transition: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "registry history query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("registry history query row resource is unsupported")
        self.identity = _label(identity, "registry history query row identity")
        self.registry_id = _label(registry_id, "registry history query row registry ID")
        self.registry_address = _address(registry_address, "registry history query row registry address", registry_model.REGISTRY_PREFIX)
        self.entry_count = _count(entry_count, "registry history query row entry count", registry_model.MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "registry history query row accepted count", registry_model.MAX_ENTRIES)
        self.release_ready_count = _count(release_ready_count, "registry history query row release-ready count", registry_model.MAX_ENTRIES)
        self.promote_count = _count(promote_count, "registry history query row promote count", registry_model.MAX_ENTRIES)
        self.hold_count = _count(hold_count, "registry history query row hold count", registry_model.MAX_ENTRIES)
        self.block_count = _count(block_count, "registry history query row block count", registry_model.MAX_ENTRIES)
        self.state = _label(state, "registry history query row state")
        if self.state not in STATES:
            raise ValidationError("registry history query row state is unsupported")
        self.decision = _label(decision, "registry history query row decision")
        if self.decision not in DECISIONS:
            raise ValidationError("registry history query row decision is unsupported")
        self.accepted = _bool(accepted, "registry history query row acceptance")
        self.release_ready = _bool(release_ready, "registry history query row release readiness")
        self.transition = _label(transition, "registry history query row transition")
        if self.transition not in TRANSITIONS:
            raise ValidationError("registry history query row transition is unsupported")
        self.detail = _text(detail, "registry history query row detail", 1024)
        self.content_address = _address(content_address, "registry history query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.accepted_count > self.entry_count or self.release_ready_count > self.entry_count or self.promote_count + self.hold_count + self.block_count != self.entry_count:
            raise ValidationError("registry history query row counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry history query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("registry history query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow:
        value = _mapping(value, "registry history query row")
        _strict(value, set(cls.FIELDS), "registry history query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow):
        raise ValidationError("registry history query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, history_address: str, version: str, boundary: str, resources: Sequence[str], resource: str, registry_id: str, state: str, decision: str, accepted: bool | None, release_ready: bool | None, transition: str, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.history_address = _address(history_address, "registry history query history address", history_model.HISTORY_PREFIX)
        self.version = _text(version, "registry history query version", 512)
        self.boundary = _text(boundary, "registry history query boundary", 512)
        self.resources = _ordered_labels(resources, "registry history query resources", RESOURCES)
        self.resource = _label(resource, "registry history query resource", required=False)
        if self.resource and self.resource not in self.resources:
            raise ValidationError("registry history query resource filter is not selected")
        self.registry_id = _label(registry_id, "registry history query registry ID", required=False)
        self.state = _label(state, "registry history query state", required=False)
        if self.state and self.state not in STATES:
            raise ValidationError("registry history query state filter is unsupported")
        self.decision = _label(decision, "registry history query decision", required=False)
        if self.decision and self.decision not in DECISIONS:
            raise ValidationError("registry history query decision filter is unsupported")
        self.accepted = _optional_bool(accepted, "registry history query accepted filter")
        self.release_ready = _optional_bool(release_ready, "registry history query release-ready filter")
        self.transition = _label(transition, "registry history query transition", required=False)
        if self.transition and self.transition not in TRANSITIONS:
            raise ValidationError("registry history query transition filter is unsupported")
        self.text = _text(text, "registry history query text", 512, required=False)
        self.offset = _count(offset, "registry history query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "registry history query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "registry history query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "registry history query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "registry history query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "registry history query next offset", MAX_TOTAL_COUNT + MAX_LIMIT)
        self.truncated = _bool(truncated, "registry history query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow.from_mapping(item) for item in _sequence(rows, "registry history query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "registry history query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("registry history query version or boundary is not current")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.matched_count > self.total_count or self.returned_count > self.matched_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count) or tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)) or not _public(self.to_dict()):
            raise ValidationError("registry history query counts or rows do not replay")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("registry history query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "resource": self.resource, "registry_id": self.registry_id, "state": self.state, "decision": self.decision, "accepted": self.accepted, "release_ready": self.release_ready, "transition": self.transition, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery:
        value = _mapping(value, "registry history query")
        _strict(value, set(cls.FIELDS), "registry history query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery):
        raise ValidationError("registry history query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(ordinal: int, resource: str, identity: str, registry_id: str, registry_address: str, entry_count: int, accepted_count: int, release_ready_count: int, promote_count: int, hold_count: int, block_count: int, state: str, decision: str, accepted: bool, release_ready: bool, transition: str, detail: str) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "identity": identity, "registry_id": registry_id, "registry_address": registry_address, "entry_count": entry_count, "accepted_count": accepted_count, "release_ready_count": release_ready_count, "promote_count": promote_count, "hold_count": hold_count, "block_count": block_count, "state": state, "decision": decision, "accepted": accepted, "release_ready": release_ready, "transition": transition, "detail": detail, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow(**(body | {"content_address": address_row(provisional)}))


def _rows(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, resources: Sequence[str]) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow, ...]:
    rows: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow] = []
    ordinal = 1
    latest = value.entries[-1] if value.entries else None
    summary_address = latest.registry_address if latest else registry_model.REGISTRY_PREFIX + ":empty"
    summary_registry_id = value.registry_id or value.history_id
    for resource in resources:
        if resource == "summary":
            rows.append(_row(ordinal, resource, value.history_id, summary_registry_id, summary_address, value.latest_entry_count, value.latest_accepted_count, value.latest_release_ready_count, latest.promote_count if latest else 0, latest.hold_count if latest else 0, latest.block_count if latest else 0, value.state, value.decision, value.accepted, value.release_ready, latest.transition if latest else "initial", "latest registry history summary"))
            ordinal += 1
        elif resource == "entries":
            for item in value.entries:
                rows.append(_row(ordinal, resource, item.registry_address, item.registry_id, item.registry_address, item.entry_count, item.accepted_count, item.release_ready_count, item.promote_count, item.hold_count, item.block_count, item.state, item.decision, item.accepted, item.release_ready, item.transition, "registry history snapshot"))
                ordinal += 1
        elif resource == "ready":
            for item in value.entries:
                if item.release_ready:
                    rows.append(_row(ordinal, resource, item.registry_address, item.registry_id, item.registry_address, item.entry_count, item.accepted_count, item.release_ready_count, item.promote_count, item.hold_count, item.block_count, item.state, item.decision, item.accepted, item.release_ready, item.transition, "release-ready registry snapshot"))
                    ordinal += 1
        elif resource == "decisions":
            for item in value.entries:
                rows.append(_row(ordinal, resource, item.registry_address, item.registry_id, item.registry_address, item.entry_count, item.accepted_count, item.release_ready_count, item.promote_count, item.hold_count, item.block_count, item.state, item.decision, item.accepted, item.release_ready, item.transition, f"{item.decision} registry history decision"))
                ordinal += 1
        elif resource == "transitions":
            for item in value.entries:
                rows.append(_row(ordinal, resource, item.registry_address, item.registry_id, item.registry_address, item.entry_count, item.accepted_count, item.release_ready_count, item.promote_count, item.hold_count, item.block_count, item.state, item.decision, item.accepted, item.release_ready, item.transition, f"{item.transition} registry history transition"))
                ordinal += 1
    return tuple(rows)


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow, query: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery) -> bool:
    if query.resource and row.resource != query.resource:
        return False
    if query.registry_id and row.registry_id != query.registry_id:
        return False
    if query.state and row.state != query.state:
        return False
    if query.decision and row.decision != query.decision:
        return False
    if query.accepted is not None and row.accepted != query.accepted:
        return False
    if query.release_ready is not None and row.release_ready != query.release_ready:
        return False
    if query.transition and row.transition != query.transition:
        return False
    if query.text and query.text.casefold() not in " ".join((row.identity, row.registry_id, row.registry_address, row.state, row.decision, row.transition, row.detail)).casefold():
        return False
    return True


def query_history(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, *, resources: Sequence[str] = RESOURCES, resource: str = "", registry_id: str = "", state: str = "", decision: str = "", accepted: bool | None = None, release_ready: bool | None = None, transition: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery:
    if not isinstance(value, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
        raise ValidationError("registry history query requires a typed history")
    resources = _ordered_labels(resources, "registry history query resources", RESOURCES)
    body = {"history_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": resources, "resource": resource, "registry_id": registry_id, "state": state, "decision": decision, "accepted": accepted, "release_ready": release_ready, "transition": transition, "text": text, "offset": offset, "limit": limit, "total_count": 0, "matched_count": 0, "returned_count": 0, "next_offset": 0, "truncated": False, "rows": (), "content_address": QUERY_PREFIX + ":pending"}
    provisional_query = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery(**body)
    all_rows = _rows(value, resources)
    matching = tuple(item for item in all_rows if _matches(item, provisional_query))
    page = matching[offset:offset + limit]
    rows = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow(**(item.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"})) for ordinal, item in enumerate(page, 1))
    rows = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow(**(item.to_dict() | {"content_address": address_row(item)})) for item in rows)
    body = body | {"total_count": len(all_rows), "matched_count": len(matching), "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < len(matching), "rows": rows}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for item in value.rows:
        writer.writerow(tuple(json.dumps(item.to_dict()[field], ensure_ascii=False, sort_keys=True) if isinstance(item.to_dict()[field], (tuple, list, dict)) else item.to_dict()[field] for field in ROW_FIELDS))
    return output.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry History Query", "", f"- History: `{value.history_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | resource | registry snapshot | transition | state | ready |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.registry_address}` | `{item.transition}` | `{item.state}` | `{item.release_ready}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "registry_id": {"type": "string"}, "registry_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "release_ready_count": {"type": "integer", "minimum": 0}, "promote_count": {"type": "integer", "minimum": 0}, "hold_count": {"type": "integer", "minimum": 0}, "block_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "transition": {"enum": list(TRANSITIONS)}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"history_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "resource": {"type": "string"}, "registry_id": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": ["boolean", "null"]}, "release_ready": {"type": ["boolean", "null"]}, "transition": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": {"$ref": "#/$defs/row"}}, "content_address": {"type": "string"}}, "$defs": {"row": row_schema()}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": list(RESOURCES), "states": list(STATES), "decisions": list(DECISIONS), "transitions": list(TRANSITIONS), "max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT, "features": ["bounded history summary queries", "snapshot and readiness projections", "decision and transition projections", "registry identity and text filters", "deterministic pagination", "addressable rows", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False}}


__all__ = ["BOUNDARY", "DECISIONS", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "STATES", "TRANSITIONS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_history", "query_json", "query_schema", "render_query_markdown", "row_schema"]
