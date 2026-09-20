"""Policy-driven release decisions over downloaded-data quality history."""

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

from . import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history as history_model
from ._safe_persistence import _validate_parent, atomic_write_bytes, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = history_model.VERSION + "-release-gate-v1"
BOUNDARY = history_model.BOUNDARY + "_release_gate"
GATE_PREFIX = history_model.HISTORY_PREFIX + "-release-gate"
POLICY_PREFIX = GATE_PREFIX + "-policy"
CHECK_PREFIX = GATE_PREFIX + "-check"
CHECKS_PREFIX = GATE_PREFIX + "-checks"
MANIFEST_PREFIX = GATE_PREFIX + "-manifest"
SUMMARY_PREFIX = GATE_PREFIX + "-summary"
DEFAULT_GATE_ID = GATE_PREFIX
FILES = ("manifest.json", "gate.json", "checks.json", "summary.json")
ARTIFACT_FILES = ("checks.json", "summary.json")
MANIFEST_ARTIFACT_FILES = ARTIFACT_FILES
SEVERITIES = ("info", "error")
STATES = ("ready", "blocked")
MAX_CHECKS = 12
MAX_GATE_BYTES = 16 * 1024 * 1024
POLICY_FIELDS = (
    "policy_id",
    "history_id",
    "minimum_entries",
    "maximum_regressed",
    "maximum_blocked",
    "require_latest_ready",
    "require_latest_accepted",
    "allow_unchanged",
    "content_address",
)
CHECK_FIELDS = (
    "ordinal",
    "check_id",
    "passed",
    "severity",
    "actual",
    "expected",
    "detail",
    "content_address",
)
CHECKS_FIELDS = ("checks", "content_address")
MANIFEST_FIELDS = ("gate_id", "history_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = (
    "gate_id",
    "history_id",
    "history_address",
    "policy_address",
    "check_count",
    "passed_count",
    "failed_count",
    "release_ready",
    "state",
    "latest_state",
    "latest_accepted",
    "entry_count",
    "regressed_count",
    "blocked_count",
    "content_address",
)
GATE_FIELDS = (
    "gate_id",
    "history_id",
    "history_address",
    "version",
    "boundary",
    "policy",
    "checks",
    "check_count",
    "passed_count",
    "failed_count",
    "release_ready",
    "state",
    "latest_state",
    "latest_accepted",
    "entry_count",
    "regressed_count",
    "blocked_count",
    "manifest",
    "summary",
    "content_address",
)
CHECK_IDS = (
    "history_present",
    "minimum_entries",
    "history_accepted",
    "latest_ready",
    "latest_accepted",
    "regression_budget",
    "blocked_budget",
    "unchanged_policy",
    "transition_conservation",
    "identity_link",
    "address_integrity",
    "public_boundary",
)


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
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if value and (":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":"))):
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


def _display(value: Any) -> str:
    return canonical_json(value)


def _public(value: Any) -> bool:
    return history_model._public(value)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


class GatePolicy:
    """Bounded, explicit rules for converting history into a release decision."""

    FIELDS = POLICY_FIELDS

    def __init__(self, policy_id: str, history_id: str, minimum_entries: int, maximum_regressed: int, maximum_blocked: int, require_latest_ready: bool, require_latest_accepted: bool, allow_unchanged: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "release gate policy ID")
        self.history_id = _label(history_id, "release gate policy history ID")
        self.minimum_entries = _count(minimum_entries, "release gate minimum entries", history_model.MAX_ENTRIES)
        self.maximum_regressed = _count(maximum_regressed, "release gate maximum regressions", history_model.MAX_ENTRIES)
        self.maximum_blocked = _count(maximum_blocked, "release gate maximum blocked snapshots", history_model.MAX_ENTRIES)
        self.require_latest_ready = _bool(require_latest_ready, "release gate latest-ready requirement")
        self.require_latest_accepted = _bool(require_latest_accepted, "release gate latest-accepted requirement")
        self.allow_unchanged = _bool(allow_unchanged, "release gate unchanged policy")
        self.content_address = _address(content_address, "release gate policy address", POLICY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("release gate policy crosses the public boundary")
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address:
            raise ValidationError("release gate policy address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> GatePolicy:
        value = _mapping(value, "release gate policy")
        _strict(value, set(cls.FIELDS), "release gate policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: GatePolicy) -> str:
    if not isinstance(value, GatePolicy):
        raise ValidationError("release gate policy address requires a typed policy")
    return _address_for(value, POLICY_PREFIX)


class GateCheck:
    """One deterministic policy assertion with a public explanation."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release gate check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "release gate check ID")
        self.passed = _bool(passed, "release gate check result")
        if severity not in SEVERITIES:
            raise ValidationError("release gate check severity is unsupported")
        self.severity = severity
        self.actual = _text(actual, "release gate check actual value")
        self.expected = _text(expected, "release gate check expected value")
        self.detail = _text(detail, "release gate check detail")
        self.content_address = _address(content_address, "release gate check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.passed and self.severity != "info":
            raise ValidationError("passed release gate checks must be informational")
        if not self.passed and self.severity != "error":
            raise ValidationError("failed release gate checks must be errors")
        if not _public(self.to_dict()):
            raise ValidationError("release gate check crosses the public boundary")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("release gate check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> GateCheck:
        value = _mapping(value, "release gate check")
        _strict(value, set(cls.FIELDS), "release gate check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: GateCheck) -> str:
    if not isinstance(value, GateCheck):
        raise ValidationError("release gate check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


def address_checks(value: Sequence[GateCheck]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, GateCheck) for item in typed):
        raise ValidationError("release gate checks address requires typed checks")
    return content_hash({"checks": [item.to_dict() for item in typed]}, prefix=CHECKS_PREFIX)


class GateManifest:
    """Exact-file manifest for a persisted release gate."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, gate_id: str, history_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.gate_id = _label(gate_id, "release gate manifest ID")
        self.history_id = _label(history_id, "release gate manifest history ID")
        self.version = _text(version, "release gate manifest version")
        self.boundary = _text(boundary, "release gate manifest boundary")
        self.files = tuple(_label(item, "release gate manifest file") for item in _sequence(files, "release gate manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "release gate manifest artifact address") for item in _sequence(artifact_addresses, "release gate manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "release gate manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if (self.version, self.boundary, self.files) != (VERSION, BOUNDARY, FILES) or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES):
            raise ValidationError("release gate manifest does not close the public file boundary")
        if not _public(self.to_dict()):
            raise ValidationError("release gate manifest crosses the public boundary")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("release gate manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> GateManifest:
        value = _mapping(value, "release gate manifest")
        _strict(value, set(cls.FIELDS), "release gate manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: GateManifest) -> str:
    if not isinstance(value, GateManifest):
        raise ValidationError("release gate manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class GateSummary:
    """Compact release decision and counter projection."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, gate_id: str, history_id: str, history_address: str, policy_address: str, check_count: int, passed_count: int, failed_count: int, release_ready: bool, state: str, latest_state: str, latest_accepted: bool, entry_count: int, regressed_count: int, blocked_count: int, content_address: str) -> None:
        self.gate_id = _label(gate_id, "release gate summary ID")
        self.history_id = _label(history_id, "release gate summary history ID")
        self.history_address = _address(history_address, "release gate summary history address", history_model.HISTORY_PREFIX)
        self.policy_address = _address(policy_address, "release gate summary policy address", POLICY_PREFIX)
        self.check_count = _count(check_count, "release gate summary check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "release gate summary passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "release gate summary failed count", MAX_CHECKS)
        self.release_ready = _bool(release_ready, "release gate summary readiness")
        if state not in STATES:
            raise ValidationError("release gate summary state is unsupported")
        self.state = state
        self.latest_state = _label(latest_state, "release gate latest state")
        self.latest_accepted = _bool(latest_accepted, "release gate latest acceptance")
        self.entry_count = _count(entry_count, "release gate summary entry count", history_model.MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "release gate summary regression count", history_model.MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "release gate summary blocked count", history_model.MAX_ENTRIES)
        self.content_address = _address(content_address, "release gate summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.passed_count + self.failed_count != self.check_count or self.release_ready != (self.failed_count == 0) or self.state != ("ready" if self.release_ready else "blocked"):
            raise ValidationError("release gate summary counters do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release gate summary crosses the public boundary")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address:
            raise ValidationError("release gate summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> GateSummary:
        value = _mapping(value, "release gate summary")
        _strict(value, set(cls.FIELDS), "release gate summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: GateSummary) -> str:
    if not isinstance(value, GateSummary):
        raise ValidationError("release gate summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class ReleaseGate:
    """Content-addressed release disposition over one history snapshot series."""

    FIELDS = GATE_FIELDS

    def __init__(self, gate_id: str, history_id: str, history_address: str, version: str, boundary: str, policy: GatePolicy | Mapping[str, Any], checks: Sequence[GateCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, release_ready: bool, state: str, latest_state: str, latest_accepted: bool, entry_count: int, regressed_count: int, blocked_count: int, manifest: GateManifest | Mapping[str, Any], summary: GateSummary | Mapping[str, Any], content_address: str) -> None:
        self.gate_id = _label(gate_id, "release gate ID")
        self.history_id = _label(history_id, "release gate history ID")
        self.history_address = _address(history_address, "release gate history address", history_model.HISTORY_PREFIX)
        self.version = _text(version, "release gate version")
        self.boundary = _text(boundary, "release gate boundary")
        self.policy = policy if isinstance(policy, GatePolicy) else GatePolicy.from_mapping(policy)
        self.checks = tuple(item if isinstance(item, GateCheck) else GateCheck.from_mapping(item) for item in _sequence(checks, "release gate checks", MAX_CHECKS))
        self.check_count = _count(check_count, "release gate check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "release gate passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "release gate failed count", MAX_CHECKS)
        self.release_ready = _bool(release_ready, "release gate readiness")
        if state not in STATES:
            raise ValidationError("release gate state is unsupported")
        self.state = state
        self.latest_state = _label(latest_state, "release gate latest state")
        self.latest_accepted = _bool(latest_accepted, "release gate latest acceptance")
        self.entry_count = _count(entry_count, "release gate entry count", history_model.MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "release gate regression count", history_model.MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "release gate blocked count", history_model.MAX_ENTRIES)
        self.manifest = manifest if isinstance(manifest, GateManifest) else GateManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, GateSummary) else GateSummary.from_mapping(summary)
        self.content_address = _address(content_address, "release gate address", GATE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if (self.version, self.boundary) != (VERSION, BOUNDARY) or self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)):
            raise ValidationError("release gate structure does not replay")
        if tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("release gate checks are not the canonical set")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count:
            raise ValidationError("release gate check counters do not replay")
        if (self.release_ready, self.state) != (self.failed_count == 0, "ready" if self.failed_count == 0 else "blocked"):
            raise ValidationError("release gate readiness does not replay")
        if (self.policy.history_id, self.summary.gate_id, self.summary.history_id) != (self.history_id, self.gate_id, self.history_id):
            raise ValidationError("release gate policy or summary linkage is invalid")
        if (self.summary.history_address, self.summary.policy_address) != (self.history_address, address_policy(self.policy)):
            raise ValidationError("release gate summary addresses do not replay")
        if tuple(self.manifest.artifact_addresses) != (address_checks(self.checks), self.summary.content_address):
            raise ValidationError("release gate manifest artifacts do not replay")
        summary_values = tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1])
        expected_summary = (self.gate_id, self.history_id, self.history_address, address_policy(self.policy), self.check_count, self.passed_count, self.failed_count, self.release_ready, self.state, self.latest_state, self.latest_accepted, self.entry_count, self.regressed_count, self.blocked_count)
        if summary_values != expected_summary:
            raise ValidationError("release gate summary does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release gate crosses the public boundary")
        if not self.content_address.startswith("pending:") and _address_for(self, GATE_PREFIX) != self.content_address:
            raise ValidationError("release gate address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "history_id": self.history_id,
            "history_address": self.history_address,
            "version": self.version,
            "boundary": self.boundary,
            "policy": self.policy.to_dict(),
            "checks": [item.to_dict() for item in self.checks],
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "release_ready": self.release_ready,
            "state": self.state,
            "latest_state": self.latest_state,
            "latest_accepted": self.latest_accepted,
            "entry_count": self.entry_count,
            "regressed_count": self.regressed_count,
            "blocked_count": self.blocked_count,
            "manifest": self.manifest.to_dict(),
            "summary": self.summary.to_dict(),
            "content_address": self.content_address,
        }

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"policy", "checks", "manifest", "summary"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseGate:
        value = _mapping(value, "release gate")
        _strict(value, set(cls.FIELDS), "release gate")
        return cls(*(value[field] for field in cls.FIELDS))


def address_gate(value: ReleaseGate) -> str:
    if not isinstance(value, ReleaseGate):
        raise ValidationError("release gate address requires a typed gate")
    return _address_for(value, GATE_PREFIX)


def _policy_for(history: Any, gate_id: str, policy: GatePolicy | Mapping[str, Any] | None) -> GatePolicy:
    if policy is None:
        return build_policy(gate_id, history.history_id)
    typed = policy if isinstance(policy, GatePolicy) else GatePolicy.from_mapping(policy)
    if typed.history_id != history.history_id:
        raise ValidationError("release gate policy history identity does not match")
    return typed


def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> GateCheck:
    item = GateCheck(ordinal, check_id, passed, "info" if passed else "error", _display(actual), _display(expected), detail, f"pending:{CHECK_PREFIX}")
    return _seal(item, address_check)


def build_policy(gate_id: str, history_id: str, *, minimum_entries: int = 1, maximum_regressed: int = 0, maximum_blocked: int = 0, require_latest_ready: bool = True, require_latest_accepted: bool = True, allow_unchanged: bool = True) -> GatePolicy:
    return _seal(GatePolicy(f"{_label(gate_id, 'release gate ID')}-policy", history_id, minimum_entries, maximum_regressed, maximum_blocked, require_latest_ready, require_latest_accepted, allow_unchanged, f"pending:{POLICY_PREFIX}"), address_policy)


def build_gate(history: Any, *, gate_id: str = DEFAULT_GATE_ID, policy: GatePolicy | Mapping[str, Any] | None = None) -> ReleaseGate:
    if not isinstance(history, history_model.DownloadedDataQualityDiffGateRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffRuntimeRegistryHistoryDiffRuntimeRegistryHistory):
        raise ValidationError("release gate requires a typed history")
    history_model.verify_history(history)
    gate_id = _label(gate_id, "release gate ID")
    policy_value = _policy_for(history, gate_id, policy)
    latest = history.entries[-1] if history.entries else None
    checks = (
        _check(1, "history_present", history.entry_count > 0, history.entry_count, "> 0", "history must contain at least one snapshot"),
        _check(2, "minimum_entries", history.entry_count >= policy_value.minimum_entries, history.entry_count, f">= {policy_value.minimum_entries}", "history depth must meet policy"),
        _check(3, "history_accepted", history.accepted, history.accepted, True, "latest history disposition must be accepted"),
        _check(4, "latest_ready", not policy_value.require_latest_ready or (latest is not None and latest.state == "ready"), latest.state if latest else "empty", "ready" if policy_value.require_latest_ready else "not-required", "latest registry state must satisfy readiness policy"),
        _check(5, "latest_accepted", not policy_value.require_latest_accepted or (latest is not None and latest.accepted), latest.accepted if latest else False, True if policy_value.require_latest_accepted else "not-required", "latest registry acceptance must satisfy policy"),
        _check(6, "regression_budget", history.regressed_count <= policy_value.maximum_regressed, history.regressed_count, f"<= {policy_value.maximum_regressed}", "history regression count must remain within budget"),
        _check(7, "blocked_budget", history.latest_blocked_count <= policy_value.maximum_blocked, history.latest_blocked_count, f"<= {policy_value.maximum_blocked}", "latest blocked count must remain within budget"),
        _check(8, "unchanged_policy", policy_value.allow_unchanged or history.unchanged_count == 0, history.unchanged_count, "allowed" if policy_value.allow_unchanged else "== 0", "unchanged transitions follow explicit policy"),
        _check(9, "transition_conservation", sum((history.initial_count, history.improved_count, history.regressed_count, history.unchanged_count, history.changed_count)) == history.entry_count, history.entry_count, "sum transitions", "history transition counters must conserve entries"),
        _check(10, "identity_link", bool(history.registry_id == (history.entries[0].registry_id if history.entries else "")), history.registry_id, "history identity", "all snapshots must share the history identity"),
        _check(11, "address_integrity", history.content_address.startswith(history_model.HISTORY_PREFIX + ":"), history.content_address, history_model.HISTORY_PREFIX, "history address must use the canonical namespace"),
        _check(12, "public_boundary", _public(history.compact()), True, True, "release output must remain value-only and path-free"),
    )
    passed_count = sum(item.passed for item in checks)
    failed_count = len(checks) - passed_count
    latest_state = latest.state if latest else "empty"
    latest_accepted = latest.accepted if latest else False
    summary = GateSummary(gate_id, history.history_id, history.content_address, address_policy(policy_value), len(checks), passed_count, failed_count, failed_count == 0, "ready" if failed_count == 0 else "blocked", latest_state, latest_accepted, history.entry_count, history.regressed_count, history.latest_blocked_count, f"pending:{SUMMARY_PREFIX}")
    _seal(summary, address_summary)
    manifest = GateManifest(gate_id, history.history_id, VERSION, BOUNDARY, FILES, (address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}")
    _seal(manifest, address_manifest)
    value = ReleaseGate(gate_id, history.history_id, history.content_address, VERSION, BOUNDARY, policy_value, checks, len(checks), passed_count, failed_count, failed_count == 0, "ready" if failed_count == 0 else "blocked", latest_state, latest_accepted, history.entry_count, history.regressed_count, history.latest_blocked_count, manifest, summary, f"pending:{GATE_PREFIX}")
    return _seal(value, address_gate)


def verify_gate(value: ReleaseGate) -> ReleaseGate:
    if not isinstance(value, ReleaseGate):
        raise ValidationError("release gate verification requires a typed gate")
    value._validate()
    return value


def gate_from_mapping(value: Mapping[str, Any]) -> ReleaseGate:
    return ReleaseGate.from_mapping(value)


def gate_json(value: ReleaseGate) -> str:
    return canonical_json(verify_gate(value).to_dict())


def checks_json(value: ReleaseGate | Sequence[GateCheck]) -> str:
    checks = value.checks if isinstance(value, ReleaseGate) else tuple(value)
    return canonical_json({"checks": [item.to_dict() for item in checks], "content_address": address_checks(checks)})


def summary_json(value: ReleaseGate) -> str:
    return canonical_json(verify_gate(value).summary.to_dict())


def manifest_json(value: ReleaseGate) -> str:
    return canonical_json(verify_gate(value).manifest.to_dict())


def gate_csv(value: ReleaseGate) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_gate(value).checks)
    return output.getvalue()


def render_gate_markdown(value: ReleaseGate) -> str:
    value = verify_gate(value)
    lines = [
        f"# Downloaded-data quality release gate {value.gate_id}",
        "",
        f"- State: {value.state}",
        f"- Release ready: {value.release_ready}",
        f"- History: {value.history_id}",
        f"- Checks: {value.passed_count}/{value.check_count} passed",
        "",
        "| # | check | result | severity | actual | expected |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.severity} | {item.actual} | {item.expected} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    atomic_write_bytes(path, canonical_json(value).encode("utf-8"), field="release gate document")


def persist_gate(value: ReleaseGate, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_gate(value)
    destination = Path(destination)
    _validate_parent(destination.parent, "release gate destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("release gate destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-release-gate-", dir=str(destination.parent)))
    try:
        documents = {"manifest.json": value.manifest.to_dict(), "gate.json": value.to_dict(), "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("release gate destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = _strict_json_loads(read_text(path, field="release gate artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("release gate artifact is not valid JSON") from error
    return _mapping(value, "release gate artifact")


def load_gate(destination: str | Path) -> ReleaseGate:
    destination = Path(destination)
    _validate_parent(destination.parent, "release gate input")
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("release gate source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("release gate directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        if read_text(destination / name, field="release gate artifact") != canonical_json(document):
            raise ValidationError("release gate artifact is not canonical")
        if len(canonical_json(document).encode("utf-8")) > MAX_GATE_BYTES:
            raise ValidationError("release gate artifact exceeds its size bound")
    value = gate_from_mapping(documents["gate.json"])
    manifest = GateManifest.from_mapping(documents["manifest.json"])
    checks_document = documents["checks.json"]
    _strict(checks_document, set(CHECKS_FIELDS), "release gate checks document")
    checks = tuple(GateCheck.from_mapping(item) for item in _sequence(checks_document["checks"], "release gate checks document checks", MAX_CHECKS))
    summary = GateSummary.from_mapping(documents["summary.json"])
    if manifest.to_dict() != value.manifest.to_dict() or summary.to_dict() != value.summary.to_dict() or list(item.to_dict() for item in checks) != value.to_dict()["checks"] or checks_document["content_address"] != address_checks(value.checks):
        raise ValidationError("release gate component documents do not replay gate.json")
    return value


def run_gate(history: Any, *, gate_id: str = DEFAULT_GATE_ID, policy: GatePolicy | Mapping[str, Any] | None = None, destination: str | Path | None = None, overwrite: bool = False) -> ReleaseGate:
    value = build_gate(history, gate_id=gate_id, policy=policy)
    if destination is not None:
        persist_gate(value, destination, overwrite=overwrite)
    return value


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GatePolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {"policy_id": {"type": "string"}, "history_id": {"type": "string"}, "minimum_entries": {"type": "integer", "minimum": 0}, "maximum_regressed": {"type": "integer", "minimum": 0}, "maximum_blocked": {"type": "integer", "minimum": 0}, "require_latest_ready": {"type": "boolean"}, "require_latest_accepted": {"type": "boolean"}, "allow_unchanged": {"type": "boolean"}, "content_address": {"type": "string"}}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "severity": {"enum": list(SEVERITIES)}, "actual": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"gate_id": {"type": "string"}, "history_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"gate_id": {"type": "string"}, "history_id": {"type": "string"}, "history_address": {"type": "string"}, "policy_address": {"type": "string"}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "release_ready": {"type": "boolean"}, "state": {"enum": list(STATES)}, "latest_state": {"type": "string"}, "latest_accepted": {"type": "boolean"}, "entry_count": {"type": "integer"}, "regressed_count": {"type": "integer"}, "blocked_count": {"type": "integer"}, "content_address": {"type": "string"}}}


def gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGate", "type": "object", "additionalProperties": False, "required": list(GATE_FIELDS), "properties": {"gate_id": {"type": "string"}, "history_id": {"type": "string"}, "history_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "policy": {"type": "object", "additionalProperties": False}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "release_ready": {"type": "boolean"}, "state": {"enum": list(STATES)}, "latest_state": {"type": "string"}, "latest_accepted": {"type": "boolean"}, "entry_count": {"type": "integer"}, "regressed_count": {"type": "integer"}, "blocked_count": {"type": "integer"}, "manifest": {"type": "object"}, "summary": {"type": "object"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "check_ids": CHECK_IDS, "severities": SEVERITIES, "states": STATES, "limits": {"max_checks": MAX_CHECKS, "max_gate_bytes": MAX_GATE_BYTES}, "features": ("history-linked release policy", "regression and blocked budgets", "latest readiness and acceptance requirements", "unchanged-transition policy", "independent check explanations", "exact four-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "GATE_PREFIX", "POLICY_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_GATE_ID", "FILES", "ARTIFACT_FILES", "MANIFEST_ARTIFACT_FILES", "SEVERITIES", "STATES", "MAX_CHECKS", "MAX_GATE_BYTES", "POLICY_FIELDS", "CHECK_FIELDS", "CHECKS_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "GATE_FIELDS", "CHECK_IDS", "GatePolicy", "GateCheck", "GateManifest", "GateSummary", "ReleaseGate", "address_policy", "address_check", "address_checks", "address_manifest", "address_summary", "address_gate", "build_policy", "build_gate", "verify_gate", "gate_from_mapping", "gate_json", "checks_json", "summary_json", "manifest_json", "gate_csv", "render_gate_markdown", "persist_gate", "load_gate", "run_gate", "policy_schema", "check_schema", "manifest_schema", "summary_schema", "gate_schema", "capabilities"]
