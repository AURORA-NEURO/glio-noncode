"""Bounded, value-free inspection queries over runtime-query snapshot diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "items", "added", "removed", "changed", "unchanged", "field-changes")
MAX_LIMIT = 128
MAX_ITEMS = diff_model.MAX_ITEMS
MAX_TOTAL_COUNT = 1 + MAX_ITEMS * (2 + len(diff_model.SEMANTIC_ROW_FIELDS))
ROW_FIELDS = ("resource", "ordinal", "identity", "change", "field", "item_resource", "stage", "component", "name", "left_snapshot_id", "right_snapshot_id", "left_row_address", "right_row_address", "item_address", "diff_id", "direction", "state_transition", "left_accepted", "right_accepted", "count", "changed_field_count", "address", "detail", "content_address")
QUERY_FIELDS = ("diff_address", "diff_id", "version", "boundary", "resources", "change_filter", "item_resource_filter", "identity_filter", "component_filter", "field_filter", "direction_filter", "state_transition_filter", "address_filter", "text_filter", "offset", "limit", "total_count", "matched_count", "returned_count", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
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
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
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
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _direction(value: Any, field: str, *, required: bool = False) -> str:
    value = _label(value, field, required=required)
    if value and value not in diff_model.DIRECTIONS:
        raise ValidationError(f"{field} is unsupported")
    return value


def _row_identity(row: Mapping[str, Any]) -> str:
    return "|".join(str(row[field]) for field in ("resource", "stage", "component", "name"))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow:
    """One addressed projection row from a persisted snapshot diff."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, identity: str, change: str, field: str, item_resource: str, stage: str, component: str, name: str, left_snapshot_id: str, right_snapshot_id: str, left_row_address: str, right_row_address: str, item_address: str, diff_id: str, direction: str, state_transition: str, left_accepted: bool, right_accepted: bool, count: int, changed_field_count: int, address: str, detail: str, content_address: str) -> None:
        self.resource = _label(resource, "snapshot diff query row resource", required=True)
        if self.resource not in RESOURCES:
            raise ValidationError("snapshot diff query row resource is unsupported")
        self.ordinal = _count(ordinal, "snapshot diff query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.identity = _text(identity, "snapshot diff query row identity", 1024, required=False)
        self.change = _label(change, "snapshot diff query row change")
        if self.change and self.change not in diff_model.CHANGES:
            raise ValidationError("snapshot diff query row change is unsupported")
        self.field = _label(field, "snapshot diff query row field")
        if self.field and self.field not in diff_model.SEMANTIC_ROW_FIELDS:
            raise ValidationError("snapshot diff query row field is unsupported")
        self.item_resource = _label(item_resource, "snapshot diff query row item resource")
        self.stage = _label(stage, "snapshot diff query row stage")
        self.component = _label(component, "snapshot diff query row component")
        self.name = _label(name, "snapshot diff query row name")
        self.left_snapshot_id = _label(left_snapshot_id, "snapshot diff query row left snapshot ID", required=True)
        self.right_snapshot_id = _label(right_snapshot_id, "snapshot diff query row right snapshot ID", required=True)
        query_model = diff_model.snapshot_model.query_model
        self.left_row_address = _address(left_row_address, "snapshot diff query row left row address", query_model.ROW_PREFIX)
        self.right_row_address = _address(right_row_address, "snapshot diff query row right row address", query_model.ROW_PREFIX)
        self.item_address = _address(item_address, "snapshot diff query row item address", diff_model.ITEM_PREFIX)
        self.diff_id = _label(diff_id, "snapshot diff query row diff ID", required=True)
        self.direction = _direction(direction, "snapshot diff query row direction")
        self.state_transition = _label(state_transition, "snapshot diff query row state transition")
        self.left_accepted = _bool(left_accepted, "snapshot diff query row left acceptance")
        self.right_accepted = _bool(right_accepted, "snapshot diff query row right acceptance")
        self.count = _count(count, "snapshot diff query row count", MAX_TOTAL_COUNT)
        self.changed_field_count = _count(changed_field_count, "snapshot diff query row changed field count", MAX_ITEMS * len(diff_model.SEMANTIC_ROW_FIELDS))
        self.address = _address(address, "snapshot diff query row source address", required=True)
        self.detail = _text(detail, "snapshot diff query row detail", 2048, required=False)
        self.content_address = _address(content_address, "snapshot diff query row content address", ROW_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary":
            if any((self.identity, self.change, self.field, self.item_resource, self.stage, self.component, self.name, self.left_row_address, self.right_row_address, self.item_address)):
                raise ValidationError("snapshot diff summary query row has unexpected item fields")
            if not self.direction or not self.state_transition or self.address.split(":", 1)[0] != diff_model.DIFF_PREFIX:
                raise ValidationError("snapshot diff summary query row is incomplete")
        else:
            if not self.identity or not self.change or not self.item_resource or not self.item_address:
                raise ValidationError("snapshot diff item query row is incomplete")
            if self.resource == "field-changes":
                if self.change not in {"added", "removed", "changed"} or not self.field:
                    raise ValidationError("snapshot diff field query row is invalid")
            elif self.field:
                raise ValidationError("snapshot diff item query row has an unexpected field")
            elif self.resource in diff_model.CHANGES and self.change != self.resource:
                raise ValidationError("snapshot diff change resource does not replay")
            if self.changed_field_count > 0 and self.change == "unchanged":
                raise ValidationError("snapshot diff query row changed-field count does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("snapshot diff query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("snapshot diff query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot diff query row")
        _strict(value, set(cls.FIELDS), "snapshot diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow):
        raise ValidationError("snapshot diff query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery:
    """A bounded, addressed query over one verified snapshot diff."""

    FIELDS = QUERY_FIELDS

    def __init__(self, diff_address: str, diff_id: str, version: str, boundary: str, resources: Sequence[str], change_filter: str, item_resource_filter: str, identity_filter: str, component_filter: str, field_filter: str, direction_filter: str, state_transition_filter: str, address_filter: str, text_filter: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, rows: Sequence[Any], content_address: str) -> None:
        self.diff_address = _address(diff_address, "snapshot diff query diff address", diff_model.DIFF_PREFIX, required=True)
        self.diff_id = _label(diff_id, "snapshot diff query diff ID", required=True)
        self.version = _text(version, "snapshot diff query version", 512, required=True)
        self.boundary = _label(boundary, "snapshot diff query boundary", required=True)
        selected = _sequence(resources, "snapshot diff query resources", len(RESOURCES))
        if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected):
            raise ValidationError("snapshot diff query resources are invalid")
        self.resources = tuple(item for item in RESOURCES if item in selected)
        self.change_filter = _label(change_filter, "snapshot diff query change filter")
        if self.change_filter and self.change_filter not in diff_model.CHANGES:
            raise ValidationError("snapshot diff query change filter is unsupported")
        self.item_resource_filter = _label(item_resource_filter, "snapshot diff query item resource filter")
        self.identity_filter = _text(identity_filter, "snapshot diff query identity filter", 1024, required=False)
        self.component_filter = _label(component_filter, "snapshot diff query component filter")
        self.field_filter = _label(field_filter, "snapshot diff query field filter")
        if self.field_filter and self.field_filter not in diff_model.SEMANTIC_ROW_FIELDS:
            raise ValidationError("snapshot diff query field filter is unsupported")
        self.direction_filter = _direction(direction_filter, "snapshot diff query direction filter")
        self.state_transition_filter = _label(state_transition_filter, "snapshot diff query state transition filter")
        self.address_filter = _address(address_filter, "snapshot diff query address filter")
        self.text_filter = _text(text_filter, "snapshot diff query text filter", 1024, required=False)
        self.offset = _count(offset, "snapshot diff query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "snapshot diff query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "snapshot diff query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "snapshot diff query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "snapshot diff query returned count", MAX_LIMIT)
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow.from_mapping(item) for item in _sequence(rows, "snapshot diff query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "snapshot diff query address", QUERY_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("snapshot diff query version or boundary is not current")
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.returned_count > max(0, self.matched_count - self.offset):
            raise ValidationError("snapshot diff query counts or pagination do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("snapshot diff query row order does not replay")
        if any(item.diff_id != self.diff_id or item.left_snapshot_id == item.right_snapshot_id and item.resource != "summary" and not item.identity for item in self.rows):
            raise ValidationError("snapshot diff query row linkage does not replay")
        if any(item.resource not in self.resources for item in self.rows):
            raise ValidationError("snapshot diff query contains a row outside selected resources")
        if not _public(self.to_dict()):
            raise ValidationError("snapshot diff query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("snapshot diff query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "rows" else [item.to_dict() for item in self.rows] for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot diff query")
        _strict(value, set(cls.FIELDS), "snapshot diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery):
        raise ValidationError("snapshot diff query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff, resource: str, ordinal: int, *, item: Any = None, field: str = "", count: int = 0, changed_field_count: int = 0, address: str = "", detail: str = "") -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow:
    body = {"resource": resource, "ordinal": ordinal, "identity": "", "change": "", "field": field, "item_resource": "", "stage": "", "component": "", "name": "", "left_snapshot_id": value.left_snapshot_id, "right_snapshot_id": value.right_snapshot_id, "left_row_address": "", "right_row_address": "", "item_address": "", "diff_id": value.diff_id, "direction": value.direction, "state_transition": value.state_transition, "left_accepted": value.left_accepted, "right_accepted": value.right_accepted, "count": count, "changed_field_count": changed_field_count, "address": address or value.content_address, "detail": detail, "content_address": ROW_PREFIX + ":pending"}
    if item is not None:
        body.update({"identity": item.identity, "change": item.change, "item_resource": item.resource, "stage": item.stage, "component": item.component, "name": item.name, "left_row_address": item.left_row_address, "right_row_address": item.right_row_address, "item_address": item.content_address, "count": 1, "changed_field_count": len(item.changed_fields), "address": item.content_address, "detail": f"{item.change} snapshot diff item"})
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def _all_rows(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow, ...]:
    value = diff_model.diff_from_mapping(value.to_dict())
    rows: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow] = []
    ordinal = 1
    rows.append(_row(value, "summary", ordinal, count=len(value.items), changed_field_count=value.changed_field_count, address=value.content_address, detail="snapshot diff summary"))
    ordinal += 1
    for resource in RESOURCES[1:]:
        if resource == "field-changes":
            for item in value.items:
                for field in item.changed_fields:
                    rows.append(_row(value, resource, ordinal, item=item, field=field))
                    ordinal += 1
            continue
        for item in value.items:
            if resource == "items" or item.change == resource:
                rows.append(_row(value, resource, ordinal, item=item))
                ordinal += 1
    return tuple(rows)


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow, *, change: str, item_resource: str, identity: str, component: str, field: str, direction: str, state_transition: str, address: str, text: str) -> bool:
    if change and row.change != change or item_resource and row.item_resource != item_resource or identity and row.identity != identity or component and row.component != component or field and row.field != field or direction and row.direction != direction or state_transition and row.state_transition != state_transition:
        return False
    if address and address not in {row.address, row.item_address, row.left_row_address, row.right_row_address}:
        return False
    if text and text.casefold() not in " ".join(str(row.to_dict()[key]) for key in ROW_FIELDS if key != "content_address").casefold():
        return False
    return True


def query_diff(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff, *, resources: Sequence[str] | None = None, change: str = "", item_resource: str = "", identity: str = "", component: str = "", field: str = "", direction: str = "", state_transition: str = "", address: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery:
    if not isinstance(value, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff):
        raise ValidationError("snapshot diff query requires a typed diff")
    value = diff_model.diff_from_mapping(value.to_dict())
    selected = tuple(RESOURCES if resources is None else _sequence(resources, "snapshot diff query resources", len(RESOURCES)))
    if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected):
        raise ValidationError("snapshot diff query resources are invalid")
    _label(change, "snapshot diff query change filter")
    if change and change not in diff_model.CHANGES:
        raise ValidationError("snapshot diff query change filter is unsupported")
    _label(item_resource, "snapshot diff query item resource filter")
    _text(identity, "snapshot diff query identity filter", 1024, required=False)
    _label(component, "snapshot diff query component filter")
    _label(field, "snapshot diff query field filter")
    if field and field not in diff_model.SEMANTIC_ROW_FIELDS:
        raise ValidationError("snapshot diff query field filter is unsupported")
    _direction(direction, "snapshot diff query direction filter")
    _label(state_transition, "snapshot diff query state transition filter")
    _address(address, "snapshot diff query address filter")
    _text(text, "snapshot diff query text filter", 1024, required=False)
    _count(offset, "snapshot diff query offset", MAX_TOTAL_COUNT)
    _count(limit, "snapshot diff query limit", MAX_LIMIT, positive=True)
    selected_rows = tuple(row for row in _all_rows(value) if row.resource in selected)
    matched = tuple(row for row in selected_rows if _matches(row, change=change, item_resource=item_resource, identity=identity, component=component, field=field, direction=direction, state_transition=state_transition, address=address, text=text))
    page = tuple(_renumber(row, index) for index, row in enumerate(matched[offset:offset + limit], offset + 1))
    body = {"diff_address": value.content_address, "diff_id": value.diff_id, "version": VERSION, "boundary": BOUNDARY, "resources": tuple(item for item in RESOURCES if item in selected), "change_filter": change, "item_resource_filter": item_resource, "identity_filter": identity, "component_filter": component, "field_filter": field, "direction_filter": direction, "state_transition_filter": state_transition, "address_filter": address, "text_filter": text, "offset": offset, "limit": limit, "total_count": len(selected_rows), "matched_count": len(matched), "returned_count": len(page), "rows": page, "content_address": QUERY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery(**(body | {"content_address": address_query(provisional)}))


def _renumber(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow, ordinal: int):
    body = value.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery.from_mapping(value)


def verify_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery):
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery):
        raise ValidationError("snapshot diff query verification requires a typed query")
    value._validate()
    if not value.content_address.endswith(":pending") and address_query(value) != value.content_address:
        raise ValidationError("snapshot diff query address verification failed")
    return value


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery) -> str:
    return canonical_json(query_from_mapping(verify_query(value).to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery) -> str:
    value = verify_query(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow(row.to_dict())
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery) -> str:
    value = verify_query(value)
    mark = chr(96)
    lines = ["# Policy Package Registry Observatory Archive Runtime Query Snapshot Diff Query", "", f"- Diff: {mark}{value.diff_id}{mark}", f"- Resources: {mark}{', '.join(value.resources)}{mark}", f"- Rows: {mark}{value.returned_count}{mark} of {mark}{value.matched_count}{mark}", f"- Address: {mark}{value.content_address}{mark}", "", "| # | resource | identity | change | field | component |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | {mark}{row.resource}{mark} | {mark}{row.identity}{mark} | {mark}{row.change}{mark} | {mark}{row.field}{mark} | {mark}{row.component}{mark} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot diff row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 1}, "identity": {"type": "string"}, "change": {"type": "string", "enum": [""] + list(diff_model.CHANGES)}, "field": {"type": "string"}, "item_resource": {"type": "string"}, "stage": {"type": "string"}, "component": {"type": "string"}, "name": {"type": "string"}, "left_snapshot_id": {"type": "string"}, "right_snapshot_id": {"type": "string"}, "left_row_address": {"type": "string"}, "right_row_address": {"type": "string"}, "item_address": {"type": "string", "pattern": "^" + diff_model.ITEM_PREFIX + ":"}, "diff_id": {"type": "string"}, "direction": {"type": "string", "enum": [""] + list(diff_model.DIRECTIONS)}, "state_transition": {"type": "string"}, "left_accepted": {"type": "boolean"}, "right_accepted": {"type": "boolean"}, "count": {"type": "integer", "minimum": 0}, "changed_field_count": {"type": "integer", "minimum": 0}, "address": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot diff query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "diff_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "change_filter": {"type": "string", "enum": [""] + list(diff_model.CHANGES)}, "item_resource_filter": {"type": "string"}, "identity_filter": {"type": "string"}, "component_filter": {"type": "string"}, "field_filter": {"type": "string"}, "direction_filter": {"type": "string", "enum": [""] + list(diff_model.DIRECTIONS)}, "state_transition_filter": {"type": "string"}, "address_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "change_classes": list(diff_model.CHANGES), "directions": list(diff_model.DIRECTIONS), "max_limit": MAX_LIMIT, "max_total_count": MAX_TOTAL_COUNT, "features": ["summary projection", "all-item projection", "change-class projections", "changed-field evidence projection", "exact identity/component/field/address/text filters", "deterministic pagination", "JSON CSV and Markdown projections"]}


__all__ = ["BOUNDARY", "MAX_ITEMS", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_diff", "query_schema", "render_query_markdown", "row_schema", "verify_query"]
