"""Value-free cross-run diffs for policy package registry histories."""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
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

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff"
DIFF_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"
SUMMARY_PREFIX = DIFF_PREFIX + "-summary"
DEFAULT_DIFF_ID = DIFF_PREFIX
FILES = ("manifest.json", "diff.json", "items.json", "summary.json")
MANIFEST_ARTIFACT_FILES = ("items.json", "summary.json")
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "mixed", "unchanged")
ITEM_FIELDS = ("ordinal", "identity", "change", "left_registry_address", "right_registry_address", "left_snapshot", "right_snapshot", "content_address")
ITEMS_FIELDS = ("items", "content_address")
MANIFEST_FIELDS = ("diff_id", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("diff_id", "left_history_address", "right_history_address", "left_entry_count", "right_entry_count", "added_count", "removed_count", "changed_count", "unchanged_count", "initial_delta", "improved_delta", "regressed_delta", "unchanged_delta", "changed_delta", "left_state", "right_state", "direction", "state_transition", "content_address")
DIFF_FIELDS = ("diff_id", "version", "boundary", "left_history_address", "right_history_address", "left_entry_count", "right_entry_count", "added_count", "removed_count", "changed_count", "unchanged_count", "initial_delta", "improved_delta", "regressed_delta", "unchanged_delta", "changed_delta", "left_state", "right_state", "direction", "state_transition", "manifest", "summary", "items", "content_address")
SNAPSHOT_FIELDS = ("registry_id", "entry_count", "accepted_count", "release_ready_count", "promote_count", "hold_count", "block_count", "state", "decision", "accepted", "release_ready", "transition")
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
    if isinstance(value, bool) or not isinstance(value, int) or abs(value) > bound:
        raise ValidationError(f"{field} is outside its signed bound")
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


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _snapshot(value: Any, field: str) -> dict[str, Any]:
    value = _mapping(value, field)
    if not value:
        return {}
    _strict(value, set(SNAPSHOT_FIELDS), field)
    for key in ("registry_id", "state", "decision", "transition"):
        _label(value[key], f"{field} {key}")
    for key in ("entry_count", "accepted_count", "release_ready_count", "promote_count", "hold_count", "block_count"):
        _count(value[key], f"{field} {key}", registry_model.MAX_ENTRIES)
    for key in ("accepted", "release_ready"):
        _bool(value[key], f"{field} {key}")
    if value["state"] not in history_model.STATES or value["decision"] not in history_model.DECISIONS or value["transition"] not in history_model.TRANSITIONS:
        raise ValidationError(f"{field} has an unsupported enum")
    if value["accepted_count"] > value["entry_count"] or value["release_ready_count"] > value["entry_count"] or value["promote_count"] + value["hold_count"] + value["block_count"] != value["entry_count"]:
        raise ValidationError(f"{field} counts are not conserved")
    return {key: value[key] for key in SNAPSHOT_FIELDS}


def _quality(snapshot: Mapping[str, Any]) -> tuple[int, int, int, int, int, int]:
    ranks = {"ready": 0, "empty": 1, "review": 2, "blocked": 3}
    return (ranks[snapshot["state"]], -snapshot["release_ready_count"], -snapshot["accepted_count"], snapshot["block_count"], snapshot["hold_count"], snapshot["entry_count"])


def _direction(left: Mapping[str, Any], right: Mapping[str, Any], changed: bool) -> str:
    if _quality(right) < _quality(left):
        return "improved"
    if _quality(right) > _quality(left):
        return "regressed"
    return "mixed" if changed else "unchanged"


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem:
    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, identity: str, change: str, left_registry_address: str, right_registry_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history diff item ordinal", MAX_ITEMS, positive=True)
        self.identity = _label(identity, "registry history diff item identity")
        self.change = _label(change, "registry history diff item change")
        if self.change not in CHANGES:
            raise ValidationError("registry history diff item change is unsupported")
        self.left_registry_address = _address(left_registry_address, "registry history diff left registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.right_registry_address = _address(right_registry_address, "registry history diff right registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.left_snapshot = _snapshot(left_snapshot, "registry history diff left snapshot")
        self.right_snapshot = _snapshot(right_snapshot, "registry history diff right snapshot")
        self.content_address = _address(content_address, "registry history diff item address", ITEM_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.change == "added" and (self.right_snapshot == {} or self.left_snapshot != {} or not self.right_registry_address or self.left_registry_address):
            raise ValidationError("added diff item does not have one right snapshot")
        if self.change == "removed" and (self.left_snapshot == {} or self.right_snapshot != {} or not self.left_registry_address or self.right_registry_address):
            raise ValidationError("removed diff item does not have one left snapshot")
        if self.change in {"changed", "unchanged"} and (not self.left_snapshot or not self.right_snapshot or not self.left_registry_address or not self.right_registry_address):
            raise ValidationError("paired diff item does not have two snapshots")
        if self.change == "unchanged" and (self.left_snapshot != self.right_snapshot or self.left_registry_address != self.right_registry_address):
            raise ValidationError("unchanged diff item contains a difference")
        if self.change == "changed" and self.left_snapshot == self.right_snapshot and self.left_registry_address == self.right_registry_address:
            raise ValidationError("changed diff item contains no difference")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("registry history diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem:
        value = _mapping(value, "registry history diff item")
        _strict(value, set(cls.FIELDS), "registry history diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem):
        raise ValidationError("registry history diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItems:
    FIELDS = ITEMS_FIELDS

    def __init__(self, items: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.items = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem.from_mapping(item) for item in _sequence(items, "registry history diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "registry history diff items address", ITEM_PREFIX + "s")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff items cross the public boundary")
        if not self.content_address.endswith(":pending") and address_items(self.items) != self.content_address:
            raise ValidationError("registry history diff items address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self.items], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItems:
        value = _mapping(value, "registry history diff items")
        _strict(value, set(cls.FIELDS), "registry history diff items")
        return cls(value["items"], value["content_address"])


def address_items(value: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem) for item in typed):
        raise ValidationError("registry history diff items address requires typed items")
    return content_hash({"items": [item.to_dict() for item in typed]}, prefix=ITEM_PREFIX + "s")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, diff_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.diff_id = _label(diff_id, "registry history diff manifest diff ID")
        self.files = tuple(_label(item, "registry history diff manifest file") for item in _sequence(files, "registry history diff manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "registry history diff manifest artifact address") for item in _sequence(artifact_addresses, "registry history diff manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "registry history diff manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("registry history diff manifest does not close the public file boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("registry history diff manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest:
        value = _mapping(value, "registry history diff manifest")
        _strict(value, set(cls.FIELDS), "registry history diff manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest):
        raise ValidationError("registry history diff manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, diff_id: str, left_history_address: str, right_history_address: str, left_entry_count: int, right_entry_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, initial_delta: int, improved_delta: int, regressed_delta: int, unchanged_delta: int, changed_delta: int, left_state: str, right_state: str, direction: str, state_transition: str, content_address: str) -> None:
        self.diff_id = _label(diff_id, "registry history diff summary diff ID")
        self.left_history_address = _address(left_history_address, "registry history diff summary left history address", history_model.HISTORY_PREFIX)
        self.right_history_address = _address(right_history_address, "registry history diff summary right history address", history_model.HISTORY_PREFIX)
        self.left_entry_count = _count(left_entry_count, "registry history diff summary left entry count", history_model.MAX_ENTRIES)
        self.right_entry_count = _count(right_entry_count, "registry history diff summary right entry count", history_model.MAX_ENTRIES)
        self.added_count = _count(added_count, "registry history diff summary added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "registry history diff summary removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "registry history diff summary changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "registry history diff summary unchanged count", MAX_ITEMS)
        self.initial_delta = _signed(initial_delta, "registry history diff summary initial delta", history_model.MAX_ENTRIES)
        self.improved_delta = _signed(improved_delta, "registry history diff summary improved delta", history_model.MAX_ENTRIES)
        self.regressed_delta = _signed(regressed_delta, "registry history diff summary regressed delta", history_model.MAX_ENTRIES)
        self.unchanged_delta = _signed(unchanged_delta, "registry history diff summary unchanged delta", history_model.MAX_ENTRIES)
        self.changed_delta = _signed(changed_delta, "registry history diff summary changed delta", history_model.MAX_ENTRIES)
        self.left_state = _label(left_state, "registry history diff summary left state")
        self.right_state = _label(right_state, "registry history diff summary right state")
        if self.left_state not in history_model.STATES or self.right_state not in history_model.STATES:
            raise ValidationError("registry history diff summary state is unsupported")
        self.direction = _label(direction, "registry history diff summary direction")
        if self.direction not in DIRECTIONS:
            raise ValidationError("registry history diff summary direction is unsupported")
        self.state_transition = _label(state_transition, "registry history diff summary state transition")
        self.content_address = _address(content_address, "registry history diff summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.added_count + self.removed_count + self.changed_count + self.unchanged_count > MAX_ITEMS:
            raise ValidationError("registry history diff summary item counts exceed bound")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff summary crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("registry history diff summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary:
        value = _mapping(value, "registry history diff summary")
        _strict(value, set(cls.FIELDS), "registry history diff summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary):
        raise ValidationError("registry history diff summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff:
    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, version: str, boundary: str, left_history_address: str, right_history_address: str, left_entry_count: int, right_entry_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, initial_delta: int, improved_delta: int, regressed_delta: int, unchanged_delta: int, changed_delta: int, left_state: str, right_state: str, direction: str, state_transition: str, manifest: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest | Mapping[str, Any], summary: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary | Mapping[str, Any], items: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _label(diff_id, "registry history diff ID")
        self.version = _text(version, "registry history diff version", 512)
        self.boundary = _text(boundary, "registry history diff boundary", 512)
        self.left_history_address = _address(left_history_address, "registry history diff left history address", history_model.HISTORY_PREFIX)
        self.right_history_address = _address(right_history_address, "registry history diff right history address", history_model.HISTORY_PREFIX)
        self.left_entry_count = _count(left_entry_count, "registry history diff left entry count", history_model.MAX_ENTRIES)
        self.right_entry_count = _count(right_entry_count, "registry history diff right entry count", history_model.MAX_ENTRIES)
        self.added_count = _count(added_count, "registry history diff added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "registry history diff removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "registry history diff changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "registry history diff unchanged count", MAX_ITEMS)
        self.initial_delta = _signed(initial_delta, "registry history diff initial delta", history_model.MAX_ENTRIES)
        self.improved_delta = _signed(improved_delta, "registry history diff improved delta", history_model.MAX_ENTRIES)
        self.regressed_delta = _signed(regressed_delta, "registry history diff regressed delta", history_model.MAX_ENTRIES)
        self.unchanged_delta = _signed(unchanged_delta, "registry history diff unchanged delta", history_model.MAX_ENTRIES)
        self.changed_delta = _signed(changed_delta, "registry history diff changed delta", history_model.MAX_ENTRIES)
        self.left_state = _label(left_state, "registry history diff left state")
        self.right_state = _label(right_state, "registry history diff right state")
        if self.left_state not in history_model.STATES or self.right_state not in history_model.STATES:
            raise ValidationError("registry history diff state is unsupported")
        self.direction = _label(direction, "registry history diff direction")
        if self.direction not in DIRECTIONS:
            raise ValidationError("registry history diff direction is unsupported")
        self.state_transition = _label(state_transition, "registry history diff state transition")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary.from_mapping(summary)
        self.items = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem.from_mapping(item) for item in _sequence(items, "registry history diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "registry history diff address", DIFF_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("registry history diff version or boundary is not current")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            raise ValidationError("registry history diff item order is not conserved")
        if len({item.identity for item in self.items}) != len(self.items):
            raise ValidationError("registry history diff item identities must be unique")
        counts = tuple(sum(item.change == change for item in self.items) for change in CHANGES)
        if counts != (self.added_count, self.removed_count, self.changed_count, self.unchanged_count):
            raise ValidationError("registry history diff item counts do not replay")
        if (self.initial_delta, self.improved_delta, self.regressed_delta, self.unchanged_delta, self.changed_delta) != (self.summary.initial_delta, self.summary.improved_delta, self.summary.regressed_delta, self.summary.unchanged_delta, self.summary.changed_delta):
            raise ValidationError("registry history diff transition deltas do not replay")
        if self.state_transition != f"{self.left_state}->{self.right_state}":
            raise ValidationError("registry history diff state transition does not replay")
        if (self.summary.diff_id, self.summary.left_history_address, self.summary.right_history_address, self.summary.left_entry_count, self.summary.right_entry_count, self.summary.added_count, self.summary.removed_count, self.summary.changed_count, self.summary.unchanged_count, self.summary.initial_delta, self.summary.improved_delta, self.summary.regressed_delta, self.summary.unchanged_delta, self.summary.changed_delta, self.summary.left_state, self.summary.right_state, self.summary.direction, self.summary.state_transition) != (self.diff_id, self.left_history_address, self.right_history_address, self.left_entry_count, self.right_entry_count, self.added_count, self.removed_count, self.changed_count, self.unchanged_count, self.initial_delta, self.improved_delta, self.regressed_delta, self.unchanged_delta, self.changed_delta, self.left_state, self.right_state, self.direction, self.state_transition):
            raise ValidationError("registry history diff summary does not replay")
        if (self.manifest.diff_id, self.manifest.files, tuple(self.manifest.artifact_addresses)) != (self.diff_id, FILES, (address_items(self.items), self.summary.content_address)):
            raise ValidationError("registry history diff manifest does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("registry history diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "left_history_address": self.left_history_address, "right_history_address": self.right_history_address, "left_entry_count": self.left_entry_count, "right_entry_count": self.right_entry_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "initial_delta": self.initial_delta, "improved_delta": self.improved_delta, "regressed_delta": self.regressed_delta, "unchanged_delta": self.unchanged_delta, "changed_delta": self.changed_delta, "left_state": self.left_state, "right_state": self.right_state, "direction": self.direction, "state_transition": self.state_transition, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "items": [item.to_dict() for item in self.items], "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "summary", "items"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff:
        value = _mapping(value, "registry history diff")
        _strict(value, set(cls.FIELDS), "registry history diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff):
        raise ValidationError("registry history diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _entry_snapshot(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry) -> dict[str, Any]:
    return {key: getattr(value, key) for key in SNAPSHOT_FIELDS}


def _item(ordinal: int, left: Any | None, right: Any | None) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem:
    left_snapshot = _entry_snapshot(left) if left else {}
    right_snapshot = _entry_snapshot(right) if right else {}
    if left is None:
        change = "added"
    elif right is None:
        change = "removed"
    elif left_snapshot == right_snapshot and left.registry_address == right.registry_address:
        change = "unchanged"
    else:
        change = "changed"
    body = {"ordinal": ordinal, "identity": f"ordinal-{ordinal}", "change": change, "left_registry_address": left.registry_address if left else "", "right_registry_address": right.registry_address if right else "", "left_snapshot": left_snapshot, "right_snapshot": right_snapshot, "content_address": ITEM_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem(**(body | {"content_address": address_item(provisional)}))


def _history_summary(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory) -> dict[str, Any]:
    latest = value.entries[-1] if value.entries else None
    return {"state": value.state, "entry_count": value.latest_entry_count, "accepted_count": value.latest_accepted_count, "release_ready_count": value.latest_release_ready_count, "block_count": latest.block_count if latest else 0, "hold_count": latest.hold_count if latest else 0}


def build_diff(left: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, right: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, *, diff_id: str = DEFAULT_DIFF_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff:
    if not isinstance(left, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory) or not isinstance(right, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
        raise ValidationError("registry history diff requires typed histories")
    if left.history_id != right.history_id or left.registry_id != right.registry_id:
        raise ValidationError("registry history diff requires matching logical identities")
    total = max(len(left.entries), len(right.entries))
    items = tuple(_item(ordinal, left.entries[ordinal - 1] if ordinal <= len(left.entries) else None, right.entries[ordinal - 1] if ordinal <= len(right.entries) else None) for ordinal in range(1, total + 1))
    counts = {change + "_count": sum(item.change == change for item in items) for change in CHANGES}
    left_transitions = {transition: sum(item.transition == transition for item in left.entries) for transition in history_model.TRANSITIONS}
    right_transitions = {transition: sum(item.transition == transition for item in right.entries) for transition in history_model.TRANSITIONS}
    deltas = {transition + "_delta": right_transitions[transition] - left_transitions[transition] for transition in history_model.TRANSITIONS}
    left_summary = _history_summary(left)
    right_summary = _history_summary(right)
    changed = any(item.change != "unchanged" for item in items)
    direction = _direction(left_summary, right_summary, changed)
    state_transition = f"{left.state}->{right.state}"
    summary_body = {"diff_id": diff_id, "left_history_address": left.content_address, "right_history_address": right.content_address, "left_entry_count": left.entry_count, "right_entry_count": right.entry_count, **counts, **deltas, "left_state": left.state, "right_state": right.state, "direction": direction, "state_transition": state_transition, "content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary(**summary_body)
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    items_address = address_items(items)
    manifest_body = {"diff_id": diff_id, "files": FILES, "artifact_addresses": (items_address, summary.content_address), "content_address": MANIFEST_PREFIX + ":pending"}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest(**manifest_body)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = {"diff_id": diff_id, "version": VERSION, "boundary": BOUNDARY, "left_history_address": left.content_address, "right_history_address": right.content_address, "left_entry_count": left.entry_count, "right_entry_count": right.entry_count, **counts, **deltas, "left_state": left.state, "right_state": right.state, "direction": direction, "state_transition": state_transition, "manifest": manifest, "summary": summary, "items": items, "content_address": DIFF_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff(**(body | {"content_address": address_diff(provisional)}))


def diff_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff.from_mapping(value)


def diff_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff) -> str:
    return canonical_json(diff_from_mapping(value.to_dict()).to_dict())


def diff_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff) -> str:
    value = diff_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ITEM_FIELDS)
    writer.writerows(tuple(json.dumps(item.to_dict()[field], ensure_ascii=False, sort_keys=True) if isinstance(item.to_dict()[field], (tuple, list, dict)) else item.to_dict()[field] for field in ITEM_FIELDS) for item in value.items)
    return output.getvalue()


def render_diff_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff) -> str:
    value = diff_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry History Diff", "", f"- Diff: `{value.diff_id}`", f"- Direction: `{value.direction}`", f"- State transition: `{value.state_transition}`", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Unchanged: `{value.unchanged_count}`", f"- Address: `{value.content_address}`", "", "| # | identity | change | left | right |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.identity}` | `{item.change}` | `{item.left_registry_address}` | `{item.right_registry_address}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def items_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItems) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItems.from_mapping(value.to_dict()).to_dict())


def summary_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary.from_mapping(value.to_dict()).to_dict())


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_diff(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff):
        raise ValidationError("registry history diff persistence requires a typed diff")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("registry history diff destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-policy-package-registry-history-diff-", dir=str(parent)))
    try:
        items = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItems(value.items, address_items(value.items))
        documents = {"manifest.json": value.manifest.to_dict(), "diff.json": value.to_dict(), "items.json": items.to_dict(), "summary.json": value.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("registry history diff destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("registry history diff artifact is not valid JSON") from error
    return _mapping(value, "registry history diff artifact")


def _read_canonical(path: Path, value: Mapping[str, Any]) -> None:
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValidationError("registry history diff artifact cannot be read") from error
    if actual != canonical_json(value):
        raise ValidationError("registry history diff artifact is not canonical")


def load_diff(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("registry history diff destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("registry history diff directory does not contain the exact file set")
    raw = {name: _read_json(destination / name) for name in FILES}
    for name, value in raw.items():
        _read_canonical(destination / name, value)
    diff = diff_from_mapping(raw["diff.json"])
    items = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItems.from_mapping(raw["items.json"])
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest.from_mapping(raw["manifest.json"])
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary.from_mapping(raw["summary.json"])
    if items.to_dict() != {"items": [item.to_dict() for item in diff.items], "content_address": address_items(diff.items)} or manifest.to_dict() != diff.manifest.to_dict() or summary.to_dict() != diff.summary.to_dict():
        raise ValidationError("registry history diff artifacts do not replay")
    return diff


def run_diff(left: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, right: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, *, diff_id: str = DEFAULT_DIFF_ID, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff:
    value = build_diff(left, right, diff_id=diff_id)
    if destination is not None:
        persist_diff(value, destination, overwrite=overwrite)
    return value


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff item", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "identity": {"type": "string"}, "change": {"enum": list(CHANGES)}, "left_registry_address": {"type": "string"}, "right_registry_address": {"type": "string"}, "left_snapshot": {"type": "object"}, "right_snapshot": {"type": "object"}, "content_address": {"type": "string"}}}


def items_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff items", "type": "object", "additionalProperties": False, "required": list(ITEMS_FIELDS), "properties": {"items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"diff_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"diff_id": {"type": "string"}, "left_history_address": {"type": "string"}, "right_history_address": {"type": "string"}, "left_entry_count": {"type": "integer", "minimum": 0}, "right_entry_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "initial_delta": {"type": "integer"}, "improved_delta": {"type": "integer"}, "regressed_delta": {"type": "integer"}, "unchanged_delta": {"type": "integer"}, "changed_delta": {"type": "integer"}, "left_state": {"enum": list(history_model.STATES)}, "right_state": {"enum": list(history_model.STATES)}, "direction": {"enum": list(DIRECTIONS)}, "state_transition": {"type": "string"}, "content_address": {"type": "string"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "left_history_address": {"type": "string"}, "right_history_address": {"type": "string"}, "left_entry_count": {"type": "integer", "minimum": 0}, "right_entry_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "initial_delta": {"type": "integer"}, "improved_delta": {"type": "integer"}, "regressed_delta": {"type": "integer"}, "unchanged_delta": {"type": "integer"}, "changed_delta": {"type": "integer"}, "left_state": {"enum": list(history_model.STATES)}, "right_state": {"enum": list(history_model.STATES)}, "direction": {"enum": list(DIRECTIONS)}, "state_transition": {"type": "string"}, "manifest": {"type": "object"}, "summary": {"type": "object"}, "items": {"type": "array", "items": item_schema(), "maxItems": MAX_ITEMS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": list(FILES), "changes": list(CHANGES), "directions": list(DIRECTIONS), "max_items": MAX_ITEMS, "features": ["cross-run history comparison", "added removed changed and unchanged classification", "signed transition deltas", "direction and state-transition folding", "exact four-file persistence", "canonical reload verification", "atomic writes", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False}}


__all__ = ["BOUNDARY", "CHANGES", "DEFAULT_DIFF_ID", "DIFF_FIELDS", "DIFF_PREFIX", "DIRECTIONS", "FILES", "ITEM_FIELDS", "ITEM_PREFIX", "ITEMS_FIELDS", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ITEMS", "SNAPSHOT_FIELDS", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItem", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffItems", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffSummary", "address_diff", "address_item", "address_items", "address_manifest", "address_summary", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "items_json", "items_schema", "load_diff", "manifest_schema", "persist_diff", "render_diff_markdown", "run_diff", "summary_json", "summary_schema"]
