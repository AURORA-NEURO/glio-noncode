"""Policy-driven release batches over D476 history-diff runtimes.

This boundary turns independently evaluated runtimes into a bounded release
decision. It keeps every runtime address, policy address, optional audit
address, and disposition visible while making the aggregate decision replayable
from canonical JSON alone.
"""

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

from . import downloaded_data_quality_d476_history_diff_runtime as runtime_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = runtime_model.VERSION + "-release-batch-v1"
BOUNDARY = runtime_model.BOUNDARY + "_release_batch"
BATCH_PREFIX = "glio-noncode-d477-release-batch"
POLICY_PREFIX = BATCH_PREFIX + "-policy"
ITEM_PREFIX = BATCH_PREFIX + "-item"
ITEMS_PREFIX = BATCH_PREFIX + "-items"
CHECK_PREFIX = BATCH_PREFIX + "-check"
CHECKS_PREFIX = BATCH_PREFIX + "-checks"
MANIFEST_PREFIX = BATCH_PREFIX + "-manifest"
SUMMARY_PREFIX = BATCH_PREFIX + "-summary"
DEFAULT_BATCH_ID = BATCH_PREFIX
FILES = ("manifest.json", "batch.json", "policy.json", "items.json", "checks.json", "summary.json")
ARTIFACT_FILES = ("policy.json", "items.json", "checks.json", "summary.json")
STATES = ("empty", "ready", "blocked")
SEVERITIES = ("info", "error")
MAX_ITEMS = 128
MAX_CHECKS = 18
MAX_BATCH_BYTES = 32 * 1024 * 1024
POLICY_FIELDS = ("policy_id", "minimum_runtimes", "minimum_ready", "maximum_blocked", "require_same_diff", "require_audited", "require_release_ready", "allow_mixed_policies", "content_address")
ITEM_FIELDS = ("ordinal", "runtime_id", "runtime_address", "diff_id", "diff_address", "policy_address", "audit_address", "state", "release_ready", "accepted", "check_count", "passed_count", "failed_count", "item_count", "content_address")
ITEMS_FIELDS = ("items", "content_address")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "severity", "actual", "expected", "detail", "content_address")
CHECKS_FIELDS = ("checks", "content_address")
MANIFEST_FIELDS = ("batch_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("batch_id", "item_count", "ready_count", "blocked_count", "audited_count", "accepted_count", "accepted", "release_ready", "state", "content_address")
BATCH_FIELDS = ("batch_id", "version", "boundary", "policy", "item_count", "ready_count", "blocked_count", "audited_count", "accepted_count", "accepted", "release_ready", "state", "manifest", "summary", "items", "checks", "content_address")
CHECK_IDS = ("nonempty", "minimum_runtimes", "minimum_ready", "blocked_budget", "state_consistency", "release_ready_policy", "runtime_acceptance", "same_diff", "unique_runtime_ids", "unique_runtime_addresses", "item_address_integrity", "audit_evidence", "policy_consistency", "counter_conservation", "policy_integrity", "runtime_links", "manifest_integrity", "public_boundary")


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
    return runtime_model.diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class BatchPolicy:
    FIELDS = POLICY_FIELDS

    def __init__(self, policy_id: str, minimum_runtimes: int, minimum_ready: int, maximum_blocked: int, require_same_diff: bool, require_audited: bool, require_release_ready: bool, allow_mixed_policies: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "release batch policy ID")
        self.minimum_runtimes = _count(minimum_runtimes, "release batch minimum runtimes", MAX_ITEMS, lower=1)
        self.minimum_ready = _count(minimum_ready, "release batch minimum ready runtimes", MAX_ITEMS, lower=1)
        self.maximum_blocked = _count(maximum_blocked, "release batch maximum blocked runtimes", MAX_ITEMS)
        self.require_same_diff = _bool(require_same_diff, "release batch same-diff requirement")
        self.require_audited = _bool(require_audited, "release batch audit requirement")
        self.require_release_ready = _bool(require_release_ready, "release batch release-readiness requirement")
        self.allow_mixed_policies = _bool(allow_mixed_policies, "release batch mixed-policy control")
        self.content_address = _address(content_address, "release batch policy address", POLICY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.minimum_ready > self.minimum_runtimes or self.maximum_blocked > MAX_ITEMS:
            raise ValidationError("release batch policy thresholds are inconsistent")
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address:
            raise ValidationError("release batch policy address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchPolicy":
        value = _mapping(value, "release batch policy")
        _strict(value, set(cls.FIELDS), "release batch policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: BatchPolicy) -> str:
    if not isinstance(value, BatchPolicy):
        raise ValidationError("release batch policy address requires a typed policy")
    return _address_for(value, POLICY_PREFIX)


class BatchItem:
    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, runtime_id: str, runtime_address: str, diff_id: str, diff_address: str, policy_address: str, audit_address: str, state: str, release_ready: bool, accepted: bool, check_count: int, passed_count: int, failed_count: int, item_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release batch item ordinal", MAX_ITEMS, lower=1)
        self.runtime_id = _label(runtime_id, "release batch runtime ID")
        self.runtime_address = _address(runtime_address, "release batch runtime address", runtime_model.RUNTIME_PREFIX)
        self.diff_id = _label(diff_id, "release batch diff ID")
        self.diff_address = _address(diff_address, "release batch diff address", runtime_model.diff_model.DIFF_PREFIX)
        self.policy_address = _address(policy_address, "release batch runtime policy address", runtime_model.POLICY_PREFIX)
        self.audit_address = _address(audit_address, "release batch runtime audit address", required=False)
        if state not in runtime_model.STATES:
            raise ValidationError("release batch item state is unsupported")
        self.state = state
        self.release_ready = _bool(release_ready, "release batch item readiness")
        self.accepted = _bool(accepted, "release batch item acceptance")
        self.check_count = _count(check_count, "release batch item check count", runtime_model.MAX_CHECKS)
        self.passed_count = _count(passed_count, "release batch item passed count", runtime_model.MAX_CHECKS)
        self.failed_count = _count(failed_count, "release batch item failed count", runtime_model.MAX_CHECKS)
        self.item_count = _count(item_count, "release batch item comparison count", runtime_model.diff_model.MAX_ITEMS)
        self.content_address = _address(content_address, "release batch item address", ITEM_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.release_ready != (self.state == "ready") or self.passed_count + self.failed_count != self.check_count or self.passed_count > self.check_count:
            raise ValidationError("release batch item disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, ITEM_PREFIX) != self.content_address:
            raise ValidationError("release batch item address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchItem":
        value = _mapping(value, "release batch item")
        _strict(value, set(cls.FIELDS), "release batch item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: BatchItem) -> str:
    if not isinstance(value, BatchItem):
        raise ValidationError("release batch item address requires a typed item")
    return _address_for(value, ITEM_PREFIX)


def address_items(value: Sequence[BatchItem]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, BatchItem) for item in typed):
        raise ValidationError("release batch items address requires typed items")
    return content_hash({"items": [item.to_dict() for item in typed]}, prefix=ITEMS_PREFIX)


class BatchCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release batch check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "release batch check ID")
        self.passed = _bool(passed, "release batch check result")
        if severity not in SEVERITIES:
            raise ValidationError("release batch check severity is unsupported")
        self.severity = severity
        self.actual = _text(actual, "release batch check actual", 32768)
        self.expected = _text(expected, "release batch check expected", 32768)
        self.detail = _text(detail, "release batch check detail", 4096)
        self.content_address = _address(content_address, "release batch check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or (self.passed and self.severity == "error"):
            raise ValidationError("release batch check identity or severity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("release batch check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchCheck":
        value = _mapping(value, "release batch check")
        _strict(value, set(cls.FIELDS), "release batch check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: BatchCheck) -> str:
    if not isinstance(value, BatchCheck):
        raise ValidationError("release batch check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


def address_checks(value: Sequence[BatchCheck]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, BatchCheck) for item in typed):
        raise ValidationError("release batch checks address requires typed checks")
    return content_hash({"checks": [item.to_dict() for item in typed]}, prefix=CHECKS_PREFIX)


class BatchManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, batch_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.batch_id = _label(batch_id, "release batch manifest batch ID")
        self.version = _text(version, "release batch manifest version", 1024)
        self.boundary = _text(boundary, "release batch manifest boundary", 2048)
        self.files = tuple(_text(item, "release batch manifest file", 128) for item in _sequence(files, "release batch manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "release batch manifest artifact address") for item in _sequence(artifact_addresses, "release batch manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "release batch manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("release batch manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("release batch manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchManifest":
        value = _mapping(value, "release batch manifest")
        _strict(value, set(cls.FIELDS), "release batch manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: BatchManifest) -> str:
    if not isinstance(value, BatchManifest):
        raise ValidationError("release batch manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class BatchSummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, batch_id: str, item_count: int, ready_count: int, blocked_count: int, audited_count: int, accepted_count: int, accepted: bool, release_ready: bool, state: str, content_address: str) -> None:
        self.batch_id = _label(batch_id, "release batch summary batch ID")
        self.item_count = _count(item_count, "release batch summary item count", MAX_ITEMS)
        self.ready_count = _count(ready_count, "release batch summary ready count", MAX_ITEMS)
        self.blocked_count = _count(blocked_count, "release batch summary blocked count", MAX_ITEMS)
        self.audited_count = _count(audited_count, "release batch summary audited count", MAX_ITEMS)
        self.accepted_count = _count(accepted_count, "release batch summary accepted count", MAX_ITEMS)
        self.accepted = _bool(accepted, "release batch summary acceptance")
        self.release_ready = _bool(release_ready, "release batch summary readiness")
        if state not in STATES:
            raise ValidationError("release batch summary state is unsupported")
        self.state = state
        self.content_address = _address(content_address, "release batch summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        expected_state = "empty" if self.item_count == 0 else "ready" if self.release_ready else "blocked"
        if self.ready_count + self.blocked_count != self.item_count or self.audited_count > self.item_count or self.accepted_count > self.item_count or self.state != expected_state or self.release_ready != (self.accepted and self.item_count > 0):
            raise ValidationError("release batch summary disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address:
            raise ValidationError("release batch summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchSummary":
        value = _mapping(value, "release batch summary")
        _strict(value, set(cls.FIELDS), "release batch summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: BatchSummary) -> str:
    if not isinstance(value, BatchSummary):
        raise ValidationError("release batch summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class ReleaseBatch:
    FIELDS = BATCH_FIELDS

    def __init__(self, batch_id: str, version: str, boundary: str, policy: Mapping[str, Any] | BatchPolicy, item_count: int, ready_count: int, blocked_count: int, audited_count: int, accepted_count: int, accepted: bool, release_ready: bool, state: str, manifest: Mapping[str, Any] | BatchManifest, summary: Mapping[str, Any] | BatchSummary, items: Sequence[BatchItem | Mapping[str, Any]], checks: Sequence[BatchCheck | Mapping[str, Any]], content_address: str) -> None:
        self.batch_id = _label(batch_id, "release batch ID")
        self.version = _text(version, "release batch version", 1024)
        self.boundary = _text(boundary, "release batch boundary", 2048)
        self.policy = policy if isinstance(policy, BatchPolicy) else BatchPolicy.from_mapping(_mapping(policy, "release batch policy"))
        self.item_count = _count(item_count, "release batch item count", MAX_ITEMS)
        self.ready_count = _count(ready_count, "release batch ready count", MAX_ITEMS)
        self.blocked_count = _count(blocked_count, "release batch blocked count", MAX_ITEMS)
        self.audited_count = _count(audited_count, "release batch audited count", MAX_ITEMS)
        self.accepted_count = _count(accepted_count, "release batch accepted count", MAX_ITEMS)
        self.accepted = _bool(accepted, "release batch acceptance")
        self.release_ready = _bool(release_ready, "release batch readiness")
        if state not in STATES:
            raise ValidationError("release batch state is unsupported")
        self.state = state
        self.manifest = manifest if isinstance(manifest, BatchManifest) else BatchManifest.from_mapping(_mapping(manifest, "release batch manifest"))
        self.summary = summary if isinstance(summary, BatchSummary) else BatchSummary.from_mapping(_mapping(summary, "release batch summary"))
        self.items = tuple(item if isinstance(item, BatchItem) else BatchItem.from_mapping(_mapping(item, "release batch item")) for item in _sequence(items, "release batch items", MAX_ITEMS))
        self.checks = tuple(item if isinstance(item, BatchCheck) else BatchCheck.from_mapping(_mapping(item, "release batch check")) for item in _sequence(checks, "release batch checks", MAX_CHECKS))
        self.content_address = _address(content_address, "release batch address", BATCH_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.item_count != len(self.items) or self.item_count > MAX_ITEMS or len(self.checks) != MAX_CHECKS:
            raise ValidationError("release batch identity, item count, or check count does not replay")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, self.item_count + 1)):
            raise ValidationError("release batch item ordinals are not contiguous")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("release batch check sequence is not canonical")
        if len({item.runtime_id for item in self.items}) != self.item_count or len({item.runtime_address for item in self.items}) != self.item_count:
            raise ValidationError("release batch contains duplicate runtime identity or address")
        ready = sum(item.state == "ready" for item in self.items)
        blocked = sum(item.state == "blocked" for item in self.items)
        audited = sum(bool(item.audit_address) for item in self.items)
        accepted = sum(item.accepted for item in self.items)
        if (self.ready_count, self.blocked_count, self.audited_count, self.accepted_count) != (ready, blocked, audited, accepted):
            raise ValidationError("release batch counters do not replay")
        if self.accepted != (all(item.passed for item in self.checks) and self.item_count > 0) or self.release_ready != (self.accepted and self.item_count > 0) or self.state != ("empty" if self.item_count == 0 else "ready" if self.release_ready else "blocked"):
            raise ValidationError("release batch disposition does not replay")
        expected_summary = (self.batch_id, self.item_count, self.ready_count, self.blocked_count, self.audited_count, self.accepted_count, self.accepted, self.release_ready, self.state)
        if tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1]) != expected_summary or self.summary.content_address != address_summary(self.summary):
            raise ValidationError("release batch summary does not replay")
        expected_manifest = (self.batch_id, VERSION, BOUNDARY, FILES, (self.policy.content_address, address_items(self.items), address_checks(self.checks), self.summary.content_address))
        actual_manifest = (self.manifest.batch_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest):
            raise ValidationError("release batch manifest does not replay")
        if not self.content_address.startswith("pending:") and address_batch(self) != self.content_address:
            raise ValidationError("release batch address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch crosses the public boundary")

    @property
    def check_count(self) -> int:
        return len(self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {"batch_id": self.batch_id, "version": self.version, "boundary": self.boundary, "policy": self.policy.to_dict(), "item_count": self.item_count, "ready_count": self.ready_count, "blocked_count": self.blocked_count, "audited_count": self.audited_count, "accepted_count": self.accepted_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "items": [item.to_dict() for item in self.items], "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReleaseBatch":
        value = _mapping(value, "release batch")
        _strict(value, set(cls.FIELDS), "release batch")
        return cls(*(value[field] for field in cls.FIELDS))


def address_batch(value: ReleaseBatch) -> str:
    if not isinstance(value, ReleaseBatch):
        raise ValidationError("release batch address requires a typed batch")
    return _address_for(value, BATCH_PREFIX)


def build_policy(policy_id: str, *, minimum_runtimes: int = 1, minimum_ready: int = 1, maximum_blocked: int = 0, require_same_diff: bool = True, require_audited: bool = False, require_release_ready: bool = True, allow_mixed_policies: bool = True) -> BatchPolicy:
    provisional = BatchPolicy(policy_id, minimum_runtimes, minimum_ready, maximum_blocked, require_same_diff, require_audited, require_release_ready, allow_mixed_policies, f"pending:{POLICY_PREFIX}")
    return _seal(provisional, address_policy)


def _item(runtime: runtime_model.DiffRuntime, ordinal: int, audit_address: str) -> BatchItem:
    runtime_model.verify_runtime(runtime)
    body = {"ordinal": ordinal, "runtime_id": runtime.runtime_id, "runtime_address": runtime.content_address, "diff_id": runtime.diff_id, "diff_address": runtime.diff_address, "policy_address": runtime.policy.content_address, "audit_address": audit_address, "state": runtime.state, "release_ready": runtime.release_ready, "accepted": runtime.accepted, "check_count": runtime.check_count, "passed_count": runtime.passed_count, "failed_count": runtime.failed_count, "item_count": runtime.item_count, "content_address": f"pending:{ITEM_PREFIX}"}
    provisional = BatchItem(**body)
    return BatchItem(**(body | {"content_address": address_item(provisional)}))


def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> BatchCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "severity": "info" if passed else "error", "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}
    provisional = BatchCheck(**body)
    return BatchCheck(**(body | {"content_address": address_check(provisional)}))


def build_batch(runtimes: Sequence[runtime_model.DiffRuntime], *, batch_id: str = DEFAULT_BATCH_ID, policy: BatchPolicy | Mapping[str, Any] | None = None, audit_addresses: Mapping[str, str] | None = None) -> ReleaseBatch:
    typed = tuple(runtimes)
    if len(typed) > MAX_ITEMS or any(not isinstance(item, runtime_model.DiffRuntime) for item in typed):
        raise ValidationError("release batch requires a bounded sequence of typed runtimes")
    for item in typed:
        runtime_model.verify_runtime(item)
    batch_policy = policy if isinstance(policy, BatchPolicy) else BatchPolicy.from_mapping(_mapping(policy, "release batch policy")) if policy is not None else build_policy(f"{batch_id}-policy")
    evidence = dict(audit_addresses or {})
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in evidence.items()):
        raise ValidationError("release batch audit evidence must be string keyed")
    items = tuple(_item(item, index, evidence.get(item.runtime_id, "")) for index, item in enumerate(typed, 1))
    ids = tuple(item.runtime_id for item in items)
    addresses = tuple(item.runtime_address for item in items)
    diffs = tuple(item.diff_id for item in items)
    policies = tuple(item.policy_address for item in items)
    ready_count = sum(item.state == "ready" for item in items)
    blocked_count = sum(item.state == "blocked" for item in items)
    audited_count = sum(bool(item.audit_address) for item in items)
    accepted_count = sum(item.accepted for item in items)
    all_same_diff = len(set(diffs)) <= 1
    all_same_policy = len(set(policies)) <= 1
    checks = (
        _check(1, "nonempty", bool(items), len(items), ">= 1", "a release batch must carry at least one runtime"),
        _check(2, "minimum_runtimes", len(items) >= batch_policy.minimum_runtimes, len(items), batch_policy.minimum_runtimes, "runtime count must meet the policy floor"),
        _check(3, "minimum_ready", ready_count >= batch_policy.minimum_ready, ready_count, batch_policy.minimum_ready, "ready runtimes must meet the policy floor"),
        _check(4, "blocked_budget", blocked_count <= batch_policy.maximum_blocked, blocked_count, batch_policy.maximum_blocked, "blocked runtimes must remain within the policy budget"),
        _check(5, "state_consistency", all(item.release_ready == (item.state == "ready") for item in items), [item.state for item in items], "ready/blocked", "item state and readiness must agree"),
        _check(6, "release_ready_policy", (not batch_policy.require_release_ready) or all(item.release_ready for item in items), [item.release_ready for item in items], True, "the policy may require every runtime to be release ready"),
        _check(7, "runtime_acceptance", all(item.accepted for item in items), accepted_count, len(items), "every runtime must be accepted when batch admission requires it"),
        _check(8, "same_diff", (not batch_policy.require_same_diff) or all_same_diff, diffs, "one diff ID", "runtime lineage must be consistent"),
        _check(9, "unique_runtime_ids", len(set(ids)) == len(ids), ids, "unique runtime IDs", "runtime identity must not be duplicated"),
        _check(10, "unique_runtime_addresses", len(set(addresses)) == len(addresses), addresses, "unique runtime addresses", "runtime content addresses must not be duplicated"),
        _check(11, "item_address_integrity", all(address_item(item) == item.content_address for item in items), True, "replayed item addresses", "item content addresses must replay"),
        _check(12, "audit_evidence", (not batch_policy.require_audited) or audited_count == len(items), audited_count, len(items), "required runtime audits must be explicitly linked"),
        _check(13, "policy_consistency", batch_policy.allow_mixed_policies or all_same_policy, policies, "one policy address", "mixed runtime policies are controlled by the batch policy"),
        _check(14, "counter_conservation", ready_count + blocked_count == len(items) and audited_count <= len(items) and accepted_count <= len(items), (ready_count, blocked_count, audited_count, accepted_count), len(items), "aggregate counters must conserve item membership"),
        _check(15, "policy_integrity", address_policy(batch_policy) == batch_policy.content_address, batch_policy.content_address, address_policy(batch_policy), "batch policy address must replay"),
        _check(16, "runtime_links", all(item.runtime_id == typed[index].runtime_id and item.runtime_address == typed[index].content_address for index, item in enumerate(items)), True, "runtime identity links", "items must retain their source runtime identities"),
        _check(17, "manifest_integrity", FILES == ("manifest.json", "batch.json", "policy.json", "items.json", "checks.json", "summary.json"), FILES, "canonical six-file artifact", "the persisted release artifact has a fixed file set"),
        _check(18, "public_boundary", all(_public(item.to_dict()) for item in items) and _public(batch_policy.to_dict()), True, "public value", "release batch values must remain value-only"),
    )
    accepted = bool(items) and all(item.passed for item in checks)
    release_ready = accepted
    state = "ready" if release_ready else "blocked" if items else "empty"
    summary = _seal(BatchSummary(batch_id, len(items), ready_count, blocked_count, audited_count, accepted_count, accepted, release_ready, state, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(BatchManifest(batch_id, VERSION, BOUNDARY, FILES, (batch_policy.content_address, address_items(items), address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(ReleaseBatch(batch_id, VERSION, BOUNDARY, batch_policy, len(items), ready_count, blocked_count, audited_count, accepted_count, accepted, release_ready, state, manifest, summary, items, checks, f"pending:{BATCH_PREFIX}"), address_batch)


def verify_batch(value: ReleaseBatch) -> ReleaseBatch:
    if not isinstance(value, ReleaseBatch):
        raise ValidationError("release batch verification requires a typed batch")
    value._validate()
    return value


def batch_from_mapping(value: Mapping[str, Any]) -> ReleaseBatch:
    return ReleaseBatch.from_mapping(value)


def batch_json(value: ReleaseBatch) -> str:
    return canonical_json(verify_batch(value).to_dict())


def policy_json(value: ReleaseBatch) -> str:
    return canonical_json(verify_batch(value).policy.to_dict())


def items_json(value: ReleaseBatch) -> str:
    value = verify_batch(value)
    return canonical_json({"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)})


def checks_json(value: ReleaseBatch) -> str:
    value = verify_batch(value)
    return canonical_json({"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)})


def summary_json(value: ReleaseBatch) -> str:
    return canonical_json(verify_batch(value).summary.to_dict())


def manifest_json(value: ReleaseBatch) -> str:
    return canonical_json(verify_batch(value).manifest.to_dict())


def batch_csv(value: ReleaseBatch) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ITEM_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_batch(value).items)
    return output.getvalue()


def render_batch_markdown(value: ReleaseBatch) -> str:
    value = verify_batch(value)
    lines = [f"# Release batch {value.batch_id}", "", f"- State: {value.state}", f"- Release ready: {str(value.release_ready).lower()}", f"- Items: {value.item_count}", f"- Ready: {value.ready_count}", f"- Blocked: {value.blocked_count}", f"- Audited: {value.audited_count}", "", "| Runtime | Diff | State | Accepted | Audit | Checks |", "| --- | --- | --- | --- | --- | ---: |"]
    lines.extend(f"| {item.runtime_id} | {item.diff_id} | {item.state} | {str(item.accepted).lower()} | {str(bool(item.audit_address)).lower()} | {item.passed_count}/{item.check_count} |" for item in value.items)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_batch(value: ReleaseBatch, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_batch(value)
    destination = Path(destination)
    _validate_parent(destination.parent, "release batch destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("release batch destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-release-batch-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "batch.json": value.to_dict(), "policy.json": value.policy.to_dict(), "items.json": {"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)}, "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("release batch destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = _strict_json_loads(read_text(path, field="release batch artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("release batch artifact is not valid JSON") from error
    return _mapping(value, "release batch artifact")


def load_batch(destination: str | Path) -> ReleaseBatch:
    destination = Path(destination)
    _validate_parent(destination.parent, "release batch input")
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("release batch source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("release batch directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="release batch artifact") != serialized or len(serialized.encode("utf-8")) > MAX_BATCH_BYTES:
            raise ValidationError("release batch artifact is non-canonical or exceeds its size bound")
    value = batch_from_mapping(documents["batch.json"])
    expected = {"manifest.json": value.manifest.to_dict(), "policy.json": value.policy.to_dict(), "items.json": {"items": [item.to_dict() for item in value.items], "content_address": address_items(value.items)}, "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()):
        raise ValidationError("release batch component documents do not replay batch.json")
    return verify_batch(value)


def run_batch(runtimes: Sequence[runtime_model.DiffRuntime], *, batch_id: str = DEFAULT_BATCH_ID, policy: BatchPolicy | Mapping[str, Any] | None = None, audit_addresses: Mapping[str, str] | None = None, destination: str | Path | None = None, overwrite: bool = False) -> ReleaseBatch:
    value = build_batch(runtimes, batch_id=batch_id, policy=policy, audit_addresses=audit_addresses)
    if destination is not None:
        persist_batch(value, destination, overwrite=overwrite)
    return value


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchPolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("runtimes") or field.endswith("ready") or field.endswith("blocked") else "boolean" if field.startswith(("require_", "allow_")) else "string"} for field in POLICY_FIELDS}}


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchItem", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {field: {"type": "integer" if field in ("ordinal", "check_count", "passed_count", "failed_count", "item_count") else "boolean" if field in ("release_ready", "accepted") else "string"} for field in ITEM_FIELDS}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("accepted", "release_ready") else "string"} for field in SUMMARY_FIELDS}}


def batch_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatch", "type": "object", "additionalProperties": False, "required": list(BATCH_FIELDS), "properties": {field: {"type": "array" if field in ("items", "checks") else "object" if field in ("policy", "manifest", "summary") else "integer" if field.endswith("count") else "boolean" if field in ("accepted", "release_ready") else "string"} for field in BATCH_FIELDS}, "$defs": {"item": item_schema(), "check": check_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "states": STATES, "check_ids": CHECK_IDS, "max_items": MAX_ITEMS, "max_checks": MAX_CHECKS, "features": ("multi-runtime release batching", "minimum-ready and maximum-blocked policy thresholds", "same-diff and audit-evidence controls", "duplicate identity rejection", "exact six-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "BATCH_PREFIX", "POLICY_PREFIX", "ITEM_PREFIX", "ITEMS_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_BATCH_ID", "FILES", "ARTIFACT_FILES", "STATES", "SEVERITIES", "MAX_ITEMS", "MAX_CHECKS", "MAX_BATCH_BYTES", "POLICY_FIELDS", "ITEM_FIELDS", "ITEMS_FIELDS", "CHECK_FIELDS", "CHECKS_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "BATCH_FIELDS", "CHECK_IDS", "BatchPolicy", "BatchItem", "BatchCheck", "BatchManifest", "BatchSummary", "ReleaseBatch", "address_policy", "address_item", "address_items", "address_check", "address_checks", "address_manifest", "address_summary", "address_batch", "build_policy", "build_batch", "verify_batch", "batch_from_mapping", "batch_json", "policy_json", "items_json", "checks_json", "summary_json", "manifest_json", "batch_csv", "render_batch_markdown", "persist_batch", "load_batch", "run_batch", "policy_schema", "item_schema", "check_schema", "manifest_schema", "summary_schema", "batch_schema", "capabilities"]
