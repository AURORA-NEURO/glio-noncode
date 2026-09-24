"""Source-free longitudinal diffs between downloaded-data review packets."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet as packet_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .downloaded_data_review_packet_contracts import PACKET_PREFIX
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = "downloaded-data-review-packet-diff-v1"
BOUNDARY = "public_downloaded_data_review_packet_diff"
DIFF_PREFIX = "glio-noncode-download-review-packet-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
DEFAULT_DIFF_ID = DIFF_PREFIX
RESOURCES = ("members", "fields", "types", "runtime")
CHANGES = ("added", "removed", "changed", "unchanged")
MEMBER_ATTRIBUTES = ("suffix", "media_type", "byte_size", "digest", "data_kind", "shape", "record_count", "field_count", "fields")
FIELD_ATTRIBUTES = ("observed_count", "missing_count", "member_count", "type_counts", "dominant_value_type", "type_consistent", "required", "state", "member_addresses")
TYPE_ATTRIBUTES = ("observed_count", "field_count", "member_count")
RUNTIME_ATTRIBUTES = ("record_count", "member_count", "field_count", "required_field_count", "optional_field_count", "sparse_field_count", "mixed_type_field_count", "accepted", "release_ready", "state")
ITEM_FIELDS = ("ordinal", "resource", "identity", "change", "changed_attributes", "left_address", "right_address", "left_snapshot", "right_snapshot", "content_address")
DIFF_FIELDS = (
    "diff_id", "version", "boundary", "packet_id", "left_packet_address", "right_packet_address",
    "left_catalog_address", "right_catalog_address", "left_runtime_address", "right_runtime_address",
    "left_member_count", "right_member_count", "left_field_count", "right_field_count", "left_type_count", "right_type_count",
    "member_added_count", "member_removed_count", "member_changed_count", "member_unchanged_count",
    "field_added_count", "field_removed_count", "field_changed_count", "field_unchanged_count",
    "type_added_count", "type_removed_count", "type_changed_count", "type_unchanged_count",
    "items", "content_address",
)
MAX_ITEMS = 8192
MAX_TEXT = 4096
MAX_LIMIT = 256


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value):
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and value and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _attribute_names(resource: str) -> tuple[str, ...]:
    return {"members": MEMBER_ATTRIBUTES, "fields": FIELD_ATTRIBUTES, "types": TYPE_ATTRIBUTES, "runtime": RUNTIME_ATTRIBUTES}[resource]


def _prefix(resource: str) -> str:
    return {"members": "glio-noncode-download-catalog-member", "fields": "glio-noncode-download-profile-contract-field", "types": "glio-noncode-download-profile-contract-type", "runtime": "glio-noncode-download-profile-contract-runtime"}[resource]


def _public(value: Any) -> bool:
    return not _has_forbidden_key(value)


class DownloadedDataReviewPacketDiffItem:
    """One value-free added, removed, changed, or unchanged evidence row."""

    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, change: str, changed_attributes: Sequence[str], left_address: str, right_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "review packet diff item ordinal", MAX_ITEMS, positive=True)
        self.resource = _label(resource, "review packet diff item resource")
        if self.resource not in RESOURCES:
            raise ValidationError("review packet diff item resource is unsupported")
        self.identity = _text(identity, "review packet diff item identity")
        self.change = _label(change, "review packet diff item change")
        if self.change not in CHANGES:
            raise ValidationError("review packet diff item change is unsupported")
        allowed = _attribute_names(self.resource)
        self.changed_attributes = tuple(_label(item, "review packet diff changed attribute") for item in _sequence(changed_attributes, "review packet diff changed attributes", len(allowed)))
        if len(set(self.changed_attributes)) != len(self.changed_attributes) or any(item not in allowed for item in self.changed_attributes) or tuple(self.changed_attributes) != tuple(sorted(self.changed_attributes, key=allowed.index)):
            raise ValidationError("review packet diff changed attributes are unsupported, duplicated, or unordered")
        self.left_address = _address(left_address, "review packet diff left address", _prefix(self.resource), required=False)
        self.right_address = _address(right_address, "review packet diff right address", _prefix(self.resource), required=False)
        self.left_snapshot = dict(_mapping(left_snapshot, "review packet diff left snapshot"))
        self.right_snapshot = dict(_mapping(right_snapshot, "review packet diff right snapshot"))
        self.content_address = _address(content_address, "review packet diff item address", ITEM_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "review packet diff item address")
        self._validate()

    def _validate(self) -> None:
        if self.change == "added" and (self.left_address or self.left_snapshot or not self.right_address or not self.right_snapshot or self.changed_attributes):
            raise ValidationError("added review packet diff item has an invalid left side")
        if self.change == "removed" and (not self.left_address or not self.left_snapshot or self.right_address or self.right_snapshot or self.changed_attributes):
            raise ValidationError("removed review packet diff item has an invalid right side")
        if self.change in {"changed", "unchanged"} and (not self.left_address or not self.right_address or not self.left_snapshot or not self.right_snapshot):
            raise ValidationError("paired review packet diff item is missing a snapshot side")
        if self.change == "unchanged" and self.changed_attributes:
            raise ValidationError("unchanged review packet diff item has changed attributes")
        if self.change == "changed" and not self.changed_attributes:
            raise ValidationError("changed review packet diff item has no changed attributes")
        if self.change == "changed":
            expected = tuple(name for name in _attribute_names(self.resource) if self.left_snapshot.get(name) != self.right_snapshot.get(name))
            if expected != self.changed_attributes:
                raise ValidationError("review packet diff changed attributes do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("review packet diff item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("review packet diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"left_snapshot", "right_snapshot"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiffItem:
        if not isinstance(value, Mapping):
            raise ValidationError("downloaded data review packet diff item must be an object")
        _strict(value, set(cls.FIELDS), "downloaded data review packet diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: DownloadedDataReviewPacketDiffItem) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffItem):
        raise ValidationError("review packet diff item addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class DownloadedDataReviewPacketDiff:
    """Complete deterministic transition between two accepted review packets."""

    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, version: str, boundary: str, packet_id: str, left_packet_address: str, right_packet_address: str, left_catalog_address: str, right_catalog_address: str, left_runtime_address: str, right_runtime_address: str, left_member_count: int, right_member_count: int, left_field_count: int, right_field_count: int, left_type_count: int, right_type_count: int, member_added_count: int, member_removed_count: int, member_changed_count: int, member_unchanged_count: int, field_added_count: int, field_removed_count: int, field_changed_count: int, field_unchanged_count: int, type_added_count: int, type_removed_count: int, type_changed_count: int, type_unchanged_count: int, items: Sequence[DownloadedDataReviewPacketDiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _label(diff_id, "review packet diff ID")
        self.version = _text(version, "review packet diff version")
        self.boundary = _text(boundary, "review packet diff boundary", 512)
        self.packet_id = _label(packet_id, "review packet diff packet ID")
        self.left_packet_address = _address(left_packet_address, "left packet address", PACKET_PREFIX)
        self.right_packet_address = _address(right_packet_address, "right packet address", PACKET_PREFIX)
        self.left_catalog_address = _address(left_catalog_address, "left catalog address", "glio-noncode-download-catalog")
        self.right_catalog_address = _address(right_catalog_address, "right catalog address", "glio-noncode-download-catalog")
        self.left_runtime_address = _address(left_runtime_address, "left runtime address", "glio-noncode-download-profile-contract-runtime")
        self.right_runtime_address = _address(right_runtime_address, "right runtime address", "glio-noncode-download-profile-contract-runtime")
        for field in ("left_member_count", "right_member_count", "left_field_count", "right_field_count", "left_type_count", "right_type_count"):
            setattr(self, field, _count(locals()[field], f"review packet diff {field}", MAX_ITEMS))
        for field in ("member_added_count", "member_removed_count", "member_changed_count", "member_unchanged_count", "field_added_count", "field_removed_count", "field_changed_count", "field_unchanged_count", "type_added_count", "type_removed_count", "type_changed_count", "type_unchanged_count"):
            setattr(self, field, _count(locals()[field], f"review packet diff {field}", MAX_ITEMS))
        self.items = tuple(item if isinstance(item, DownloadedDataReviewPacketDiffItem) else DownloadedDataReviewPacketDiffItem.from_mapping(item) for item in _sequence(items, "review packet diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "review packet diff address", DIFF_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "review packet diff address")
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("review packet diff version or boundary is not current")
        if not self.items or len(self.items) > MAX_ITEMS or tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or len({(item.resource, item.identity) for item in self.items}) != len(self.items):
            raise ValidationError("review packet diff item order or identity does not replay")
        for resource in ("members", "fields", "types"):
            expected = {change: sum(item.resource == resource and item.change == change for item in self.items) for change in CHANGES}
            if any(getattr(self, f"{resource[:-1]}_{change}_count") != expected[change] for change in CHANGES):
                raise ValidationError("review packet diff resource counts do not replay")
        if self.left_member_count != self.member_removed_count + self.member_changed_count + self.member_unchanged_count or self.right_member_count != self.member_added_count + self.member_changed_count + self.member_unchanged_count:
            raise ValidationError("review packet diff member totals do not replay")
        if self.left_field_count != self.field_removed_count + self.field_changed_count + self.field_unchanged_count or self.right_field_count != self.field_added_count + self.field_changed_count + self.field_unchanged_count:
            raise ValidationError("review packet diff field totals do not replay")
        if self.left_type_count != self.type_removed_count + self.type_changed_count + self.type_unchanged_count or self.right_type_count != self.type_added_count + self.type_changed_count + self.type_unchanged_count:
            raise ValidationError("review packet diff type totals do not replay")
        if self.left_packet_address == self.right_packet_address and any(item.change != "unchanged" for item in self.items):
            raise ValidationError("identical review packets cannot contain transitions")
        if not _public(self.to_dict()):
            raise ValidationError("review packet diff crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("review packet diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS if field != "items"} | {"items": tuple(item.to_dict() for item in self.items)}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "items"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiff:
        if not isinstance(value, Mapping):
            raise ValidationError("downloaded data review packet diff must be an object")
        _strict(value, set(cls.FIELDS), "downloaded data review packet diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: DownloadedDataReviewPacketDiff) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiff):
        raise ValidationError("review packet diff addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _item(ordinal: int, resource: str, identity: str, change: str, left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> DownloadedDataReviewPacketDiffItem:
    left_snapshot = dict(left or {})
    right_snapshot = dict(right or {})
    changed = () if change in {"added", "removed"} else tuple(name for name in _attribute_names(resource) if left_snapshot.get(name) != right_snapshot.get(name))
    body = {"ordinal": ordinal, "resource": resource, "identity": identity, "change": change, "changed_attributes": changed, "left_address": left_snapshot.get("content_address", ""), "right_address": right_snapshot.get("content_address", ""), "left_snapshot": left_snapshot, "right_snapshot": right_snapshot, "content_address": ITEM_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffItem(**body)
    return DownloadedDataReviewPacketDiffItem(**(body | {"content_address": address_item(provisional)}))


def _rows(resource: str, left: Any, right: Any) -> list[tuple[str, str, Mapping[str, Any] | None, Mapping[str, Any] | None]]:
    if resource == "members":
        left_values = {item.member_name: item.to_dict() for item in left.members}
        right_values = {item.member_name: item.to_dict() for item in right.members}
    elif resource == "fields":
        left_values = {item.field_name: item.to_dict() for item in left.contract.fields}
        right_values = {item.field_name: item.to_dict() for item in right.contract.fields}
    elif resource == "types":
        left_values = {item.value_type: item.to_dict() for item in left.contract.types}
        right_values = {item.value_type: item.to_dict() for item in right.contract.types}
    else:
        left_values = {"summary": {name: getattr(left, name) for name in RUNTIME_ATTRIBUTES} | {"content_address": left.content_address}}
        right_values = {"summary": {name: getattr(right, name) for name in RUNTIME_ATTRIBUTES} | {"content_address": right.content_address}}
    rows = []
    for identity in sorted(set(left_values) | set(right_values)):
        before = left_values.get(identity)
        after = right_values.get(identity)
        if before is None:
            change = "added"
        elif after is None:
            change = "removed"
        else:
            change = "unchanged" if all(before.get(name) == after.get(name) for name in _attribute_names(resource)) else "changed"
        rows.append((identity, change, before, after))
    return rows


def build_diff(left: Any, right: Any, *, diff_id: str = DEFAULT_DIFF_ID) -> DownloadedDataReviewPacketDiff:
    left_packet = packet_model.verify_packet(left)
    right_packet = packet_model.verify_packet(right)
    left_catalog, left_runtime, _left_audit, _left_review = packet_model.load_packet(left_packet)
    right_catalog, right_runtime, _right_audit, _right_review = packet_model.load_packet(right_packet)
    if left_packet.manifest.packet_id != right_packet.manifest.packet_id:
        raise ValidationError("review packet diff requires matching packet IDs")
    rows: list[DownloadedDataReviewPacketDiffItem] = []
    for resource, source_left, source_right in (("members", left_catalog, right_catalog), ("fields", left_runtime, right_runtime), ("types", left_runtime, right_runtime), ("runtime", left_runtime, right_runtime)):
        for identity, change, before, after in _rows(resource, source_left, source_right):
            rows.append(_item(len(rows) + 1, resource, identity, change, before, after))
    counts = {(resource, change): sum(item.resource == resource and item.change == change for item in rows) for resource in ("members", "fields", "types") for change in CHANGES}
    body = {
        "diff_id": diff_id, "version": VERSION, "boundary": BOUNDARY, "packet_id": left_packet.manifest.packet_id,
        "left_packet_address": left_packet.packet_address, "right_packet_address": right_packet.packet_address,
        "left_catalog_address": left_catalog.content_address, "right_catalog_address": right_catalog.content_address,
        "left_runtime_address": left_runtime.content_address, "right_runtime_address": right_runtime.content_address,
        "left_member_count": len(left_catalog.members), "right_member_count": len(right_catalog.members),
        "left_field_count": len(left_runtime.contract.fields), "right_field_count": len(right_runtime.contract.fields),
        "left_type_count": len(left_runtime.contract.types), "right_type_count": len(right_runtime.contract.types),
        **{f"{resource[:-1]}_{change}_count": counts[(resource, change)] for resource in ("members", "fields", "types") for change in CHANGES},
        "items": rows, "content_address": DIFF_PREFIX + ":pending",
    }
    provisional = DownloadedDataReviewPacketDiff(**body)
    return DownloadedDataReviewPacketDiff(**(body | {"content_address": address_diff(provisional)}))


def verify_diff(value: Any) -> DownloadedDataReviewPacketDiff:
    diff = value if isinstance(value, DownloadedDataReviewPacketDiff) else load_diff(value)
    if not isinstance(diff, DownloadedDataReviewPacketDiff):
        raise ValidationError("review packet diff verification requires its typed contract")
    if address_diff(diff) != diff.content_address:
        raise ValidationError("review packet diff address does not replay")
    return DownloadedDataReviewPacketDiff.from_mapping(diff.to_dict())


def diff_from_mapping(value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiff:
    return DownloadedDataReviewPacketDiff.from_mapping(value)


def diff_json(value: Any) -> str:
    return canonical_json(verify_diff(value).to_dict()) + "\n"


def write_diff(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiff:
    diff = verify_diff(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("review packet diff destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("review packet diff destination is not a file")
    _validate_parent(path.parent, "review packet diff destination")
    atomic_write_text(path, diff_json(diff), field="review packet diff destination")
    return diff


def load_diff(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiff:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded data review packet diff", max_bytes=16 * 1024 * 1024))
    return DownloadedDataReviewPacketDiff.from_mapping(raw)


def query_diff(value: Any, *, resource: str = "", change: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    diff = verify_diff(value)
    resource = _label(resource, "review packet diff query resource", required=False)
    change = _label(change, "review packet diff query change", required=False)
    text = _text(text, "review packet diff query text", required=False)
    offset = _count(offset, "review packet diff query offset", MAX_ITEMS)
    limit = _count(limit, "review packet diff query limit", MAX_LIMIT, positive=True)
    if resource and resource not in RESOURCES:
        raise ValidationError("review packet diff query resource is unsupported")
    if change and change not in CHANGES:
        raise ValidationError("review packet diff query change is unsupported")
    candidates = tuple(item for item in diff.items if (not resource or item.resource == resource) and (not change or item.change == change) and (not text or text.casefold() in " ".join((item.resource, item.identity, item.change, *item.changed_attributes)).casefold()))
    selected = candidates[offset:offset + limit]
    result = {"diff_address": diff.content_address, "resource": resource, "change": change, "text": text, "offset": offset, "limit": limit, "total": len(diff.items), "matched": len(candidates), "returned": len(selected), "truncated": offset + len(selected) < len(candidates), "items": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=DIFF_PREFIX + "-query")}


def diff_csv(value: Any, *, resource: str = "", change: str = "", text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_diff(value, resource=resource, change=change, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    fields = ("ordinal", "resource", "identity", "change", "changed_attributes", "left_address", "right_address", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in result["items"]:
        writer.writerow({field: ",".join(item[field]) if field == "changed_attributes" else item[field] for field in fields})
    return stream.getvalue()


def render_diff_markdown(value: Any) -> str:
    diff = verify_diff(value)
    lines = ["# Downloaded Data Review Packet Diff", "", f"- Packet ID: `{diff.packet_id}`", f"- Left packet: `{diff.left_packet_address}`", f"- Right packet: `{diff.right_packet_address}`", f"- Added / removed / changed / unchanged: **{sum(item.change == 'added' for item in diff.items)} / {sum(item.change == 'removed' for item in diff.items)} / {sum(item.change == 'changed' for item in diff.items)} / {sum(item.change == 'unchanged' for item in diff.items)}**", f"- Diff address: `{diff.content_address}`", "", "| # | resource | identity | change | attributes |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.identity}` | `{item.change}` | `{', '.join(item.changed_attributes)}` |" for item in diff.items)
    return "\n".join(lines) + "\n"


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review packet diff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {field: {"type": "array" if field == "items" else "string" if field in {"diff_id", "version", "boundary", "packet_id", "left_packet_address", "right_packet_address", "left_catalog_address", "right_catalog_address", "left_runtime_address", "right_runtime_address", "content_address"} else "integer"} for field in DIFF_FIELDS}}


def capabilities() -> dict[str, Any]:
    operations = ("build_diff", "verify_diff", "load_source_free", "query_items", "export_json", "export_csv", "render_markdown", "write_atomic")
    return {"public": True, "independent": True, "source_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": list(RESOURCES), "changes": list(CHANGES), "operation_count": len(operations), "operations": list(operations), "max_items": MAX_ITEMS}


__all__ = [
    "BOUNDARY", "CHANGES", "DEFAULT_DIFF_ID", "DIFF_FIELDS", "DIFF_PREFIX", "FIELD_ATTRIBUTES", "ITEM_FIELDS", "ITEM_PREFIX", "MAX_ITEMS", "MAX_LIMIT", "MEMBER_ATTRIBUTES", "RESOURCES", "RUNTIME_ATTRIBUTES", "TYPE_ATTRIBUTES", "VERSION", "DownloadedDataReviewPacketDiff", "DownloadedDataReviewPacketDiffItem", "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "load_diff", "query_diff", "render_diff_markdown", "verify_diff", "write_diff",
]
