"""Policy-driven evaluation of D488 gate-decision ledger diffs."""

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

from . import downloaded_data_quality_d488_gate_decision_ledger_diff as diff_model
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
SUMMARY_FIELDS = ("runtime_id", "diff_id", "diff_address", "policy_address", "check_count", "passed_count", "failed_count", "release_ready", "state", "direction", "state_transition", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "accepted", "content_address")
RUNTIME_FIELDS = ("runtime_id", "diff_id", "diff_address", "version", "boundary", "policy", "checks", "check_count", "passed_count", "failed_count", "release_ready", "state", "direction", "state_transition", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "accepted", "manifest", "summary", "content_address")
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
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__") or not hasattr(value, "__iter__") or len(value) > maximum:
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
    return diff_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class RuntimePolicy:
    FIELDS = POLICY_FIELDS

    def __init__(self, policy_id: str, diff_id: str, minimum_items: int, maximum_added: int, maximum_removed: int, maximum_changed: int, allowed_directions: Sequence[str], require_accepted: bool, require_state_change: bool, allow_unchanged: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "ledger diff runtime policy ID")
        self.diff_id = _label(diff_id, "ledger diff runtime policy diff ID")
        self.minimum_items = _count(minimum_items, "ledger diff runtime minimum items", diff_model.MAX_ITEMS, lower=1)
        self.maximum_added = _count(maximum_added, "ledger diff runtime maximum added", diff_model.MAX_ITEMS)
        self.maximum_removed = _count(maximum_removed, "ledger diff runtime maximum removed", diff_model.MAX_ITEMS)
        self.maximum_changed = _count(maximum_changed, "ledger diff runtime maximum changed", diff_model.MAX_ITEMS)
        self.allowed_directions = tuple(_label(item, "ledger diff runtime allowed direction") for item in _sequence(allowed_directions, "ledger diff runtime allowed directions", len(diff_model.DIRECTIONS)))
        self.require_accepted = _bool(require_accepted, "ledger diff runtime acceptance requirement")
        self.require_state_change = _bool(require_state_change, "ledger diff runtime state-change requirement")
        self.allow_unchanged = _bool(allow_unchanged, "ledger diff runtime unchanged policy")
        self.content_address = _address(content_address, "ledger diff runtime policy address", POLICY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.allowed_directions or any(item not in diff_model.DIRECTIONS for item in self.allowed_directions) or len(set(self.allowed_directions)) != len(self.allowed_directions):
            raise ValidationError("ledger diff runtime policy directions are unsupported or duplicated")
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime policy address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"allowed_directions": list(self.allowed_directions), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimePolicy":
        value = _mapping(value, "ledger diff runtime policy")
        _strict(value, set(cls.FIELDS), "ledger diff runtime policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: RuntimePolicy) -> str:
    if not isinstance(value, RuntimePolicy):
        raise ValidationError("ledger diff runtime policy address requires a typed policy")
    return _address_for(value, POLICY_PREFIX)


class RuntimeCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff runtime check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "ledger diff runtime check ID")
        self.passed = _bool(passed, "ledger diff runtime check result")
        if severity not in SEVERITIES:
            raise ValidationError("ledger diff runtime check severity is unsupported")
        self.severity = severity
        self.actual = _text(actual, "ledger diff runtime check actual", 32768)
        self.expected = _text(expected, "ledger diff runtime check expected", 32768)
        self.detail = _text(detail, "ledger diff runtime check detail", 4096)
        self.content_address = _address(content_address, "ledger diff runtime check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or (self.passed and self.severity == "error"):
            raise ValidationError("ledger diff runtime check identity or severity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeCheck":
        value = _mapping(value, "ledger diff runtime check")
        _strict(value, set(cls.FIELDS), "ledger diff runtime check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RuntimeCheck) -> str:
    if not isinstance(value, RuntimeCheck):
        raise ValidationError("ledger diff runtime check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


def address_checks(value: Sequence[RuntimeCheck]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, RuntimeCheck) for item in typed):
        raise ValidationError("ledger diff runtime checks address requires typed checks")
    return content_hash({"checks": [item.to_dict() for item in typed]}, prefix=CHECKS_PREFIX)


class RuntimeManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, diff_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "ledger diff runtime manifest runtime ID")
        self.diff_id = _label(diff_id, "ledger diff runtime manifest diff ID")
        self.version = _text(version, "ledger diff runtime manifest version", 1024)
        self.boundary = _text(boundary, "ledger diff runtime manifest boundary", 2048)
        self.files = tuple(_text(item, "ledger diff runtime manifest file", 128) for item in _sequence(files, "ledger diff runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "ledger diff runtime manifest artifact address") for item in _sequence(artifact_addresses, "ledger diff runtime manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "ledger diff runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger diff runtime manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeManifest":
        value = _mapping(value, "ledger diff runtime manifest")
        _strict(value, set(cls.FIELDS), "ledger diff runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: RuntimeManifest) -> str:
    if not isinstance(value, RuntimeManifest):
        raise ValidationError("ledger diff runtime manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class RuntimeSummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, runtime_id: str, diff_id: str, diff_address: str, policy_address: str, check_count: int, passed_count: int, failed_count: int, release_ready: bool, state: str, direction: str, state_transition: str, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "ledger diff runtime summary ID")
        self.diff_id = _label(diff_id, "ledger diff runtime summary diff ID")
        self.diff_address = _address(diff_address, "ledger diff runtime summary diff address", diff_model.DIFF_PREFIX)
        self.policy_address = _address(policy_address, "ledger diff runtime summary policy address", POLICY_PREFIX)
        self.check_count = _count(check_count, "ledger diff runtime summary check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "ledger diff runtime summary passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "ledger diff runtime summary failed count", MAX_CHECKS)
        self.release_ready = _bool(release_ready, "ledger diff runtime summary readiness")
        if state not in STATES or direction not in diff_model.DIRECTIONS:
            raise ValidationError("ledger diff runtime summary state or direction is unsupported")
        self.state = state
        self.direction = direction
        self.state_transition = _text(state_transition, "ledger diff runtime summary state transition", 128)
        self.item_count = _count(item_count, "ledger diff runtime summary item count", diff_model.MAX_ITEMS)
        self.added_count = _count(added_count, "ledger diff runtime summary added count", diff_model.MAX_ITEMS)
        self.removed_count = _count(removed_count, "ledger diff runtime summary removed count", diff_model.MAX_ITEMS)
        self.changed_count = _count(changed_count, "ledger diff runtime summary changed count", diff_model.MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "ledger diff runtime summary unchanged count", diff_model.MAX_ITEMS)
        self.accepted = _bool(accepted, "ledger diff runtime summary acceptance")
        self.content_address = _address(content_address, "ledger diff runtime summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.passed_count + self.failed_count != self.check_count or self.passed_count > self.check_count or self.release_ready != (self.state == "ready") or self.added_count + self.removed_count + self.changed_count + self.unchanged_count != self.item_count:
            raise ValidationError("ledger diff runtime summary disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeSummary":
        value = _mapping(value, "ledger diff runtime summary")
        _strict(value, set(cls.FIELDS), "ledger diff runtime summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: RuntimeSummary) -> str:
    if not isinstance(value, RuntimeSummary):
        raise ValidationError("ledger diff runtime summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class LedgerDiffRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, diff_id: str, diff_address: str, version: str, boundary: str, policy: Mapping[str, Any] | RuntimePolicy, checks: Sequence[RuntimeCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, release_ready: bool, state: str, direction: str, state_transition: str, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, accepted: bool, manifest: Mapping[str, Any] | RuntimeManifest, summary: Mapping[str, Any] | RuntimeSummary, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "ledger diff runtime ID")
        self.diff_id = _label(diff_id, "ledger diff runtime diff ID")
        self.diff_address = _address(diff_address, "ledger diff runtime diff address", diff_model.DIFF_PREFIX)
        self.version = _text(version, "ledger diff runtime version", 1024)
        self.boundary = _text(boundary, "ledger diff runtime boundary", 2048)
        self.policy = policy if isinstance(policy, RuntimePolicy) else RuntimePolicy.from_mapping(_mapping(policy, "ledger diff runtime policy"))
        self.checks = tuple(item if isinstance(item, RuntimeCheck) else RuntimeCheck.from_mapping(_mapping(item, "ledger diff runtime check")) for item in _sequence(checks, "ledger diff runtime checks", MAX_CHECKS))
        self.check_count = _count(check_count, "ledger diff runtime check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "ledger diff runtime passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "ledger diff runtime failed count", MAX_CHECKS)
        self.release_ready = _bool(release_ready, "ledger diff runtime readiness")
        if state not in STATES or direction not in diff_model.DIRECTIONS:
            raise ValidationError("ledger diff runtime state or direction is unsupported")
        self.state = state
        self.direction = direction
        self.state_transition = _text(state_transition, "ledger diff runtime state transition", 128)
        self.item_count = _count(item_count, "ledger diff runtime item count", diff_model.MAX_ITEMS)
        self.added_count = _count(added_count, "ledger diff runtime added count", diff_model.MAX_ITEMS)
        self.removed_count = _count(removed_count, "ledger diff runtime removed count", diff_model.MAX_ITEMS)
        self.changed_count = _count(changed_count, "ledger diff runtime changed count", diff_model.MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "ledger diff runtime unchanged count", diff_model.MAX_ITEMS)
        self.accepted = _bool(accepted, "ledger diff runtime acceptance")
        self.manifest = manifest if isinstance(manifest, RuntimeManifest) else RuntimeManifest.from_mapping(_mapping(manifest, "ledger diff runtime manifest"))
        self.summary = summary if isinstance(summary, RuntimeSummary) else RuntimeSummary.from_mapping(_mapping(summary, "ledger diff runtime summary"))
        self.content_address = _address(content_address, "ledger diff runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.policy.diff_id != self.diff_id or self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.release_ready != all(item.passed for item in self.checks) or self.release_ready != (self.state == "ready") or self.accepted != self.summary.accepted:
            raise ValidationError("ledger diff runtime disposition does not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("ledger diff runtime checks are not canonical")
        expected_summary = (self.runtime_id, self.diff_id, self.diff_address, self.policy.content_address, self.check_count, self.passed_count, self.failed_count, self.release_ready, self.state, self.direction, self.state_transition, self.item_count, self.added_count, self.removed_count, self.changed_count, self.unchanged_count, self.accepted)
        if tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1]) != expected_summary or self.summary.content_address != address_summary(self.summary):
            raise ValidationError("ledger diff runtime summary does not replay")
        if self.manifest.runtime_id != self.runtime_id or self.manifest.diff_id != self.diff_id or self.manifest.files != FILES or self.manifest.artifact_addresses != (address_checks(self.checks), self.summary.content_address) or self.manifest.content_address != address_manifest(self.manifest):
            raise ValidationError("ledger diff runtime manifest does not replay")
        if self.policy.content_address != address_policy(self.policy) or self.content_address != address_runtime(self):
            if not self.content_address.startswith("pending:"):
                raise ValidationError("ledger diff runtime address or policy does not replay")
        if not self.content_address.startswith("pending:") and address_runtime(self) != self.content_address:
            raise ValidationError("ledger diff runtime address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "diff_id": self.diff_id, "diff_address": self.diff_address, "version": self.version, "boundary": self.boundary, "policy": self.policy.to_dict(), "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "release_ready": self.release_ready, "state": self.state, "direction": self.direction, "state_transition": self.state_transition, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerDiffRuntime":
        value = _mapping(value, "ledger diff runtime")
        _strict(value, set(cls.FIELDS), "ledger diff runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: LedgerDiffRuntime) -> str:
    if not isinstance(value, LedgerDiffRuntime):
        raise ValidationError("ledger diff runtime address requires a typed runtime")
    return _address_for(value, RUNTIME_PREFIX)


def build_policy(policy_id: str, diff_id: str, *, minimum_items: int = 1, maximum_added: int = diff_model.MAX_ITEMS, maximum_removed: int = diff_model.MAX_ITEMS, maximum_changed: int = diff_model.MAX_ITEMS, allowed_directions: Sequence[str] = diff_model.DIRECTIONS, require_accepted: bool = True, require_state_change: bool = True, allow_unchanged: bool = True) -> RuntimePolicy:
    return _seal(RuntimePolicy(policy_id, diff_id, minimum_items, maximum_added, maximum_removed, maximum_changed, allowed_directions, require_accepted, require_state_change, allow_unchanged, f"pending:{POLICY_PREFIX}"), address_policy)


def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> RuntimeCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "severity": "info" if passed else "error", "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}
    provisional = RuntimeCheck(**body)
    return RuntimeCheck(**(body | {"content_address": address_check(provisional)}))


def build_runtime(diff: diff_model.LedgerDiff, *, runtime_id: str = DEFAULT_RUNTIME_ID, policy: RuntimePolicy | Mapping[str, Any] | None = None) -> LedgerDiffRuntime:
    diff_model.verify_diff(diff)
    runtime_policy = policy if isinstance(policy, RuntimePolicy) else RuntimePolicy.from_mapping(_mapping(policy, "ledger diff runtime policy")) if policy is not None else build_policy(f"{runtime_id}-policy", diff.diff_id)
    same_state = diff.left_state == diff.right_state
    checks = (
        _check(1, "diff_present", bool(diff.content_address), diff.content_address, "content-addressed diff", "the evaluated diff must be present"),
        _check(2, "diff_accepted", (not runtime_policy.require_accepted) or diff.accepted, diff.accepted, True, "the upstream diff must satisfy acceptance policy"),
        _check(3, "minimum_items", diff.item_count >= runtime_policy.minimum_items, diff.item_count, runtime_policy.minimum_items, "diff item count must meet the policy floor"),
        _check(4, "added_budget", diff.added_count <= runtime_policy.maximum_added, diff.added_count, runtime_policy.maximum_added, "added decisions must remain within budget"),
        _check(5, "removed_budget", diff.removed_count <= runtime_policy.maximum_removed, diff.removed_count, runtime_policy.maximum_removed, "removed decisions must remain within budget"),
        _check(6, "changed_budget", diff.changed_count <= runtime_policy.maximum_changed, diff.changed_count, runtime_policy.maximum_changed, "changed decisions must remain within budget"),
        _check(7, "direction_policy", diff.direction in runtime_policy.allowed_directions, diff.direction, runtime_policy.allowed_directions, "direction must be permitted"),
        _check(8, "state_transition", (not runtime_policy.require_state_change) or not same_state, diff.state_transition, "different ledger states", "policy may require a state transition"),
        _check(9, "unchanged_policy", runtime_policy.allow_unchanged or diff.unchanged_count == 0, diff.unchanged_count, 0, "unchanged decisions must follow policy"),
        _check(10, "comparison_conservation", diff.added_count + diff.removed_count + diff.changed_count + diff.unchanged_count == diff.item_count, diff.item_count, "sum of classifications", "comparison counts must conserve decisions"),
        _check(11, "identity_link", runtime_policy.diff_id == diff.diff_id and diff.summary.diff_id == diff.diff_id, (runtime_policy.diff_id, diff.diff_id), "matching diff IDs", "policy and summary must link to the evaluated diff"),
        _check(12, "address_integrity", diff.summary.left_ledger_address == diff.left_ledger_address and diff.summary.right_ledger_address == diff.right_ledger_address, True, "retained ledger addresses", "diff lineage addresses must remain intact"),
        _check(13, "policy_integrity", address_policy(runtime_policy) == runtime_policy.content_address, runtime_policy.content_address, address_policy(runtime_policy), "policy address must replay"),
    )
    disposition = all(item.passed for item in checks)
    checks = checks + (_check(14, "release_disposition", disposition, disposition, True, "release readiness is the conjunction of policy checks"), _check(15, "public_boundary", _public(diff.to_dict()) and _public(runtime_policy.to_dict()), True, "public value", "runtime inputs must remain value-only"))
    passed = sum(item.passed for item in checks)
    failed = len(checks) - passed
    release_ready = all(item.passed for item in checks)
    state = "ready" if release_ready else "blocked"
    summary = _seal(RuntimeSummary(runtime_id, diff.diff_id, diff.content_address, runtime_policy.content_address, MAX_CHECKS, passed, failed, release_ready, state, diff.direction, diff.state_transition, diff.item_count, diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count, diff.accepted, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(RuntimeManifest(runtime_id, diff.diff_id, VERSION, BOUNDARY, FILES, (address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(LedgerDiffRuntime(runtime_id, diff.diff_id, diff.content_address, VERSION, BOUNDARY, runtime_policy, checks, MAX_CHECKS, passed, failed, release_ready, state, diff.direction, diff.state_transition, diff.item_count, diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count, diff.accepted, manifest, summary, f"pending:{RUNTIME_PREFIX}"), address_runtime)


def verify_runtime(value: LedgerDiffRuntime, diff: diff_model.LedgerDiff | None = None) -> LedgerDiffRuntime:
    if not isinstance(value, LedgerDiffRuntime):
        raise ValidationError("ledger diff runtime verification requires a typed runtime")
    value._validate()
    if diff is not None and (diff_model.verify_diff(diff).content_address != value.diff_address or diff.diff_id != value.diff_id):
        raise ValidationError("ledger diff runtime does not link to the supplied diff")
    return value


def runtime_from_mapping(value: Mapping[str, Any], diff: diff_model.LedgerDiff | None = None) -> LedgerDiffRuntime:
    return verify_runtime(LedgerDiffRuntime.from_mapping(value), diff)


def runtime_json(value: LedgerDiffRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def checks_json(value: LedgerDiffRuntime) -> str:
    value = verify_runtime(value)
    return canonical_json({"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)})


def summary_json(value: LedgerDiffRuntime) -> str:
    return canonical_json(verify_runtime(value).summary.to_dict())


def manifest_json(value: LedgerDiffRuntime) -> str:
    return canonical_json(verify_runtime(value).manifest.to_dict())


def runtime_csv(value: LedgerDiffRuntime) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_runtime(value).checks)
    return output.getvalue()


def render_runtime_markdown(value: LedgerDiffRuntime) -> str:
    value = verify_runtime(value)
    lines = [f"# Ledger diff runtime {value.runtime_id}", "", f"- State: {value.state}", f"- Release ready: {str(value.release_ready).lower()}", f"- Direction: {value.direction}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: LedgerDiffRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_runtime(value)
    destination = Path(destination)
    _validate_parent(destination.parent, "ledger diff runtime destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("ledger diff runtime destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-ledger-diff-runtime-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "runtime.json": value.to_dict(), "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("ledger diff runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = _strict_json_loads(read_text(path, field="ledger diff runtime artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("ledger diff runtime artifact is not valid JSON") from error
    return _mapping(value, "ledger diff runtime artifact")


def load_runtime(destination: str | Path, diff: diff_model.LedgerDiff | None = None) -> LedgerDiffRuntime:
    destination = Path(destination)
    _validate_parent(destination.parent, "ledger diff runtime input")
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("ledger diff runtime source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("ledger diff runtime directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="ledger diff runtime artifact") != serialized or len(serialized.encode("utf-8")) > MAX_RUNTIME_BYTES:
            raise ValidationError("ledger diff runtime artifact is non-canonical or exceeds its size bound")
    value = runtime_from_mapping(documents["runtime.json"], diff)
    expected = {"manifest.json": value.manifest.to_dict(), "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()):
        raise ValidationError("ledger diff runtime component documents do not replay runtime.json")
    return verify_runtime(value, diff)


def run_runtime(diff: diff_model.LedgerDiff, *, runtime_id: str = DEFAULT_RUNTIME_ID, policy: RuntimePolicy | Mapping[str, Any] | None = None, destination: str | Path | None = None, overwrite: bool = False) -> LedgerDiffRuntime:
    value = build_runtime(diff, runtime_id=runtime_id, policy=policy)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimePolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "array" if field == "allowed_directions" else "integer" if field.startswith("minimum") or field.startswith("maximum") else "boolean" if field.startswith("require") or field.startswith("allow") else "string"} for field in POLICY_FIELDS}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("release_ready", "accepted") else "string"} for field in SUMMARY_FIELDS}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "object" if field in ("policy", "manifest", "summary") else "integer" if field.endswith("count") else "boolean" if field in ("release_ready", "accepted") else "string"} for field in RUNTIME_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "check_ids": CHECK_IDS, "directions": diff_model.DIRECTIONS, "states": STATES, "max_checks": MAX_CHECKS, "features": ("D488 ledger diff policy evaluation", "added removed and changed budgets", "direction and state-transition controls", "exact four-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "RUNTIME_PREFIX", "POLICY_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_RUNTIME_ID", "FILES", "ARTIFACT_FILES", "STATES", "SEVERITIES", "MAX_CHECKS", "MAX_RUNTIME_BYTES", "POLICY_FIELDS", "CHECK_FIELDS", "CHECKS_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "RUNTIME_FIELDS", "CHECK_IDS", "RuntimePolicy", "RuntimeCheck", "RuntimeManifest", "RuntimeSummary", "LedgerDiffRuntime", "address_policy", "address_check", "address_checks", "address_manifest", "address_summary", "address_runtime", "build_policy", "build_runtime", "verify_runtime", "runtime_from_mapping", "runtime_json", "checks_json", "summary_json", "manifest_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime", "policy_schema", "check_schema", "manifest_schema", "summary_schema", "runtime_schema", "capabilities"]
