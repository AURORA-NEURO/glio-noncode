"""Compare multiple D484 history-diff runtime policies as one scenario."""

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

from . import downloaded_data_quality_d484_history_diff_runtime_registry_history_diff_runtime as runtime_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = runtime_model.VERSION + "-scenario-v1"
BOUNDARY = runtime_model.BOUNDARY + "_scenario"
SCENARIO_PREFIX = "glio-noncode-d485-history-diff-runtime-policy-scenario"
POLICY_PREFIX = SCENARIO_PREFIX + "-policy"
ENTRY_PREFIX = SCENARIO_PREFIX + "-entry"
ENTRIES_PREFIX = SCENARIO_PREFIX + "-entries"
CHECK_PREFIX = SCENARIO_PREFIX + "-check"
CHECKS_PREFIX = SCENARIO_PREFIX + "-checks"
MANIFEST_PREFIX = SCENARIO_PREFIX + "-manifest"
SUMMARY_PREFIX = SCENARIO_PREFIX + "-summary"
DEFAULT_SCENARIO_ID = SCENARIO_PREFIX
FILES = ("manifest.json", "scenario.json", "policy.json", "entries.json", "checks.json", "summary.json")
ARTIFACT_FILES = ("policy.json", "entries.json", "checks.json", "summary.json")
STATES = ("empty", "ready", "mixed", "blocked")
SEVERITIES = ("info", "error")
RISK_FLAGS = ("blocked_runtime", "zero_added_margin", "zero_removed_margin", "zero_changed_margin", "mixed_outcome", "policy_spread")
MAX_ENTRIES = 128
MAX_CHECKS = 18
MAX_SCENARIO_BYTES = 32 * 1024 * 1024
POLICY_FIELDS = ("policy_id", "minimum_runtimes", "minimum_ready", "maximum_blocked", "require_same_diff", "require_same_direction", "require_same_transition", "require_unique_policies", "require_at_least_one_ready", "require_at_least_one_blocked", "require_accepted", "allow_mixed", "content_address")
ENTRY_FIELDS = ("ordinal", "runtime_id", "runtime_address", "diff_id", "diff_address", "policy_id", "policy_address", "direction", "state_transition", "state", "release_ready", "accepted", "check_count", "passed_count", "failed_count", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "added_margin", "removed_margin", "changed_margin", "risk_flags", "content_address")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "severity", "actual", "expected", "detail", "content_address")
MANIFEST_FIELDS = ("scenario_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("scenario_id", "diff_id", "direction", "state_transition", "entry_count", "ready_count", "blocked_count", "accepted_count", "minimum_added_margin", "minimum_removed_margin", "minimum_changed_margin", "risk_flags", "accepted", "release_ready", "state", "content_address")
SCENARIO_FIELDS = ("scenario_id", "version", "boundary", "policy", "entry_count", "ready_count", "blocked_count", "accepted_count", "minimum_added_margin", "minimum_removed_margin", "minimum_changed_margin", "risk_flags", "accepted", "release_ready", "state", "diff_id", "direction", "state_transition", "manifest", "summary", "entries", "checks", "content_address")
CHECK_IDS = ("nonempty", "minimum_runtimes", "minimum_ready", "blocked_budget", "state_consistency", "outcome_policy", "runtime_acceptance", "same_diff", "same_direction", "same_transition", "unique_runtime_ids", "unique_runtime_addresses", "unique_policy_ids", "margin_integrity", "risk_replay", "counter_conservation", "policy_integrity", "public_boundary")


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
def _public(value: Any) -> bool: return runtime_model.diff_model.history_model.registry_model.runtime_model.diff_model.history_model.batch_model.runtime_model.diff_model.history_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value
def _ordered_flags(flags: Sequence[str]) -> tuple[str, ...]: return tuple(item for item in RISK_FLAGS if item in flags)


class ScenarioPolicy:
    FIELDS = POLICY_FIELDS
    def __init__(self, policy_id: str, minimum_runtimes: int, minimum_ready: int, maximum_blocked: int, require_same_diff: bool, require_same_direction: bool, require_same_transition: bool, require_unique_policies: bool, require_at_least_one_ready: bool, require_at_least_one_blocked: bool, require_accepted: bool, allow_mixed: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "policy scenario policy ID"); self.minimum_runtimes = _count(minimum_runtimes, "policy scenario minimum runtimes", MAX_ENTRIES, lower=1); self.minimum_ready = _count(minimum_ready, "policy scenario minimum ready", MAX_ENTRIES); self.maximum_blocked = _count(maximum_blocked, "policy scenario maximum blocked", MAX_ENTRIES); self.require_same_diff = _bool(require_same_diff, "policy scenario same-diff requirement"); self.require_same_direction = _bool(require_same_direction, "policy scenario same-direction requirement"); self.require_same_transition = _bool(require_same_transition, "policy scenario same-transition requirement"); self.require_unique_policies = _bool(require_unique_policies, "policy scenario unique-policy requirement"); self.require_at_least_one_ready = _bool(require_at_least_one_ready, "policy scenario ready requirement"); self.require_at_least_one_blocked = _bool(require_at_least_one_blocked, "policy scenario blocked requirement"); self.require_accepted = _bool(require_accepted, "policy scenario acceptance requirement"); self.allow_mixed = _bool(allow_mixed, "policy scenario mixed-outcome requirement"); self.content_address = _address(content_address, "policy scenario policy address", POLICY_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.minimum_ready > self.minimum_runtimes or (not self.allow_mixed and self.require_at_least_one_ready and self.require_at_least_one_blocked): raise ValidationError("policy scenario policy thresholds are inconsistent")
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address: raise ValidationError("policy scenario policy address does not replay")
        if not _public(self.to_dict()): raise ValidationError("policy scenario policy crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ScenarioPolicy":
        value = _mapping(value, "policy scenario policy"); _strict(value, set(cls.FIELDS), "policy scenario policy"); return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: ScenarioPolicy) -> str:
    if not isinstance(value, ScenarioPolicy): raise ValidationError("policy scenario policy address requires a typed policy")
    return _address_for(value, POLICY_PREFIX)


class ScenarioEntry:
    FIELDS = ENTRY_FIELDS
    def __init__(self, ordinal: int, runtime_id: str, runtime_address: str, diff_id: str, diff_address: str, policy_id: str, policy_address: str, direction: str, state_transition: str, state: str, release_ready: bool, accepted: bool, check_count: int, passed_count: int, failed_count: int, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, added_margin: int, removed_margin: int, changed_margin: int, risk_flags: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "policy scenario entry ordinal", MAX_ENTRIES, lower=1); self.runtime_id = _label(runtime_id, "policy scenario runtime ID"); self.runtime_address = _address(runtime_address, "policy scenario runtime address", runtime_model.RUNTIME_PREFIX); self.diff_id = _label(diff_id, "policy scenario diff ID"); self.diff_address = _address(diff_address, "policy scenario diff address", runtime_model.diff_model.DIFF_PREFIX); self.policy_id = _label(policy_id, "policy scenario runtime policy ID"); self.policy_address = _address(policy_address, "policy scenario runtime policy address", runtime_model.POLICY_PREFIX)
        if direction not in runtime_model.diff_model.DIRECTIONS or state not in runtime_model.STATES: raise ValidationError("policy scenario entry direction or state is unsupported")
        self.direction = direction; self.state_transition = _text(state_transition, "policy scenario entry state transition", 128); self.state = state; self.release_ready = _bool(release_ready, "policy scenario entry readiness"); self.accepted = _bool(accepted, "policy scenario entry acceptance"); self.check_count = _count(check_count, "policy scenario entry check count", runtime_model.MAX_CHECKS); self.passed_count = _count(passed_count, "policy scenario entry passed count", runtime_model.MAX_CHECKS); self.failed_count = _count(failed_count, "policy scenario entry failed count", runtime_model.MAX_CHECKS); self.item_count = _count(item_count, "policy scenario entry item count", runtime_model.diff_model.MAX_ITEMS); self.added_count = _count(added_count, "policy scenario entry added count", runtime_model.diff_model.MAX_ITEMS); self.removed_count = _count(removed_count, "policy scenario entry removed count", runtime_model.diff_model.MAX_ITEMS); self.changed_count = _count(changed_count, "policy scenario entry changed count", runtime_model.diff_model.MAX_ITEMS); self.unchanged_count = _count(unchanged_count, "policy scenario entry unchanged count", runtime_model.diff_model.MAX_ITEMS); self.added_margin = _count(added_margin, "policy scenario entry added margin", runtime_model.diff_model.MAX_ITEMS * 2, lower=-runtime_model.diff_model.MAX_ITEMS); self.removed_margin = _count(removed_margin, "policy scenario entry removed margin", runtime_model.diff_model.MAX_ITEMS * 2, lower=-runtime_model.diff_model.MAX_ITEMS); self.changed_margin = _count(changed_margin, "policy scenario entry changed margin", runtime_model.diff_model.MAX_ITEMS * 2, lower=-runtime_model.diff_model.MAX_ITEMS); self.risk_flags = _ordered_flags(tuple(_label(item, "policy scenario entry risk flag") for item in _sequence(risk_flags, "policy scenario entry risk flags", len(RISK_FLAGS)))); self.content_address = _address(content_address, "policy scenario entry address", ENTRY_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.release_ready != (self.state == "ready") or self.passed_count + self.failed_count != self.check_count or self.passed_count > self.check_count or self.added_count + self.removed_count + self.changed_count + self.unchanged_count != self.item_count: raise ValidationError("policy scenario entry disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, ENTRY_PREFIX) != self.content_address: raise ValidationError("policy scenario entry address does not replay")
        if not _public(self.to_dict()): raise ValidationError("policy scenario entry crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"risk_flags": list(self.risk_flags), "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ScenarioEntry":
        value = _mapping(value, "policy scenario entry"); _strict(value, set(cls.FIELDS), "policy scenario entry"); return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: ScenarioEntry) -> str:
    if not isinstance(value, ScenarioEntry): raise ValidationError("policy scenario entry address requires a typed entry")
    return _address_for(value, ENTRY_PREFIX)
def address_entries(value: Sequence[ScenarioEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, ScenarioEntry) for item in typed): raise ValidationError("policy scenario entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class ScenarioCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "policy scenario check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "policy scenario check ID"); self.passed = _bool(passed, "policy scenario check result")
        if severity not in SEVERITIES: raise ValidationError("policy scenario check severity is unsupported")
        self.severity = severity; self.actual = _text(actual, "policy scenario check actual", 32768); self.expected = _text(expected, "policy scenario check expected", 32768); self.detail = _text(detail, "policy scenario check detail", 4096); self.content_address = _address(content_address, "policy scenario check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or (self.passed and self.severity == "error"): raise ValidationError("policy scenario check identity or severity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("policy scenario check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("policy scenario check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ScenarioCheck":
        value = _mapping(value, "policy scenario check"); _strict(value, set(cls.FIELDS), "policy scenario check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: ScenarioCheck) -> str:
    if not isinstance(value, ScenarioCheck): raise ValidationError("policy scenario check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)
def address_checks(value: Sequence[ScenarioCheck]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, ScenarioCheck) for item in typed): raise ValidationError("policy scenario checks address requires typed checks")
    return content_hash({"checks": [item.to_dict() for item in typed]}, prefix=CHECKS_PREFIX)


class ScenarioManifest:
    FIELDS = MANIFEST_FIELDS
    def __init__(self, scenario_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.scenario_id = _label(scenario_id, "policy scenario manifest ID"); self.version = _text(version, "policy scenario manifest version", 1024); self.boundary = _text(boundary, "policy scenario manifest boundary", 2048); self.files = tuple(_text(item, "policy scenario manifest file", 128) for item in _sequence(files, "policy scenario manifest files", len(FILES))); self.artifact_addresses = tuple(_address(item, "policy scenario manifest artifact address") for item in _sequence(artifact_addresses, "policy scenario manifest artifact addresses", len(ARTIFACT_FILES))); self.content_address = _address(content_address, "policy scenario manifest address", MANIFEST_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY: raise ValidationError("policy scenario manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address: raise ValidationError("policy scenario manifest address does not replay")
        if not _public(self.to_dict()): raise ValidationError("policy scenario manifest crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ScenarioManifest":
        value = _mapping(value, "policy scenario manifest"); _strict(value, set(cls.FIELDS), "policy scenario manifest"); return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: ScenarioManifest) -> str:
    if not isinstance(value, ScenarioManifest): raise ValidationError("policy scenario manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class ScenarioSummary:
    FIELDS = SUMMARY_FIELDS
    def __init__(self, scenario_id: str, diff_id: str, direction: str, state_transition: str, entry_count: int, ready_count: int, blocked_count: int, accepted_count: int, minimum_added_margin: int, minimum_removed_margin: int, minimum_changed_margin: int, risk_flags: Sequence[str], accepted: bool, release_ready: bool, state: str, content_address: str) -> None:
        self.scenario_id = _label(scenario_id, "policy scenario summary ID"); self.diff_id = _label(diff_id, "policy scenario summary diff ID"); self.direction = _label(direction, "policy scenario summary direction"); self.state_transition = _text(state_transition, "policy scenario summary state transition", 128); self.entry_count = _count(entry_count, "policy scenario summary entry count", MAX_ENTRIES); self.ready_count = _count(ready_count, "policy scenario summary ready count", MAX_ENTRIES); self.blocked_count = _count(blocked_count, "policy scenario summary blocked count", MAX_ENTRIES); self.accepted_count = _count(accepted_count, "policy scenario summary accepted count", MAX_ENTRIES); self.minimum_added_margin = _count(minimum_added_margin, "policy scenario minimum added margin", runtime_model.diff_model.MAX_ITEMS * 2, lower=-runtime_model.diff_model.MAX_ITEMS); self.minimum_removed_margin = _count(minimum_removed_margin, "policy scenario minimum removed margin", runtime_model.diff_model.MAX_ITEMS * 2, lower=-runtime_model.diff_model.MAX_ITEMS); self.minimum_changed_margin = _count(minimum_changed_margin, "policy scenario minimum changed margin", runtime_model.diff_model.MAX_ITEMS * 2, lower=-runtime_model.diff_model.MAX_ITEMS); self.risk_flags = _ordered_flags(tuple(_label(item, "policy scenario summary risk flag") for item in _sequence(risk_flags, "policy scenario summary risk flags", len(RISK_FLAGS)))); self.accepted = _bool(accepted, "policy scenario summary acceptance"); self.release_ready = _bool(release_ready, "policy scenario summary readiness")
        if state not in STATES: raise ValidationError("policy scenario summary state is unsupported")
        self.state = state; self.content_address = _address(content_address, "policy scenario summary address", SUMMARY_PREFIX); self._validate()
    def _validate(self) -> None:
        expected_state = "empty" if self.entry_count == 0 else "ready" if self.blocked_count == 0 else "blocked" if self.ready_count == 0 else "mixed"
        if self.ready_count + self.blocked_count != self.entry_count or self.accepted_count > self.entry_count or self.state != expected_state or self.accepted != (self.entry_count > 0 and self.accepted_count == self.entry_count): raise ValidationError("policy scenario summary disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address: raise ValidationError("policy scenario summary address does not replay")
        if not _public(self.to_dict()): raise ValidationError("policy scenario summary crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"risk_flags": list(self.risk_flags), "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ScenarioSummary":
        value = _mapping(value, "policy scenario summary"); _strict(value, set(cls.FIELDS), "policy scenario summary"); return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: ScenarioSummary) -> str:
    if not isinstance(value, ScenarioSummary): raise ValidationError("policy scenario summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class PolicyScenario:
    FIELDS = SCENARIO_FIELDS
    def __init__(self, scenario_id: str, version: str, boundary: str, policy: Mapping[str, Any] | ScenarioPolicy, entry_count: int, ready_count: int, blocked_count: int, accepted_count: int, minimum_added_margin: int, minimum_removed_margin: int, minimum_changed_margin: int, risk_flags: Sequence[str], accepted: bool, release_ready: bool, state: str, diff_id: str, direction: str, state_transition: str, manifest: Mapping[str, Any] | ScenarioManifest, summary: Mapping[str, Any] | ScenarioSummary, entries: Sequence[ScenarioEntry | Mapping[str, Any]], checks: Sequence[ScenarioCheck | Mapping[str, Any]], content_address: str) -> None:
        self.scenario_id = _label(scenario_id, "policy scenario ID"); self.version = _text(version, "policy scenario version", 1024); self.boundary = _text(boundary, "policy scenario boundary", 2048); self.policy = policy if isinstance(policy, ScenarioPolicy) else ScenarioPolicy.from_mapping(_mapping(policy, "policy scenario policy")); self.entry_count = _count(entry_count, "policy scenario entry count", MAX_ENTRIES); self.ready_count = _count(ready_count, "policy scenario ready count", MAX_ENTRIES); self.blocked_count = _count(blocked_count, "policy scenario blocked count", MAX_ENTRIES); self.accepted_count = _count(accepted_count, "policy scenario accepted count", MAX_ENTRIES); self.minimum_added_margin = _count(minimum_added_margin, "policy scenario minimum added margin", runtime_model.diff_model.MAX_ITEMS * 2, lower=-runtime_model.diff_model.MAX_ITEMS); self.minimum_removed_margin = _count(minimum_removed_margin, "policy scenario minimum removed margin", runtime_model.diff_model.MAX_ITEMS * 2, lower=-runtime_model.diff_model.MAX_ITEMS); self.minimum_changed_margin = _count(minimum_changed_margin, "policy scenario minimum changed margin", runtime_model.diff_model.MAX_ITEMS * 2, lower=-runtime_model.diff_model.MAX_ITEMS); self.risk_flags = _ordered_flags(tuple(_label(item, "policy scenario risk flag") for item in _sequence(risk_flags, "policy scenario risk flags", len(RISK_FLAGS)))); self.accepted = _bool(accepted, "policy scenario acceptance"); self.release_ready = _bool(release_ready, "policy scenario readiness")
        if state not in STATES: raise ValidationError("policy scenario state is unsupported")
        self.state = state; self.diff_id = _label(diff_id, "policy scenario diff ID"); self.direction = _label(direction, "policy scenario direction"); self.state_transition = _text(state_transition, "policy scenario state transition", 128); self.manifest = manifest if isinstance(manifest, ScenarioManifest) else ScenarioManifest.from_mapping(_mapping(manifest, "policy scenario manifest")); self.summary = summary if isinstance(summary, ScenarioSummary) else ScenarioSummary.from_mapping(_mapping(summary, "policy scenario summary")); self.entries = tuple(item if isinstance(item, ScenarioEntry) else ScenarioEntry.from_mapping(_mapping(item, "policy scenario entry")) for item in _sequence(entries, "policy scenario entries", MAX_ENTRIES)); self.checks = tuple(item if isinstance(item, ScenarioCheck) else ScenarioCheck.from_mapping(_mapping(item, "policy scenario check")) for item in _sequence(checks, "policy scenario checks", MAX_CHECKS)); self.content_address = _address(content_address, "policy scenario address", SCENARIO_PREFIX); self._validate()
    def _validate(self) -> None:
        expected_state = "empty" if self.entry_count == 0 else "ready" if self.blocked_count == 0 else "blocked" if self.ready_count == 0 else "mixed"
        if self.version != VERSION or self.boundary != BOUNDARY or self.policy.policy_id == "" or self.entry_count != len(self.entries) or self.ready_count + self.blocked_count != self.entry_count or self.accepted_count > self.entry_count or self.state != expected_state or self.release_ready != all(item.passed for item in self.checks) or self.accepted != (self.entry_count > 0 and self.accepted_count == self.entry_count): raise ValidationError("policy scenario identity or counters do not replay")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)) or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("policy scenario entries or checks are not canonical")
        expected_summary = (self.scenario_id, self.diff_id, self.direction, self.state_transition, self.entry_count, self.ready_count, self.blocked_count, self.accepted_count, self.minimum_added_margin, self.minimum_removed_margin, self.minimum_changed_margin, self.risk_flags, self.accepted, self.release_ready, self.state)
        if tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1]) != expected_summary or self.summary.content_address != address_summary(self.summary): raise ValidationError("policy scenario summary does not replay")
        expected_manifest = (self.scenario_id, VERSION, BOUNDARY, FILES, (self.policy.content_address, address_entries(self.entries), address_checks(self.checks), self.summary.content_address)); actual_manifest = (self.manifest.scenario_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest): raise ValidationError("policy scenario manifest does not replay")
        if not self.content_address.startswith("pending:") and address_scenario(self) != self.content_address: raise ValidationError("policy scenario address does not replay")
        if not _public(self.to_dict()): raise ValidationError("policy scenario crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"scenario_id": self.scenario_id, "version": self.version, "boundary": self.boundary, "policy": self.policy.to_dict(), "entry_count": self.entry_count, "ready_count": self.ready_count, "blocked_count": self.blocked_count, "accepted_count": self.accepted_count, "minimum_added_margin": self.minimum_added_margin, "minimum_removed_margin": self.minimum_removed_margin, "minimum_changed_margin": self.minimum_changed_margin, "risk_flags": list(self.risk_flags), "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "diff_id": self.diff_id, "direction": self.direction, "state_transition": self.state_transition, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "entries": [item.to_dict() for item in self.entries], "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address, "version": self.version, "boundary": self.boundary}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PolicyScenario":
        value = _mapping(value, "policy scenario"); _strict(value, set(cls.FIELDS), "policy scenario"); return cls(*(value[field] for field in cls.FIELDS))


def address_scenario(value: PolicyScenario) -> str:
    if not isinstance(value, PolicyScenario): raise ValidationError("policy scenario address requires a typed scenario")
    return _address_for(value, SCENARIO_PREFIX)


def build_policy(policy_id: str, *, minimum_runtimes: int = 1, minimum_ready: int = 1, maximum_blocked: int = 0, require_same_diff: bool = True, require_same_direction: bool = True, require_same_transition: bool = True, require_unique_policies: bool = True, require_at_least_one_ready: bool = True, require_at_least_one_blocked: bool = False, require_accepted: bool = True, allow_mixed: bool = True) -> ScenarioPolicy:
    return _seal(ScenarioPolicy(policy_id, minimum_runtimes, minimum_ready, maximum_blocked, require_same_diff, require_same_direction, require_same_transition, require_unique_policies, require_at_least_one_ready, require_at_least_one_blocked, require_accepted, allow_mixed, f"pending:{POLICY_PREFIX}"), address_policy)
def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> ScenarioCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "severity": "info" if passed else "error", "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = ScenarioCheck(**body); return ScenarioCheck(**(body | {"content_address": address_check(provisional)}))
def _entry(runtime: runtime_model.HistoryDiffRuntime, ordinal: int) -> ScenarioEntry:
    added_margin = runtime.policy.maximum_added - runtime.added_count; removed_margin = runtime.policy.maximum_removed - runtime.removed_count; changed_margin = runtime.policy.maximum_changed - runtime.changed_count; flags: list[str] = []
    if not runtime.release_ready: flags.append("blocked_runtime")
    if added_margin == 0: flags.append("zero_added_margin")
    if removed_margin == 0: flags.append("zero_removed_margin")
    if changed_margin == 0: flags.append("zero_changed_margin")
    return _seal(ScenarioEntry(ordinal, runtime.runtime_id, runtime.content_address, runtime.diff_id, runtime.diff_address, runtime.policy.policy_id, runtime.policy.content_address, runtime.direction, runtime.state_transition, runtime.state, runtime.release_ready, runtime.accepted, runtime.check_count, runtime.passed_count, runtime.failed_count, runtime.item_count, runtime.added_count, runtime.removed_count, runtime.changed_count, runtime.unchanged_count, added_margin, removed_margin, changed_margin, flags, f"pending:{ENTRY_PREFIX}"), address_entry)
def _derived_risks(entries: Sequence[ScenarioEntry], ready_count: int, blocked_count: int) -> tuple[str, ...]:
    flags = {flag for entry in entries for flag in entry.risk_flags}
    if ready_count and blocked_count: flags.add("mixed_outcome")
    if len({entry.policy_id for entry in entries}) > 1: flags.add("policy_spread")
    return _ordered_flags(tuple(flags))
def build_scenario(runtimes: Sequence[runtime_model.HistoryDiffRuntime], *, scenario_id: str = DEFAULT_SCENARIO_ID, policy: ScenarioPolicy | Mapping[str, Any] | None = None) -> PolicyScenario:
    typed = tuple(runtimes)
    if len(typed) > MAX_ENTRIES: raise ValidationError("policy scenario runtime set exceeds its bound")
    if any(not isinstance(item, runtime_model.HistoryDiffRuntime) for item in typed): raise ValidationError("policy scenario requires typed runtimes")
    for item in typed: runtime_model.verify_runtime(item)
    scenario_policy = policy if isinstance(policy, ScenarioPolicy) else ScenarioPolicy.from_mapping(_mapping(policy, "policy scenario policy")) if policy is not None else build_policy(f"{scenario_id}-policy", minimum_runtimes=max(1, len(typed)))
    entries = tuple(_entry(item, index) for index, item in enumerate(typed, 1)); ready_count = sum(item.release_ready for item in entries); blocked_count = len(entries) - ready_count; accepted_count = sum(item.accepted for item in entries); first = typed[0] if typed else None; diff_id = first.diff_id if first else "empty"; direction = first.direction if first else "empty"; transition = first.state_transition if first else "empty"; minimum_added = min((item.added_margin for item in entries), default=0); minimum_removed = min((item.removed_margin for item in entries), default=0); minimum_changed = min((item.changed_margin for item in entries), default=0); risks = _derived_risks(entries, ready_count, blocked_count); state = "empty" if not entries else "ready" if not blocked_count else "blocked" if not ready_count else "mixed"
    same_diff = bool(entries) and len({item.diff_id for item in entries}) == 1; same_direction = bool(entries) and len({item.direction for item in entries}) == 1; same_transition = bool(entries) and len({item.state_transition for item in entries}) == 1; unique_runtime_ids = len({item.runtime_id for item in entries}) == len(entries); unique_runtime_addresses = len({item.runtime_address for item in entries}) == len(entries); unique_policy_ids = len({item.policy_id for item in entries}) == len(entries); margins = all((item.added_margin == typed[item.ordinal - 1].policy.maximum_added - item.added_count and item.removed_margin == typed[item.ordinal - 1].policy.maximum_removed - item.removed_count and item.changed_margin == typed[item.ordinal - 1].policy.maximum_changed - item.changed_count) for item in entries); scenario = _scenario_provisional(scenario_id, scenario_policy, entries, ready_count, blocked_count, accepted_count, minimum_added, minimum_removed, minimum_changed, risks, diff_id, direction, transition)
    checks = (_check(1, "nonempty", bool(entries), len(entries), ">= 1", "a scenario must contain at least one runtime"), _check(2, "minimum_runtimes", len(entries) >= scenario_policy.minimum_runtimes, len(entries), scenario_policy.minimum_runtimes, "runtime count must meet the scenario floor"), _check(3, "minimum_ready", ready_count >= scenario_policy.minimum_ready, ready_count, scenario_policy.minimum_ready, "ready runtimes must meet the scenario floor"), _check(4, "blocked_budget", blocked_count <= scenario_policy.maximum_blocked, blocked_count, scenario_policy.maximum_blocked, "blocked runtimes must remain within budget"), _check(5, "state_consistency", all(item.release_ready == (item.state == "ready") for item in entries) and state == ("empty" if not entries else "ready" if not blocked_count else "blocked" if not ready_count else "mixed"), state, "derived runtime state", "scenario state and entry states must replay"), _check(6, "outcome_policy", (not scenario_policy.require_at_least_one_ready or ready_count > 0) and (not scenario_policy.require_at_least_one_blocked or blocked_count > 0) and (scenario_policy.allow_mixed or not (ready_count and blocked_count)), (ready_count, blocked_count, state), (scenario_policy.require_at_least_one_ready, scenario_policy.require_at_least_one_blocked, scenario_policy.allow_mixed), "outcome shape must follow policy"), _check(7, "runtime_acceptance", (not scenario_policy.require_accepted) or accepted_count == len(entries), accepted_count, len(entries), "runtime acceptance must follow policy"), _check(8, "same_diff", (not scenario_policy.require_same_diff) or same_diff, [item.diff_id for item in entries], "one diff ID", "all runtimes must target the same diff"), _check(9, "same_direction", (not scenario_policy.require_same_direction) or same_direction, [item.direction for item in entries], "one direction", "all runtimes must target the same direction"), _check(10, "same_transition", (not scenario_policy.require_same_transition) or same_transition, [item.state_transition for item in entries], "one transition", "all runtimes must target the same transition"), _check(11, "unique_runtime_ids", unique_runtime_ids, [item.runtime_id for item in entries], "unique runtime IDs", "runtime identities must not collide"), _check(12, "unique_runtime_addresses", unique_runtime_addresses, [item.runtime_address for item in entries], "unique runtime addresses", "runtime addresses must not collide"), _check(13, "unique_policy_ids", (not scenario_policy.require_unique_policies) or unique_policy_ids, [item.policy_id for item in entries], "unique policy IDs", "policy variants must remain distinguishable"), _check(14, "margin_integrity", margins, True, "replayed budget margins", "budget margins must derive from each runtime policy"), _check(15, "risk_replay", risks == _derived_risks(entries, ready_count, blocked_count), risks, "derived risk flags", "scenario risk flags must replay from entries"), _check(16, "counter_conservation", ready_count + blocked_count == len(entries) and accepted_count <= len(entries), (ready_count, blocked_count, accepted_count), "conserved counters", "scenario counters must conserve entries"), _check(17, "policy_integrity", address_policy(scenario_policy) == scenario_policy.content_address, scenario_policy.content_address, address_policy(scenario_policy), "scenario policy address must replay"), _check(18, "public_boundary", _public(scenario_policy.to_dict()) and all(_public(item.to_dict()) for item in entries), True, "public values", "scenario inputs must remain value-only"))
    passed = sum(item.passed for item in checks); accepted = bool(entries) and accepted_count == len(entries); release_ready = all(item.passed for item in checks); summary = _seal(ScenarioSummary(scenario_id, diff_id, direction, transition, len(entries), ready_count, blocked_count, accepted_count, minimum_added, minimum_removed, minimum_changed, risks, accepted, release_ready, state, f"pending:{SUMMARY_PREFIX}"), address_summary); manifest = _seal(ScenarioManifest(scenario_id, VERSION, BOUNDARY, FILES, (scenario_policy.content_address, address_entries(entries), address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest); return _seal(PolicyScenario(scenario_id, VERSION, BOUNDARY, scenario_policy, len(entries), ready_count, blocked_count, accepted_count, minimum_added, minimum_removed, minimum_changed, risks, accepted, release_ready, state, diff_id, direction, transition, manifest, summary, entries, checks, f"pending:{SCENARIO_PREFIX}"), address_scenario)
def _scenario_provisional(scenario_id: str, policy: ScenarioPolicy, entries: Sequence[ScenarioEntry], ready_count: int, blocked_count: int, accepted_count: int, minimum_added: int, minimum_removed: int, minimum_changed: int, risks: Sequence[str], diff_id: str, direction: str, transition: str) -> dict[str, Any]:
    return {"scenario_id": scenario_id, "policy": policy.to_dict(), "entry_count": len(entries), "ready_count": ready_count, "blocked_count": blocked_count, "accepted_count": accepted_count, "minimum_added_margin": minimum_added, "minimum_removed_margin": minimum_removed, "minimum_changed_margin": minimum_changed, "risk_flags": list(risks), "diff_id": diff_id, "direction": direction, "state_transition": transition}
def verify_scenario(value: PolicyScenario) -> PolicyScenario:
    if not isinstance(value, PolicyScenario): raise ValidationError("policy scenario verification requires a typed scenario")
    value._validate(); return value
def scenario_from_mapping(value: Mapping[str, Any]) -> PolicyScenario: return verify_scenario(PolicyScenario.from_mapping(value))
def scenario_json(value: PolicyScenario) -> str: return canonical_json(verify_scenario(value).to_dict())
def policy_json(value: PolicyScenario) -> str: return canonical_json(verify_scenario(value).policy.to_dict())
def entries_json(value: PolicyScenario) -> str:
    value = verify_scenario(value); return canonical_json({"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)})
def checks_json(value: PolicyScenario) -> str:
    value = verify_scenario(value); return canonical_json({"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)})
def summary_json(value: PolicyScenario) -> str: return canonical_json(verify_scenario(value).summary.to_dict())
def manifest_json(value: PolicyScenario) -> str: return canonical_json(verify_scenario(value).manifest.to_dict())
def scenario_csv(value: PolicyScenario) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ENTRY_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_scenario(value).entries); return output.getvalue()
def render_scenario_markdown(value: PolicyScenario) -> str:
    value = verify_scenario(value); lines = [f"# Policy scenario {value.scenario_id}", "", f"- State: {value.state}", f"- Release ready: {str(value.release_ready).lower()}", f"- Runtimes: {value.ready_count}/{value.entry_count} ready", f"- Risks: {', '.join(value.risk_flags) or 'none'}", "", "| Runtime | Policy | State | Added margin | Removed margin | Changed margin |", "| --- | --- | --- | ---: | ---: | ---: |"] ; lines.extend(f"| {item.runtime_id} | {item.policy_id} | {item.state} | {item.added_margin} | {item.removed_margin} | {item.changed_margin} |" for item in value.entries); return "\n".join(lines) + "\n"
def _write(path: Path, value: Mapping[str, Any]) -> None: path.write_text(canonical_json(value), encoding="utf-8", newline="\n")
def persist_scenario(value: PolicyScenario, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_scenario(value); destination = Path(destination); _validate_parent(destination.parent, "policy scenario destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)): raise ValidationError("policy scenario destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True); temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-policy-scenario-", dir=str(destination.parent))); documents = {"manifest.json": value.manifest.to_dict(), "scenario.json": value.to_dict(), "policy.json": value.policy.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES: _write(temporary / name, documents[name])
        if destination.exists(): shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True); raise ValidationError("policy scenario destination could not be written") from error
    return destination
def _read_json(path: Path) -> Mapping[str, Any]:
    try: value = _strict_json_loads(read_text(path, field="policy scenario artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error: raise ValidationError("policy scenario artifact is not valid JSON") from error
    return _mapping(value, "policy scenario artifact")
def load_scenario(destination: str | Path) -> PolicyScenario:
    destination = Path(destination); _validate_parent(destination.parent, "policy scenario input")
    if not destination.is_dir() or destination.is_symlink(): raise ValidationError("policy scenario source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children): raise ValidationError("policy scenario directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="policy scenario artifact") != serialized or len(serialized.encode("utf-8")) > MAX_SCENARIO_BYTES: raise ValidationError("policy scenario artifact is non-canonical or exceeds its size bound")
    value = scenario_from_mapping(documents["scenario.json"]); expected = {"manifest.json": value.manifest.to_dict(), "policy.json": value.policy.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()): raise ValidationError("policy scenario component documents do not replay scenario.json")
    return verify_scenario(value)
def run_scenario(runtimes: Sequence[runtime_model.HistoryDiffRuntime], *, scenario_id: str = DEFAULT_SCENARIO_ID, policy: ScenarioPolicy | Mapping[str, Any] | None = None, destination: str | Path | None = None, overwrite: bool = False) -> PolicyScenario:
    value = build_scenario(runtimes, scenario_id=scenario_id, policy=policy)
    if destination is not None: persist_scenario(value, destination, overwrite=overwrite)
    return value
def policy_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "PolicyScenarioPolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "integer" if field.startswith("minimum") or field.startswith("maximum") else "boolean" if field.startswith("require") or field.startswith("allow") else "string"} for field in POLICY_FIELDS}}
def entry_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "PolicyScenarioEntry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": "array" if field == "risk_flags" else "integer" if field in ("ordinal", "check_count", "passed_count", "failed_count", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "added_margin", "removed_margin", "changed_margin") else "boolean" if field in ("release_ready", "accepted") else "string"} for field in ENTRY_FIELDS}}
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "PolicyScenarioCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def manifest_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "PolicyScenarioManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}
def summary_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "PolicyScenarioSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "array" if field == "risk_flags" else "integer" if field.endswith("count") or field.startswith("minimum_") else "boolean" if field in ("accepted", "release_ready") else "string"} for field in SUMMARY_FIELDS}}
def scenario_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "PolicyScenario", "type": "object", "additionalProperties": False, "required": list(SCENARIO_FIELDS), "properties": {field: {"type": "array" if field in ("risk_flags", "entries", "checks") else "object" if field in ("policy", "manifest", "summary") else "integer" if field.endswith("count") or field.startswith("minimum_") else "boolean" if field in ("accepted", "release_ready") else "string"} for field in SCENARIO_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "check_ids": CHECK_IDS, "risk_flags": RISK_FLAGS, "states": STATES, "max_entries": MAX_ENTRIES, "max_checks": MAX_CHECKS, "features": ("cross-policy runtime scenario comparison", "budget margin and risk projections", "mixed readiness analysis", "exact six-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "SCENARIO_PREFIX", "POLICY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_SCENARIO_ID", "FILES", "ARTIFACT_FILES", "STATES", "SEVERITIES", "RISK_FLAGS", "MAX_ENTRIES", "MAX_CHECKS", "MAX_SCENARIO_BYTES", "POLICY_FIELDS", "ENTRY_FIELDS", "CHECK_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "SCENARIO_FIELDS", "CHECK_IDS", "ScenarioPolicy", "ScenarioEntry", "ScenarioCheck", "ScenarioManifest", "ScenarioSummary", "PolicyScenario", "address_policy", "address_entry", "address_entries", "address_check", "address_checks", "address_manifest", "address_summary", "address_scenario", "build_policy", "build_scenario", "verify_scenario", "scenario_from_mapping", "scenario_json", "policy_json", "entries_json", "checks_json", "summary_json", "manifest_json", "scenario_csv", "render_scenario_markdown", "persist_scenario", "load_scenario", "run_scenario", "policy_schema", "entry_schema", "check_schema", "manifest_schema", "summary_schema", "scenario_schema", "capabilities"]
