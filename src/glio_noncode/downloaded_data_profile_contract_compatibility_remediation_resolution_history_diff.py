"""Deterministic value-free diffs between remediation-resolution histories."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history as history_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff"
DIFF_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
DEFAULT_DIFF_ID = DIFF_PREFIX
RESOURCES = ("summary", "items")
ITEM_RESOURCES = ("items",)
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "mixed", "unchanged")
CHANGED_ATTRIBUTES = ("resolution_id", "plan_id", "resolution_address", "required_open_count", "pending_count", "resolved_count", "waived_count", "rejected_count", "not_applicable_count", "state", "decision", "release_ready", "transition", "previous_resolution_address")
ITEM_FIELDS = ("ordinal", "resource", "identity", "change", "changed_attributes", "left_address", "right_address", "left_snapshot", "right_snapshot", "content_address")
DIFF_FIELDS = ("diff_id", "version", "boundary", "left_history_address", "right_history_address", "left_entry_count", "right_entry_count", "left_latest_required_open_count", "right_latest_required_open_count", "left_release_ready", "right_release_ready", "left_initial_count", "right_initial_count", "left_improved_count", "right_improved_count", "left_regressed_count", "right_regressed_count", "left_unchanged_count", "right_unchanged_count", "added_count", "removed_count", "changed_count", "unchanged_count", "improved_delta", "regressed_delta", "direction", "state_transition", "items", "content_address")
MAX_ITEMS = 2 * history_model.MAX_ENTRIES


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _signed(value: Any, field: str, bound: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < -bound or value > bound:
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


def _ordered_labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not labels or len(set(labels)) != len(labels) or any(item not in allowed for item in labels) or tuple(sorted(labels, key=allowed.index)) != labels:
        raise ValidationError(f"{field} contains unsupported or unordered labels")
    return labels


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _entry_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    return history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry.from_mapping(value).to_dict()


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem:
    """One value-free added, removed, changed, or unchanged history entry."""

    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, change: str, changed_attributes: Sequence[str], left_address: str, right_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff item ordinal", MAX_ITEMS, positive=True)
        self.resource = _label(resource, "history diff item resource")
        if self.resource not in ITEM_RESOURCES:
            raise ValidationError("history diff item resource is unsupported")
        self.identity = _label(identity, "history diff item identity")
        self.change = _label(change, "history diff item change")
        if self.change not in CHANGES:
            raise ValidationError("history diff item change is unsupported")
        self.changed_attributes = tuple(_label(item, "history diff changed attribute") for item in _sequence(changed_attributes, "history diff changed attributes", len(CHANGED_ATTRIBUTES)))
        if len(set(self.changed_attributes)) != len(self.changed_attributes) or any(item not in CHANGED_ATTRIBUTES for item in self.changed_attributes) or tuple(self.changed_attributes) != tuple(sorted(self.changed_attributes, key=CHANGED_ATTRIBUTES.index)):
            raise ValidationError("history diff changed attributes are unsupported, duplicated, or unordered")
        self.left_address = _address(left_address, "history diff left address", history_model.ENTRY_PREFIX) if left_address else ""
        self.right_address = _address(right_address, "history diff right address", history_model.ENTRY_PREFIX) if right_address else ""
        self.left_snapshot = dict(_mapping(left_snapshot, "history diff left snapshot"))
        self.right_snapshot = dict(_mapping(right_snapshot, "history diff right snapshot"))
        if self.left_snapshot:
            self.left_snapshot = _entry_snapshot(self.left_snapshot)
        if self.right_snapshot:
            self.right_snapshot = _entry_snapshot(self.right_snapshot)
        self.content_address = _address(content_address, "history diff item address", ITEM_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and (self.left_snapshot or self.right_snapshot or self.left_address or self.right_address):
            raise ValidationError("history diff summary item contains entry fields")
        if self.resource == "items" and self.change == "added" and (self.left_address or self.left_snapshot or not self.right_address or not self.right_snapshot or self.changed_attributes):
            raise ValidationError("added history diff item has invalid left side")
        if self.resource == "items" and self.change == "removed" and (not self.left_address or not self.left_snapshot or self.right_address or self.right_snapshot or self.changed_attributes):
            raise ValidationError("removed history diff item has invalid right side")
        if self.resource == "items" and self.change in {"changed", "unchanged"} and (not self.left_address or not self.right_address or not self.left_snapshot or not self.right_snapshot):
            raise ValidationError("history diff item is missing a snapshot side")
        if self.change == "unchanged" and self.changed_attributes:
            raise ValidationError("unchanged history diff item has changed attributes")
        if self.change == "changed" and not self.changed_attributes:
            raise ValidationError("changed history diff item has no changed attributes")
        if self.change == "changed":
            left = {key: value for key, value in self.left_snapshot.items() if key != "content_address"}
            right = {key: value for key, value in self.right_snapshot.items() if key != "content_address"}
            expected = tuple(name for name in CHANGED_ATTRIBUTES if left.get(name) != right.get(name))
            if expected != self.changed_attributes:
                raise ValidationError("history diff item changed attributes do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("history diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"left_snapshot", "right_snapshot"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem:
        value = _mapping(value, "history diff item")
        _strict(value, set(cls.FIELDS), "history diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem):
        raise ValidationError("history diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff:
    """Complete deterministic transition between two value-free histories."""

    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, version: str, boundary: str, left_history_address: str, right_history_address: str, left_entry_count: int, right_entry_count: int, left_latest_required_open_count: int, right_latest_required_open_count: int, left_release_ready: bool, right_release_ready: bool, left_initial_count: int, right_initial_count: int, left_improved_count: int, right_improved_count: int, left_regressed_count: int, right_regressed_count: int, left_unchanged_count: int, right_unchanged_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, improved_delta: int, regressed_delta: int, direction: str, state_transition: str, items: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _label(diff_id, "history diff ID")
        self.version = _text(version, "history diff version")
        self.boundary = _text(boundary, "history diff boundary", 512)
        self.left_history_address = _address(left_history_address, "left history address", history_model.HISTORY_PREFIX)
        self.right_history_address = _address(right_history_address, "right history address", history_model.HISTORY_PREFIX)
        self.left_entry_count = _count(left_entry_count, "left history entry count", history_model.MAX_ENTRIES)
        self.right_entry_count = _count(right_entry_count, "right history entry count", history_model.MAX_ENTRIES)
        self.left_latest_required_open_count = _count(left_latest_required_open_count, "left history open count", history_model.MAX_ENTRIES)
        self.right_latest_required_open_count = _count(right_latest_required_open_count, "right history open count", history_model.MAX_ENTRIES)
        self.left_release_ready = _bool(left_release_ready, "left history release readiness")
        self.right_release_ready = _bool(right_release_ready, "right history release readiness")
        for field in ("left_initial_count", "right_initial_count", "left_improved_count", "right_improved_count", "left_regressed_count", "right_regressed_count", "left_unchanged_count", "right_unchanged_count", "added_count", "removed_count", "changed_count", "unchanged_count"):
            setattr(self, field, _count(locals()[field], f"history diff {field}", MAX_ITEMS))
        self.improved_delta = _signed(improved_delta, "history diff improved delta", history_model.MAX_ENTRIES)
        self.regressed_delta = _signed(regressed_delta, "history diff regressed delta", history_model.MAX_ENTRIES)
        self.direction = _label(direction, "history diff direction")
        if self.direction not in DIRECTIONS:
            raise ValidationError("history diff direction is unsupported")
        self.state_transition = _label(state_transition, "history diff state transition")
        self.items = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem.from_mapping(item) for item in _sequence(items, "history diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "history diff address", DIFF_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff version or boundary is not current")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or len({(item.resource, item.identity) for item in self.items}) != len(self.items):
            raise ValidationError("history diff item order or identity does not replay")
        counts = {change: sum(item.resource == "items" and item.change == change for item in self.items) for change in CHANGES}
        if (self.added_count, self.removed_count, self.changed_count, self.unchanged_count) != tuple(counts[change] for change in CHANGES):
            raise ValidationError("history diff change counts do not replay")
        if self.left_entry_count != counts["removed"] + counts["changed"] + counts["unchanged"] or self.right_entry_count != counts["added"] + counts["changed"] + counts["unchanged"]:
            raise ValidationError("history diff entry totals do not replay")
        if (self.left_initial_count, self.left_improved_count, self.left_regressed_count, self.left_unchanged_count) == (0, 0, 0, 0) and self.left_entry_count:
            raise ValidationError("non-empty left history must retain transition counts")
        if (self.right_initial_count, self.right_improved_count, self.right_regressed_count, self.right_unchanged_count) == (0, 0, 0, 0) and self.right_entry_count:
            raise ValidationError("non-empty right history must retain transition counts")
        if self.left_entry_count != self.left_initial_count + self.left_improved_count + self.left_regressed_count + self.left_unchanged_count or self.right_entry_count != self.right_initial_count + self.right_improved_count + self.right_regressed_count + self.right_unchanged_count:
            raise ValidationError("history transition totals do not replay")
        if self.improved_delta != self.right_improved_count - self.left_improved_count or self.regressed_delta != self.right_regressed_count - self.left_regressed_count:
            raise ValidationError("history diff aggregate deltas do not replay")
        if not self.state_transition or "." in self.state_transition:
            raise ValidationError("history diff state transition is unsupported")
        expected_direction = _direction(self.left_latest_required_open_count, self.right_latest_required_open_count, self.left_release_ready, self.right_release_ready)
        if self.direction != expected_direction:
            raise ValidationError("history diff direction does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("history diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "left_history_address": self.left_history_address, "right_history_address": self.right_history_address, "left_entry_count": self.left_entry_count, "right_entry_count": self.right_entry_count, "left_latest_required_open_count": self.left_latest_required_open_count, "right_latest_required_open_count": self.right_latest_required_open_count, "left_release_ready": self.left_release_ready, "right_release_ready": self.right_release_ready, "left_initial_count": self.left_initial_count, "right_initial_count": self.right_initial_count, "left_improved_count": self.left_improved_count, "right_improved_count": self.right_improved_count, "left_regressed_count": self.left_regressed_count, "right_regressed_count": self.right_regressed_count, "left_unchanged_count": self.left_unchanged_count, "right_unchanged_count": self.right_unchanged_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "improved_delta": self.improved_delta, "regressed_delta": self.regressed_delta, "direction": self.direction, "state_transition": self.state_transition, "items": tuple(item.to_dict() for item in self.items), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "items"}

    def resource_items(self, resource: str) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem, ...]:
        resource = _label(resource, "history diff resource lookup")
        if resource not in RESOURCES:
            raise ValidationError("history diff resource is unsupported")
        return tuple(item for item in self.items if item.resource == resource)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff:
        value = _mapping(value, "history diff")
        _strict(value, set(cls.FIELDS), "history diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff):
        raise ValidationError("history diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _direction(left_open: int, right_open: int, left_ready: bool, right_ready: bool) -> str:
    if right_open < left_open or (right_open == left_open and right_ready and not left_ready):
        return "improved"
    if right_open > left_open or (right_open == left_open and left_ready and not right_ready):
        return "regressed"
    if right_open == left_open and left_ready == right_ready:
        return "unchanged"
    return "mixed"


def _item(ordinal: int, identity: str, change: str, left: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry | None, right: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry | None) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem:
    left_snapshot = left.to_dict() if left else {}
    right_snapshot = right.to_dict() if right else {}
    changed = () if change in {"added", "removed"} else tuple(name for name in CHANGED_ATTRIBUTES if left_snapshot.get(name) != right_snapshot.get(name))
    body = {"ordinal": ordinal, "resource": "items", "identity": identity, "change": change, "changed_attributes": changed, "left_address": left.content_address if left else "", "right_address": right.content_address if right else "", "left_snapshot": left_snapshot, "right_snapshot": right_snapshot, "content_address": ITEM_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem(**(body | {"content_address": address_item(provisional)}))


def _state_name(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory) -> str:
    return value.state


def build_diff(left: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory, right: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory, *, diff_id: str = DEFAULT_DIFF_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff:
    if not isinstance(left, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory) or not isinstance(right, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory):
        raise ValidationError("history diff requires typed histories")
    left_values = {str(value.ordinal): value for value in left.entries}
    right_values = {str(value.ordinal): value for value in right.entries}
    items = []
    for ordinal, identity in enumerate(sorted(set(left_values) | set(right_values), key=int), 1):
        before, after = left_values.get(identity), right_values.get(identity)
        change = "added" if before is None else "removed" if after is None else "unchanged" if (before.to_dict() | {"content_address": None}) == (after.to_dict() | {"content_address": None}) else "changed"
        items.append(_item(ordinal, identity, change, before, after))
    counts = tuple(sum(item.change == change for item in items) for change in CHANGES)
    body = {"diff_id": diff_id, "version": VERSION, "boundary": BOUNDARY, "left_history_address": left.content_address, "right_history_address": right.content_address, "left_entry_count": left.entry_count, "right_entry_count": right.entry_count, "left_latest_required_open_count": left.latest_required_open_count, "right_latest_required_open_count": right.latest_required_open_count, "left_release_ready": left.release_ready, "right_release_ready": right.release_ready, "left_initial_count": left.initial_count, "right_initial_count": right.initial_count, "left_improved_count": left.improved_count, "right_improved_count": right.improved_count, "left_regressed_count": left.regressed_count, "right_regressed_count": right.regressed_count, "left_unchanged_count": left.unchanged_count, "right_unchanged_count": right.unchanged_count, "added_count": counts[0], "removed_count": counts[1], "changed_count": counts[2], "unchanged_count": counts[3], "improved_delta": right.improved_count - left.improved_count, "regressed_delta": right.regressed_count - left.regressed_count, "direction": _direction(left.latest_required_open_count, right.latest_required_open_count, left.release_ready, right.release_ready), "state_transition": f"{_state_name(left)}-{_state_name(right)}", "items": tuple(items), "content_address": DIFF_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff(**(body | {"content_address": address_diff(provisional)}))


def diff_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff.from_mapping(value)


def diff_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff) -> str:
    return canonical_json(diff_from_mapping(value.to_dict()).to_dict())


def diff_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff) -> str:
    value = diff_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ITEM_FIELDS)
    writer.writerows(tuple(";".join(item.changed_attributes) if field == "changed_attributes" else item.to_dict()[field] for field in ITEM_FIELDS) for item in value.items)
    return stream.getvalue()


def render_diff_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff) -> str:
    value = diff_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Diff", "", f"- Diff: `{value.diff_id}`", f"- Direction: `{value.direction}`", f"- State transition: `{value.state_transition}`", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Unchanged: `{value.unchanged_count}`", f"- Address: `{value.content_address}`", "", "| # | snapshot | change | changed attributes |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.identity}` | `{item.change}` | `{', '.join(item.changed_attributes)}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff item", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(ITEM_RESOURCES)}, "identity": {"type": "string"}, "change": {"enum": list(CHANGES)}, "changed_attributes": {"type": "array", "items": {"enum": list(CHANGED_ATTRIBUTES)}}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "left_snapshot": {"type": "object"}, "right_snapshot": {"type": "object"}, "content_address": {"type": "string"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "left_history_address": {"type": "string"}, "right_history_address": {"type": "string"}, "left_entry_count": {"type": "integer", "minimum": 0}, "right_entry_count": {"type": "integer", "minimum": 0}, "left_latest_required_open_count": {"type": "integer", "minimum": 0}, "right_latest_required_open_count": {"type": "integer", "minimum": 0}, "left_release_ready": {"type": "boolean"}, "right_release_ready": {"type": "boolean"}, "left_initial_count": {"type": "integer", "minimum": 0}, "right_initial_count": {"type": "integer", "minimum": 0}, "left_improved_count": {"type": "integer", "minimum": 0}, "right_improved_count": {"type": "integer", "minimum": 0}, "left_regressed_count": {"type": "integer", "minimum": 0}, "right_regressed_count": {"type": "integer", "minimum": 0}, "left_unchanged_count": {"type": "integer", "minimum": 0}, "right_unchanged_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "improved_delta": {"type": "integer"}, "regressed_delta": {"type": "integer"}, "direction": {"enum": list(DIRECTIONS)}, "state_transition": {"type": "string"}, "items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "changes": CHANGES, "directions": DIRECTIONS, "operations": ("build_diff", "diff_from_mapping", "diff_json", "diff_csv", "render_diff_markdown"), "limits": {"max_items": MAX_ITEMS}}


__all__ = ["BOUNDARY", "CHANGES", "CHANGED_ATTRIBUTES", "DEFAULT_DIFF_ID", "DIFF_FIELDS", "DIFF_PREFIX", "DIRECTIONS", "ITEM_FIELDS", "ITEM_PREFIX", "ITEM_RESOURCES", "MAX_ITEMS", "RESOURCES", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem", "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_diff_markdown"]
