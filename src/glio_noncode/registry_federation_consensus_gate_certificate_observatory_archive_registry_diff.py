"""Deterministic version diff for certificate-observatory archive registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-diff-v1"
BOUNDARY = registry_model.BOUNDARY + "_diff"
DIFF_PREFIX = registry_model.REGISTRY_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
CHANGE_TYPES = ("added", "removed", "changed")
MAX_ITEMS = registry_model.MAX_ENTRIES * 2


def _text(value: Any, field: str, maximum: int = 2048, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value):
        raise ValidationError(f"{field} must be a public address")
    if value and prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem:
    """One changed archive identity between two registry versions."""

    FIELDS = ("ordinal", "change_type", "entry_id", "archive_id", "left_address", "right_address", "left_entry_address", "right_entry_address", "changed_fields", "content_address")

    def __init__(self, ordinal: int, change_type: str, entry_id: str, archive_id: str, left_address: str, right_address: str, left_entry_address: str, right_entry_address: str, changed_fields: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry diff item ordinal", MAX_ITEMS, positive=True)
        if change_type not in CHANGE_TYPES:
            raise ValidationError("registry diff change type is unsupported")
        self.change_type = change_type
        self.entry_id = _label(entry_id, "registry diff entry ID")
        self.archive_id = _label(archive_id, "registry diff archive ID")
        self.left_address = _address(left_address, "registry diff left archive address", registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.right_address = _address(right_address, "registry diff right archive address", registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.left_entry_address = _address(left_entry_address, "registry diff left entry address", registry_model.ENTRY_PREFIX, required=False)
        self.right_entry_address = _address(right_entry_address, "registry diff right entry address", registry_model.ENTRY_PREFIX, required=False)
        self.changed_fields = tuple(_label(item, "registry diff changed field") for item in _sequence(changed_fields, "registry diff changed fields", len(registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry.FIELDS)))
        self.content_address = _address(content_address, "registry diff item address", ITEM_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry diff item address")
        self._validate()

    def _validate(self) -> None:
        if len(set(self.changed_fields)) != len(self.changed_fields):
            raise ValidationError("registry diff changed fields must be unique")
        if self.change_type == "added" and not self.right_address:
            raise ValidationError("added registry diff item requires a right archive")
        if self.change_type == "removed" and not self.left_address:
            raise ValidationError("removed registry diff item requires a left archive")
        if self.change_type == "changed" and (not self.left_address or not self.right_address or not self.changed_fields):
            raise ValidationError("changed registry diff item requires both sides and fields")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("registry diff item address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem":
        value = _mapping(value, "registry diff item")
        _strict(value, set(cls.FIELDS), "registry diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem):
        raise ValidationError("registry diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff:
    """Addressed comparison of two registry snapshots."""

    FIELDS = ("diff_id", "left_registry_address", "right_registry_address", "left_entry_count", "right_entry_count", "added_count", "removed_count", "changed_count", "unchanged_count", "items", "content_address")

    def __init__(self, diff_id: str, left_registry_address: str, right_registry_address: str, left_entry_count: int, right_entry_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, items: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem], content_address: str) -> None:
        self.diff_id = _label(diff_id, "registry diff ID")
        self.left_registry_address = _address(left_registry_address, "registry diff left registry address", registry_model.REGISTRY_PREFIX)
        self.right_registry_address = _address(right_registry_address, "registry diff right registry address", registry_model.REGISTRY_PREFIX)
        self.left_entry_count = _count(left_entry_count, "registry diff left entry count", registry_model.MAX_ENTRIES)
        self.right_entry_count = _count(right_entry_count, "registry diff right entry count", registry_model.MAX_ENTRIES)
        self.added_count = _count(added_count, "registry diff added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "registry diff removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "registry diff changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "registry diff unchanged count", registry_model.MAX_ENTRIES)
        self.items = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem.from_mapping(item) for item in _sequence(items, "registry diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "registry diff address", DIFF_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry diff address")
        self._validate()

    def _validate(self) -> None:
        if len(self.items) != self.added_count + self.removed_count + self.changed_count or self.unchanged_count > min(self.left_entry_count, self.right_entry_count):
            raise ValidationError("registry diff counters are not conserved")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            raise ValidationError("registry diff item ordinals are not exact")
        if sum(item.change_type == "added" for item in self.items) != self.added_count or sum(item.change_type == "removed" for item in self.items) != self.removed_count or sum(item.change_type == "changed" for item in self.items) != self.changed_count:
            raise ValidationError("registry diff change counters do not replay")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("registry diff address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry diff crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "left_registry_address": self.left_registry_address, "right_registry_address": self.right_registry_address, "left_entry_count": self.left_entry_count, "right_entry_count": self.right_entry_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "items": tuple(item.to_dict() for item in self.items), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in self.FIELDS if key != "items"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff":
        value = _mapping(value, "registry diff")
        _strict(value, set(cls.FIELDS), "registry diff")
        items = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem.from_mapping(item) for item in _sequence(value["items"], "registry diff items", MAX_ITEMS))
        return cls(value["diff_id"], value["left_registry_address"], value["right_registry_address"], value["left_entry_count"], value["right_entry_count"], value["added_count"], value["removed_count"], value["changed_count"], value["unchanged_count"], items, value["content_address"])


def address_diff(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff):
        raise ValidationError("registry diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _changed_fields(left: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry, right: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry) -> tuple[str, ...]:
    return tuple(field for field in registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry.FIELDS if field != "content_address" and left.to_dict()[field] != right.to_dict()[field])


def _item(ordinal: int, change_type: str, left: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry | None, right: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry | None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem:
    selected = right or left
    if selected is None:
        raise ValidationError("registry diff item requires a side")
    fields = _changed_fields(left, right) if left is not None and right is not None else tuple()
    body = {"ordinal": ordinal, "change_type": change_type, "entry_id": selected.entry_id, "archive_id": selected.archive_id, "left_address": "" if left is None else left.archive_address, "right_address": "" if right is None else right.archive_address, "left_entry_address": "" if left is None else left.content_address, "right_entry_address": "" if right is None else right.content_address, "changed_fields": fields}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem(**body, content_address=ITEM_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem(**body, content_address=address_item(provisional))


def build_diff(left: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry, right: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry, *, diff_id: str = "consensus-certificate-observatory-archive-registry-diff") -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff:
    left = registry_model.verify_registry(left)
    right = registry_model.verify_registry(right)
    left_by_archive = {item.archive_id: item for item in left.entries}
    right_by_archive = {item.archive_id: item for item in right.entries}
    items = []
    added = removed = changed = unchanged = 0
    for archive_id in sorted(set(left_by_archive) | set(right_by_archive)):
        l_item = left_by_archive.get(archive_id)
        r_item = right_by_archive.get(archive_id)
        if l_item is None:
            added += 1
            items.append(_item(len(items) + 1, "added", None, r_item))
        elif r_item is None:
            removed += 1
            items.append(_item(len(items) + 1, "removed", l_item, None))
        elif l_item.to_dict() == r_item.to_dict():
            unchanged += 1
        else:
            changed += 1
            items.append(_item(len(items) + 1, "changed", l_item, r_item))
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff(diff_id, left.content_address, right.content_address, left.entry_count, right.entry_count, added, removed, changed, unchanged, tuple(items), DIFF_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff(provisional.diff_id, provisional.left_registry_address, provisional.right_registry_address, provisional.left_entry_count, provisional.right_entry_count, provisional.added_count, provisional.removed_count, provisional.changed_count, provisional.unchanged_count, provisional.items, address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff:
    return verify_diff(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff.from_mapping(value))


def verify_diff(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff) or (not value.content_address.endswith(":pending") and address_diff(value) != value.content_address):
        raise ValidationError("registry diff is not valid")
    return value


def diff_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff) -> str:
    value = verify_diff(value)
    stream = io.StringIO()
    fields = ("ordinal", "change_type", "entry_id", "archive_id", "left_address", "right_address", "left_entry_address", "right_entry_address", "changed_fields", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        row["changed_fields"] = ",".join(row["changed_fields"])
        writer.writerow({field: row[field] for field in fields})
    return stream.getvalue()


def render_diff_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff) -> str:
    value = verify_diff(value)
    lines = ["# Certificate Observatory Archive Registry Diff", "", f"- Left: `{value.left_registry_address}`", f"- Right: `{value.right_registry_address}`", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Unchanged: `{value.unchanged_count}`", f"- Address: `{value.content_address}`", "", "| # | change | entry | archive | fields |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.change_type}` | `{item.entry_id}` | `{item.archive_id}` | `{', '.join(item.changed_fields) or '—'}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "change_type": {"type": "string", "enum": list(CHANGE_TYPES)}, "entry_id": {"type": "string"}, "archive_id": {"type": "string"}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "left_entry_address": {"type": "string"}, "right_entry_address": {"type": "string"}, "changed_fields": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + ITEM_PREFIX + ":"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff.FIELDS), "properties": {"diff_id": {"type": "string"}, "left_registry_address": {"type": "string"}, "right_registry_address": {"type": "string"}, "left_entry_count": {"type": "integer", "minimum": 0}, "right_entry_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "items": {"type": "array", "items": item_schema()}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "change_types": CHANGE_TYPES, "limits": {"max_items": MAX_ITEMS}, "features": ("archive identity matching", "added removed and changed entries", "changed-field disclosure", "unchanged counter", "addressable diff items", "JSON CSV and Markdown exports"), "schemas": ("item", "diff")}


__all__ = [
    "BOUNDARY",
    "CHANGE_TYPES",
    "DIFF_PREFIX",
    "ITEM_PREFIX",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem",
    "VERSION",
    "address_diff",
    "address_item",
    "build_diff",
    "capabilities",
    "diff_csv",
    "diff_from_mapping",
    "diff_json",
    "diff_schema",
    "item_schema",
    "render_diff_markdown",
    "verify_diff",
]
