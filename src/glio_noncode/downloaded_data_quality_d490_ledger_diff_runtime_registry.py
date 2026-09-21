"""Policy-controlled registry for D489 ledger-diff runtimes."""

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

from . import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime as runtime_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = runtime_model.VERSION + "-registry-v1"
BOUNDARY = runtime_model.BOUNDARY + "_registry"
REGISTRY_PREFIX = "glio-noncode-d490-ledger-diff-runtime-registry"
POLICY_PREFIX = REGISTRY_PREFIX + "-policy"
ENTRY_PREFIX = REGISTRY_PREFIX + "-entry"
ENTRIES_PREFIX = REGISTRY_PREFIX + "-entries"
CHECK_PREFIX = REGISTRY_PREFIX + "-check"
CHECKS_PREFIX = REGISTRY_PREFIX + "-checks"
MANIFEST_PREFIX = REGISTRY_PREFIX + "-manifest"
SUMMARY_PREFIX = REGISTRY_PREFIX + "-summary"
DEFAULT_REGISTRY_ID = REGISTRY_PREFIX
FILES = ("manifest.json", "registry.json", "policy.json", "entries.json", "checks.json", "summary.json")
ARTIFACT_FILES = ("policy.json", "entries.json", "checks.json", "summary.json")
STATES = ("empty", "ready", "blocked")
SEVERITIES = ("info", "error")
MAX_ENTRIES = 128
MAX_CHECKS = 16
MAX_REGISTRY_BYTES = 32 * 1024 * 1024
POLICY_FIELDS = ("policy_id", "minimum_runtimes", "minimum_ready", "maximum_blocked", "require_same_diff", "require_same_direction", "require_audited", "require_release_ready", "content_address")
ENTRY_FIELDS = ("ordinal", "runtime_id", "runtime_address", "diff_id", "diff_address", "policy_address", "audit_address", "direction", "state", "release_ready", "accepted", "check_count", "passed_count", "failed_count", "item_count", "content_address")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "severity", "actual", "expected", "detail", "content_address")
MANIFEST_FIELDS = ("registry_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("registry_id", "diff_id", "direction", "entry_count", "ready_count", "blocked_count", "audited_count", "accepted_count", "accepted", "release_ready", "state", "content_address")
REGISTRY_FIELDS = ("registry_id", "version", "boundary", "policy", "entry_count", "ready_count", "blocked_count", "audited_count", "accepted_count", "accepted", "release_ready", "state", "diff_id", "direction", "manifest", "summary", "entries", "checks", "content_address")
CHECK_IDS = ("nonempty", "minimum_runtimes", "minimum_ready", "blocked_budget", "state_consistency", "release_ready_policy", "runtime_acceptance", "same_diff", "same_direction", "unique_runtime_ids", "unique_runtime_addresses", "audit_evidence", "entry_addresses", "counter_conservation", "policy_integrity", "public_boundary")


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
    return runtime_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class RegistryPolicy:
    FIELDS = POLICY_FIELDS

    def __init__(self, policy_id: str, minimum_runtimes: int, minimum_ready: int, maximum_blocked: int, require_same_diff: bool, require_same_direction: bool, require_audited: bool, require_release_ready: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "ledger diff runtime registry policy ID")
        self.minimum_runtimes = _count(minimum_runtimes, "ledger diff runtime registry minimum runtimes", MAX_ENTRIES, lower=1)
        self.minimum_ready = _count(minimum_ready, "ledger diff runtime registry minimum ready", MAX_ENTRIES, lower=1)
        self.maximum_blocked = _count(maximum_blocked, "ledger diff runtime registry maximum blocked", MAX_ENTRIES)
        self.require_same_diff = _bool(require_same_diff, "ledger diff runtime registry same-diff requirement")
        self.require_same_direction = _bool(require_same_direction, "ledger diff runtime registry same-direction requirement")
        self.require_audited = _bool(require_audited, "ledger diff runtime registry audit requirement")
        self.require_release_ready = _bool(require_release_ready, "ledger diff runtime registry release-readiness requirement")
        self.content_address = _address(content_address, "ledger diff runtime registry policy address", POLICY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.minimum_ready > self.minimum_runtimes:
            raise ValidationError("ledger diff runtime registry policy thresholds are inconsistent")
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry policy address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryPolicy":
        value = _mapping(value, "ledger diff runtime registry policy")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: RegistryPolicy) -> str:
    if not isinstance(value, RegistryPolicy):
        raise ValidationError("ledger diff runtime registry policy address requires a typed policy")
    return _address_for(value, POLICY_PREFIX)


class RegistryEntry:
    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, runtime_id: str, runtime_address: str, diff_id: str, diff_address: str, policy_address: str, audit_address: str, direction: str, state: str, release_ready: bool, accepted: bool, check_count: int, passed_count: int, failed_count: int, item_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff runtime registry entry ordinal", MAX_ENTRIES, lower=1)
        self.runtime_id = _label(runtime_id, "ledger diff runtime registry runtime ID")
        self.runtime_address = _address(runtime_address, "ledger diff runtime registry runtime address", runtime_model.RUNTIME_PREFIX)
        self.diff_id = _label(diff_id, "ledger diff runtime registry diff ID")
        self.diff_address = _address(diff_address, "ledger diff runtime registry diff address", runtime_model.diff_model.DIFF_PREFIX)
        self.policy_address = _address(policy_address, "ledger diff runtime registry runtime policy address", runtime_model.POLICY_PREFIX)
        self.audit_address = _address(audit_address, "ledger diff runtime registry runtime audit address", required=False)
        if direction not in runtime_model.diff_model.DIRECTIONS:
            raise ValidationError("ledger diff runtime registry entry direction is unsupported")
        if state not in runtime_model.STATES:
            raise ValidationError("ledger diff runtime registry entry state is unsupported")
        self.direction = direction
        self.state = state
        self.release_ready = _bool(release_ready, "ledger diff runtime registry entry readiness")
        self.accepted = _bool(accepted, "ledger diff runtime registry entry acceptance")
        self.check_count = _count(check_count, "ledger diff runtime registry entry check count", runtime_model.MAX_CHECKS)
        self.passed_count = _count(passed_count, "ledger diff runtime registry entry passed count", runtime_model.MAX_CHECKS)
        self.failed_count = _count(failed_count, "ledger diff runtime registry entry failed count", runtime_model.MAX_CHECKS)
        self.item_count = _count(item_count, "ledger diff runtime registry entry item count", runtime_model.diff_model.MAX_ITEMS)
        self.content_address = _address(content_address, "ledger diff runtime registry entry address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.release_ready != (self.state == "ready") or self.passed_count + self.failed_count != self.check_count or self.passed_count > self.check_count:
            raise ValidationError("ledger diff runtime registry entry disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, ENTRY_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry entry address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryEntry":
        value = _mapping(value, "ledger diff runtime registry entry")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: RegistryEntry) -> str:
    if not isinstance(value, RegistryEntry):
        raise ValidationError("ledger diff runtime registry entry address requires a typed entry")
    return _address_for(value, ENTRY_PREFIX)


def address_entries(value: Sequence[RegistryEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, RegistryEntry) for item in typed):
        raise ValidationError("ledger diff runtime registry entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class RegistryCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff runtime registry check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "ledger diff runtime registry check ID")
        self.passed = _bool(passed, "ledger diff runtime registry check result")
        if severity not in SEVERITIES:
            raise ValidationError("ledger diff runtime registry check severity is unsupported")
        self.severity = severity
        self.actual = _text(actual, "ledger diff runtime registry check actual", 32768)
        self.expected = _text(expected, "ledger diff runtime registry check expected", 32768)
        self.detail = _text(detail, "ledger diff runtime registry check detail", 4096)
        self.content_address = _address(content_address, "ledger diff runtime registry check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or (self.passed and self.severity == "error"):
            raise ValidationError("ledger diff runtime registry check identity or severity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryCheck":
        value = _mapping(value, "ledger diff runtime registry check")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryCheck) -> str:
    if not isinstance(value, RegistryCheck):
        raise ValidationError("ledger diff runtime registry check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


def address_checks(value: Sequence[RegistryCheck]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, RegistryCheck) for item in typed):
        raise ValidationError("ledger diff runtime registry checks address requires typed checks")
    return content_hash({"checks": [item.to_dict() for item in typed]}, prefix=CHECKS_PREFIX)


class RegistryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.registry_id = _label(registry_id, "ledger diff runtime registry manifest ID")
        self.version = _text(version, "ledger diff runtime registry manifest version", 1024)
        self.boundary = _text(boundary, "ledger diff runtime registry manifest boundary", 2048)
        self.files = tuple(_text(item, "ledger diff runtime registry manifest file", 128) for item in _sequence(files, "ledger diff runtime registry manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "ledger diff runtime registry manifest artifact address") for item in _sequence(artifact_addresses, "ledger diff runtime registry manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "ledger diff runtime registry manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger diff runtime registry manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryManifest":
        value = _mapping(value, "ledger diff runtime registry manifest")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: RegistryManifest) -> str:
    if not isinstance(value, RegistryManifest):
        raise ValidationError("ledger diff runtime registry manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class RegistrySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, registry_id: str, diff_id: str, direction: str, entry_count: int, ready_count: int, blocked_count: int, audited_count: int, accepted_count: int, accepted: bool, release_ready: bool, state: str, content_address: str) -> None:
        self.registry_id = _label(registry_id, "ledger diff runtime registry summary ID")
        self.diff_id = _label(diff_id, "ledger diff runtime registry summary diff ID", required=False)
        self.direction = _label(direction, "ledger diff runtime registry summary direction", required=False)
        self.entry_count = _count(entry_count, "ledger diff runtime registry summary entry count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "ledger diff runtime registry summary ready count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "ledger diff runtime registry summary blocked count", MAX_ENTRIES)
        self.audited_count = _count(audited_count, "ledger diff runtime registry summary audited count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "ledger diff runtime registry summary accepted count", MAX_ENTRIES)
        self.accepted = _bool(accepted, "ledger diff runtime registry summary acceptance")
        self.release_ready = _bool(release_ready, "ledger diff runtime registry summary readiness")
        if state not in STATES:
            raise ValidationError("ledger diff runtime registry summary state is unsupported")
        self.state = state
        self.content_address = _address(content_address, "ledger diff runtime registry summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.ready_count + self.blocked_count != self.entry_count or self.audited_count > self.entry_count or self.accepted_count > self.entry_count or self.release_ready != (self.state == "ready") or self.accepted != (self.entry_count > 0 and self.accepted_count == self.entry_count):
            raise ValidationError("ledger diff runtime registry summary disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistrySummary":
        value = _mapping(value, "ledger diff runtime registry summary")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: RegistrySummary) -> str:
    if not isinstance(value, RegistrySummary):
        raise ValidationError("ledger diff runtime registry summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class RuntimeRegistry:
    FIELDS = REGISTRY_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, policy: Mapping[str, Any] | RegistryPolicy, entry_count: int, ready_count: int, blocked_count: int, audited_count: int, accepted_count: int, accepted: bool, release_ready: bool, state: str, diff_id: str, direction: str, manifest: Mapping[str, Any] | RegistryManifest, summary: Mapping[str, Any] | RegistrySummary, entries: Sequence[RegistryEntry | Mapping[str, Any]], checks: Sequence[RegistryCheck | Mapping[str, Any]], content_address: str) -> None:
        self.registry_id = _label(registry_id, "ledger diff runtime registry ID")
        self.version = _text(version, "ledger diff runtime registry version", 1024)
        self.boundary = _text(boundary, "ledger diff runtime registry boundary", 2048)
        self.policy = policy if isinstance(policy, RegistryPolicy) else RegistryPolicy.from_mapping(_mapping(policy, "ledger diff runtime registry policy"))
        self.entry_count = _count(entry_count, "ledger diff runtime registry entry count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "ledger diff runtime registry ready count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "ledger diff runtime registry blocked count", MAX_ENTRIES)
        self.audited_count = _count(audited_count, "ledger diff runtime registry audited count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "ledger diff runtime registry accepted count", MAX_ENTRIES)
        self.accepted = _bool(accepted, "ledger diff runtime registry acceptance")
        self.release_ready = _bool(release_ready, "ledger diff runtime registry readiness")
        if state not in STATES:
            raise ValidationError("ledger diff runtime registry state is unsupported")
        self.state = state
        self.diff_id = _label(diff_id, "ledger diff runtime registry diff ID", required=False)
        self.direction = _label(direction, "ledger diff runtime registry direction", required=False)
        self.manifest = manifest if isinstance(manifest, RegistryManifest) else RegistryManifest.from_mapping(_mapping(manifest, "ledger diff runtime registry manifest"))
        self.summary = summary if isinstance(summary, RegistrySummary) else RegistrySummary.from_mapping(_mapping(summary, "ledger diff runtime registry summary"))
        self.entries = tuple(item if isinstance(item, RegistryEntry) else RegistryEntry.from_mapping(_mapping(item, "ledger diff runtime registry entry")) for item in _sequence(entries, "ledger diff runtime registry entries", MAX_ENTRIES))
        self.checks = tuple(item if isinstance(item, RegistryCheck) else RegistryCheck.from_mapping(_mapping(item, "ledger diff runtime registry check")) for item in _sequence(checks, "ledger diff runtime registry checks", MAX_CHECKS))
        self.content_address = _address(content_address, "ledger diff runtime registry address", REGISTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.entry_count != len(self.entries) or self.ready_count + self.blocked_count != self.entry_count or self.audited_count > self.entry_count or self.accepted_count > self.entry_count or self.accepted != (self.entry_count > 0 and self.accepted_count == self.entry_count) or self.release_ready != all(item.passed for item in self.checks) or self.release_ready != (self.state == "ready") or len(self.checks) != MAX_CHECKS or self.policy.minimum_runtimes > MAX_ENTRIES:
            raise ValidationError("ledger diff runtime registry disposition does not replay")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)) or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("ledger diff runtime registry order is not canonical")
        expected_summary = (self.registry_id, self.diff_id, self.direction, self.entry_count, self.ready_count, self.blocked_count, self.audited_count, self.accepted_count, self.accepted, self.release_ready, self.state)
        if tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1]) != expected_summary or self.summary.content_address != address_summary(self.summary):
            raise ValidationError("ledger diff runtime registry summary does not replay")
        expected_manifest = (self.registry_id, VERSION, BOUNDARY, FILES, (self.policy.content_address, address_entries(self.entries), address_checks(self.checks), self.summary.content_address))
        actual_manifest = (self.manifest.registry_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest):
            raise ValidationError("ledger diff runtime registry manifest does not replay")
        if self.policy.content_address != address_policy(self.policy):
            raise ValidationError("ledger diff runtime registry policy address does not replay")
        if not self.content_address.startswith("pending:") and address_registry(self) != self.content_address:
            raise ValidationError("ledger diff runtime registry address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "policy": self.policy.to_dict(), "entry_count": self.entry_count, "ready_count": self.ready_count, "blocked_count": self.blocked_count, "audited_count": self.audited_count, "accepted_count": self.accepted_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "diff_id": self.diff_id, "direction": self.direction, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "entries": [item.to_dict() for item in self.entries], "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeRegistry":
        value = _mapping(value, "ledger diff runtime registry")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_registry(value: RuntimeRegistry) -> str:
    if not isinstance(value, RuntimeRegistry):
        raise ValidationError("ledger diff runtime registry address requires a typed registry")
    return _address_for(value, REGISTRY_PREFIX)


def build_policy(policy_id: str, *, minimum_runtimes: int = 1, minimum_ready: int = 1, maximum_blocked: int = 0, require_same_diff: bool = True, require_same_direction: bool = True, require_audited: bool = False, require_release_ready: bool = True) -> RegistryPolicy:
    return _seal(RegistryPolicy(policy_id, minimum_runtimes, minimum_ready, maximum_blocked, require_same_diff, require_same_direction, require_audited, require_release_ready, f"pending:{POLICY_PREFIX}"), address_policy)


def _entry(value: runtime_model.LedgerDiffRuntime, ordinal: int, audit_address: str) -> RegistryEntry:
    runtime_model.verify_runtime(value)
    body = {"ordinal": ordinal, "runtime_id": value.runtime_id, "runtime_address": value.content_address, "diff_id": value.diff_id, "diff_address": value.diff_address, "policy_address": value.policy.content_address, "audit_address": audit_address, "direction": value.direction, "state": value.state, "release_ready": value.release_ready, "accepted": value.accepted, "check_count": value.check_count, "passed_count": value.passed_count, "failed_count": value.failed_count, "item_count": value.item_count, "content_address": f"pending:{ENTRY_PREFIX}"}
    provisional = RegistryEntry(**body)
    return RegistryEntry(**(body | {"content_address": address_entry(provisional)}))


def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> RegistryCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "severity": "info" if passed else "error", "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}
    provisional = RegistryCheck(**body)
    return RegistryCheck(**(body | {"content_address": address_check(provisional)}))


def build_registry(runtimes: Sequence[runtime_model.LedgerDiffRuntime], *, registry_id: str = DEFAULT_REGISTRY_ID, policy: RegistryPolicy | Mapping[str, Any] | None = None, audit_addresses: Mapping[str, str] | None = None) -> RuntimeRegistry:
    typed = tuple(runtimes)
    if len(typed) > MAX_ENTRIES or any(not isinstance(item, runtime_model.LedgerDiffRuntime) for item in typed):
        raise ValidationError("ledger diff runtime registry requires a bounded sequence of typed runtimes")
    for item in typed:
        runtime_model.verify_runtime(item)
    registry_policy = policy if isinstance(policy, RegistryPolicy) else RegistryPolicy.from_mapping(_mapping(policy, "ledger diff runtime registry policy")) if policy is not None else build_policy(f"{registry_id}-policy")
    evidence = dict(audit_addresses or {})
    entries = tuple(_entry(item, index, evidence.get(item.runtime_id, "")) for index, item in enumerate(typed, 1))
    ids = tuple(item.runtime_id for item in entries)
    addresses = tuple(item.runtime_address for item in entries)
    diff_ids = tuple(item.diff_id for item in entries)
    directions = tuple(item.direction for item in entries)
    ready_count = sum(item.state == "ready" for item in entries)
    blocked_count = sum(item.state == "blocked" for item in entries)
    audited_count = sum(bool(item.audit_address) for item in entries)
    accepted_count = sum(item.accepted for item in entries)
    same_diff = len(set(diff_ids)) <= 1
    same_direction = len(set(directions)) <= 1
    checks = (
        _check(1, "nonempty", bool(entries), len(entries), ">= 1", "a registry must carry at least one runtime"),
        _check(2, "minimum_runtimes", len(entries) >= registry_policy.minimum_runtimes, len(entries), registry_policy.minimum_runtimes, "runtime count must meet policy"),
        _check(3, "minimum_ready", ready_count >= registry_policy.minimum_ready, ready_count, registry_policy.minimum_ready, "ready count must meet policy"),
        _check(4, "blocked_budget", blocked_count <= registry_policy.maximum_blocked, blocked_count, registry_policy.maximum_blocked, "blocked count must remain within policy"),
        _check(5, "state_consistency", all(item.release_ready == (item.state == "ready") for item in entries), True, "ready/blocked", "entry state and readiness must agree"),
        _check(6, "release_ready_policy", (not registry_policy.require_release_ready) or all(item.release_ready for item in entries), [item.release_ready for item in entries], True, "policy may require all runtimes ready"),
        _check(7, "runtime_acceptance", all(item.accepted for item in entries), accepted_count, len(entries), "every runtime must be accepted"),
        _check(8, "same_diff", (not registry_policy.require_same_diff) or same_diff, diff_ids, "one diff ID", "runtime lineage must be consistent"),
        _check(9, "same_direction", (not registry_policy.require_same_direction) or same_direction, directions, "one direction", "runtime direction must be consistent"),
        _check(10, "unique_runtime_ids", len(set(ids)) == len(ids), ids, "unique runtime IDs", "runtime identity must not be duplicated"),
        _check(11, "unique_runtime_addresses", len(set(addresses)) == len(addresses), addresses, "unique runtime addresses", "runtime addresses must not be duplicated"),
        _check(12, "audit_evidence", (not registry_policy.require_audited) or audited_count == len(entries), audited_count, len(entries), "required audits must be linked"),
        _check(13, "entry_addresses", all(address_entry(item) == item.content_address for item in entries), True, "replayed entry addresses", "entry addresses must replay"),
        _check(14, "counter_conservation", ready_count + blocked_count == len(entries) and audited_count <= len(entries) and accepted_count <= len(entries), (ready_count, blocked_count, audited_count, accepted_count), len(entries), "aggregate counters must conserve entries"),
        _check(15, "policy_integrity", address_policy(registry_policy) == registry_policy.content_address, registry_policy.content_address, address_policy(registry_policy), "policy address must replay"),
        _check(16, "public_boundary", all(_public(item.to_dict()) for item in entries) and _public(registry_policy.to_dict()), True, "public value", "registry values must remain value-only"),
    )
    accepted = bool(entries) and accepted_count == len(entries)
    release_ready = bool(entries) and all(item.passed for item in checks)
    state = "ready" if release_ready else "blocked" if entries else "empty"
    diff_id = diff_ids[0] if diff_ids and same_diff else ""
    direction = directions[0] if directions and same_direction else ""
    summary = _seal(RegistrySummary(registry_id, diff_id, direction, len(entries), ready_count, blocked_count, audited_count, accepted_count, accepted, release_ready, state, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(RegistryManifest(registry_id, VERSION, BOUNDARY, FILES, (registry_policy.content_address, address_entries(entries), address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(RuntimeRegistry(registry_id, VERSION, BOUNDARY, registry_policy, len(entries), ready_count, blocked_count, audited_count, accepted_count, accepted, release_ready, state, diff_id, direction, manifest, summary, entries, checks, f"pending:{REGISTRY_PREFIX}"), address_registry)


def verify_registry(value: RuntimeRegistry) -> RuntimeRegistry:
    if not isinstance(value, RuntimeRegistry):
        raise ValidationError("ledger diff runtime registry verification requires a typed registry")
    value._validate()
    return value


def registry_from_mapping(value: Mapping[str, Any]) -> RuntimeRegistry:
    return RuntimeRegistry.from_mapping(value)


def registry_json(value: RuntimeRegistry) -> str:
    return canonical_json(verify_registry(value).to_dict())


def policy_json(value: RuntimeRegistry) -> str:
    return canonical_json(verify_registry(value).policy.to_dict())


def entries_json(value: RuntimeRegistry) -> str:
    value = verify_registry(value)
    return canonical_json({"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)})


def checks_json(value: RuntimeRegistry) -> str:
    value = verify_registry(value)
    return canonical_json({"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)})


def manifest_json(value: RuntimeRegistry) -> str:
    return canonical_json(verify_registry(value).manifest.to_dict())


def summary_json(value: RuntimeRegistry) -> str:
    return canonical_json(verify_registry(value).summary.to_dict())


def registry_csv(value: RuntimeRegistry) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ENTRY_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_registry(value).entries)
    return output.getvalue()


def render_registry_markdown(value: RuntimeRegistry) -> str:
    value = verify_registry(value)
    lines = [f"# Ledger diff runtime registry {value.registry_id}", "", f"- State: {value.state}", f"- Release ready: {str(value.release_ready).lower()}", f"- Entries: {value.entry_count}", f"- Ready: {value.ready_count}", f"- Blocked: {value.blocked_count}", "", "| Runtime | Direction | State | Accepted | Checks |", "| --- | --- | --- | --- | ---: |"]
    lines.extend(f"| {item.runtime_id} | {item.direction} | {item.state} | {str(item.accepted).lower()} | {item.passed_count}/{item.check_count} |" for item in value.entries)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_registry(value: RuntimeRegistry, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_registry(value)
    destination = Path(destination)
    _validate_parent(destination.parent, "ledger diff runtime registry destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("ledger diff runtime registry destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-ledger-diff-runtime-registry-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "registry.json": value.to_dict(), "policy.json": value.policy.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("ledger diff runtime registry destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = _strict_json_loads(read_text(path, field="ledger diff runtime registry artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("ledger diff runtime registry artifact is not valid JSON") from error
    return _mapping(value, "ledger diff runtime registry artifact")


def load_registry(destination: str | Path) -> RuntimeRegistry:
    destination = Path(destination)
    _validate_parent(destination.parent, "ledger diff runtime registry input")
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("ledger diff runtime registry source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("ledger diff runtime registry directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="ledger diff runtime registry artifact") != serialized or len(serialized.encode("utf-8")) > MAX_REGISTRY_BYTES:
            raise ValidationError("ledger diff runtime registry artifact is non-canonical or exceeds its size bound")
    value = registry_from_mapping(documents["registry.json"])
    expected = {"manifest.json": value.manifest.to_dict(), "policy.json": value.policy.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()):
        raise ValidationError("ledger diff runtime registry component documents do not replay registry.json")
    return verify_registry(value)


def run_registry(runtimes: Sequence[runtime_model.LedgerDiffRuntime], *, registry_id: str = DEFAULT_REGISTRY_ID, policy: RegistryPolicy | Mapping[str, Any] | None = None, audit_addresses: Mapping[str, str] | None = None, destination: str | Path | None = None, overwrite: bool = False) -> RuntimeRegistry:
    value = build_registry(runtimes, registry_id=registry_id, policy=policy, audit_addresses=audit_addresses)
    if destination is not None:
        persist_registry(value, destination, overwrite=overwrite)
    return value


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryPolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("runtimes") or field.endswith("ready") or field.endswith("blocked") else "boolean" if field.startswith("require_") else "string"} for field in POLICY_FIELDS}}


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryEntry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": "integer" if field in ("ordinal", "check_count", "passed_count", "failed_count", "item_count") else "boolean" if field in ("release_ready", "accepted") else "string"} for field in ENTRY_FIELDS}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistrySummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("accepted", "release_ready") else "string"} for field in SUMMARY_FIELDS}}


def registry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistry", "type": "object", "additionalProperties": False, "required": list(REGISTRY_FIELDS), "properties": {field: {"type": "array" if field in ("entries", "checks") else "object" if field in ("policy", "manifest", "summary") else "integer" if field.endswith("count") else "boolean" if field in ("accepted", "release_ready") else "string"} for field in REGISTRY_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "check_ids": CHECK_IDS, "states": STATES, "max_entries": MAX_ENTRIES, "max_checks": MAX_CHECKS, "features": ("multi-runtime D489 ledger diff admission", "minimum-ready and maximum-blocked policies", "same-diff and same-direction controls", "optional runtime audit evidence", "exact six-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "REGISTRY_PREFIX", "POLICY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_REGISTRY_ID", "FILES", "ARTIFACT_FILES", "STATES", "SEVERITIES", "MAX_ENTRIES", "MAX_CHECKS", "MAX_REGISTRY_BYTES", "POLICY_FIELDS", "ENTRY_FIELDS", "CHECK_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "REGISTRY_FIELDS", "CHECK_IDS", "RegistryPolicy", "RegistryEntry", "RegistryCheck", "RegistryManifest", "RegistrySummary", "RuntimeRegistry", "address_policy", "address_entry", "address_entries", "address_check", "address_checks", "address_manifest", "address_summary", "address_registry", "build_policy", "build_registry", "verify_registry", "registry_from_mapping", "registry_json", "policy_json", "entries_json", "checks_json", "manifest_json", "summary_json", "registry_csv", "render_registry_markdown", "persist_registry", "load_registry", "run_registry", "policy_schema", "entry_schema", "check_schema", "manifest_schema", "summary_schema", "registry_schema", "capabilities"]
