"""Policy-driven release decisions over runtime registry history diffs."""

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

from . import downloaded_data_quality_d339_history_diff as diff_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = diff_model.VERSION + "-runtime-v1"
BOUNDARY = diff_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = diff_model.DIFF_PREFIX + "-runtime"
POLICY_PREFIX = RUNTIME_PREFIX + "-policy"
CHECK_PREFIX = RUNTIME_PREFIX + "-check"
CHECKS_PREFIX = RUNTIME_PREFIX + "-checks"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
SUMMARY_PREFIX = RUNTIME_PREFIX + "-summary"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
FILES = ("manifest.json", "runtime.json", "checks.json", "summary.json")
ARTIFACT_FILES = ("checks.json", "summary.json")
STATES = ("ready", "blocked")
SEVERITIES = ("info", "error")
MAX_CHECKS = 15
MAX_RUNTIME_BYTES = 32 * 1024 * 1024
POLICY_FIELDS = ("policy_id", "diff_id", "minimum_items", "maximum_added", "maximum_removed", "maximum_changed", "allowed_directions", "require_accepted", "require_state_change", "allow_unchanged", "content_address")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "severity", "actual", "expected", "detail", "content_address")
CHECKS_FIELDS = ("checks", "content_address")
MANIFEST_FIELDS = ("runtime_id", "diff_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("runtime_id", "diff_id", "diff_address", "policy_address", "check_count", "passed_count", "failed_count", "release_ready", "state", "direction", "state_transition", "item_count", "added_count", "removed_count", "changed_count", "accepted", "content_address")
RUNTIME_FIELDS = ("runtime_id", "diff_id", "diff_address", "version", "boundary", "policy", "checks", "check_count", "passed_count", "failed_count", "release_ready", "state", "direction", "state_transition", "item_count", "added_count", "removed_count", "changed_count", "accepted", "manifest", "summary", "content_address")
CHECK_IDS = ("diff_present", "diff_accepted", "minimum_items", "added_budget", "removed_budget", "changed_budget", "direction_policy", "state_transition", "unchanged_policy", "comparison_conservation", "identity_link", "address_integrity", "policy_integrity", "release_disposition", "public_boundary")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if not value:
        return value
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
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


def _public(value: Any) -> bool:
    return diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class RuntimePolicy:
    FIELDS = POLICY_FIELDS

    def __init__(self, policy_id: str, diff_id: str, minimum_items: int, maximum_added: int, maximum_removed: int, maximum_changed: int, allowed_directions: Sequence[str], require_accepted: bool, require_state_change: bool, allow_unchanged: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "history diff runtime policy ID")
        self.diff_id = _label(diff_id, "history diff runtime policy diff ID")
        self.minimum_items = _count(minimum_items, "history diff runtime minimum items", diff_model.MAX_ITEMS)
        self.maximum_added = _count(maximum_added, "history diff runtime maximum added items", diff_model.MAX_ITEMS)
        self.maximum_removed = _count(maximum_removed, "history diff runtime maximum removed items", diff_model.MAX_ITEMS)
        self.maximum_changed = _count(maximum_changed, "history diff runtime maximum changed items", diff_model.MAX_ITEMS)
        self.allowed_directions = tuple(_label(item, "history diff runtime allowed direction") for item in _sequence(allowed_directions, "history diff runtime allowed directions", len(diff_model.DIRECTIONS)))
        self.require_accepted = _bool(require_accepted, "history diff runtime acceptance requirement")
        self.require_state_change = _bool(require_state_change, "history diff runtime state-change requirement")
        self.allow_unchanged = _bool(allow_unchanged, "history diff runtime unchanged policy")
        self.content_address = _address(content_address, "history diff runtime policy address", POLICY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.allowed_directions or len(set(self.allowed_directions)) != len(self.allowed_directions) or any(item not in diff_model.DIRECTIONS for item in self.allowed_directions):
            raise ValidationError("history diff runtime policy directions are unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address:
            raise ValidationError("history diff runtime policy address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff runtime policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimePolicy":
        value = _mapping(value, "history diff runtime policy")
        _strict(value, set(cls.FIELDS), "history diff runtime policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: RuntimePolicy) -> str:
    if not isinstance(value, RuntimePolicy):
        raise ValidationError("history diff runtime policy address requires a typed policy")
    return _address_for(value, POLICY_PREFIX)


class RuntimeCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff runtime check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "history diff runtime check ID")
        self.passed = _bool(passed, "history diff runtime check result")
        if severity not in SEVERITIES:
            raise ValidationError("history diff runtime check severity is unsupported")
        self.severity = severity
        self.actual = _text(actual, "history diff runtime check actual", 32768)
        self.expected = _text(expected, "history diff runtime check expected", 32768)
        self.detail = _text(detail, "history diff runtime check detail", 4096)
        self.content_address = _address(content_address, "history diff runtime check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or (self.passed and self.severity == "error"):
            raise ValidationError("history diff runtime check identity or severity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("history diff runtime check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff runtime check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeCheck":
        value = _mapping(value, "history diff runtime check")
        _strict(value, set(cls.FIELDS), "history diff runtime check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RuntimeCheck) -> str:
    if not isinstance(value, RuntimeCheck):
        raise ValidationError("history diff runtime check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


def address_checks(value: Sequence[RuntimeCheck]) -> str:
    checks = tuple(value)
    if any(not isinstance(item, RuntimeCheck) for item in checks):
        raise ValidationError("history diff runtime checks address requires typed checks")
    return content_hash({"checks": [item.to_dict() for item in checks]}, prefix=CHECKS_PREFIX)


class RuntimeManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, diff_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history diff runtime manifest ID")
        self.diff_id = _label(diff_id, "history diff runtime manifest diff ID")
        self.version = _text(version, "history diff runtime manifest version", 1024)
        self.boundary = _text(boundary, "history diff runtime manifest boundary", 2048)
        self.files = tuple(_text(item, "history diff runtime manifest file", 128) for item in _sequence(files, "history diff runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "history diff runtime manifest artifact address") for item in _sequence(artifact_addresses, "history diff runtime manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "history diff runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff runtime manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("history diff runtime manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff runtime manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeManifest":
        value = _mapping(value, "history diff runtime manifest")
        _strict(value, set(cls.FIELDS), "history diff runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: RuntimeManifest) -> str:
    if not isinstance(value, RuntimeManifest):
        raise ValidationError("history diff runtime manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class RuntimeSummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, runtime_id: str, diff_id: str, diff_address: str, policy_address: str, check_count: int, passed_count: int, failed_count: int, release_ready: bool, state: str, direction: str, state_transition: str, item_count: int, added_count: int, removed_count: int, changed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history diff runtime summary ID")
        self.diff_id = _label(diff_id, "history diff runtime summary diff ID")
        self.diff_address = _address(diff_address, "history diff runtime summary diff address", diff_model.DIFF_PREFIX)
        self.policy_address = _address(policy_address, "history diff runtime summary policy address", POLICY_PREFIX)
        self.check_count = _count(check_count, "history diff runtime summary check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "history diff runtime summary passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history diff runtime summary failed count", MAX_CHECKS)
        self.release_ready = _bool(release_ready, "history diff runtime summary readiness")
        if state not in STATES or direction not in diff_model.DIRECTIONS:
            raise ValidationError("history diff runtime summary state or direction is unsupported")
        self.state = state
        self.direction = direction
        self.state_transition = _text(state_transition, "history diff runtime summary state transition", 128)
        self.item_count = _count(item_count, "history diff runtime summary item count", diff_model.MAX_ITEMS)
        self.added_count = _count(added_count, "history diff runtime summary added count", diff_model.MAX_ITEMS)
        self.removed_count = _count(removed_count, "history diff runtime summary removed count", diff_model.MAX_ITEMS)
        self.changed_count = _count(changed_count, "history diff runtime summary changed count", diff_model.MAX_ITEMS)
        self.accepted = _bool(accepted, "history diff runtime summary acceptance")
        self.content_address = _address(content_address, "history diff runtime summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.passed_count + self.failed_count != self.check_count or self.release_ready != (self.failed_count == 0) or self.state != ("ready" if self.release_ready else "blocked"):
            raise ValidationError("history diff runtime summary disposition does not replay")
        if self.added_count + self.removed_count + self.changed_count > self.item_count:
            raise ValidationError("history diff runtime summary comparison counts exceed items")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address:
            raise ValidationError("history diff runtime summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff runtime summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeSummary":
        value = _mapping(value, "history diff runtime summary")
        _strict(value, set(cls.FIELDS), "history diff runtime summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: RuntimeSummary) -> str:
    if not isinstance(value, RuntimeSummary):
        raise ValidationError("history diff runtime summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class DiffRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, diff_id: str, diff_address: str, version: str, boundary: str, policy: Mapping[str, Any] | RuntimePolicy, checks: Sequence[RuntimeCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, release_ready: bool, state: str, direction: str, state_transition: str, item_count: int, added_count: int, removed_count: int, changed_count: int, accepted: bool, manifest: Mapping[str, Any] | RuntimeManifest, summary: Mapping[str, Any] | RuntimeSummary, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history diff runtime ID")
        self.diff_id = _label(diff_id, "history diff runtime diff ID")
        self.diff_address = _address(diff_address, "history diff runtime diff address", diff_model.DIFF_PREFIX)
        self.version = _text(version, "history diff runtime version", 1024)
        self.boundary = _text(boundary, "history diff runtime boundary", 2048)
        self.policy = policy if isinstance(policy, RuntimePolicy) else RuntimePolicy.from_mapping(_mapping(policy, "history diff runtime policy"))
        self.checks = tuple(item if isinstance(item, RuntimeCheck) else RuntimeCheck.from_mapping(_mapping(item, "history diff runtime check")) for item in _sequence(checks, "history diff runtime checks", MAX_CHECKS))
        self.check_count = _count(check_count, "history diff runtime check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "history diff runtime passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history diff runtime failed count", MAX_CHECKS)
        self.release_ready = _bool(release_ready, "history diff runtime readiness")
        if state not in STATES or direction not in diff_model.DIRECTIONS:
            raise ValidationError("history diff runtime state or direction is unsupported")
        self.state = state
        self.direction = direction
        self.state_transition = _text(state_transition, "history diff runtime state transition", 128)
        self.item_count = _count(item_count, "history diff runtime item count", diff_model.MAX_ITEMS)
        self.added_count = _count(added_count, "history diff runtime added count", diff_model.MAX_ITEMS)
        self.removed_count = _count(removed_count, "history diff runtime removed count", diff_model.MAX_ITEMS)
        self.changed_count = _count(changed_count, "history diff runtime changed count", diff_model.MAX_ITEMS)
        self.accepted = _bool(accepted, "history diff runtime acceptance")
        self.manifest = manifest if isinstance(manifest, RuntimeManifest) else RuntimeManifest.from_mapping(_mapping(manifest, "history diff runtime manifest"))
        self.summary = summary if isinstance(summary, RuntimeSummary) else RuntimeSummary.from_mapping(_mapping(summary, "history diff runtime summary"))
        self.content_address = _address(content_address, "history diff runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.policy.diff_id != self.diff_id or self.check_count != len(self.checks) or self.check_count != MAX_CHECKS:
            raise ValidationError("history diff runtime identity or check count does not replay")
        if (self.passed_count, self.failed_count) != (sum(item.passed for item in self.checks), sum(not item.passed for item in self.checks)):
            raise ValidationError("history diff runtime counters do not replay")
        if self.release_ready != (self.failed_count == 0) or self.state != ("ready" if self.release_ready else "blocked"):
            raise ValidationError("history diff runtime disposition does not replay")
        counts = (self.added_count, self.removed_count, self.changed_count)
        if any(item < 0 for item in counts) or sum(counts) > self.item_count:
            raise ValidationError("history diff runtime comparison counts do not replay")
        expected_summary = (self.runtime_id, self.diff_id, self.diff_address, address_policy(self.policy), self.check_count, self.passed_count, self.failed_count, self.release_ready, self.state, self.direction, self.state_transition, self.item_count, self.added_count, self.removed_count, self.changed_count, self.accepted)
        actual_summary = tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1])
        if actual_summary != expected_summary or self.summary.content_address != address_summary(self.summary):
            raise ValidationError("history diff runtime summary does not replay")
        expected_manifest = (self.runtime_id, self.diff_id, VERSION, BOUNDARY, FILES, (address_checks(self.checks), self.summary.content_address))
        actual_manifest = (self.manifest.runtime_id, self.manifest.diff_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest):
            raise ValidationError("history diff runtime manifest does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, RUNTIME_PREFIX) != self.content_address:
            raise ValidationError("history diff runtime address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "diff_id": self.diff_id, "diff_address": self.diff_address, "version": self.version, "boundary": self.boundary, "policy": self.policy.to_dict(), "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "release_ready": self.release_ready, "state": self.state, "direction": self.direction, "state_transition": self.state_transition, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffRuntime":
        value = _mapping(value, "history diff runtime")
        _strict(value, set(cls.FIELDS), "history diff runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DiffRuntime) -> str:
    if not isinstance(value, DiffRuntime):
        raise ValidationError("history diff runtime address requires a typed runtime")
    return _address_for(value, RUNTIME_PREFIX)


def build_policy(policy_id: str, diff_id: str, *, minimum_items: int = 1, maximum_added: int = diff_model.MAX_ITEMS, maximum_removed: int = 0, maximum_changed: int = 0, allowed_directions: Sequence[str] = ("improved", "changed", "unchanged"), require_accepted: bool = True, require_state_change: bool = False, allow_unchanged: bool = True) -> RuntimePolicy:
    value = RuntimePolicy(policy_id, diff_id, minimum_items, maximum_added, maximum_removed, maximum_changed, allowed_directions, require_accepted, require_state_change, allow_unchanged, f"pending:{POLICY_PREFIX}")
    return _seal(value, address_policy)


def _policy_for(diff: diff_model.HistoryDiff, runtime_id: str, policy: RuntimePolicy | Mapping[str, Any] | None) -> RuntimePolicy:
    if policy is None:
        return build_policy(runtime_id, diff.diff_id)
    value = policy if isinstance(policy, RuntimePolicy) else RuntimePolicy.from_mapping(_mapping(policy, "history diff runtime policy"))
    if value.diff_id != diff.diff_id:
        raise ValidationError("history diff runtime policy diff identity does not match")
    return value


def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> RuntimeCheck:
    return RuntimeCheck(ordinal, check_id, passed, "info" if passed else "error", canonical_json(actual), canonical_json(expected), detail, f"pending:{CHECK_PREFIX}")


def build_runtime(diff: diff_model.HistoryDiff, *, runtime_id: str = DEFAULT_RUNTIME_ID, policy: RuntimePolicy | Mapping[str, Any] | None = None) -> DiffRuntime:
    if not isinstance(diff, diff_model.HistoryDiff):
        raise ValidationError("history diff runtime requires a typed diff")
    diff_model.verify_diff(diff)
    runtime_id = _label(runtime_id, "history diff runtime ID")
    policy_value = _policy_for(diff, runtime_id, policy)
    transition_parts = diff.state_transition.split("->")
    transition_valid = len(transition_parts) == 2 and all(part in diff_model.history_model.STATES for part in transition_parts)
    checks = (
        _check(1, "diff_present", bool(diff.content_address), diff.content_address, diff_model.DIFF_PREFIX, "comparison must have a canonical address"),
        _check(2, "diff_accepted", not policy_value.require_accepted or diff.accepted, diff.accepted, True if policy_value.require_accepted else "not-required", "comparison acceptance must satisfy policy"),
        _check(3, "minimum_items", diff.item_count >= policy_value.minimum_items, diff.item_count, f">= {policy_value.minimum_items}", "comparison depth must satisfy policy"),
        _check(4, "added_budget", diff.added_count <= policy_value.maximum_added, diff.added_count, f"<= {policy_value.maximum_added}", "added snapshot budget must remain bounded"),
        _check(5, "removed_budget", diff.removed_count <= policy_value.maximum_removed, diff.removed_count, f"<= {policy_value.maximum_removed}", "removed snapshot budget must remain bounded"),
        _check(6, "changed_budget", diff.changed_count <= policy_value.maximum_changed, diff.changed_count, f"<= {policy_value.maximum_changed}", "changed snapshot budget must remain bounded"),
        _check(7, "direction_policy", diff.direction in policy_value.allowed_directions, diff.direction, policy_value.allowed_directions, "comparison direction must be permitted"),
        _check(8, "state_transition", transition_valid and (not policy_value.require_state_change or transition_parts[0] != transition_parts[1]), diff.state_transition, "valid state transition" if not policy_value.require_state_change else "distinct state transition", "state transition must satisfy policy"),
        _check(9, "unchanged_policy", policy_value.allow_unchanged or diff.unchanged_count == 0, diff.unchanged_count, "allowed" if policy_value.allow_unchanged else "== 0", "unchanged snapshots must follow policy"),
        _check(10, "comparison_conservation", sum((diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count)) == diff.item_count, diff.item_count, "sum change classes", "comparison classes must conserve items"),
        _check(11, "identity_link", diff.summary.diff_id == diff.diff_id and diff.summary.registry_id == diff.registry_id, (diff.summary.diff_id, diff.summary.registry_id), (diff.diff_id, diff.registry_id), "summary identity must link to comparison"),
        _check(12, "address_integrity", diff.content_address == diff_model.address_diff(diff) and diff.summary.content_address == diff_model.address_summary(diff.summary), (diff.content_address, diff.summary.content_address), "canonical diff and summary addresses", "comparison addresses must replay"),
        _check(13, "policy_integrity", policy_value.diff_id == diff.diff_id and policy_value.content_address == address_policy(policy_value), (policy_value.diff_id, policy_value.content_address), (diff.diff_id, address_policy(policy_value)), "policy must bind to this comparison"),
        _check(14, "release_disposition", (diff.accepted or not policy_value.require_accepted) and diff.direction in policy_value.allowed_directions, (diff.accepted, diff.direction), (True if policy_value.require_accepted else "not-required", policy_value.allowed_directions), "release disposition must be policy-compatible"),
        _check(15, "public_boundary", _public(diff.to_dict()), True, True, "runtime decision must remain value-only and path-free"),
    )
    checks = tuple(_seal(item, address_check) for item in checks)
    passed = sum(item.passed for item in checks)
    release_ready = passed == len(checks)
    summary = _seal(RuntimeSummary(runtime_id, diff.diff_id, diff.content_address, address_policy(policy_value), len(checks), passed, len(checks) - passed, release_ready, "ready" if release_ready else "blocked", diff.direction, diff.state_transition, diff.item_count, diff.added_count, diff.removed_count, diff.changed_count, diff.accepted, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(RuntimeManifest(runtime_id, diff.diff_id, VERSION, BOUNDARY, FILES, (address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(DiffRuntime(runtime_id, diff.diff_id, diff.content_address, VERSION, BOUNDARY, policy_value, checks, len(checks), passed, len(checks) - passed, release_ready, "ready" if release_ready else "blocked", diff.direction, diff.state_transition, diff.item_count, diff.added_count, diff.removed_count, diff.changed_count, diff.accepted, manifest, summary, f"pending:{RUNTIME_PREFIX}"), address_runtime)


def verify_runtime(value: DiffRuntime, diff: diff_model.HistoryDiff | None = None) -> DiffRuntime:
    if not isinstance(value, DiffRuntime):
        raise ValidationError("history diff runtime verification requires a typed runtime")
    if diff is not None:
        diff_model.verify_diff(diff)
        if diff.content_address != value.diff_address:
            raise ValidationError("history diff runtime source comparison address does not match")
    value._validate()
    return value


def runtime_from_mapping(value: Mapping[str, Any], diff: diff_model.HistoryDiff | None = None) -> DiffRuntime:
    result = DiffRuntime.from_mapping(value)
    if diff is not None:
        verify_runtime(result, diff)
    return result


def runtime_json(value: DiffRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def checks_json(value: DiffRuntime) -> str:
    value = verify_runtime(value)
    return canonical_json({"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)})


def summary_json(value: DiffRuntime) -> str:
    return canonical_json(verify_runtime(value).summary.to_dict())


def manifest_json(value: DiffRuntime) -> str:
    return canonical_json(verify_runtime(value).manifest.to_dict())


def runtime_csv(value: DiffRuntime) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_runtime(value).checks); return output.getvalue()


def render_runtime_markdown(value: DiffRuntime) -> str:
    value = verify_runtime(value)
    lines = [f"# Runtime registry history diff runtime {value.runtime_id}", "", f"- State: {value.state}", f"- Release ready: {str(value.release_ready).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", f"- Direction: {value.direction}", f"- State transition: {value.state_transition}", f"- Items: {value.item_count}", "", "| Check | Result | Severity | Detail |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.severity} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: DiffRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_runtime(value); destination = Path(destination); _validate_parent(destination.parent, "history diff runtime destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("history diff runtime destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True); temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-history-diff-runtime-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "runtime.json": value.to_dict(), "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES: _write(temporary / name, documents[name])
        if destination.exists(): shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True); raise ValidationError("history diff runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try: value = _strict_json_loads(read_text(path, field="history diff runtime artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error: raise ValidationError("history diff runtime artifact is not valid JSON") from error
    return _mapping(value, "history diff runtime artifact")


def load_runtime(destination: str | Path, diff: diff_model.HistoryDiff | None = None) -> DiffRuntime:
    destination = Path(destination); _validate_parent(destination.parent, "history diff runtime input")
    if not destination.is_dir() or destination.is_symlink(): raise ValidationError("history diff runtime source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children): raise ValidationError("history diff runtime directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="history diff runtime artifact") != serialized or len(serialized.encode("utf-8")) > MAX_RUNTIME_BYTES: raise ValidationError("history diff runtime artifact is non-canonical or exceeds its size bound")
    value = runtime_from_mapping(documents["runtime.json"], diff)
    expected = {"manifest.json": value.manifest.to_dict(), "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()): raise ValidationError("history diff runtime component documents do not replay runtime.json")
    return verify_runtime(value, diff)


def run_runtime(diff: diff_model.HistoryDiff, *, runtime_id: str = DEFAULT_RUNTIME_ID, policy: RuntimePolicy | Mapping[str, Any] | None = None, destination: str | Path | None = None, overwrite: bool = False) -> DiffRuntime:
    value = build_runtime(diff, runtime_id=runtime_id, policy=policy)
    if destination is not None: persist_runtime(value, destination, overwrite=overwrite)
    return value


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffRuntimePolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "array" if field == "allowed_directions" else "integer" if field.startswith("minimum") or field.startswith("maximum") else "boolean" if field.startswith("require") or field.startswith("allow") else "string"} for field in POLICY_FIELDS}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffRuntimeCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffRuntimeManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffRuntimeSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("release_ready", "accepted") else "string"} for field in SUMMARY_FIELDS}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffRuntime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field in ("release_ready", "accepted") else "object" if field in ("policy", "manifest", "summary") else "string"} for field in RUNTIME_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "check_ids": CHECK_IDS, "states": STATES, "severities": SEVERITIES, "max_checks": MAX_CHECKS, "features": ("diff-linked release policy", "direction and transition controls", "added removed and changed budgets", "exact four-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "RUNTIME_PREFIX", "POLICY_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_RUNTIME_ID", "FILES", "ARTIFACT_FILES", "STATES", "SEVERITIES", "MAX_CHECKS", "MAX_RUNTIME_BYTES", "POLICY_FIELDS", "CHECK_FIELDS", "CHECKS_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "RUNTIME_FIELDS", "CHECK_IDS", "RuntimePolicy", "RuntimeCheck", "RuntimeManifest", "RuntimeSummary", "DiffRuntime", "address_policy", "address_check", "address_checks", "address_manifest", "address_summary", "address_runtime", "build_policy", "build_runtime", "verify_runtime", "runtime_from_mapping", "runtime_json", "checks_json", "summary_json", "manifest_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime", "policy_schema", "check_schema", "manifest_schema", "summary_schema", "runtime_schema", "capabilities"]






















