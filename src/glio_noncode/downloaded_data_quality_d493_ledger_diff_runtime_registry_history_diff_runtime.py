"""Policy evaluation of D492 baseline/candidate history comparisons."""
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
from . import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as diff_model
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
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(c) < 32 and c not in "\n\t" for c in value): raise ValidationError(f"{field} must be bounded text")
    return value
def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(c.isspace() for c in value) or "/" in value or "\\" in value or '"' in value): raise ValidationError(f"{field} must be a compact label")
    return value
def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if not value or value.startswith("pending:") or value.endswith(":pending"): return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix and not value.startswith(prefix + ":")): raise ValidationError(f"{field} has the wrong namespace")
    return value
def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= maximum: raise ValidationError(f"{field} is outside its bound")
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
def _public(value: Any) -> bool: return diff_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value

class RuntimePolicy:
    FIELDS = POLICY_FIELDS
    def __init__(self, policy_id: str, diff_id: str, minimum_items: int, maximum_added: int, maximum_removed: int, maximum_changed: int, allowed_directions: Sequence[str], require_accepted: bool, require_state_change: bool, allow_unchanged: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "D493 policy ID"); self.diff_id = _label(diff_id, "D493 diff ID"); self.minimum_items = _count(minimum_items, "D493 minimum items", diff_model.MAX_ITEMS, lower=1); self.maximum_added = _count(maximum_added, "D493 added budget", diff_model.MAX_ITEMS); self.maximum_removed = _count(maximum_removed, "D493 removed budget", diff_model.MAX_ITEMS); self.maximum_changed = _count(maximum_changed, "D493 changed budget", diff_model.MAX_ITEMS); self.allowed_directions = tuple(_label(x, "D493 allowed direction") for x in _sequence(allowed_directions, "D493 allowed directions", len(diff_model.DIRECTIONS))); self.require_accepted = _bool(require_accepted, "D493 acceptance requirement"); self.require_state_change = _bool(require_state_change, "D493 state-change requirement"); self.allow_unchanged = _bool(allow_unchanged, "D493 unchanged policy"); self.content_address = _address(content_address, "D493 policy address", POLICY_PREFIX); self._validate()
    def _validate(self) -> None:
        if not self.allowed_directions or len(set(self.allowed_directions)) != len(self.allowed_directions) or any(x not in diff_model.DIRECTIONS for x in self.allowed_directions): raise ValidationError("D493 directions are unsupported or duplicated")
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address: raise ValidationError("D493 policy address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D493 policy crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {f: getattr(self, f) for f in self.FIELDS[:-1]} | {"allowed_directions": list(self.allowed_directions), "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimePolicy":
        value = _mapping(value, "D493 policy"); _strict(value, set(cls.FIELDS), "D493 policy"); return cls(*(value[f] for f in cls.FIELDS))

def address_policy(value: RuntimePolicy) -> str:
    if not isinstance(value, RuntimePolicy): raise ValidationError("D493 addressing requires a typed policy")
    return _address_for(value, POLICY_PREFIX)

class RuntimeCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "D493 check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "D493 check ID"); self.passed = _bool(passed, "D493 check result")
        if severity not in SEVERITIES: raise ValidationError("D493 severity is unsupported")
        self.severity = severity; self.actual = _text(actual, "D493 actual", 32768); self.expected = _text(expected, "D493 expected", 32768); self.detail = _text(detail, "D493 detail", 4096); self.content_address = _address(content_address, "D493 check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or (self.passed and self.severity == "error") or (not self.passed and self.severity != "error"): raise ValidationError("D493 check identity/severity is invalid")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("D493 check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D493 check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {f: getattr(self, f) for f in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeCheck":
        value = _mapping(value, "D493 check"); _strict(value, set(cls.FIELDS), "D493 check"); return cls(*(value[f] for f in cls.FIELDS))

def address_check(value: RuntimeCheck) -> str:
    if not isinstance(value, RuntimeCheck): raise ValidationError("D493 addressing requires a typed check")
    return _address_for(value, CHECK_PREFIX)
def address_checks(value: Sequence[RuntimeCheck]) -> str:
    checks = tuple(value)
    if any(not isinstance(x, RuntimeCheck) for x in checks): raise ValidationError("D493 check addressing requires typed checks")
    return content_hash({"checks": [x.to_dict() for x in checks]}, prefix=CHECKS_PREFIX)

class RuntimeChecks:
    FIELDS = CHECKS_FIELDS
    def __init__(self, checks: Sequence[RuntimeCheck | Mapping[str, Any]], content_address: str) -> None:
        self.checks = tuple(x if isinstance(x, RuntimeCheck) else RuntimeCheck.from_mapping(_mapping(x, "D493 check")) for x in _sequence(checks, "D493 checks", MAX_CHECKS)); self.content_address = _address(content_address, "D493 checks address", CHECKS_PREFIX); self._validate()
    def _validate(self) -> None:
        if tuple(x.ordinal for x in self.checks) != tuple(range(1, len(self.checks) + 1)): raise ValidationError("D493 checks are not contiguous")
        if not self.content_address.startswith("pending:") and address_checks(self.checks) != self.content_address: raise ValidationError("D493 checks address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D493 checks cross the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"checks": [x.to_dict() for x in self.checks], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeChecks":
        value = _mapping(value, "D493 checks"); _strict(value, set(cls.FIELDS), "D493 checks"); return cls(value["checks"], value["content_address"])

class RuntimeManifest:
    FIELDS = MANIFEST_FIELDS
    def __init__(self, runtime_id: str, diff_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "D493 manifest runtime ID"); self.diff_id = _label(diff_id, "D493 manifest diff ID"); self.version = _text(version, "D493 manifest version", 1024); self.boundary = _text(boundary, "D493 manifest boundary", 2048); self.files = tuple(_text(x, "D493 filename", 128) for x in _sequence(files, "D493 files", len(FILES))); self.artifact_addresses = tuple(_address(x, "D493 artifact address") for x in _sequence(artifact_addresses, "D493 artifact addresses", len(ARTIFACT_FILES))); self.content_address = _address(content_address, "D493 manifest address", MANIFEST_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or (self.version, self.boundary) != (VERSION, BOUNDARY): raise ValidationError("D493 manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address: raise ValidationError("D493 manifest address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D493 manifest crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {f: list(getattr(self, f)) if f in ("files", "artifact_addresses") else getattr(self, f) for f in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeManifest":
        value = _mapping(value, "D493 manifest"); _strict(value, set(cls.FIELDS), "D493 manifest"); return cls(*(value[f] for f in cls.FIELDS))

def address_manifest(value: RuntimeManifest) -> str:
    if not isinstance(value, RuntimeManifest): raise ValidationError("D493 addressing requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)

class RuntimeSummary:
    FIELDS = SUMMARY_FIELDS
    def __init__(self, runtime_id: str, diff_id: str, diff_address: str, policy_address: str, check_count: int, passed_count: int, failed_count: int, release_ready: bool, state: str, direction: str, state_transition: str, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "D493 summary runtime ID"); self.diff_id = _label(diff_id, "D493 summary diff ID"); self.diff_address = _address(diff_address, "D493 summary diff address", diff_model.DIFF_PREFIX); self.policy_address = _address(policy_address, "D493 summary policy address", POLICY_PREFIX); self.check_count = _count(check_count, "D493 summary check count", MAX_CHECKS); self.passed_count = _count(passed_count, "D493 summary passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "D493 summary failed count", MAX_CHECKS); self.release_ready = _bool(release_ready, "D493 summary readiness")
        if state not in STATES or direction not in diff_model.DIRECTIONS: raise ValidationError("D493 state or direction is unsupported")
        self.state = state; self.direction = direction; self.state_transition = _text(state_transition, "D493 summary transition", 128); self.item_count = _count(item_count, "D493 summary item count", diff_model.MAX_ITEMS); self.added_count = _count(added_count, "D493 summary added", diff_model.MAX_ITEMS); self.removed_count = _count(removed_count, "D493 summary removed", diff_model.MAX_ITEMS); self.changed_count = _count(changed_count, "D493 summary changed", diff_model.MAX_ITEMS); self.unchanged_count = _count(unchanged_count, "D493 summary unchanged", diff_model.MAX_ITEMS); self.accepted = _bool(accepted, "D493 summary acceptance"); self.content_address = _address(content_address, "D493 summary address", SUMMARY_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.passed_count + self.failed_count != self.check_count or self.release_ready != (self.state == "ready") or self.added_count + self.removed_count + self.changed_count + self.unchanged_count != self.item_count: raise ValidationError("D493 summary counters or disposition do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address: raise ValidationError("D493 summary address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D493 summary crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {f: getattr(self, f) for f in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeSummary":
        value = _mapping(value, "D493 summary"); _strict(value, set(cls.FIELDS), "D493 summary"); return cls(*(value[f] for f in cls.FIELDS))

def address_summary(value: RuntimeSummary) -> str:
    if not isinstance(value, RuntimeSummary): raise ValidationError("D493 addressing requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)

class HistoryDiffRuntime:
    FIELDS = RUNTIME_FIELDS
    def __init__(self, runtime_id: str, diff_id: str, diff_address: str, version: str, boundary: str, policy: Mapping[str, Any] | RuntimePolicy, checks: Sequence[RuntimeCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, release_ready: bool, state: str, direction: str, state_transition: str, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, accepted: bool, manifest: Mapping[str, Any] | RuntimeManifest, summary: Mapping[str, Any] | RuntimeSummary, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "D493 runtime ID"); self.diff_id = _label(diff_id, "D493 diff ID"); self.diff_address = _address(diff_address, "D493 diff address", diff_model.DIFF_PREFIX); self.version = _text(version, "D493 version", 1024); self.boundary = _text(boundary, "D493 boundary", 2048); self.policy = policy if isinstance(policy, RuntimePolicy) else RuntimePolicy.from_mapping(_mapping(policy, "D493 policy")); self.checks = tuple(x if isinstance(x, RuntimeCheck) else RuntimeCheck.from_mapping(_mapping(x, "D493 check")) for x in _sequence(checks, "D493 checks", MAX_CHECKS)); self.check_count = _count(check_count, "D493 check count", MAX_CHECKS); self.passed_count = _count(passed_count, "D493 passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "D493 failed count", MAX_CHECKS); self.release_ready = _bool(release_ready, "D493 readiness")
        if state not in STATES or direction not in diff_model.DIRECTIONS: raise ValidationError("D493 state or direction is unsupported")
        self.state = state; self.direction = direction; self.state_transition = _text(state_transition, "D493 transition", 128); self.item_count = _count(item_count, "D493 item count", diff_model.MAX_ITEMS); self.added_count = _count(added_count, "D493 added count", diff_model.MAX_ITEMS); self.removed_count = _count(removed_count, "D493 removed count", diff_model.MAX_ITEMS); self.changed_count = _count(changed_count, "D493 changed count", diff_model.MAX_ITEMS); self.unchanged_count = _count(unchanged_count, "D493 unchanged count", diff_model.MAX_ITEMS); self.accepted = _bool(accepted, "D493 acceptance"); self.manifest = manifest if isinstance(manifest, RuntimeManifest) else RuntimeManifest.from_mapping(_mapping(manifest, "D493 manifest")); self.summary = summary if isinstance(summary, RuntimeSummary) else RuntimeSummary.from_mapping(_mapping(summary, "D493 summary")); self.content_address = _address(content_address, "D493 runtime address", RUNTIME_PREFIX); self._validate()
    def _validate(self) -> None:
        if (self.version, self.boundary) != (VERSION, BOUNDARY) or self.policy.diff_id != self.diff_id or self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(x.passed for x in self.checks) or self.release_ready != (self.state == "ready") or sum((self.added_count, self.removed_count, self.changed_count, self.unchanged_count)) != self.item_count: raise ValidationError("D493 runtime identity or counters do not replay")
        if tuple(x.ordinal for x in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(x.check_id for x in self.checks) != CHECK_IDS: raise ValidationError("D493 checks are not canonical")
        expected = (self.runtime_id, self.diff_id, self.diff_address, self.policy.content_address, self.check_count, self.passed_count, self.failed_count, self.release_ready, self.state, self.direction, self.state_transition, self.item_count, self.added_count, self.removed_count, self.changed_count, self.unchanged_count, self.accepted)
        if tuple(getattr(self.summary, f) for f in SUMMARY_FIELDS[:-1]) != expected or address_summary(self.summary) != self.summary.content_address: raise ValidationError("D493 summary does not replay")
        expected_manifest = (self.runtime_id, self.diff_id, VERSION, BOUNDARY, FILES, (address_checks(self.checks), self.summary.content_address)); actual = (self.manifest.runtime_id, self.manifest.diff_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual != expected_manifest or address_manifest(self.manifest) != self.manifest.content_address: raise ValidationError("D493 manifest does not replay")
        if self.release_ready != (all(x.passed for x in self.checks) and self.accepted): raise ValidationError("D493 readiness does not follow the full gate result")
        if not self.content_address.startswith("pending:") and address_runtime(self) != self.content_address: raise ValidationError("D493 runtime address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D493 runtime crosses the public boundary")
    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "diff_id": self.diff_id, "diff_address": self.diff_address, "version": self.version, "boundary": self.boundary, "policy": self.policy.to_dict(), "checks": [x.to_dict() for x in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "release_ready": self.release_ready, "state": self.state, "direction": self.direction, "state_transition": self.state_transition, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryDiffRuntime":
        value = _mapping(value, "D493 runtime"); _strict(value, set(cls.FIELDS), "D493 runtime"); return cls(*(value[f] for f in cls.FIELDS))

def address_runtime(value: HistoryDiffRuntime) -> str:
    if not isinstance(value, HistoryDiffRuntime): raise ValidationError("D493 addressing requires a typed runtime")
    return _address_for(value, RUNTIME_PREFIX)

def build_policy(policy_id: str, diff_id: str, *, minimum_items: int = 1, maximum_added: int = diff_model.MAX_ITEMS, maximum_removed: int = 0, maximum_changed: int = 0, allowed_directions: Sequence[str] = ("improved", "changed", "unchanged"), require_accepted: bool = True, require_state_change: bool = False, allow_unchanged: bool = True) -> RuntimePolicy:
    return _seal(RuntimePolicy(policy_id, diff_id, minimum_items, maximum_added, maximum_removed, maximum_changed, allowed_directions, require_accepted, require_state_change, allow_unchanged, f"pending:{POLICY_PREFIX}"), address_policy)

def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> RuntimeCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "severity": "info" if passed else "error", "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = RuntimeCheck(**body); return RuntimeCheck(**(body | {"content_address": address_check(provisional)}))

def build_runtime(diff: diff_model.HistoryDiff, *, runtime_id: str = DEFAULT_RUNTIME_ID, policy: RuntimePolicy | Mapping[str, Any] | None = None) -> HistoryDiffRuntime:
    diff_model.verify_diff(diff); selected = policy if isinstance(policy, RuntimePolicy) else RuntimePolicy.from_mapping(_mapping(policy, "D493 policy")) if policy is not None else build_policy(f"{runtime_id}-policy", diff.diff_id)
    same_state = diff.state_transition.split("->", 1)[0] == diff.state_transition.split("->", 1)[-1]
    checks = (
        _check(1, "diff_present", bool(diff.diff_id and diff.content_address), (diff.diff_id, bool(diff.content_address)), "diff identity and address", "a comparison must be present"),
        _check(2, "diff_accepted", (not selected.require_accepted) or diff.accepted, diff.accepted, True, "source comparison acceptance follows policy"),
        _check(3, "minimum_items", diff.item_count >= selected.minimum_items, diff.item_count, selected.minimum_items, "comparison item count meets the floor"),
        _check(4, "added_budget", diff.added_count <= selected.maximum_added, diff.added_count, selected.maximum_added, "added snapshots remain within budget"),
        _check(5, "removed_budget", diff.removed_count <= selected.maximum_removed, diff.removed_count, selected.maximum_removed, "removed snapshots remain within budget"),
        _check(6, "changed_budget", diff.changed_count <= selected.maximum_changed, diff.changed_count, selected.maximum_changed, "changed snapshots remain within budget"),
        _check(7, "direction_policy", diff.direction in selected.allowed_directions, diff.direction, selected.allowed_directions, "comparison direction is allowed"),
        _check(8, "state_transition", (not selected.require_state_change) or not same_state, diff.state_transition, "different latest states", "policy may require a state change"),
        _check(9, "unchanged_policy", selected.allow_unchanged or diff.unchanged_count == 0, diff.unchanged_count, 0, "unchanged snapshots follow policy"),
        _check(10, "comparison_conservation", diff.added_count + diff.removed_count + diff.changed_count + diff.unchanged_count == diff.item_count, diff.item_count, "sum of change classes", "comparison classes conserve aligned items"),
        _check(11, "identity_link", selected.diff_id == diff.diff_id and diff.summary.diff_id == diff.diff_id, (selected.diff_id, diff.diff_id), "matching diff IDs", "policy and summary link to the evaluated diff"),
        _check(12, "address_integrity", diff.summary.left_history_address == diff.left_history_address and diff.summary.right_history_address == diff.right_history_address, True, "both source history addresses retained", "comparison lineage must remain intact"),
        _check(13, "policy_integrity", address_policy(selected) == selected.content_address, selected.content_address, address_policy(selected), "policy address replays"),
        _check(14, "release_disposition", False, "pending", "all preceding checks", "release readiness is the conjunction of checks"),
        _check(15, "public_boundary", _public(diff.to_dict()) and _public(selected.to_dict()), True, "public value", "runtime inputs remain value-only"),
    )
    disposition = all(x.passed for x in checks[:13]); checks = checks[:13] + (_check(14, "release_disposition", disposition, disposition, True, "release readiness is the conjunction of policy checks"), checks[14])
    passed = sum(x.passed for x in checks); failed = MAX_CHECKS - passed; ready = all(x.passed for x in checks) and diff.accepted; state = "ready" if ready else "blocked"
    summary = _seal(RuntimeSummary(runtime_id, diff.diff_id, diff.content_address, selected.content_address, MAX_CHECKS, passed, failed, ready, state, diff.direction, diff.state_transition, diff.item_count, diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count, diff.accepted, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(RuntimeManifest(runtime_id, diff.diff_id, VERSION, BOUNDARY, FILES, (address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(HistoryDiffRuntime(runtime_id, diff.diff_id, diff.content_address, VERSION, BOUNDARY, selected, checks, MAX_CHECKS, passed, failed, ready, state, diff.direction, diff.state_transition, diff.item_count, diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count, diff.accepted, manifest, summary, f"pending:{RUNTIME_PREFIX}"), address_runtime)

def verify_runtime(value: HistoryDiffRuntime, diff: diff_model.HistoryDiff | None = None) -> HistoryDiffRuntime:
    if not isinstance(value, HistoryDiffRuntime): raise ValidationError("D493 verification requires a typed runtime")
    value._validate()
    if diff is not None and (diff_model.verify_diff(diff).content_address != value.diff_address or diff.diff_id != value.diff_id): raise ValidationError("D493 runtime does not link to the supplied comparison")
    return value
def runtime_from_mapping(value: Mapping[str, Any], diff: diff_model.HistoryDiff | None = None) -> HistoryDiffRuntime: return verify_runtime(HistoryDiffRuntime.from_mapping(value), diff)
def runtime_json(value: HistoryDiffRuntime) -> str: return canonical_json(verify_runtime(value).to_dict())
def checks_json(value: HistoryDiffRuntime) -> str:
    value = verify_runtime(value); return canonical_json({"checks": [x.to_dict() for x in value.checks], "content_address": address_checks(value.checks)})
def summary_json(value: HistoryDiffRuntime) -> str: return canonical_json(verify_runtime(value).summary.to_dict())
def manifest_json(value: HistoryDiffRuntime) -> str: return canonical_json(verify_runtime(value).manifest.to_dict())
def runtime_csv(value: HistoryDiffRuntime) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(x.to_dict() for x in verify_runtime(value).checks); return output.getvalue()
def render_runtime_markdown(value: HistoryDiffRuntime) -> str:
    value = verify_runtime(value); lines = [f"# D493 runtime {value.runtime_id}", "", f"- State: {value.state}", f"- Release ready: {str(value.release_ready).lower()}", f"- Direction: {value.direction}", f"- Transition: {value.state_transition}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Passed | Severity | Detail |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {x.check_id} | {str(x.passed).lower()} | {x.severity} | {x.detail} |" for x in value.checks); return "\n".join(lines) + "\n"
def _write(path: Path, value: Mapping[str, Any]) -> None: path.write_text(canonical_json(value), encoding="utf-8", newline="\n")
def persist_runtime(value: HistoryDiffRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_runtime(value); destination = Path(destination); _validate_parent(destination.parent, "D493 destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)): raise ValidationError("D493 destination exists or is not a regular directory")
    destination.parent.mkdir(parents=True, exist_ok=True); temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-d493-runtime-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "runtime.json": value.to_dict(), "checks.json": {"checks": [x.to_dict() for x in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES: _write(temporary / name, documents[name])
        if destination.exists(): shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True); raise ValidationError("D493 destination could not be written") from error
    return destination
def _read_json(path: Path) -> Mapping[str, Any]:
    try: value = _strict_json_loads(read_text(path, field="D493 artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error: raise ValidationError("D493 artifact is not valid JSON") from error
    return _mapping(value, "D493 artifact")
def load_runtime(destination: str | Path, diff: diff_model.HistoryDiff | None = None) -> HistoryDiffRuntime:
    destination = Path(destination); _validate_parent(destination.parent, "D493 input")
    if not destination.is_dir() or destination.is_symlink(): raise ValidationError("D493 source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(x.name for x in children)) != tuple(sorted(FILES)) or any(x.is_symlink() or not x.is_file() for x in children): raise ValidationError("D493 directory must contain the exact regular artifact set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        raw = canonical_json(document)
        if read_text(destination / name, field="D493 artifact") != raw or len(raw.encode("utf-8")) > MAX_RUNTIME_BYTES: raise ValidationError("D493 artifact is noncanonical or exceeds its size bound")
    value = runtime_from_mapping(documents["runtime.json"], diff); expected = {"manifest.json": value.manifest.to_dict(), "checks.json": {"checks": [x.to_dict() for x in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()): raise ValidationError("D493 components do not replay runtime.json")
    return value
def run_runtime(diff: diff_model.HistoryDiff, *, runtime_id: str = DEFAULT_RUNTIME_ID, policy: RuntimePolicy | Mapping[str, Any] | None = None, destination: str | Path | None = None, overwrite: bool = False) -> HistoryDiffRuntime:
    value = build_runtime(diff, runtime_id=runtime_id, policy=policy)
    if destination is not None: persist_runtime(value, destination, overwrite=overwrite)
    return value
def policy_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimePolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {f: {"type": "array" if f == "allowed_directions" else "integer" if f.startswith("minimum") or f.startswith("maximum") else "boolean" if f.startswith("require") or f.startswith("allow") else "string"} for f in POLICY_FIELDS}}
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {f: {"type": "integer" if f == "ordinal" else "boolean" if f == "passed" else "string"} for f in CHECK_FIELDS}}
def checks_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeChecks", "type": "object", "additionalProperties": False, "required": list(CHECKS_FIELDS), "properties": {"checks": {"type": "array", "items": {"$ref": "#/$defs/check"}}, "content_address": {"type": "string"}}, "$defs": {"check": check_schema()}}
def manifest_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {f: {"type": "array" if f in ("files", "artifact_addresses") else "string"} for f in MANIFEST_FIELDS}}
def summary_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {f: {"type": "integer" if f.endswith("count") else "boolean" if f in ("release_ready", "accepted") else "string"} for f in SUMMARY_FIELDS}}
def runtime_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {f: {"type": "array" if f == "checks" else "object" if f in ("policy", "manifest", "summary") else "integer" if f.endswith("count") else "boolean" if f in ("release_ready", "accepted") else "string"} for f in RUNTIME_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("strict/release policy controls", "added removed and changed budgets", "direction transition acceptance and unchanged controls", "deterministic ready/blocked decisions", "exact four-file persistence", "canonical reload and tamper rejection"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}

__all__ = ["VERSION", "BOUNDARY", "RUNTIME_PREFIX", "POLICY_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_RUNTIME_ID", "FILES", "ARTIFACT_FILES", "STATES", "SEVERITIES", "MAX_CHECKS", "MAX_RUNTIME_BYTES", "POLICY_FIELDS", "CHECK_FIELDS", "CHECKS_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "RUNTIME_FIELDS", "CHECK_IDS", "RuntimePolicy", "RuntimeCheck", "RuntimeChecks", "RuntimeManifest", "RuntimeSummary", "HistoryDiffRuntime", "address_policy", "address_check", "address_checks", "address_manifest", "address_summary", "address_runtime", "build_policy", "build_runtime", "verify_runtime", "runtime_from_mapping", "runtime_json", "checks_json", "summary_json", "manifest_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime", "policy_schema", "check_schema", "checks_schema", "manifest_schema", "summary_schema", "runtime_schema", "capabilities"]
