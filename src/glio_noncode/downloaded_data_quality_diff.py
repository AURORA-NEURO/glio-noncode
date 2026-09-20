"""Deterministic baseline/candidate comparisons for downloaded-data quality."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality as quality_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-v1"
BOUNDARY = "public_downloaded_data_quality_diff"
DIFF_PREFIX = "glio-noncode-download-quality-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
DEFAULT_DIFF_ID = DIFF_PREFIX
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "changed", "unchanged", "added", "removed")
ITEM_CHANGED_ATTRIBUTES = ("severity", "passed", "measured", "limit", "detail", "evidence_addresses")
ITEM_FIELDS = (
    "ordinal",
    "identity",
    "change",
    "direction",
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
    "left_quality_address",
    "right_quality_address",
    "left_policy_address",
    "right_policy_address",
    "left_record_count",
    "right_record_count",
    "left_member_count",
    "right_member_count",
    "left_field_count",
    "right_field_count",
    "left_check_count",
    "right_check_count",
    "left_failed_count",
    "right_failed_count",
    "added_count",
    "removed_count",
    "changed_count",
    "unchanged_count",
    "improved_count",
    "regressed_count",
    "accepted_transition",
    "state_transition",
    "items",
    "content_address",
)
MAX_ITEMS = quality_model.MAX_FINDINGS * 2


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


def _finding_identity(value: quality_model.DownloadedDataQualityFinding) -> str:
    return canonical_json((value.rule_id, value.scope, value.member_name, value.field_name))


def _finding_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    return quality_model.DownloadedDataQualityFinding.from_mapping(value).to_dict()


def _changed_attributes(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(name for name in ITEM_CHANGED_ATTRIBUTES if left.get(name) != right.get(name))


def _direction(change: str, left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> str:
    if change == "added":
        return "added"
    if change == "removed":
        return "removed"
    if left is None or right is None:
        raise ValidationError("quality diff transition is missing a side")
    left_passed, right_passed = left["passed"], right["passed"]
    if left_passed != right_passed:
        return "improved" if right_passed else "regressed"
    return "changed" if change == "changed" else "unchanged"


class DownloadedDataQualityDiffItem:
    """One finding transition between two quality decisions."""

    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, identity: str, change: str, direction: str, changed_attributes: Sequence[str], left_address: str, right_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality diff item ordinal", MAX_ITEMS, positive=True)
        self.identity = _text(identity, "quality diff item identity", 4096)
        self.change = _label(change, "quality diff item change")
        if self.change not in CHANGES:
            raise ValidationError("quality diff item change is unsupported")
        self.direction = _label(direction, "quality diff item direction")
        if self.direction not in DIRECTIONS:
            raise ValidationError("quality diff item direction is unsupported")
        self.changed_attributes = tuple(_label(item, "quality diff changed attribute") for item in _sequence(changed_attributes, "quality diff changed attributes", len(ITEM_CHANGED_ATTRIBUTES)))
        if len(set(self.changed_attributes)) != len(self.changed_attributes) or any(item not in ITEM_CHANGED_ATTRIBUTES for item in self.changed_attributes) or tuple(self.changed_attributes) != tuple(sorted(self.changed_attributes, key=ITEM_CHANGED_ATTRIBUTES.index)):
            raise ValidationError("quality diff changed attributes are unsupported, duplicated, or unordered")
        self.left_address = _address(left_address, "quality diff left finding address", quality_model.FINDING_PREFIX) if left_address else ""
        self.right_address = _address(right_address, "quality diff right finding address", quality_model.FINDING_PREFIX) if right_address else ""
        self.left_snapshot = dict(_mapping(left_snapshot, "quality diff left snapshot"))
        self.right_snapshot = dict(_mapping(right_snapshot, "quality diff right snapshot"))
        if self.left_snapshot:
            self.left_snapshot = _finding_snapshot(self.left_snapshot)
        if self.right_snapshot:
            self.right_snapshot = _finding_snapshot(self.right_snapshot)
        self.content_address = _address(content_address, "quality diff item address", ITEM_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff item address")
        self._validate()

    def _validate(self) -> None:
        if self.change == "added" and (self.left_address or self.left_snapshot or not self.right_address or not self.right_snapshot or self.changed_attributes or self.direction != "added"):
            raise ValidationError("added quality diff item has invalid left side")
        if self.change == "removed" and (not self.left_address or not self.left_snapshot or self.right_address or self.right_snapshot or self.changed_attributes or self.direction != "removed"):
            raise ValidationError("removed quality diff item has invalid right side")
        if self.change in {"changed", "unchanged"} and (not self.left_address or not self.right_address or not self.left_snapshot or not self.right_snapshot):
            raise ValidationError("quality diff item is missing a snapshot side")
        if self.change == "unchanged" and (self.changed_attributes or self.direction != "unchanged"):
            raise ValidationError("unchanged quality diff item does not replay")
        if self.change == "changed" and (not self.changed_attributes or self.direction not in {"improved", "regressed", "changed"}):
            raise ValidationError("changed quality diff item does not replay")
        if self.change == "changed" and tuple(self.changed_attributes) != _changed_attributes(self.left_snapshot, self.right_snapshot):
            raise ValidationError("quality diff changed attributes do not replay")
        if self.change in {"changed", "unchanged"} and self.identity != _finding_identity(quality_model.DownloadedDataQualityFinding.from_mapping(self.left_snapshot)):
            raise ValidationError("quality diff identity does not replay")
        if self.change in {"changed", "unchanged"} and self.direction != _direction(self.change, self.left_snapshot, self.right_snapshot):
            raise ValidationError("quality diff direction does not replay")
        if not self.left_snapshot and not self.right_snapshot:
            raise ValidationError("quality diff item has no snapshots")
        if not _public(self.to_dict()):
            raise ValidationError("quality diff item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("quality diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"left_snapshot", "right_snapshot"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffItem":
        value = _mapping(value, "downloaded data quality diff item")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: DownloadedDataQualityDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class DownloadedDataQualityDiff:
    """Complete deterministic transition between two quality decisions."""

    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, version: str, boundary: str, left_quality_address: str, right_quality_address: str, left_policy_address: str, right_policy_address: str, left_record_count: int, right_record_count: int, left_member_count: int, right_member_count: int, left_field_count: int, right_field_count: int, left_check_count: int, right_check_count: int, left_failed_count: int, right_failed_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, improved_count: int, regressed_count: int, accepted_transition: str, state_transition: str, items: Sequence[DownloadedDataQualityDiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _label(diff_id, "quality diff ID")
        self.version = _text(version, "quality diff version")
        self.boundary = _text(boundary, "quality diff boundary", 512)
        self.left_quality_address = _address(left_quality_address, "left quality address", quality_model.QUALITY_PREFIX)
        self.right_quality_address = _address(right_quality_address, "right quality address", quality_model.QUALITY_PREFIX)
        self.left_policy_address = _address(left_policy_address, "left policy address", quality_model.POLICY_PREFIX)
        self.right_policy_address = _address(right_policy_address, "right policy address", quality_model.POLICY_PREFIX)
        for field in ("left_record_count", "right_record_count"):
            setattr(self, field, _count(locals()[field], f"quality diff {field}", quality_model.profile_model.MAX_RECORDS))
        for field in ("left_member_count", "right_member_count"):
            setattr(self, field, _count(locals()[field], f"quality diff {field}", quality_model.profile_model.MAX_MEMBERS))
        for field in ("left_field_count", "right_field_count"):
            setattr(self, field, _count(locals()[field], f"quality diff {field}", quality_model.profile_model.MAX_FIELDS))
        for field in ("left_check_count", "right_check_count", "left_failed_count", "right_failed_count", "added_count", "removed_count", "changed_count", "unchanged_count", "improved_count", "regressed_count"):
            setattr(self, field, _count(locals()[field], f"quality diff {field}", MAX_ITEMS))
        self.accepted_transition = _text(accepted_transition, "quality diff accepted transition", 32)
        self.state_transition = _text(state_transition, "quality diff state transition", 64)
        self.items = tuple(item if isinstance(item, DownloadedDataQualityDiffItem) else DownloadedDataQualityDiffItem.from_mapping(item) for item in _sequence(items, "quality diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "quality diff address", DIFF_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff address")
        self._validate()

    def _validate(self) -> None:
        counts = {change: sum(item.change == change for item in self.items) for change in CHANGES}
        directions = {direction: sum(item.direction == direction for item in self.items) for direction in DIRECTIONS}
        if self.left_quality_address == self.right_quality_address:
            if any(item.change != "unchanged" for item in self.items):
                raise ValidationError("identical quality results cannot contain transitions")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or len({item.identity for item in self.items}) != len(self.items):
            raise ValidationError("quality diff item order or identity does not replay")
        if any(getattr(self, f"{change}_count") != counts[change] for change in CHANGES):
            raise ValidationError("quality diff change counts do not replay")
        if self.improved_count != directions["improved"] or self.regressed_count != directions["regressed"]:
            raise ValidationError("quality diff direction counts do not replay")
        if self.left_check_count != counts["removed"] + counts["changed"] + counts["unchanged"] or self.right_check_count != counts["added"] + counts["changed"] + counts["unchanged"]:
            raise ValidationError("quality diff check totals do not replay")
        if self.left_failed_count > self.left_check_count or self.right_failed_count > self.right_check_count:
            raise ValidationError("quality diff failed counts exceed checks")
        if self.accepted_transition not in {"True->True", "True->False", "False->True", "False->False"}:
            raise ValidationError("quality diff accepted transition is unsupported")
        if "->" not in self.state_transition or len(self.state_transition.split("->")) != 2:
            raise ValidationError("quality diff state transition is malformed")
        if self.version != VERSION or self.boundary != BOUNDARY or not _public(self.to_dict()):
            raise ValidationError("quality diff version, boundary, or public projection failed")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("quality diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS if field != "items"} | {"items": tuple(item.to_dict() for item in self.items)}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "items"}

    def item(self, ordinal: int) -> DownloadedDataQualityDiffItem:
        ordinal = _count(ordinal, "quality diff item lookup", MAX_ITEMS, positive=True)
        for item in self.items:
            if item.ordinal == ordinal:
                return item
        raise ValidationError("quality diff item was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiff":
        value = _mapping(value, "downloaded data quality diff")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: DownloadedDataQualityDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def build_diff(left: quality_model.DownloadedDataQuality, right: quality_model.DownloadedDataQuality, *, diff_id: str = DEFAULT_DIFF_ID) -> DownloadedDataQualityDiff:
    """Build a path-free finding transition with deterministic identity joins."""

    if not isinstance(left, quality_model.DownloadedDataQuality) or not isinstance(right, quality_model.DownloadedDataQuality):
        raise ValidationError("quality diff requires two typed quality results")
    left_by_identity = {_finding_identity(item): item for item in left.findings}
    right_by_identity = {_finding_identity(item): item for item in right.findings}
    if len(left_by_identity) != len(left.findings) or len(right_by_identity) != len(right.findings):
        raise ValidationError("quality findings contain duplicate comparison identities")
    items: list[DownloadedDataQualityDiffItem] = []
    for ordinal, identity in enumerate(sorted(set(left_by_identity) | set(right_by_identity)), 1):
        left_item = left_by_identity.get(identity)
        right_item = right_by_identity.get(identity)
        left_snapshot = left_item.to_dict() if left_item else {}
        right_snapshot = right_item.to_dict() if right_item else {}
        if left_item is None:
            change = "added"
        elif right_item is None:
            change = "removed"
        else:
            change = "unchanged" if _changed_attributes(left_snapshot, right_snapshot) == () else "changed"
        body = {
            "ordinal": ordinal,
            "identity": identity,
            "change": change,
            "direction": _direction(change, left_snapshot or None, right_snapshot or None),
            "changed_attributes": _changed_attributes(left_snapshot, right_snapshot) if change == "changed" else (),
            "left_address": left_item.content_address if left_item else "",
            "right_address": right_item.content_address if right_item else "",
            "left_snapshot": left_snapshot,
            "right_snapshot": right_snapshot,
        }
        provisional = DownloadedDataQualityDiffItem(**body, content_address=ITEM_PREFIX + ":pending")
        items.append(DownloadedDataQualityDiffItem(**body, content_address=address_item(provisional)))
    body = {
        "diff_id": diff_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "left_quality_address": left.content_address,
        "right_quality_address": right.content_address,
        "left_policy_address": left.policy.content_address,
        "right_policy_address": right.policy.content_address,
        "left_record_count": left.record_count,
        "right_record_count": right.record_count,
        "left_member_count": left.member_count,
        "right_member_count": right.member_count,
        "left_field_count": left.field_count,
        "right_field_count": right.field_count,
        "left_check_count": left.check_count,
        "right_check_count": right.check_count,
        "left_failed_count": left.failed_count,
        "right_failed_count": right.failed_count,
        "added_count": sum(item.change == "added" for item in items),
        "removed_count": sum(item.change == "removed" for item in items),
        "changed_count": sum(item.change == "changed" for item in items),
        "unchanged_count": sum(item.change == "unchanged" for item in items),
        "improved_count": sum(item.direction == "improved" for item in items),
        "regressed_count": sum(item.direction == "regressed" for item in items),
        "accepted_transition": f"{left.accepted}->{right.accepted}",
        "state_transition": f"{left.state}->{right.state}",
        "items": tuple(items),
    }
    provisional = DownloadedDataQualityDiff(**body, content_address=DIFF_PREFIX + ":pending")
    return DownloadedDataQualityDiff(**body, content_address=address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiff:
    return DownloadedDataQualityDiff.from_mapping(value)


def diff_json(value: DownloadedDataQualityDiff) -> str:
    return canonical_json(DownloadedDataQualityDiff.from_mapping(value.to_dict()).to_dict())


def diff_csv(value: DownloadedDataQualityDiff) -> str:
    value = DownloadedDataQualityDiff.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ITEM_FIELDS)
    for item in value.items:
        row = item.summary()
        writer.writerow(tuple(row[field] if field not in {"changed_attributes"} else ";".join(row[field]) for field in ITEM_FIELDS))
    return stream.getvalue()


def render_diff_markdown(value: DownloadedDataQualityDiff) -> str:
    value = DownloadedDataQualityDiff.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff", "", f"- Diff: `{value.diff_id}`", f"- Left: `{value.left_quality_address}`", f"- Right: `{value.right_quality_address}`", f"- Transition: `{value.state_transition}`", f"- Accepted: `{value.accepted_transition}`", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Improved: `{value.improved_count}`", f"- Regressed: `{value.regressed_count}`", "", "| ordinal | change | direction | identity | changed attributes |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.change} | {item.direction} | `{item.identity}` | {', '.join(item.changed_attributes) or '—'} |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff item", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "identity": {"type": "string"}, "change": {"enum": list(CHANGES)}, "direction": {"enum": list(DIRECTIONS)}, "changed_attributes": {"type": "array", "items": {"enum": list(ITEM_CHANGED_ATTRIBUTES)}}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "left_snapshot": {"type": "object"}, "right_snapshot": {"type": "object"}, "content_address": {"type": "string"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {"diff_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "left_quality_address": {"type": "string"}, "right_quality_address": {"type": "string"}, "left_policy_address": {"type": "string"}, "right_policy_address": {"type": "string"}, "left_record_count": {"type": "integer", "minimum": 0}, "right_record_count": {"type": "integer", "minimum": 0}, "left_member_count": {"type": "integer", "minimum": 0}, "right_member_count": {"type": "integer", "minimum": 0}, "left_field_count": {"type": "integer", "minimum": 0}, "right_field_count": {"type": "integer", "minimum": 0}, "left_check_count": {"type": "integer", "minimum": 0}, "right_check_count": {"type": "integer", "minimum": 0}, "left_failed_count": {"type": "integer", "minimum": 0}, "right_failed_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "accepted_transition": {"type": "string"}, "state_transition": {"type": "string"}, "items": {"type": "array", "items": item_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "changes": CHANGES, "directions": DIRECTIONS, "operations": ("build_diff", "diff_from_mapping", "diff_json", "diff_csv", "render_diff_markdown"), "limits": {"max_items": MAX_ITEMS}}


__all__ = ["BOUNDARY", "CHANGES", "DIFF_FIELDS", "DIFF_PREFIX", "DIRECTIONS", "ITEM_CHANGED_ATTRIBUTES", "ITEM_FIELDS", "MAX_ITEMS", "DownloadedDataQualityDiff", "DownloadedDataQualityDiffItem", "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_diff_markdown"]
