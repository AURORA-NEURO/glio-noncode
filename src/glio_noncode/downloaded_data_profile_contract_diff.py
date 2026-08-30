"""Deterministic value-free schema evolution diffs between contract snapshots."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile as profile_model
from . import downloaded_data_profile_contract as contract_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-diff-v1"
BOUNDARY = "public_downloaded_data_profile_contract_diff"
DIFF_PREFIX = "glio-noncode-download-profile-contract-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
DEFAULT_DIFF_ID = DIFF_PREFIX
RESOURCES = ("fields", "members", "types")
CHANGES = ("added", "removed", "changed", "unchanged")
FIELD_CHANGED_ATTRIBUTES = ("observed_count", "missing_count", "member_count", "type_counts", "dominant_value_type", "type_consistent", "required", "state", "member_addresses")
MEMBER_CHANGED_ATTRIBUTES = ("member_name", "member_ordinal", "data_kind", "record_count", "field_count", "required_field_count", "optional_field_count", "mixed_type_field_count", "field_names", "required_field_names", "optional_field_names", "mixed_type_field_names")
TYPE_CHANGED_ATTRIBUTES = ("value_type", "observed_count", "field_count", "member_count")
MAX_TYPE_ROWS = len(profile_model.VALUE_TYPES)
MAX_ITEMS = 2 * (profile_model.MAX_FIELDS + profile_model.MAX_MEMBERS + MAX_TYPE_ROWS)
ITEM_FIELDS = (
    "ordinal",
    "resource",
    "identity",
    "change",
    "changed_attributes",
    "left_address",
    "right_address",
    "left_snapshot",
    "right_snapshot",
    "content_address",
)
DIFF_FIELDS = (
    "diff_id",
    "version",
    "boundary",
    "left_contract_address",
    "right_contract_address",
    "left_record_count",
    "right_record_count",
    "left_field_count",
    "right_field_count",
    "left_member_count",
    "right_member_count",
    "field_added_count",
    "field_removed_count",
    "field_changed_count",
    "field_unchanged_count",
    "member_added_count",
    "member_removed_count",
    "member_changed_count",
    "member_unchanged_count",
    "type_added_count",
    "type_removed_count",
    "type_changed_count",
    "type_unchanged_count",
    "items",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
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


def _attribute_names(resource: str) -> tuple[str, ...]:
    return {"fields": FIELD_CHANGED_ATTRIBUTES, "members": MEMBER_CHANGED_ATTRIBUTES, "types": TYPE_CHANGED_ATTRIBUTES}[resource]


def _typed_snapshot(resource: str, value: Mapping[str, Any]) -> dict[str, Any]:
    if resource == "fields":
        return contract_model.DownloadedDataContractField.from_mapping(value).to_dict()
    if resource == "members":
        return contract_model.DownloadedDataContractMember.from_mapping(value).to_dict()
    if resource == "types":
        return contract_model.DownloadedDataContractType.from_mapping(value).to_dict()
    raise ValidationError("contract diff resource is unsupported")


class DownloadedDataProfileContractDiffItem:
    """One value-free added, removed, changed, or unchanged contract row."""

    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, change: str, changed_attributes: Sequence[str], left_address: str, right_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "contract diff item ordinal", MAX_ITEMS, positive=True)
        self.resource = _label(resource, "contract diff item resource")
        if self.resource not in RESOURCES:
            raise ValidationError("contract diff item resource is unsupported")
        self.identity = _text(identity, "contract diff item identity", 4096)
        self.change = _label(change, "contract diff item change")
        if self.change not in CHANGES:
            raise ValidationError("contract diff item change is unsupported")
        allowed = _attribute_names(self.resource)
        self.changed_attributes = tuple(_label(item, "contract diff changed attribute") for item in _sequence(changed_attributes, "contract diff changed attributes", len(allowed)))
        if len(set(self.changed_attributes)) != len(self.changed_attributes) or any(item not in allowed for item in self.changed_attributes) or tuple(self.changed_attributes) != tuple(sorted(self.changed_attributes, key=allowed.index)):
            raise ValidationError("contract diff changed attributes are unsupported, duplicated, or unordered")
        prefix = {"fields": contract_model.FIELD_PREFIX, "members": contract_model.MEMBER_PREFIX, "types": contract_model.TYPE_PREFIX}[self.resource]
        self.left_address = _address(left_address, "contract diff left address", prefix) if left_address else ""
        self.right_address = _address(right_address, "contract diff right address", prefix) if right_address else ""
        self.left_snapshot = dict(_mapping(left_snapshot, "contract diff left snapshot"))
        self.right_snapshot = dict(_mapping(right_snapshot, "contract diff right snapshot"))
        if self.left_snapshot:
            self.left_snapshot = _typed_snapshot(self.resource, self.left_snapshot)
        if self.right_snapshot:
            self.right_snapshot = _typed_snapshot(self.resource, self.right_snapshot)
        self.content_address = _address(content_address, "contract diff item address", ITEM_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract diff item address")
        self._validate()

    def _validate(self) -> None:
        if self.change == "added" and (self.left_address or self.left_snapshot or not self.right_address or not self.right_snapshot or self.changed_attributes):
            raise ValidationError("added contract diff item has invalid left side")
        if self.change == "removed" and (not self.left_address or not self.left_snapshot or self.right_address or self.right_snapshot or self.changed_attributes):
            raise ValidationError("removed contract diff item has invalid right side")
        if self.change in {"changed", "unchanged"} and (not self.left_address or not self.right_address or not self.left_snapshot or not self.right_snapshot):
            raise ValidationError("contract diff item is missing a snapshot side")
        if self.change == "unchanged" and self.changed_attributes:
            raise ValidationError("unchanged contract diff item has changed attributes")
        if self.change == "changed" and not self.changed_attributes:
            raise ValidationError("changed contract diff item has no changed attributes")
        if self.change == "changed":
            left = {key: value for key, value in self.left_snapshot.items() if key != "content_address"}
            right = {key: value for key, value in self.right_snapshot.items() if key != "content_address"}
            expected = tuple(name for name in _attribute_names(self.resource) if left.get(name) != right.get(name))
            if expected != self.changed_attributes:
                raise ValidationError("contract diff item changed attributes do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("contract diff item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("contract diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"left_snapshot", "right_snapshot"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffItem:
        value = _mapping(value, "downloaded data profile contract diff item")
        _strict(value, set(cls.FIELDS), "downloaded data profile contract diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: DownloadedDataProfileContractDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class DownloadedDataProfileContractDiff:
    """Complete deterministic transition between two value-free contracts."""

    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, version: str, boundary: str, left_contract_address: str, right_contract_address: str, left_record_count: int, right_record_count: int, left_field_count: int, right_field_count: int, left_member_count: int, right_member_count: int, field_added_count: int, field_removed_count: int, field_changed_count: int, field_unchanged_count: int, member_added_count: int, member_removed_count: int, member_changed_count: int, member_unchanged_count: int, type_added_count: int, type_removed_count: int, type_changed_count: int, type_unchanged_count: int, items: Sequence[DownloadedDataProfileContractDiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _label(diff_id, "contract diff ID")
        self.version = _text(version, "contract diff version")
        self.boundary = _text(boundary, "contract diff boundary", 512)
        self.left_contract_address = _address(left_contract_address, "left contract address", contract_model.CONTRACT_PREFIX)
        self.right_contract_address = _address(right_contract_address, "right contract address", contract_model.CONTRACT_PREFIX)
        self.left_record_count = _count(left_record_count, "left contract record count", profile_model.MAX_RECORDS)
        self.right_record_count = _count(right_record_count, "right contract record count", profile_model.MAX_RECORDS)
        self.left_field_count = _count(left_field_count, "left contract field count", profile_model.MAX_FIELDS)
        self.right_field_count = _count(right_field_count, "right contract field count", profile_model.MAX_FIELDS)
        self.left_member_count = _count(left_member_count, "left contract member count", profile_model.MAX_MEMBERS)
        self.right_member_count = _count(right_member_count, "right contract member count", profile_model.MAX_MEMBERS)
        for field in ("field_added_count", "field_removed_count", "field_changed_count", "field_unchanged_count", "member_added_count", "member_removed_count", "member_changed_count", "member_unchanged_count", "type_added_count", "type_removed_count", "type_changed_count", "type_unchanged_count"):
            setattr(self, field, _count(locals()[field], f"contract diff {field}", MAX_ITEMS))
        self.items = tuple(item if isinstance(item, DownloadedDataProfileContractDiffItem) else DownloadedDataProfileContractDiffItem.from_mapping(item) for item in _sequence(items, "contract diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "contract diff address", DIFF_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract diff address")
        self._validate()

    def _validate(self) -> None:
        counts = {resource: {change: sum(item.resource == resource and item.change == change for item in self.items) for change in CHANGES} for resource in RESOURCES}
        expected_counts = {
            "field": counts["fields"],
            "member": counts["members"],
            "type": counts["types"],
        }
        if len(self.items) != sum(sum(item.values()) for item in expected_counts.values()) or tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or len({(item.resource, item.identity) for item in self.items}) != len(self.items):
            raise ValidationError("contract diff item order or identity does not replay")
        for prefix, _resource in (("field", "fields"), ("member", "members"), ("type", "types")):
            expected = expected_counts[prefix]
            if any(getattr(self, f"{prefix}_{change}_count") != expected[change] for change in CHANGES):
                raise ValidationError("contract diff resource counts do not replay")
        if self.left_field_count != counts["fields"]["removed"] + counts["fields"]["changed"] + counts["fields"]["unchanged"] or self.right_field_count != counts["fields"]["added"] + counts["fields"]["changed"] + counts["fields"]["unchanged"]:
            raise ValidationError("contract diff field totals do not replay")
        if self.left_member_count != counts["members"]["removed"] + counts["members"]["changed"] + counts["members"]["unchanged"] or self.right_member_count != counts["members"]["added"] + counts["members"]["changed"] + counts["members"]["unchanged"]:
            raise ValidationError("contract diff member totals do not replay")
        if self.left_contract_address == self.right_contract_address and any(item.change != "unchanged" for item in self.items):
            raise ValidationError("identical contracts cannot contain transitions")
        if self.version != VERSION or self.boundary != BOUNDARY or not _public(self.to_dict()):
            raise ValidationError("contract diff version, boundary, or public projection failed")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("contract diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "left_contract_address": self.left_contract_address, "right_contract_address": self.right_contract_address, "left_record_count": self.left_record_count, "right_record_count": self.right_record_count, "left_field_count": self.left_field_count, "right_field_count": self.right_field_count, "left_member_count": self.left_member_count, "right_member_count": self.right_member_count, "field_added_count": self.field_added_count, "field_removed_count": self.field_removed_count, "field_changed_count": self.field_changed_count, "field_unchanged_count": self.field_unchanged_count, "member_added_count": self.member_added_count, "member_removed_count": self.member_removed_count, "member_changed_count": self.member_changed_count, "member_unchanged_count": self.member_unchanged_count, "type_added_count": self.type_added_count, "type_removed_count": self.type_removed_count, "type_changed_count": self.type_changed_count, "type_unchanged_count": self.type_unchanged_count, "items": tuple(item.to_dict() for item in self.items), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "items"}

    def resource_items(self, resource: str) -> tuple[DownloadedDataProfileContractDiffItem, ...]:
        resource = _label(resource, "contract diff resource lookup")
        if resource not in RESOURCES:
            raise ValidationError("contract diff resource is unsupported")
        return tuple(item for item in self.items if item.resource == resource)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractDiff:
        value = _mapping(value, "downloaded data profile contract diff")
        _strict(value, set(cls.FIELDS), "downloaded data profile contract diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: DownloadedDataProfileContractDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _identity(resource: str, value: contract_model.DownloadedDataContractField | contract_model.DownloadedDataContractMember | contract_model.DownloadedDataContractType) -> str:
    if resource == "fields":
        return value.field_name
    if resource == "members":
        return f"{value.member_ordinal}"
    return value.value_type


def _item(ordinal: int, resource: str, identity: str, change: str, left: Any, right: Any) -> DownloadedDataProfileContractDiffItem:
    left_snapshot = left.to_dict() if left else {}
    right_snapshot = right.to_dict() if right else {}
    changed = () if change in {"added", "removed"} else tuple(name for name in _attribute_names(resource) if left_snapshot.get(name) != right_snapshot.get(name))
    body = {"ordinal": ordinal, "resource": resource, "identity": identity, "change": change, "changed_attributes": changed, "left_address": left.content_address if left else "", "right_address": right.content_address if right else "", "left_snapshot": left_snapshot, "right_snapshot": right_snapshot, "content_address": ITEM_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractDiffItem(**body)
    return DownloadedDataProfileContractDiffItem(**(body | {"content_address": address_item(provisional)}))


def _resource_rows(resource: str, left: contract_model.DownloadedDataProfileContract, right: contract_model.DownloadedDataProfileContract) -> list[tuple[str, str, Any, Any]]:
    left_values = {(_identity(resource, value)): value for value in getattr(left, resource)}
    right_values = {(_identity(resource, value)): value for value in getattr(right, resource)}
    rows = []
    for identity in sorted(set(left_values) | set(right_values)):
        before, after = left_values.get(identity), right_values.get(identity)
        before_projection = before.to_dict() | {"content_address": None} if before else None
        after_projection = after.to_dict() | {"content_address": None} if after else None
        change = "added" if before is None else "removed" if after is None else "unchanged" if before_projection == after_projection else "changed"
        rows.append((identity, change, before, after))
    return rows


def build_diff(left: contract_model.DownloadedDataProfileContract, right: contract_model.DownloadedDataProfileContract, *, diff_id: str = "glio-noncode-downloaded-data-profile-contract-diff") -> DownloadedDataProfileContractDiff:
    """Build a structural contract transition without source values."""

    if not isinstance(left, contract_model.DownloadedDataProfileContract) or not isinstance(right, contract_model.DownloadedDataProfileContract):
        raise ValidationError("contract diff requires typed contracts")
    items = []
    ordinal = 1
    for resource in RESOURCES:
        for identity, change, before, after in _resource_rows(resource, left, right):
            items.append(_item(ordinal, resource, identity, change, before, after))
            ordinal += 1
    body = {"diff_id": diff_id, "version": VERSION, "boundary": BOUNDARY, "left_contract_address": left.content_address, "right_contract_address": right.content_address, "left_record_count": left.record_count, "right_record_count": right.record_count, "left_field_count": left.field_count, "right_field_count": right.field_count, "left_member_count": left.member_count, "right_member_count": right.member_count}
    for resource, prefix in (("fields", "field"), ("members", "member"), ("types", "type")):
        for change in CHANGES:
            body[f"{prefix}_{change}_count"] = sum(item.resource == resource and item.change == change for item in items)
    body["items"] = tuple(items)
    provisional = DownloadedDataProfileContractDiff(**body, content_address=DIFF_PREFIX + ":pending")
    return DownloadedDataProfileContractDiff(**body, content_address=address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractDiff:
    return DownloadedDataProfileContractDiff.from_mapping(value)


def diff_json(value: DownloadedDataProfileContractDiff) -> str:
    return canonical_json(DownloadedDataProfileContractDiff.from_mapping(value.to_dict()).to_dict())


def diff_csv(value: DownloadedDataProfileContractDiff) -> str:
    value = DownloadedDataProfileContractDiff.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ITEM_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field not in {"changed_attributes", "left_snapshot", "right_snapshot"} else ";".join(item.changed_attributes) if field == "changed_attributes" else canonical_json(item.to_dict()[field]) for field in ITEM_FIELDS) for item in value.items)
    return stream.getvalue()


def render_diff_markdown(value: DownloadedDataProfileContractDiff) -> str:
    value = DownloadedDataProfileContractDiff.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Diff", "", f"- Left contract: `{value.left_contract_address}`", f"- Right contract: `{value.right_contract_address}`", f"- Fields: `+{value.field_added_count} -{value.field_removed_count} ~{value.field_changed_count} ={value.field_unchanged_count}`", f"- Members: `+{value.member_added_count} -{value.member_removed_count} ~{value.member_changed_count} ={value.member_unchanged_count}`", f"- Types: `+{value.type_added_count} -{value.type_removed_count} ~{value.type_changed_count} ={value.type_unchanged_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | identity | change | attributes |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.identity}` | `{item.change}` | `{', '.join(item.changed_attributes)}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract diff item", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "change": {"enum": list(CHANGES)}, "changed_attributes": {"type": "array", "items": {"type": "string"}}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "left_snapshot": {"type": "object"}, "right_snapshot": {"type": "object"}, "content_address": {"type": "string"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract diff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {"diff_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "left_contract_address": {"type": "string"}, "right_contract_address": {"type": "string"}, "left_record_count": {"type": "integer", "minimum": 0}, "right_record_count": {"type": "integer", "minimum": 0}, "left_field_count": {"type": "integer", "minimum": 0}, "right_field_count": {"type": "integer", "minimum": 0}, "left_member_count": {"type": "integer", "minimum": 0}, "right_member_count": {"type": "integer", "minimum": 0}, **{f"{prefix}_{change}_count": {"type": "integer", "minimum": 0} for prefix in ("field", "member", "type") for change in CHANGES}, "items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "changes": CHANGES, "operations": ("build_diff", "diff_from_mapping", "diff_json", "diff_csv", "render_diff_markdown"), "limits": {"max_items": MAX_ITEMS}}


__all__ = ["BOUNDARY", "CHANGES", "DEFAULT_DIFF_ID", "DIFF_FIELDS", "DIFF_PREFIX", "ITEM_FIELDS", "ITEM_PREFIX", "MAX_ITEMS", "RESOURCES", "DownloadedDataProfileContractDiff", "DownloadedDataProfileContractDiffItem", "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_diff_markdown"]
