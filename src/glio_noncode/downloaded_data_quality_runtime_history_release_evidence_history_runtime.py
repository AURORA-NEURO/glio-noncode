"""Policy-driven runtime release decisions over release-evidence history."""

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

from . import downloaded_data_quality_runtime_history_release_evidence_history as history_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = history_model.VERSION + "-runtime-v1"
BOUNDARY = history_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = history_model.HISTORY_PREFIX + "-runtime"
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
MAX_CHECKS = 14
MAX_RUNTIME_BYTES = 32 * 1024 * 1024
POLICY_FIELDS = ("policy_id", "history_id", "minimum_entries", "maximum_regressed", "maximum_blocked", "require_latest_ready", "require_latest_evidence_ready", "allow_unchanged", "allow_changed", "content_address")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "severity", "actual", "expected", "detail", "content_address")
CHECKS_FIELDS = ("checks", "content_address")
MANIFEST_FIELDS = ("runtime_id", "history_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("runtime_id", "history_id", "history_address", "policy_address", "check_count", "passed_count", "failed_count", "release_ready", "state", "latest_state", "latest_ready", "entry_count", "regressed_count", "blocked_count", "content_address")
RUNTIME_FIELDS = ("runtime_id", "history_id", "history_address", "version", "boundary", "policy", "checks", "check_count", "passed_count", "failed_count", "release_ready", "state", "latest_state", "latest_ready", "entry_count", "regressed_count", "blocked_count", "manifest", "summary", "content_address")
CHECK_IDS = ("history_present", "minimum_entries", "history_accepted", "latest_ready", "latest_evidence_ready", "regression_budget", "blocked_budget", "unchanged_policy", "changed_policy", "transition_conservation", "identity_link", "head_link", "address_integrity", "public_boundary")


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
    return history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class RuntimePolicy:
    FIELDS = POLICY_FIELDS

    def __init__(self, policy_id: str, history_id: str, minimum_entries: int, maximum_regressed: int, maximum_blocked: int, require_latest_ready: bool, require_latest_evidence_ready: bool, allow_unchanged: bool, allow_changed: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "history runtime policy ID")
        self.history_id = _label(history_id, "history runtime policy history ID")
        self.minimum_entries = _count(minimum_entries, "history runtime minimum entries", history_model.MAX_ENTRIES, lower=1)
        self.maximum_regressed = _count(maximum_regressed, "history runtime maximum regressions", history_model.MAX_ENTRIES)
        self.maximum_blocked = _count(maximum_blocked, "history runtime maximum blocked entries", history_model.MAX_ENTRIES)
        self.require_latest_ready = _bool(require_latest_ready, "history runtime latest state requirement")
        self.require_latest_evidence_ready = _bool(require_latest_evidence_ready, "history runtime latest evidence requirement")
        self.allow_unchanged = _bool(allow_unchanged, "history runtime unchanged policy")
        self.allow_changed = _bool(allow_changed, "history runtime changed policy")
        self.content_address = _address(content_address, "history runtime policy address", POLICY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address:
            raise ValidationError("history runtime policy address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history runtime policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimePolicy":
        value = _mapping(value, "history runtime policy")
        _strict(value, set(cls.FIELDS), "history runtime policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: RuntimePolicy) -> str:
    if not isinstance(value, RuntimePolicy):
        raise ValidationError("history runtime policy address requires a typed policy")
    return _address_for(value, POLICY_PREFIX)


class RuntimeCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history runtime check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "history runtime check ID")
        self.passed = _bool(passed, "history runtime check result")
        if severity not in SEVERITIES:
            raise ValidationError("history runtime check severity is unsupported")
        self.severity = severity
        self.actual = _text(actual, "history runtime check actual", 32768)
        self.expected = _text(expected, "history runtime check expected", 32768)
        self.detail = _text(detail, "history runtime check detail", 4096)
        self.content_address = _address(content_address, "history runtime check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("history runtime check identity is unsupported")
        if self.passed and self.severity == "error":
            raise ValidationError("passed history runtime check cannot have error severity")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("history runtime check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history runtime check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeCheck":
        value = _mapping(value, "history runtime check")
        _strict(value, set(cls.FIELDS), "history runtime check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RuntimeCheck) -> str:
    if not isinstance(value, RuntimeCheck):
        raise ValidationError("history runtime check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


def address_checks(value: Sequence[RuntimeCheck]) -> str:
    checks = tuple(value)
    if any(not isinstance(item, RuntimeCheck) for item in checks):
        raise ValidationError("history runtime checks address requires typed checks")
    return content_hash({"checks": [item.to_dict() for item in checks]}, prefix=CHECKS_PREFIX)


class RuntimeManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, history_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history runtime manifest ID")
        self.history_id = _label(history_id, "history runtime manifest history ID")
        self.version = _text(version, "history runtime manifest version", 1024)
        self.boundary = _text(boundary, "history runtime manifest boundary", 2048)
        self.files = tuple(_text(item, "history runtime manifest file", 128) for item in _sequence(files, "history runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "history runtime manifest artifact address") for item in _sequence(artifact_addresses, "history runtime manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "history runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES):
            raise ValidationError("history runtime manifest is not canonical")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history runtime manifest version or boundary is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("history runtime manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history runtime manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeManifest":
        value = _mapping(value, "history runtime manifest")
        _strict(value, set(cls.FIELDS), "history runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: RuntimeManifest) -> str:
    if not isinstance(value, RuntimeManifest):
        raise ValidationError("history runtime manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class RuntimeSummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, runtime_id: str, history_id: str, history_address: str, policy_address: str, check_count: int, passed_count: int, failed_count: int, release_ready: bool, state: str, latest_state: str, latest_ready: bool, entry_count: int, regressed_count: int, blocked_count: int, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history runtime summary ID")
        self.history_id = _label(history_id, "history runtime summary history ID")
        self.history_address = _address(history_address, "history runtime summary history address", history_model.HISTORY_PREFIX)
        self.policy_address = _address(policy_address, "history runtime summary policy address", POLICY_PREFIX)
        self.check_count = _count(check_count, "history runtime summary check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "history runtime summary passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history runtime summary failed count", MAX_CHECKS)
        self.release_ready = _bool(release_ready, "history runtime summary readiness")
        if state not in STATES:
            raise ValidationError("history runtime summary state is unsupported")
        self.state = state
        if latest_state not in STATES:
            raise ValidationError("history runtime summary latest state is unsupported")
        self.latest_state = latest_state
        self.latest_ready = _bool(latest_ready, "history runtime latest readiness")
        self.entry_count = _count(entry_count, "history runtime summary entry count", history_model.MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "history runtime summary regression count", history_model.MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "history runtime summary blocked count", history_model.MAX_ENTRIES)
        self.content_address = _address(content_address, "history runtime summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.passed_count + self.failed_count != self.check_count or self.release_ready != (self.failed_count == 0) or self.state != ("ready" if self.release_ready else "blocked"):
            raise ValidationError("history runtime summary disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address:
            raise ValidationError("history runtime summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history runtime summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeSummary":
        value = _mapping(value, "history runtime summary")
        _strict(value, set(cls.FIELDS), "history runtime summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: RuntimeSummary) -> str:
    if not isinstance(value, RuntimeSummary):
        raise ValidationError("history runtime summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class HistoryRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, history_id: str, history_address: str, version: str, boundary: str, policy: Mapping[str, Any] | RuntimePolicy, checks: Sequence[RuntimeCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, release_ready: bool, state: str, latest_state: str, latest_ready: bool, entry_count: int, regressed_count: int, blocked_count: int, manifest: Mapping[str, Any] | RuntimeManifest, summary: Mapping[str, Any] | RuntimeSummary, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history runtime ID")
        self.history_id = _label(history_id, "history runtime history ID")
        self.history_address = _address(history_address, "history runtime history address", history_model.HISTORY_PREFIX)
        self.version = _text(version, "history runtime version", 1024)
        self.boundary = _text(boundary, "history runtime boundary", 2048)
        self.policy = policy if isinstance(policy, RuntimePolicy) else RuntimePolicy.from_mapping(_mapping(policy, "history runtime policy"))
        self.checks = tuple(item if isinstance(item, RuntimeCheck) else RuntimeCheck.from_mapping(_mapping(item, "history runtime check")) for item in _sequence(checks, "history runtime checks", MAX_CHECKS))
        self.check_count = _count(check_count, "history runtime check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "history runtime passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history runtime failed count", MAX_CHECKS)
        self.release_ready = _bool(release_ready, "history runtime readiness")
        if state not in STATES:
            raise ValidationError("history runtime state is unsupported")
        self.state = state
        if latest_state not in STATES:
            raise ValidationError("history runtime latest state is unsupported")
        self.latest_state = latest_state
        self.latest_ready = _bool(latest_ready, "history runtime latest readiness")
        self.entry_count = _count(entry_count, "history runtime entry count", history_model.MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "history runtime regression count", history_model.MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "history runtime blocked count", history_model.MAX_ENTRIES)
        self.manifest = manifest if isinstance(manifest, RuntimeManifest) else RuntimeManifest.from_mapping(_mapping(manifest, "history runtime manifest"))
        self.summary = summary if isinstance(summary, RuntimeSummary) else RuntimeSummary.from_mapping(_mapping(summary, "history runtime summary"))
        self.content_address = _address(content_address, "history runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history runtime version or boundary is unsupported")
        if self.policy.history_id != self.history_id or self.check_count != len(self.checks) or self.check_count != MAX_CHECKS:
            raise ValidationError("history runtime identity or check count does not replay")
        if (self.passed_count, self.failed_count) != (sum(item.passed for item in self.checks), sum(not item.passed for item in self.checks)):
            raise ValidationError("history runtime counters do not replay")
        if self.release_ready != (self.failed_count == 0) or self.state != ("ready" if self.release_ready else "blocked"):
            raise ValidationError("history runtime disposition does not replay")
        expected_summary = (self.runtime_id, self.history_id, self.history_address, address_policy(self.policy), self.check_count, self.passed_count, self.failed_count, self.release_ready, self.state, self.latest_state, self.latest_ready, self.entry_count, self.regressed_count, self.blocked_count)
        actual_summary = tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1])
        if actual_summary != expected_summary or self.summary.content_address != address_summary(self.summary):
            raise ValidationError("history runtime summary does not replay")
        expected_manifest = (self.runtime_id, self.history_id, VERSION, BOUNDARY, FILES, (address_checks(self.checks), self.summary.content_address))
        actual_manifest = (self.manifest.runtime_id, self.manifest.history_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest):
            raise ValidationError("history runtime manifest does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, RUNTIME_PREFIX) != self.content_address:
            raise ValidationError("history runtime address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "history_id": self.history_id, "history_address": self.history_address, "version": self.version, "boundary": self.boundary, "policy": self.policy.to_dict(), "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "release_ready": self.release_ready, "state": self.state, "latest_state": self.latest_state, "latest_ready": self.latest_ready, "entry_count": self.entry_count, "regressed_count": self.regressed_count, "blocked_count": self.blocked_count, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryRuntime":
        value = _mapping(value, "history runtime")
        _strict(value, set(cls.FIELDS), "history runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: HistoryRuntime) -> str:
    if not isinstance(value, HistoryRuntime):
        raise ValidationError("history runtime address requires a typed runtime")
    return _address_for(value, RUNTIME_PREFIX)


def build_policy(policy_id: str, history_id: str, *, minimum_entries: int = 1, maximum_regressed: int = 0, maximum_blocked: int = 0, require_latest_ready: bool = True, require_latest_evidence_ready: bool = True, allow_unchanged: bool = True, allow_changed: bool = True) -> RuntimePolicy:
    value = RuntimePolicy(policy_id, history_id, minimum_entries, maximum_regressed, maximum_blocked, require_latest_ready, require_latest_evidence_ready, allow_unchanged, allow_changed, f"pending:{POLICY_PREFIX}")
    return _seal(value, address_policy)


def _policy_for(history: history_model.EvidenceHistory, runtime_id: str, policy: RuntimePolicy | Mapping[str, Any] | None) -> RuntimePolicy:
    if policy is None:
        return build_policy(runtime_id, history.history_id)
    value = policy if isinstance(policy, RuntimePolicy) else RuntimePolicy.from_mapping(_mapping(policy, "history runtime policy"))
    if value.history_id != history.history_id:
        raise ValidationError("history runtime policy history identity does not match")
    return value


def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> RuntimeCheck:
    return RuntimeCheck(ordinal, check_id, passed, "info" if passed else "error", canonical_json(actual), canonical_json(expected), detail, f"pending:{CHECK_PREFIX}")


def build_runtime(history: history_model.EvidenceHistory, *, runtime_id: str = DEFAULT_RUNTIME_ID, policy: RuntimePolicy | Mapping[str, Any] | None = None) -> HistoryRuntime:
    if not isinstance(history, history_model.EvidenceHistory):
        raise ValidationError("history runtime requires a typed evidence history")
    history_model.verify_history(history)
    runtime_id = _label(runtime_id, "history runtime ID")
    policy_value = _policy_for(history, runtime_id, policy)
    latest = history.entries[-1] if history.entries else None
    blocked_count = sum(item.state == "blocked" for item in history.entries)
    checks = (
        _check(1, "history_present", history.entry_count > 0, history.entry_count, "> 0", "history must contain evidence snapshots"),
        _check(2, "minimum_entries", history.entry_count >= policy_value.minimum_entries, history.entry_count, f">= {policy_value.minimum_entries}", "history depth must meet policy"),
        _check(3, "history_accepted", history.accepted, history.accepted, True, "history must be structurally accepted"),
        _check(4, "latest_ready", not policy_value.require_latest_ready or (latest is not None and latest.state == "ready"), latest.state if latest else "empty", "ready" if policy_value.require_latest_ready else "not-required", "latest history state must satisfy policy"),
        _check(5, "latest_evidence_ready", not policy_value.require_latest_evidence_ready or (latest is not None and latest.evidence_ready), latest.evidence_ready if latest else False, True if policy_value.require_latest_evidence_ready else "not-required", "latest evidence readiness must satisfy policy"),
        _check(6, "regression_budget", history.regressed_count <= policy_value.maximum_regressed, history.regressed_count, f"<= {policy_value.maximum_regressed}", "regressed transitions must remain within budget"),
        _check(7, "blocked_budget", blocked_count <= policy_value.maximum_blocked, blocked_count, f"<= {policy_value.maximum_blocked}", "blocked snapshots must remain within budget"),
        _check(8, "unchanged_policy", policy_value.allow_unchanged or history.unchanged_count == 0, history.unchanged_count, "allowed" if policy_value.allow_unchanged else "== 0", "unchanged transitions follow policy"),
        _check(9, "changed_policy", policy_value.allow_changed or history.changed_count == 0, history.changed_count, "allowed" if policy_value.allow_changed else "== 0", "changed transitions follow policy"),
        _check(10, "transition_conservation", sum((history.initial_count, history.improved_count, history.regressed_count, history.unchanged_count, history.changed_count)) == history.entry_count, history.entry_count, "sum transitions", "history transitions must conserve entries"),
        _check(11, "identity_link", all(item.gate_id == history.gate_id and item.source_history_id == history.source_history_id for item in history.entries), history.gate_id, "history identity", "all snapshots must share stable identity"),
        _check(12, "head_link", bool(history.entries) and history.entries[-1].content_address.startswith(history_model.ENTRY_PREFIX + ":"), history.entries[-1].content_address if history.entries else "empty", history_model.ENTRY_PREFIX, "history head must use its canonical address namespace"),
        _check(13, "address_integrity", history.content_address.startswith(history_model.HISTORY_PREFIX + ":"), history.content_address, history_model.HISTORY_PREFIX, "history address must use canonical namespace"),
        _check(14, "public_boundary", _public(history.to_dict()), True, True, "history runtime must remain value-only and path-free"),
    )
    checks = tuple(_seal(item, address_check) for item in checks)
    passed = sum(item.passed for item in checks)
    release_ready = passed == len(checks)
    summary = _seal(RuntimeSummary(runtime_id, history.history_id, history.content_address, address_policy(policy_value), len(checks), passed, len(checks) - passed, release_ready, "ready" if release_ready else "blocked", latest.state if latest else "empty", latest.evidence_ready if latest else False, history.entry_count, history.regressed_count, blocked_count, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(RuntimeManifest(runtime_id, history.history_id, VERSION, BOUNDARY, FILES, (address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    value = HistoryRuntime(runtime_id, history.history_id, history.content_address, VERSION, BOUNDARY, policy_value, checks, len(checks), passed, len(checks) - passed, release_ready, "ready" if release_ready else "blocked", latest.state if latest else "empty", latest.evidence_ready if latest else False, history.entry_count, history.regressed_count, blocked_count, manifest, summary, f"pending:{RUNTIME_PREFIX}")
    return _seal(value, address_runtime)


def verify_runtime(value: HistoryRuntime, history: history_model.EvidenceHistory | None = None) -> HistoryRuntime:
    if not isinstance(value, HistoryRuntime):
        raise ValidationError("history runtime verification requires a typed runtime")
    if history is not None:
        history_model.verify_history(history)
        if history.content_address != value.history_address:
            raise ValidationError("history runtime source history address does not match")
    value._validate()
    return value


def runtime_from_mapping(value: Mapping[str, Any], history: history_model.EvidenceHistory | None = None) -> HistoryRuntime:
    result = HistoryRuntime.from_mapping(value)
    if history is not None:
        verify_runtime(result, history)
    return result


def runtime_json(value: HistoryRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def checks_json(value: HistoryRuntime) -> str:
    checks = verify_runtime(value).checks
    return canonical_json({"checks": [item.to_dict() for item in checks], "content_address": address_checks(checks)})


def summary_json(value: HistoryRuntime) -> str:
    return canonical_json(verify_runtime(value).summary.to_dict())


def manifest_json(value: HistoryRuntime) -> str:
    return canonical_json(verify_runtime(value).manifest.to_dict())


def runtime_csv(value: HistoryRuntime) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_runtime(value).checks)
    return output.getvalue()


def render_runtime_markdown(value: HistoryRuntime) -> str:
    value = verify_runtime(value)
    lines = [f"# Downloaded-data quality release-evidence history runtime {value.runtime_id}", "", f"- State: {value.state}", f"- Release ready: {str(value.release_ready).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", f"- Latest state: {value.latest_state}", f"- Latest ready: {str(value.latest_ready).lower()}", f"- Entries: {value.entry_count}", f"- Regressed: {value.regressed_count}", f"- Blocked: {value.blocked_count}", "", "| Check | Result | Severity | Detail |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.severity} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: HistoryRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_runtime(value)
    destination = Path(destination)
    _validate_parent(destination.parent, "history runtime destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("history runtime destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-release-evidence-history-runtime-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "runtime.json": value.to_dict(), "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("history runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = _strict_json_loads(read_text(path, field="history runtime artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("history runtime artifact is not valid JSON") from error
    return _mapping(value, "history runtime artifact")


def load_runtime(destination: str | Path, history: history_model.EvidenceHistory | None = None) -> HistoryRuntime:
    destination = Path(destination)
    _validate_parent(destination.parent, "history runtime input")
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("history runtime source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("history runtime directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="history runtime artifact") != serialized:
            raise ValidationError("history runtime artifact is not canonical")
        if len(serialized.encode("utf-8")) > MAX_RUNTIME_BYTES:
            raise ValidationError("history runtime artifact exceeds its size bound")
    value = runtime_from_mapping(documents["runtime.json"], history)
    checks = {"manifest.json": value.manifest.to_dict(), "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(expected) for name, expected in checks.items()):
        raise ValidationError("history runtime component documents do not replay runtime.json")
    return verify_runtime(value, history)


def run_runtime(history: history_model.EvidenceHistory, *, runtime_id: str = DEFAULT_RUNTIME_ID, policy: RuntimePolicy | Mapping[str, Any] | None = None, destination: str | Path | None = None, overwrite: bool = False) -> HistoryRuntime:
    value = build_runtime(history, runtime_id=runtime_id, policy=policy)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimePolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "integer" if field in ("minimum_entries", "maximum_regressed", "maximum_blocked") else "boolean" if field in ("require_latest_ready", "require_latest_evidence_ready", "allow_unchanged", "allow_changed") else "string"} for field in POLICY_FIELDS}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "actual": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("release_ready", "latest_ready") else "string"} for field in SUMMARY_FIELDS}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryRuntime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field in ("release_ready", "latest_ready") else "object" if field in ("policy", "manifest", "summary") else "string"} for field in RUNTIME_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "check_ids": CHECK_IDS, "states": STATES, "severities": SEVERITIES, "max_checks": MAX_CHECKS, "features": ("history-linked release policy", "minimum-depth and budget checks", "latest readiness and evidence requirements", "unchanged and changed transition policies", "exact four-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "RUNTIME_PREFIX", "POLICY_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_RUNTIME_ID", "FILES", "ARTIFACT_FILES", "STATES", "SEVERITIES", "MAX_CHECKS", "MAX_RUNTIME_BYTES", "POLICY_FIELDS", "CHECK_FIELDS", "CHECKS_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "RUNTIME_FIELDS", "CHECK_IDS", "RuntimePolicy", "RuntimeCheck", "RuntimeManifest", "RuntimeSummary", "HistoryRuntime", "address_policy", "address_check", "address_checks", "address_manifest", "address_summary", "address_runtime", "build_policy", "build_runtime", "verify_runtime", "runtime_from_mapping", "runtime_json", "checks_json", "summary_json", "manifest_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime", "policy_schema", "check_schema", "manifest_schema", "summary_schema", "runtime_schema", "capabilities"]
