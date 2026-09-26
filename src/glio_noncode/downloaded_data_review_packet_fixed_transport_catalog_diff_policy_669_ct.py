"""Typed contracts for longitudinal comparisons of module668 catalogs."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .downloaded_data_review_packet_fixed_transport_catalog_diff_policy_668_ct import CATALOG_PREFIX, STATES as POSTURES
from .errors import ValidationError
from .serialization import content_hash

VERSION = CATALOG_PREFIX + "-diff-v1"
BOUNDARY = "public_" + VERSION.replace("-", "_")
DIFF_PREFIX = CATALOG_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
MAX_ITEMS = 512
MAX_LIMIT = 256
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "changed", "unchanged")
STATE_TRANSITIONS = tuple("same-" + posture for posture in POSTURES) + tuple(f"{left}-to-{right}" for left in POSTURES for right in POSTURES if left != right)
SNAPSHOT_FIELDS = ("entry_id", "package_id", "package_address", "manifest_address", "diff_address", "policy_address", "audit_address", "policy_state", "policy_accepted", "audit_accepted", "package_byte_count", "member_count")
ITEM_FIELDS = ("ordinal", "entry_id", "change", "changed_fields", "left_address", "right_address", "left_snapshot", "right_snapshot", "content_address")
DIFF_FIELDS = ("diff_id", "version", "boundary", "catalog_id", "left_catalog_address", "right_catalog_address", "left_posture", "right_posture", "state_transition", "direction", "added_count", "removed_count", "changed_count", "unchanged_count", "items", "content_address")

def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if not value:
        return value
    if value.endswith(":pending"):
        return value
    digest = value.rsplit(":", 1)[-1]
    if ":" not in value or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a canonical content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


@dataclass(frozen=True)
class DiffItem:
    ordinal: int
    entry_id: str
    change: str
    changed_fields: tuple[str, ...]
    left_address: str
    right_address: str
    left_snapshot: dict[str, Any]
    right_snapshot: dict[str, Any]
    content_address: str

    def __post_init__(self) -> None:
        _count(self.ordinal, "module669 item ordinal", MAX_ITEMS)
        _label(self.entry_id, "module669 item entry ID")
        if self.change not in CHANGES or tuple(field for field in SNAPSHOT_FIELDS if field in self.changed_fields) != self.changed_fields or any(field not in SNAPSHOT_FIELDS for field in self.changed_fields):
            raise ValidationError("module669 item change fields are not canonical")
        if not isinstance(self.left_snapshot, dict) or not isinstance(self.right_snapshot, dict) or set(self.left_snapshot) - set(SNAPSHOT_FIELDS) or set(self.right_snapshot) - set(SNAPSHOT_FIELDS):
            raise ValidationError("module669 item snapshots contain unsupported fields")
        if self.change == "added" and self.left_snapshot or self.change == "removed" and self.right_snapshot or self.change == "unchanged" and self.changed_fields:
            raise ValidationError("module669 item change state does not match snapshots")
        _address(self.left_address, "module669 left item address", required=False)
        _address(self.right_address, "module669 right item address", required=False)
        _address(self.content_address, "module669 item address", ITEM_PREFIX)
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("module669 item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in ITEM_FIELDS}


def address_item(value: DiffItem) -> str:
    if not isinstance(value, DiffItem):
        raise ValidationError("module669 item addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


@dataclass(frozen=True)
class Diff:
    diff_id: str
    version: str
    boundary: str
    catalog_id: str
    left_catalog_address: str
    right_catalog_address: str
    left_posture: str
    right_posture: str
    state_transition: str
    direction: str
    added_count: int
    removed_count: int
    changed_count: int
    unchanged_count: int
    items: tuple[DiffItem, ...]
    content_address: str

    def __post_init__(self) -> None:
        _label(self.diff_id, "module669 diff ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("module669 diff identity is not current")
        _label(self.catalog_id, "module669 diff catalog ID")
        _address(self.left_catalog_address, "module669 left catalog address", CATALOG_PREFIX)
        _address(self.right_catalog_address, "module669 right catalog address", CATALOG_PREFIX)
        if self.left_posture not in POSTURES or self.right_posture not in POSTURES or self.state_transition not in STATE_TRANSITIONS or self.direction not in DIRECTIONS:
            raise ValidationError("module669 posture, transition, or direction is unsupported")
        for field in ("added_count", "removed_count", "changed_count", "unchanged_count"):
            _count(getattr(self, field), f"module669 {field}", MAX_ITEMS)
        if len(self.items) > MAX_ITEMS or sum((self.added_count, self.removed_count, self.changed_count, self.unchanged_count)) != len(self.items):
            raise ValidationError("module669 item counts do not replay")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or tuple(item.entry_id for item in self.items) != tuple(sorted(item.entry_id for item in self.items)) or len({item.entry_id for item in self.items}) != len(self.items):
            raise ValidationError("module669 item order or identity is not canonical")
        _address(self.content_address, "module669 diff address", DIFF_PREFIX)
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("module669 diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": VERSION, "boundary": BOUNDARY, "catalog_id": self.catalog_id, "left_catalog_address": self.left_catalog_address, "right_catalog_address": self.right_catalog_address, "left_posture": self.left_posture, "right_posture": self.right_posture, "state_transition": self.state_transition, "direction": self.direction, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "items": tuple(item.to_dict() for item in self.items), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in DIFF_FIELDS if field != "items"}


def address_diff(value: Diff) -> str:
    if not isinstance(value, Diff):
        raise ValidationError("module669 diff addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module669 catalog diff item", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {"ordinal": {"type": "integer"}, "entry_id": {"type": "string"}, "change": {"enum": list(CHANGES)}, "changed_fields": {"type": "array"}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "content_address": {"type": "string"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module669 transport catalog diff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "catalog_id": {"type": "string"}, "items": {"type": "array", "maxItems": MAX_ITEMS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "source_free": True, "content_addressed": True, "bounded": True, "max_items": MAX_ITEMS, "changes": CHANGES, "directions": DIRECTIONS, "postures": POSTURES, "state_transitions": STATE_TRANSITIONS, "snapshot_fields": SNAPSHOT_FIELDS, "operations": ("build_diff", "diff_json", "diff_csv", "render_diff_markdown", "query_diff", "verify_diff")}


__all__ = ["BOUNDARY", "CHANGES", "DIFF_FIELDS", "DIFF_PREFIX", "DIRECTIONS", "ITEM_FIELDS", "ITEM_PREFIX", "MAX_ITEMS", "MAX_LIMIT", "POSTURES", "SNAPSHOT_FIELDS", "STATE_TRANSITIONS", "VERSION", "Diff", "DiffItem", "address_diff", "address_item", "capabilities", "diff_schema", "item_schema"]
