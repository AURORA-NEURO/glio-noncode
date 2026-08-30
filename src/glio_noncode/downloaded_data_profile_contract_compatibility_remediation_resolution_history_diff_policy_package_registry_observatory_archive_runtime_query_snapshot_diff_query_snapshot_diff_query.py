"""Bounded inspection queries over persisted query-snapshot comparisons."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff as diff_model
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
ROW_FIELDS = ("resource", "ordinal", "key", "identity", "change", "source_resource", "field", "left_snapshot_id", "right_snapshot_id", "left_row_address", "right_row_address", "item_address", "diff_id", "direction", "state_transition", "left_accepted", "right_accepted", "count", "changed_field_count", "address", "detail", "content_address")
QUERY_FIELDS = ("diff_address", "diff_id", "version", "boundary", "resources", "change_filter", "source_resource_filter", "key_filter", "identity_filter", "field_filter", "direction_filter", "state_transition_filter", "address_filter", "text_filter", "offset", "limit", "total_count", "matched_count", "returned_count", "rows", "content_address")


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
    return "|".join(str(row[field]) for field in ("resource", "key", "field"))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow:
    """One addressed projection row from a persisted comparison."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, key: str, identity: str, change: str, source_resource: str, field: str, left_snapshot_id: str, right_snapshot_id: str, left_row_address: str, right_row_address: str, item_address: str, diff_id: str, direction: str, state_transition: str, left_accepted: bool, right_accepted: bool, count: int, changed_field_count: int, address: str, detail: str, content_address: str) -> None:
        self.resource = _label(resource, "comparison query row resource", required=True)
        if self.resource not in RESOURCES:
            raise ValidationError("comparison query row resource is unsupported")
        self.ordinal = _count(ordinal, "comparison query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.key = _text(key, "comparison query row key", 2048, required=False)
        self.identity = _text(identity, "comparison query row identity", 1024, required=False)
        self.change = _label(change, "comparison query row change")
        if self.change and self.change not in diff_model.CHANGES:
            raise ValidationError("comparison query row change is unsupported")
        self.source_resource = _label(source_resource, "comparison query row source resource")
        if self.source_resource and self.source_resource not in diff_model.snapshot_model.query_model.RESOURCES:
            raise ValidationError("comparison query row source resource is unsupported")
        self.field = _label(field, "comparison query row field")
        if self.field and self.field not in diff_model.SEMANTIC_ROW_FIELDS:
            raise ValidationError("comparison query row field is unsupported")
        self.left_snapshot_id = _label(left_snapshot_id, "comparison query row left snapshot ID", required=True)
        self.right_snapshot_id = _label(right_snapshot_id, "comparison query row right snapshot ID", required=True)
        query_model = diff_model.snapshot_model.query_model
        self.left_row_address = _address(left_row_address, "comparison query row left row address", query_model.ROW_PREFIX)
        self.right_row_address = _address(right_row_address, "comparison query row right row address", query_model.ROW_PREFIX)
        self.item_address = _address(item_address, "comparison query row item address", diff_model.ITEM_PREFIX)
        self.diff_id = _label(diff_id, "comparison query row diff ID", required=True)
        self.direction = _direction(direction, "comparison query row direction", required=True)
        self.state_transition = _label(state_transition, "comparison query row state transition", required=True)
        self.left_accepted = _bool(left_accepted, "comparison query row left acceptance")
        self.right_accepted = _bool(right_accepted, "comparison query row right acceptance")
        self.count = _count(count, "comparison query row count", MAX_TOTAL_COUNT)
        self.changed_field_count = _count(changed_field_count, "comparison query row changed field count", MAX_ITEMS * len(diff_model.SEMANTIC_ROW_FIELDS))
        self.address = _address(address, "comparison query row source address", required=True)
        self.detail = _text(detail, "comparison query row detail", 2048, required=False)
        self.content_address = _address(content_address, "comparison query row content address", ROW_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary":
            if any((self.key, self.identity, self.change, self.source_resource, self.field, self.left_row_address, self.right_row_address, self.item_address)):
                raise ValidationError("comparison query summary row has unexpected item fields")
            if self.address.split(":", 1)[0] != diff_model.DIFF_PREFIX:
                raise ValidationError("comparison query summary row source address is invalid")
        else:
            if not self.key or not self.identity or not self.change or not self.source_resource or not self.item_address:
                raise ValidationError("comparison query item row is incomplete")
            if self.resource == "field-changes":
                if self.change not in {"added", "removed", "changed"} or not self.field:
                    raise ValidationError("comparison query field row is invalid")
            elif self.resource in diff_model.CHANGES and self.change != self.resource:
                raise ValidationError("comparison query change resource does not replay")
        if self.change == "unchanged" and self.changed_field_count:
            raise ValidationError("comparison query unchanged row has changed fields")
        if not _public(self.to_dict()):
            raise ValidationError("comparison query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("comparison query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison query row")
        _strict(value, set(cls.FIELDS), "comparison query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow):
        raise ValidationError("comparison query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery:
    """A bounded, addressed query over one verified comparison."""

    FIELDS = QUERY_FIELDS

    def __init__(self, diff_address: str, diff_id: str, version: str, boundary: str, resources: Sequence[str], change_filter: str, source_resource_filter: str, key_filter: str, identity_filter: str, field_filter: str, direction_filter: str, state_transition_filter: str, address_filter: str, text_filter: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, rows: Sequence[Any], content_address: str) -> None:
        self.diff_address = _address(diff_address, "comparison query diff address", diff_model.DIFF_PREFIX, required=True)
        self.diff_id = _label(diff_id, "comparison query diff ID", required=True)
        self.version = _text(version, "comparison query version", 512, required=True)
        self.boundary = _label(boundary, "comparison query boundary", required=True)
        selected = _sequence(resources, "comparison query resources", len(RESOURCES))
        if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected):
            raise ValidationError("comparison query resources are invalid")
        self.resources = tuple(item for item in RESOURCES if item in selected)
        self.change_filter = _label(change_filter, "comparison query change filter")
        if self.change_filter and self.change_filter not in diff_model.CHANGES:
            raise ValidationError("comparison query change filter is unsupported")
        self.source_resource_filter = _label(source_resource_filter, "comparison query source resource filter")
        if self.source_resource_filter and self.source_resource_filter not in diff_model.snapshot_model.query_model.RESOURCES:
            raise ValidationError("comparison query source resource filter is unsupported")
        self.key_filter = _text(key_filter, "comparison query key filter", 2048, required=False)
        self.identity_filter = _text(identity_filter, "comparison query identity filter", 1024, required=False)
        self.field_filter = _label(field_filter, "comparison query field filter")
        if self.field_filter and self.field_filter not in diff_model.SEMANTIC_ROW_FIELDS:
            raise ValidationError("comparison query field filter is unsupported")
        self.direction_filter = _direction(direction_filter, "comparison query direction filter")
        self.state_transition_filter = _label(state_transition_filter, "comparison query state transition filter")
        self.address_filter = _address(address_filter, "comparison query address filter")
        self.text_filter = _text(text_filter, "comparison query text filter", 1024, required=False)
        self.offset = _count(offset, "comparison query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "comparison query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "comparison query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "comparison query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "comparison query returned count", MAX_LIMIT)
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow.from_mapping(item) for item in _sequence(rows, "comparison query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "comparison query address", QUERY_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("comparison query version or boundary is not current")
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.returned_count > max(0, self.matched_count - self.offset):
            raise ValidationError("comparison query counts or pagination do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("comparison query row order does not replay")
        if any(item.diff_id != self.diff_id or item.left_snapshot_id == "" or item.right_snapshot_id == "" for item in self.rows):
            raise ValidationError("comparison query row linkage does not replay")
        if any(item.resource not in self.resources for item in self.rows):
            raise ValidationError("comparison query contains a row outside selected resources")
        if not _public(self.to_dict()):
            raise ValidationError("comparison query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("comparison query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "rows" else [item.to_dict() for item in self.rows] for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison query")
        _strict(value, set(cls.FIELDS), "comparison query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery):
        raise ValidationError("comparison query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff, resource: str, ordinal: int, *, item: Any = None, field: str = "", count: int = 0, changed_field_count: int = 0, address: str = "", detail: str = ""):
    body = {"resource": resource, "ordinal": ordinal, "key": "", "identity": "", "change": "", "source_resource": "", "field": field, "left_snapshot_id": value.left_snapshot_id, "right_snapshot_id": value.right_snapshot_id, "left_row_address": "", "right_row_address": "", "item_address": "", "diff_id": value.diff_id, "direction": value.direction, "state_transition": value.state_transition, "left_accepted": value.left_accepted, "right_accepted": value.right_accepted, "count": count, "changed_field_count": changed_field_count, "address": address or value.content_address, "detail": detail, "content_address": ROW_PREFIX + ":pending"}
    if item is not None:
        body.update({"key": item.key, "identity": item.identity, "change": item.change, "source_resource": item.resource, "field": field if resource == "field-changes" else item.field, "left_row_address": item.left_row_address, "right_row_address": item.right_row_address, "item_address": item.content_address, "count": 1, "changed_field_count": len(item.changed_fields), "address": item.content_address, "detail": f"{item.change} comparison field" if resource == "field-changes" else f"{item.change} comparison item"})
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def _all_rows(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow, ...]:
    value = diff_model.diff_from_mapping(value.to_dict())
    rows: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow] = []
    ordinal = 1
    rows.append(_row(value, "summary", ordinal, count=len(value.items), changed_field_count=value.changed_field_count, address=value.content_address, detail="comparison summary"))
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


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow, *, change: str, source_resource: str, key: str, identity: str, field: str, direction: str, state_transition: str, address: str, text: str) -> bool:
    if change and row.change != change or source_resource and row.source_resource != source_resource or key and row.key != key or identity and row.identity != identity or field and row.field != field or direction and row.direction != direction or state_transition and row.state_transition != state_transition:
        return False
    if address and address not in {row.address, row.item_address, row.left_row_address, row.right_row_address}:
        return False
    return not text or text.casefold() in " ".join(str(row.to_dict()[key]) for key in ROW_FIELDS if key != "content_address").casefold()


def query_diff(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff, *, resources: Sequence[str] | None = None, change: str = "", source_resource: str = "", key: str = "", identity: str = "", field: str = "", direction: str = "", state_transition: str = "", address: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery:
    if not isinstance(value, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff):
        raise ValidationError("comparison query requires a typed comparison")
    value = diff_model.diff_from_mapping(value.to_dict())
    selected = tuple(RESOURCES if resources is None else _sequence(resources, "comparison query resources", len(RESOURCES)))
    if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected):
        raise ValidationError("comparison query resources are invalid")
    _label(change, "comparison query change filter")
    if change and change not in diff_model.CHANGES:
        raise ValidationError("comparison query change filter is unsupported")
    _label(source_resource, "comparison query source resource filter")
    if source_resource and source_resource not in diff_model.snapshot_model.query_model.RESOURCES:
        raise ValidationError("comparison query source resource filter is unsupported")
    _text(key, "comparison query key filter", 2048, required=False)
    _text(identity, "comparison query identity filter", 1024, required=False)
    _label(field, "comparison query field filter")
    if field and field not in diff_model.SEMANTIC_ROW_FIELDS:
        raise ValidationError("comparison query field filter is unsupported")
    _direction(direction, "comparison query direction filter")
    _label(state_transition, "comparison query state transition filter")
    _address(address, "comparison query address filter")
    _text(text, "comparison query text filter", 1024, required=False)
    _count(offset, "comparison query offset", MAX_TOTAL_COUNT)
    _count(limit, "comparison query limit", MAX_LIMIT, positive=True)
    selected_rows = tuple(row for row in _all_rows(value) if row.resource in selected)
    matched = tuple(row for row in selected_rows if _matches(row, change=change, source_resource=source_resource, key=key, identity=identity, field=field, direction=direction, state_transition=state_transition, address=address, text=text))
    page = tuple(_renumber(row, index) for index, row in enumerate(matched[offset:offset + limit], offset + 1))
    body = {"diff_address": value.content_address, "diff_id": value.diff_id, "version": VERSION, "boundary": BOUNDARY, "resources": tuple(item for item in RESOURCES if item in selected), "change_filter": change, "source_resource_filter": source_resource, "key_filter": key, "identity_filter": identity, "field_filter": field, "direction_filter": direction, "state_transition_filter": state_transition, "address_filter": address, "text_filter": text, "offset": offset, "limit": limit, "total_count": len(selected_rows), "matched_count": len(matched), "returned_count": len(page), "rows": page, "content_address": QUERY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery(**(body | {"content_address": address_query(provisional)}))


def _renumber(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow, ordinal: int):
    body = value.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow(**(body | {"content_address": address_row(provisional)}))


def query_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery.from_mapping(value)


def verify_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery):
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery):
        raise ValidationError("comparison query verification requires a typed query")
    value._validate()
    if not value.content_address.endswith(":pending") and address_query(value) != value.content_address:
        raise ValidationError("comparison query address verification failed")
    return value


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery) -> str:
    return canonical_json(query_from_mapping(verify_query(value).to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery) -> str:
    value = verify_query(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow(row.to_dict())
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery) -> str:
    value = verify_query(value)
    mark = chr(96)
    lines = ["# Policy Package Registry Observatory Archive Runtime Query Snapshot Diff Query", "", f"- Diff: {mark}{value.diff_id}{mark}", f"- Resources: {mark}{', '.join(value.resources)}{mark}", f"- Rows: {mark}{value.returned_count}{mark} of {mark}{value.matched_count}{mark}", f"- Address: {mark}{value.content_address}{mark}", "", "| # | resource | source resource | identity | change | field |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {row.ordinal} | {mark}{row.resource}{mark} | {mark}{row.source_resource}{mark} | {mark}{row.identity}{mark} | {mark}{row.change}{mark} | {mark}{row.field}{mark} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot diff query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 1}, "key": {"type": "string"}, "identity": {"type": "string"}, "change": {"type": "string", "enum": [""] + list(diff_model.CHANGES)}, "source_resource": {"type": "string", "enum": [""] + list(diff_model.snapshot_model.query_model.RESOURCES)}, "field": {"type": "string", "enum": [""] + list(diff_model.SEMANTIC_ROW_FIELDS)}, "left_snapshot_id": {"type": "string"}, "right_snapshot_id": {"type": "string"}, "left_row_address": {"type": "string"}, "right_row_address": {"type": "string"}, "item_address": {"type": "string", "pattern": "^" + diff_model.ITEM_PREFIX + ":"}, "diff_id": {"type": "string"}, "direction": {"type": "string", "enum": list(diff_model.DIRECTIONS)}, "state_transition": {"type": "string"}, "left_accepted": {"type": "boolean"}, "right_accepted": {"type": "boolean"}, "count": {"type": "integer", "minimum": 0}, "changed_field_count": {"type": "integer", "minimum": 0}, "address": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot diff query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "diff_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "change_filter": {"type": "string", "enum": [""] + list(diff_model.CHANGES)}, "source_resource_filter": {"type": "string", "enum": [""] + list(diff_model.snapshot_model.query_model.RESOURCES)}, "key_filter": {"type": "string"}, "identity_filter": {"type": "string"}, "field_filter": {"type": "string", "enum": [""] + list(diff_model.SEMANTIC_ROW_FIELDS)}, "direction_filter": {"type": "string", "enum": [""] + list(diff_model.DIRECTIONS)}, "state_transition_filter": {"type": "string"}, "address_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "change_classes": list(diff_model.CHANGES), "source_resources": list(diff_model.snapshot_model.query_model.RESOURCES), "fields": list(diff_model.SEMANTIC_ROW_FIELDS), "directions": list(diff_model.DIRECTIONS), "max_limit": MAX_LIMIT, "max_total_count": MAX_TOTAL_COUNT, "features": ["summary projection", "all-item projection", "change-class projections", "changed-field projection", "exact source-resource/key/identity/field/direction/transition/address/text filters", "deterministic pagination", "JSON CSV and Markdown projections"]}


__all__ = ["BOUNDARY", "MAX_ITEMS", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_diff", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema", "verify_query"]
