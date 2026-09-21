"""Compare baseline and candidate D487 gate-decision ledgers."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger as ledger_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = ledger_model.VERSION + "-diff-v1"
BOUNDARY = ledger_model.BOUNDARY + "_diff"
DIFF_PREFIX = ledger_model.LEDGER_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
ITEMS_PREFIX = DIFF_PREFIX + "-items"
POLICY_PREFIX = DIFF_PREFIX + "-policy"
CHECK_PREFIX = DIFF_PREFIX + "-check"
CHECKS_PREFIX = DIFF_PREFIX + "-checks"
MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"
SUMMARY_PREFIX = DIFF_PREFIX + "-summary"
DEFAULT_DIFF_ID = DIFF_PREFIX
FILES = ("manifest.json", "diff.json", "policy.json", "items.json", "checks.json", "summary.json")
ARTIFACT_FILES = ("policy.json", "items.json", "checks.json", "summary.json")
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "changed", "unchanged")
STATES = ("ready", "blocked", "empty")
SEVERITIES = ("info", "error")
MAX_ITEMS = ledger_model.MAX_ENTRIES * 2
MAX_CHECKS = 16
MAX_DIFF_BYTES = 32 * 1024 * 1024
POLICY_FIELDS = ("policy_id", "left_ledger_id", "right_ledger_id", "minimum_items", "maximum_added", "maximum_removed", "maximum_changed", "allowed_directions", "require_same_scenario", "require_append_only", "require_head_change", "require_accepted", "content_address")
ITEM_FIELDS = ("ordinal", "decision_id", "change", "changed_fields", "left_entry_address", "right_entry_address", "left_snapshot", "right_snapshot", "content_address")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "severity", "actual", "expected", "detail", "content_address")
MANIFEST_FIELDS = ("diff_id", "left_ledger_id", "right_ledger_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("diff_id", "left_ledger_id", "right_ledger_id", "left_ledger_address", "right_ledger_address", "left_entry_count", "right_entry_count", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "state_transition", "left_state", "right_state", "left_final_ready", "right_final_ready", "accepted", "release_ready", "content_address")
DIFF_FIELDS = ("diff_id", "version", "boundary", "left_ledger_id", "right_ledger_id", "left_ledger_address", "right_ledger_address", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "state_transition", "left_state", "right_state", "left_final_ready", "right_final_ready", "accepted", "release_ready", "policy", "checks", "manifest", "summary", "items", "content_address")
CHECK_IDS = ("ledgers_present", "ledger_identity", "same_scenario", "minimum_items", "added_budget", "removed_budget", "changed_budget", "append_only", "head_change", "direction_policy", "accepted_policy", "classification_conservation", "identity_integrity", "address_integrity", "policy_integrity", "release_disposition")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value): raise ValidationError(f"{field} must be bounded public text")
    return value
def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value): raise ValidationError(f"{field} must be a compact label")
    return value
def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if not value: return value
    if value.startswith("pending:") or value.endswith(":pending"): return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")): raise ValidationError(f"{field} has the wrong address namespace")
    return value
def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum: raise ValidationError(f"{field} is outside its bound")
    return value
def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool): raise ValidationError(f"{field} must be boolean")
    return value
def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)
def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ValidationError(f"{field} must be an object")
    return value
def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed: raise ValidationError(f"{field} contains unknown or missing fields")
def _public(value: Any) -> bool: return ledger_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _snapshot(value: Any, field: str, *, required: bool) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        if not required and value == {}: return {}
        raise ValidationError(f"{field} must be an object")
    if not required and not value: return {}
    _strict(value, set(ledger_model.ENTRY_FIELDS), field)
    result = dict(value)
    if not _public(result): raise ValidationError(f"{field} crosses the public boundary")
    return result
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class LedgerDiffPolicy:
    FIELDS = POLICY_FIELDS
    def __init__(self, policy_id: str, left_ledger_id: str, right_ledger_id: str, minimum_items: int, maximum_added: int, maximum_removed: int, maximum_changed: int, allowed_directions: Sequence[str], require_same_scenario: bool, require_append_only: bool, require_head_change: bool, require_accepted: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "ledger diff policy ID"); self.left_ledger_id = _label(left_ledger_id, "ledger diff left ledger ID"); self.right_ledger_id = _label(right_ledger_id, "ledger diff right ledger ID"); self.minimum_items = _count(minimum_items, "ledger diff minimum items", MAX_ITEMS, lower=1); self.maximum_added = _count(maximum_added, "ledger diff maximum added", MAX_ITEMS); self.maximum_removed = _count(maximum_removed, "ledger diff maximum removed", MAX_ITEMS); self.maximum_changed = _count(maximum_changed, "ledger diff maximum changed", MAX_ITEMS); self.allowed_directions = tuple(_label(item, "ledger diff allowed direction") for item in _sequence(allowed_directions, "ledger diff allowed directions", len(DIRECTIONS))); self.require_same_scenario = _bool(require_same_scenario, "ledger diff same-scenario requirement"); self.require_append_only = _bool(require_append_only, "ledger diff append-only requirement"); self.require_head_change = _bool(require_head_change, "ledger diff head-change requirement"); self.require_accepted = _bool(require_accepted, "ledger diff acceptance requirement"); self.content_address = _address(content_address, "ledger diff policy address", POLICY_PREFIX); self._validate()
    def _validate(self) -> None:
        if not self.allowed_directions or any(item not in DIRECTIONS for item in self.allowed_directions) or len(set(self.allowed_directions)) != len(self.allowed_directions): raise ValidationError("ledger diff policy directions are unsupported or duplicated")
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address: raise ValidationError("ledger diff policy address does not replay")
        if not _public(self.to_dict()): raise ValidationError("ledger diff policy crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"allowed_directions": list(self.allowed_directions), "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerDiffPolicy":
        value = _mapping(value, "ledger diff policy"); _strict(value, set(cls.FIELDS), "ledger diff policy"); return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: LedgerDiffPolicy) -> str:
    if not isinstance(value, LedgerDiffPolicy): raise ValidationError("ledger diff policy address requires a typed policy")
    return _address_for(value, POLICY_PREFIX)


class DiffItem:
    FIELDS = ITEM_FIELDS
    def __init__(self, ordinal: int, decision_id: str, change: str, changed_fields: Sequence[str], left_entry_address: str, right_entry_address: str, left_snapshot: Mapping[str, Any], right_snapshot: Mapping[str, Any], content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff item ordinal", MAX_ITEMS, lower=1); self.decision_id = _label(decision_id, "ledger diff decision ID")
        if change not in CHANGES: raise ValidationError("ledger diff change is unsupported")
        self.change = change; self.changed_fields = tuple(_label(item, "ledger diff changed field") for item in _sequence(changed_fields, "ledger diff changed fields", len(ledger_model.ENTRY_FIELDS))); self.left_entry_address = _address(left_entry_address, "ledger diff left entry address", ledger_model.ENTRY_PREFIX, required=False); self.right_entry_address = _address(right_entry_address, "ledger diff right entry address", ledger_model.ENTRY_PREFIX, required=False); self.left_snapshot = _snapshot(left_snapshot, "ledger diff left snapshot", required=False); self.right_snapshot = _snapshot(right_snapshot, "ledger diff right snapshot", required=False); self.content_address = _address(content_address, "ledger diff item address", ITEM_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.change == "added" and (self.left_snapshot or not self.right_snapshot or self.left_entry_address or not self.right_entry_address): raise ValidationError("added ledger diff item does not replay")
        if self.change == "removed" and (not self.left_snapshot or self.right_snapshot or not self.left_entry_address or self.right_entry_address): raise ValidationError("removed ledger diff item does not replay")
        if self.change in ("changed", "unchanged") and (not self.left_snapshot or not self.right_snapshot or not self.left_entry_address or not self.right_entry_address): raise ValidationError("matched ledger diff item does not replay")
        if self.change == "changed" and (not self.changed_fields or all(self.left_snapshot.get(field) == self.right_snapshot.get(field) for field in self.changed_fields)): raise ValidationError("changed ledger diff item has no changed field")
        if self.change == "unchanged" and (self.changed_fields or self.left_snapshot != self.right_snapshot): raise ValidationError("unchanged ledger diff item has changed content")
        if self.change in ("added", "removed") and self.changed_fields: raise ValidationError("added or removed ledger diff item has changed fields")
        if not self.content_address.startswith("pending:") and _address_for(self, ITEM_PREFIX) != self.content_address: raise ValidationError("ledger diff item address does not replay")
        if not _public(self.to_dict()): raise ValidationError("ledger diff item crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"changed_fields": list(self.changed_fields), "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffItem":
        value = _mapping(value, "ledger diff item"); _strict(value, set(cls.FIELDS), "ledger diff item"); return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: DiffItem) -> str:
    if not isinstance(value, DiffItem): raise ValidationError("ledger diff item address requires a typed item")
    return _address_for(value, ITEM_PREFIX)
def address_items(value: Sequence[DiffItem]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DiffItem) for item in typed): raise ValidationError("ledger diff items address requires typed items")
    return content_hash({"items": [item.to_dict() for item in typed]}, prefix=ITEMS_PREFIX)


class DiffCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "ledger diff check ID"); self.passed = _bool(passed, "ledger diff check result")
        if severity not in SEVERITIES: raise ValidationError("ledger diff check severity is unsupported")
        self.severity = severity; self.actual = _text(actual, "ledger diff check actual", 32768); self.expected = _text(expected, "ledger diff check expected", 32768); self.detail = _text(detail, "ledger diff check detail", 4096); self.content_address = _address(content_address, "ledger diff check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or (self.passed and self.severity == "error"): raise ValidationError("ledger diff check identity or severity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("ledger diff check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("ledger diff check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffCheck":
        value = _mapping(value, "ledger diff check"); _strict(value, set(cls.FIELDS), "ledger diff check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DiffCheck) -> str:
    if not isinstance(value, DiffCheck): raise ValidationError("ledger diff check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)
def address_checks(value: Sequence[DiffCheck]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DiffCheck) for item in typed): raise ValidationError("ledger diff checks address requires typed checks")
    return content_hash({"checks": [item.to_dict() for item in typed]}, prefix=CHECKS_PREFIX)


class DiffManifest:
    FIELDS = MANIFEST_FIELDS
    def __init__(self, diff_id: str, left_ledger_id: str, right_ledger_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.diff_id = _label(diff_id, "ledger diff manifest diff ID"); self.left_ledger_id = _label(left_ledger_id, "ledger diff manifest left ledger ID"); self.right_ledger_id = _label(right_ledger_id, "ledger diff manifest right ledger ID"); self.version = _text(version, "ledger diff manifest version", 1024); self.boundary = _text(boundary, "ledger diff manifest boundary", 2048); self.files = tuple(_text(item, "ledger diff manifest file", 128) for item in _sequence(files, "ledger diff manifest files", len(FILES))); self.artifact_addresses = tuple(_address(item, "ledger diff manifest artifact address") for item in _sequence(artifact_addresses, "ledger diff manifest artifact addresses", len(ARTIFACT_FILES))); self.content_address = _address(content_address, "ledger diff manifest address", MANIFEST_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY: raise ValidationError("ledger diff manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address: raise ValidationError("ledger diff manifest address does not replay")
        if not _public(self.to_dict()): raise ValidationError("ledger diff manifest crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffManifest":
        value = _mapping(value, "ledger diff manifest"); _strict(value, set(cls.FIELDS), "ledger diff manifest"); return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DiffManifest) -> str:
    if not isinstance(value, DiffManifest): raise ValidationError("ledger diff manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class DiffSummary:
    FIELDS = SUMMARY_FIELDS
    def __init__(self, diff_id: str, left_ledger_id: str, right_ledger_id: str, left_ledger_address: str, right_ledger_address: str, left_entry_count: int, right_entry_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, state_transition: str, left_state: str, right_state: str, left_final_ready: bool, right_final_ready: bool, accepted: bool, release_ready: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "ledger diff summary diff ID"); self.left_ledger_id = _label(left_ledger_id, "ledger diff summary left ledger ID"); self.right_ledger_id = _label(right_ledger_id, "ledger diff summary right ledger ID"); self.left_ledger_address = _address(left_ledger_address, "ledger diff summary left ledger address", ledger_model.LEDGER_PREFIX); self.right_ledger_address = _address(right_ledger_address, "ledger diff summary right ledger address", ledger_model.LEDGER_PREFIX); self.left_entry_count = _count(left_entry_count, "ledger diff summary left entry count", ledger_model.MAX_ENTRIES); self.right_entry_count = _count(right_entry_count, "ledger diff summary right entry count", ledger_model.MAX_ENTRIES); self.added_count = _count(added_count, "ledger diff summary added count", MAX_ITEMS); self.removed_count = _count(removed_count, "ledger diff summary removed count", MAX_ITEMS); self.changed_count = _count(changed_count, "ledger diff summary changed count", MAX_ITEMS); self.unchanged_count = _count(unchanged_count, "ledger diff summary unchanged count", MAX_ITEMS)
        if direction not in DIRECTIONS or left_state not in ledger_model.STATES or right_state not in ledger_model.STATES: raise ValidationError("ledger diff summary direction or state is unsupported")
        self.direction = direction; self.state_transition = _text(state_transition, "ledger diff summary state transition", 128); self.left_state = left_state; self.right_state = right_state; self.left_final_ready = _bool(left_final_ready, "ledger diff summary left readiness"); self.right_final_ready = _bool(right_final_ready, "ledger diff summary right readiness"); self.accepted = _bool(accepted, "ledger diff summary acceptance"); self.release_ready = _bool(release_ready, "ledger diff summary readiness"); self.content_address = _address(content_address, "ledger diff summary address", SUMMARY_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.added_count + self.removed_count + self.changed_count + self.unchanged_count > MAX_ITEMS or self.left_final_ready != (self.left_state == "ready") or self.right_final_ready != (self.right_state == "ready"): raise ValidationError("ledger diff summary does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address: raise ValidationError("ledger diff summary address does not replay")
        if not _public(self.to_dict()): raise ValidationError("ledger diff summary crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffSummary":
        value = _mapping(value, "ledger diff summary"); _strict(value, set(cls.FIELDS), "ledger diff summary"); return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DiffSummary) -> str:
    if not isinstance(value, DiffSummary): raise ValidationError("ledger diff summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class LedgerDiff:
    FIELDS = DIFF_FIELDS
    def __init__(self, diff_id: str, version: str, boundary: str, left_ledger_id: str, right_ledger_id: str, left_ledger_address: str, right_ledger_address: str, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, state_transition: str, left_state: str, right_state: str, left_final_ready: bool, right_final_ready: bool, accepted: bool, release_ready: bool, policy: Mapping[str, Any] | LedgerDiffPolicy, checks: Sequence[DiffCheck | Mapping[str, Any]], manifest: Mapping[str, Any] | DiffManifest, summary: Mapping[str, Any] | DiffSummary, items: Sequence[DiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _label(diff_id, "ledger diff ID"); self.version = _text(version, "ledger diff version", 1024); self.boundary = _text(boundary, "ledger diff boundary", 2048); self.left_ledger_id = _label(left_ledger_id, "ledger diff left ledger ID"); self.right_ledger_id = _label(right_ledger_id, "ledger diff right ledger ID"); self.left_ledger_address = _address(left_ledger_address, "ledger diff left ledger address", ledger_model.LEDGER_PREFIX); self.right_ledger_address = _address(right_ledger_address, "ledger diff right ledger address", ledger_model.LEDGER_PREFIX); self.item_count = _count(item_count, "ledger diff item count", MAX_ITEMS); self.added_count = _count(added_count, "ledger diff added count", MAX_ITEMS); self.removed_count = _count(removed_count, "ledger diff removed count", MAX_ITEMS); self.changed_count = _count(changed_count, "ledger diff changed count", MAX_ITEMS); self.unchanged_count = _count(unchanged_count, "ledger diff unchanged count", MAX_ITEMS)
        if direction not in DIRECTIONS or left_state not in ledger_model.STATES or right_state not in ledger_model.STATES: raise ValidationError("ledger diff direction or state is unsupported")
        self.direction = direction; self.state_transition = _text(state_transition, "ledger diff state transition", 128); self.left_state = left_state; self.right_state = right_state; self.left_final_ready = _bool(left_final_ready, "ledger diff left readiness"); self.right_final_ready = _bool(right_final_ready, "ledger diff right readiness"); self.accepted = _bool(accepted, "ledger diff acceptance"); self.release_ready = _bool(release_ready, "ledger diff readiness"); self.policy = policy if isinstance(policy, LedgerDiffPolicy) else LedgerDiffPolicy.from_mapping(_mapping(policy, "ledger diff policy")); self.checks = tuple(item if isinstance(item, DiffCheck) else DiffCheck.from_mapping(_mapping(item, "ledger diff check")) for item in _sequence(checks, "ledger diff checks", MAX_CHECKS)); self.manifest = manifest if isinstance(manifest, DiffManifest) else DiffManifest.from_mapping(_mapping(manifest, "ledger diff manifest")); self.summary = summary if isinstance(summary, DiffSummary) else DiffSummary.from_mapping(_mapping(summary, "ledger diff summary")); self.items = tuple(item if isinstance(item, DiffItem) else DiffItem.from_mapping(_mapping(item, "ledger diff item")) for item in _sequence(items, "ledger diff items", MAX_ITEMS)); self.content_address = _address(content_address, "ledger diff address", DIFF_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.item_count != len(self.items) or self.added_count + self.removed_count + self.changed_count + self.unchanged_count != self.item_count or self.release_ready != all(item.passed for item in self.checks): raise ValidationError("ledger diff identity, conservation, or disposition does not replay")
        if (self.added_count, self.removed_count, self.changed_count, self.unchanged_count) != tuple(sum(item.change == change for item in self.items) for change in CHANGES): raise ValidationError("ledger diff change counters do not replay")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, self.item_count + 1)) or len({item.decision_id for item in self.items}) != self.item_count: raise ValidationError("ledger diff item identity or order does not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("ledger diff checks are not canonical")
        expected_summary = (self.diff_id, self.left_ledger_id, self.right_ledger_id, self.left_ledger_address, self.right_ledger_address, self.summary.left_entry_count, self.summary.right_entry_count, self.added_count, self.removed_count, self.changed_count, self.unchanged_count, self.direction, self.state_transition, self.left_state, self.right_state, self.left_final_ready, self.right_final_ready, self.accepted, self.release_ready)
        if tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1]) != expected_summary or self.summary.content_address != address_summary(self.summary): raise ValidationError("ledger diff summary does not replay")
        expected_manifest = (self.diff_id, self.left_ledger_id, self.right_ledger_id, VERSION, BOUNDARY, FILES, (self.policy.content_address, address_items(self.items), address_checks(self.checks), self.summary.content_address)); actual_manifest = (self.manifest.diff_id, self.manifest.left_ledger_id, self.manifest.right_ledger_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest): raise ValidationError("ledger diff manifest does not replay")
        if not self.content_address.startswith("pending:") and address_diff(self) != self.content_address: raise ValidationError("ledger diff address does not replay")
        if not _public(self.to_dict()): raise ValidationError("ledger diff crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "left_ledger_id": self.left_ledger_id, "right_ledger_id": self.right_ledger_id, "left_ledger_address": self.left_ledger_address, "right_ledger_address": self.right_ledger_address, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "direction": self.direction, "state_transition": self.state_transition, "left_state": self.left_state, "right_state": self.right_state, "left_final_ready": self.left_final_ready, "right_final_ready": self.right_final_ready, "accepted": self.accepted, "release_ready": self.release_ready, "policy": self.policy.to_dict(), "checks": [item.to_dict() for item in self.checks], "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "items": [item.to_dict() for item in self.items], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerDiff":
        value = _mapping(value, "ledger diff"); _strict(value, set(cls.FIELDS), "ledger diff"); return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: LedgerDiff) -> str:
    if not isinstance(value, LedgerDiff): raise ValidationError("ledger diff address requires a typed diff")
    return _address_for(value, DIFF_PREFIX)
def build_policy(policy_id: str, left_ledger_id: str, right_ledger_id: str, *, minimum_items: int = 1, maximum_added: int = MAX_ITEMS, maximum_removed: int = 0, maximum_changed: int = 0, allowed_directions: Sequence[str] = ("improved", "changed", "unchanged"), require_same_scenario: bool = True, require_append_only: bool = True, require_head_change: bool = True, require_accepted: bool = True) -> LedgerDiffPolicy:
    return _seal(LedgerDiffPolicy(policy_id, left_ledger_id, right_ledger_id, minimum_items, maximum_added, maximum_removed, maximum_changed, allowed_directions, require_same_scenario, require_append_only, require_head_change, require_accepted, f"pending:{POLICY_PREFIX}"), address_policy)
def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> DiffCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "severity": "info" if passed else "error", "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = DiffCheck(**body); return DiffCheck(**(body | {"content_address": address_check(provisional)}))
def _direction(left: ledger_model.GateDecisionLedger, right: ledger_model.GateDecisionLedger, items: Sequence[DiffItem]) -> str:
    if left.final_ready != right.final_ready: return "improved" if right.final_ready else "regressed"
    return "unchanged" if not any(item.change != "unchanged" for item in items) else "changed"
def build_diff(left: ledger_model.GateDecisionLedger, right: ledger_model.GateDecisionLedger, *, diff_id: str = DEFAULT_DIFF_ID, policy: LedgerDiffPolicy | Mapping[str, Any] | None = None) -> LedgerDiff:
    ledger_model.verify_ledger(left); ledger_model.verify_ledger(right)
    if left.ledger_id != right.ledger_id: raise ValidationError("ledger diff requires matching ledger identity")
    left_by = {item.decision_id: item for item in left.entries}; right_by = {item.decision_id: item for item in right.entries}; identities = list(left_by) + [item for item in right_by if item not in left_by]; items: list[DiffItem] = []; fields = tuple(field for field in ledger_model.ENTRY_FIELDS if field != "content_address")
    for ordinal, identity in enumerate(identities, 1):
        left_entry = left_by.get(identity); right_entry = right_by.get(identity); left_snapshot = left_entry.to_dict() if left_entry else {}; right_snapshot = right_entry.to_dict() if right_entry else {}; change = "added" if left_entry is None else "removed" if right_entry is None else "unchanged" if left_snapshot == right_snapshot else "changed"; changed = tuple(field for field in fields if left_snapshot.get(field) != right_snapshot.get(field)) if change == "changed" else (); body = {"ordinal": ordinal, "decision_id": identity, "change": change, "changed_fields": changed, "left_entry_address": left_entry.content_address if left_entry else "", "right_entry_address": right_entry.content_address if right_entry else "", "left_snapshot": left_snapshot, "right_snapshot": right_snapshot, "content_address": f"pending:{ITEM_PREFIX}"}; provisional = DiffItem(**body); items.append(DiffItem(**(body | {"content_address": address_item(provisional)})))
    added = sum(item.change == "added" for item in items); removed = sum(item.change == "removed" for item in items); changed = sum(item.change == "changed" for item in items); unchanged = sum(item.change == "unchanged" for item in items); diff_policy = policy if isinstance(policy, LedgerDiffPolicy) else LedgerDiffPolicy.from_mapping(_mapping(policy, "ledger diff policy")) if policy is not None else build_policy(f"{diff_id}-policy", left.ledger_id, right.ledger_id); right_ids = {item.decision_id for item in right.entries}; append_only = removed == 0 and all(item.decision_id in right_ids for item in items if item.change != "added"); head_change = (left.head_decision_id, left.head_entry_address) != (right.head_decision_id, right.head_entry_address); same_scenario = bool(left.summary.scenario_id and left.summary.scenario_id == right.summary.scenario_id); direction = _direction(left, right, items); transition = f"{left.state}->{right.state}"
    checks = (_check(1, "ledgers_present", bool(left.content_address and right.content_address), (left.ledger_id, right.ledger_id), "two ledger addresses", "both ledger inputs must be present"), _check(2, "ledger_identity", diff_policy.left_ledger_id == left.ledger_id and diff_policy.right_ledger_id == right.ledger_id, (diff_policy.left_ledger_id, diff_policy.right_ledger_id), (left.ledger_id, right.ledger_id), "policy must target both ledgers"), _check(3, "same_scenario", (not diff_policy.require_same_scenario) or same_scenario, (left.summary.scenario_id, right.summary.scenario_id), "one scenario ID", "baseline and candidate must share a scenario"), _check(4, "minimum_items", len(items) >= diff_policy.minimum_items, len(items), diff_policy.minimum_items, "diff item count must meet the policy floor"), _check(5, "added_budget", added <= diff_policy.maximum_added, added, diff_policy.maximum_added, "added decisions must remain within budget"), _check(6, "removed_budget", removed <= diff_policy.maximum_removed, removed, diff_policy.maximum_removed, "removed decisions must remain within budget"), _check(7, "changed_budget", changed <= diff_policy.maximum_changed, changed, diff_policy.maximum_changed, "changed decisions must remain within budget"), _check(8, "append_only", (not diff_policy.require_append_only) or append_only, removed, 0, "candidate must retain baseline decisions"), _check(9, "head_change", (not diff_policy.require_head_change) or head_change, (left.head_decision_id, right.head_decision_id), "different ledger heads", "candidate must advance the head when required"), _check(10, "direction_policy", direction in diff_policy.allowed_directions, direction, diff_policy.allowed_directions, "direction must be permitted"), _check(11, "accepted_policy", (not diff_policy.require_accepted) or (left.accepted and right.accepted), (left.accepted, right.accepted), True, "both ledgers must be accepted"), _check(12, "classification_conservation", added + removed + changed + unchanged == len(items), (added, removed, changed, unchanged), "conserved item count", "diff classifications must conserve items"), _check(13, "identity_integrity", len({item.decision_id for item in items}) == len(items), [item.decision_id for item in items], "unique decision IDs", "diff identities must remain unique"), _check(14, "address_integrity", all((not item.left_snapshot or item.left_entry_address) and (not item.right_snapshot or item.right_entry_address) for item in items), True, "retained entry addresses", "every retained snapshot must retain its source address"), _check(15, "policy_integrity", address_policy(diff_policy) == diff_policy.content_address, diff_policy.content_address, address_policy(diff_policy), "policy address must replay")); disposition = all(item.passed for item in checks); checks = checks + (_check(16, "release_disposition", disposition, disposition, True, "diff acceptance is the conjunction of comparison checks"),); passed = all(item.passed for item in checks); accepted = left.accepted and right.accepted and bool(items); summary = _seal(DiffSummary(diff_id, left.ledger_id, right.ledger_id, left.content_address, right.content_address, left.entry_count, right.entry_count, added, removed, changed, unchanged, direction, transition, left.state, right.state, left.final_ready, right.final_ready, accepted, passed, f"pending:{SUMMARY_PREFIX}"), address_summary); manifest = _seal(DiffManifest(diff_id, left.ledger_id, right.ledger_id, VERSION, BOUNDARY, FILES, (diff_policy.content_address, address_items(items), address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest); return _seal(LedgerDiff(diff_id, VERSION, BOUNDARY, left.ledger_id, right.ledger_id, left.content_address, right.content_address, len(items), added, removed, changed, unchanged, direction, transition, left.state, right.state, left.final_ready, right.final_ready, accepted, passed, diff_policy, checks, manifest, summary, items, f"pending:{DIFF_PREFIX}"), address_diff)
def verify_diff(value: LedgerDiff) -> LedgerDiff:
    if not isinstance(value, LedgerDiff): raise ValidationError("ledger diff verification requires a typed diff")
    value._validate(); return value
def diff_from_mapping(value: Mapping[str, Any]) -> LedgerDiff: return LedgerDiff.from_mapping(value)
def diff_json(value: LedgerDiff) -> str: return canonical_json(verify_diff(value).to_dict())
def policy_json(value: LedgerDiff) -> str: return canonical_json(verify_diff(value).policy.to_dict())
def items_json(value: LedgerDiff) -> str:
    value = verify_diff(value); return canonical_json({"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)})
def checks_json(value: LedgerDiff) -> str:
    value = verify_diff(value); return canonical_json({"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)})
def manifest_json(value: LedgerDiff) -> str: return canonical_json(verify_diff(value).manifest.to_dict())
def summary_json(value: LedgerDiff) -> str: return canonical_json(verify_diff(value).summary.to_dict())
def diff_csv(value: LedgerDiff) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ITEM_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_diff(value).items); return output.getvalue()
def render_diff_markdown(value: LedgerDiff) -> str:
    value = verify_diff(value); lines = [f"# Gate decision ledger diff {value.diff_id}", "", f"- Direction: {value.direction}", f"- State transition: {value.state_transition}", f"- Added: {value.added_count}", f"- Removed: {value.removed_count}", f"- Changed: {value.changed_count}", f"- Unchanged: {value.unchanged_count}", "", "| Decision | Change | Fields |", "| --- | --- | --- |"] ; lines.extend(f"| {item.decision_id} | {item.change} | {', '.join(item.changed_fields) or '-'} |" for item in value.items); return "\n".join(lines) + "\n"
def _write(path: Path, value: Mapping[str, Any]) -> None: path.write_text(canonical_json(value), encoding="utf-8", newline="\n")
def persist_diff(value: LedgerDiff, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_diff(value); destination = Path(destination); _validate_parent(destination.parent, "ledger diff destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)): raise ValidationError("ledger diff destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True); temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-ledger-diff-", dir=str(destination.parent))); documents = {"manifest.json": value.manifest.to_dict(), "diff.json": value.to_dict(), "policy.json": value.policy.to_dict(), "items.json": {"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)}, "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES: _write(temporary / name, documents[name])
        if destination.exists(): shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True); raise ValidationError("ledger diff destination could not be written") from error
    return destination
def _read_json(path: Path) -> Mapping[str, Any]:
    try: value = _strict_json_loads(read_text(path, field="ledger diff artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error: raise ValidationError("ledger diff artifact is not valid JSON") from error
    return _mapping(value, "ledger diff artifact")
def load_diff(destination: str | Path) -> LedgerDiff:
    destination = Path(destination); _validate_parent(destination.parent, "ledger diff input")
    if not destination.is_dir() or destination.is_symlink(): raise ValidationError("ledger diff source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children): raise ValidationError("ledger diff directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="ledger diff artifact") != serialized or len(serialized.encode("utf-8")) > MAX_DIFF_BYTES: raise ValidationError("ledger diff artifact is non-canonical or exceeds its size bound")
    value = diff_from_mapping(documents["diff.json"]); expected = {"manifest.json": value.manifest.to_dict(), "policy.json": value.policy.to_dict(), "items.json": {"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)}, "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()): raise ValidationError("ledger diff component documents do not replay diff.json")
    return verify_diff(value)
def run_diff(left: ledger_model.GateDecisionLedger, right: ledger_model.GateDecisionLedger, *, diff_id: str = DEFAULT_DIFF_ID, policy: LedgerDiffPolicy | Mapping[str, Any] | None = None, destination: str | Path | None = None, overwrite: bool = False) -> LedgerDiff:
    value = build_diff(left, right, diff_id=diff_id, policy=policy)
    if destination is not None: persist_diff(value, destination, overwrite=overwrite)
    return value
def policy_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffPolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "array" if field == "allowed_directions" else "integer" if field.startswith("minimum") or field.startswith("maximum") else "boolean" if field.startswith("require") else "string"} for field in POLICY_FIELDS}}
def item_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffItem", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {field: {"type": "array" if field == "changed_fields" else "object" if field in ("left_snapshot", "right_snapshot") else "integer" if field == "ordinal" else "string"} for field in ITEM_FIELDS}}
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def manifest_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}
def summary_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("left_final_ready", "right_final_ready", "accepted", "release_ready") else "string"} for field in SUMMARY_FIELDS}}
def diff_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {field: {"type": "array" if field in ("checks", "items") else "object" if field in ("policy", "manifest", "summary") else "integer" if field.endswith("count") else "boolean" if field in ("left_final_ready", "right_final_ready", "accepted", "release_ready") else "string"} for field in DIFF_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "changes": CHANGES, "directions": DIRECTIONS, "check_ids": CHECK_IDS, "max_items": MAX_ITEMS, "max_checks": MAX_CHECKS, "features": ("baseline and candidate gate-ledger comparison", "field-level decision deltas", "append-only and head-change policy controls", "exact six-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "DIFF_PREFIX", "ITEM_PREFIX", "ITEMS_PREFIX", "POLICY_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_DIFF_ID", "FILES", "ARTIFACT_FILES", "CHANGES", "DIRECTIONS", "STATES", "SEVERITIES", "MAX_ITEMS", "MAX_CHECKS", "MAX_DIFF_BYTES", "POLICY_FIELDS", "ITEM_FIELDS", "CHECK_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "DIFF_FIELDS", "CHECK_IDS", "LedgerDiffPolicy", "DiffItem", "DiffCheck", "DiffManifest", "DiffSummary", "LedgerDiff", "address_policy", "address_item", "address_items", "address_check", "address_checks", "address_manifest", "address_summary", "address_diff", "build_policy", "build_diff", "verify_diff", "diff_from_mapping", "diff_json", "policy_json", "items_json", "checks_json", "manifest_json", "summary_json", "diff_csv", "render_diff_markdown", "persist_diff", "load_diff", "run_diff", "policy_schema", "item_schema", "check_schema", "manifest_schema", "summary_schema", "diff_schema", "capabilities"]
