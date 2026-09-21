"""Turn a D485 policy scenario into an explicit release-gate decision."""

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

from . import downloaded_data_quality_d485_history_diff_runtime_policy_scenario as scenario_model
from . import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_audit as scenario_audit_model
from . import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query as scenario_query_model
from . import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query_audit as scenario_query_audit_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = scenario_model.VERSION + "-gate-v1"
BOUNDARY = scenario_model.BOUNDARY + "_gate"
GATE_PREFIX = "glio-noncode-d486-history-diff-runtime-policy-scenario-release-gate"
POLICY_PREFIX = GATE_PREFIX + "-policy"
CHECK_PREFIX = GATE_PREFIX + "-check"
CHECKS_PREFIX = GATE_PREFIX + "-checks"
MANIFEST_PREFIX = GATE_PREFIX + "-manifest"
SUMMARY_PREFIX = GATE_PREFIX + "-summary"
DEFAULT_GATE_ID = GATE_PREFIX
FILES = ("manifest.json", "gate.json", "policy.json", "checks.json", "summary.json")
ARTIFACT_FILES = ("policy.json", "checks.json", "summary.json")
STATES = ("ready", "blocked")
SEVERITIES = ("info", "error")
MAX_CHECKS = 18
MAX_GATE_BYTES = 32 * 1024 * 1024
POLICY_FIELDS = ("policy_id", "scenario_id", "minimum_ready", "maximum_blocked", "minimum_added_margin", "minimum_removed_margin", "minimum_changed_margin", "disallowed_risk_flags", "require_scenario_accepted", "require_scenario_release_ready", "require_audit_accepted", "require_query_complete", "require_query_audit_accepted", "content_address")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "severity", "actual", "expected", "detail", "content_address")
MANIFEST_FIELDS = ("gate_id", "scenario_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("gate_id", "scenario_id", "scenario_address", "scenario_state", "ready_count", "blocked_count", "minimum_added_margin", "minimum_removed_margin", "minimum_changed_margin", "risk_count", "disallowed_risk_count", "audit_accepted", "query_complete", "query_audit_accepted", "accepted", "release_ready", "state", "content_address")
GATE_FIELDS = ("gate_id", "version", "boundary", "scenario_id", "scenario_address", "scenario_state", "scenario_accepted", "scenario_release_ready", "audit_address", "query_address", "query_audit_address", "audit_accepted", "query_complete", "query_audit_accepted", "policy", "checks", "check_count", "passed_count", "failed_count", "accepted", "release_ready", "state", "summary", "manifest", "content_address")
CHECK_IDS = ("scenario_present", "scenario_acceptance", "scenario_readiness", "minimum_ready", "maximum_blocked", "added_margin_floor", "removed_margin_floor", "changed_margin_floor", "risk_allowlist", "audit_evidence", "query_evidence", "query_complete", "query_audit_evidence", "scenario_identity", "evidence_identity", "policy_integrity", "release_disposition", "public_boundary")


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
def _signed(value: Any, field: str) -> int:
    maximum = scenario_model.runtime_model.diff_model.MAX_ITEMS * 2
    if isinstance(value, bool) or not isinstance(value, int) or value < -scenario_model.runtime_model.diff_model.MAX_ITEMS or value > maximum: raise ValidationError(f"{field} is outside its bound")
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
def _public(value: Any) -> bool: return scenario_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class GatePolicy:
    FIELDS = POLICY_FIELDS
    def __init__(self, policy_id: str, scenario_id: str, minimum_ready: int, maximum_blocked: int, minimum_added_margin: int, minimum_removed_margin: int, minimum_changed_margin: int, disallowed_risk_flags: Sequence[str], require_scenario_accepted: bool, require_scenario_release_ready: bool, require_audit_accepted: bool, require_query_complete: bool, require_query_audit_accepted: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "release gate policy ID"); self.scenario_id = _label(scenario_id, "release gate policy scenario ID"); self.minimum_ready = _count(minimum_ready, "release gate minimum ready", scenario_model.MAX_ENTRIES); self.maximum_blocked = _count(maximum_blocked, "release gate maximum blocked", scenario_model.MAX_ENTRIES); self.minimum_added_margin = _signed(minimum_added_margin, "release gate minimum added margin"); self.minimum_removed_margin = _signed(minimum_removed_margin, "release gate minimum removed margin"); self.minimum_changed_margin = _signed(minimum_changed_margin, "release gate minimum changed margin"); self.disallowed_risk_flags = tuple(_label(item, "release gate disallowed risk flag") for item in _sequence(disallowed_risk_flags, "release gate disallowed risk flags", len(scenario_model.RISK_FLAGS))); self.require_scenario_accepted = _bool(require_scenario_accepted, "release gate scenario acceptance requirement"); self.require_scenario_release_ready = _bool(require_scenario_release_ready, "release gate scenario readiness requirement"); self.require_audit_accepted = _bool(require_audit_accepted, "release gate audit requirement"); self.require_query_complete = _bool(require_query_complete, "release gate query completeness requirement"); self.require_query_audit_accepted = _bool(require_query_audit_accepted, "release gate query audit requirement"); self.content_address = _address(content_address, "release gate policy address", POLICY_PREFIX); self._validate()
    def _validate(self) -> None:
        if len(set(self.disallowed_risk_flags)) != len(self.disallowed_risk_flags) or any(item not in scenario_model.RISK_FLAGS for item in self.disallowed_risk_flags): raise ValidationError("release gate disallowed risk flags are unsupported or duplicated")
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address: raise ValidationError("release gate policy address does not replay")
        if not _public(self.to_dict()): raise ValidationError("release gate policy crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"disallowed_risk_flags": list(self.disallowed_risk_flags), "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GatePolicy":
        value = _mapping(value, "release gate policy"); _strict(value, set(cls.FIELDS), "release gate policy"); return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: GatePolicy) -> str:
    if not isinstance(value, GatePolicy): raise ValidationError("release gate policy address requires a typed policy")
    return _address_for(value, POLICY_PREFIX)


class GateCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release gate check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "release gate check ID"); self.passed = _bool(passed, "release gate check result")
        if severity not in SEVERITIES: raise ValidationError("release gate check severity is unsupported")
        self.severity = severity; self.actual = _text(actual, "release gate check actual", 32768); self.expected = _text(expected, "release gate check expected", 32768); self.detail = _text(detail, "release gate check detail", 4096); self.content_address = _address(content_address, "release gate check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or (self.passed and self.severity == "error"): raise ValidationError("release gate check identity or severity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("release gate check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("release gate check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GateCheck":
        value = _mapping(value, "release gate check"); _strict(value, set(cls.FIELDS), "release gate check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: GateCheck) -> str:
    if not isinstance(value, GateCheck): raise ValidationError("release gate check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)
def address_checks(value: Sequence[GateCheck]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, GateCheck) for item in typed): raise ValidationError("release gate checks address requires typed checks")
    return content_hash({"checks": [item.to_dict() for item in typed]}, prefix=CHECKS_PREFIX)


class GateManifest:
    FIELDS = MANIFEST_FIELDS
    def __init__(self, gate_id: str, scenario_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.gate_id = _label(gate_id, "release gate manifest ID"); self.scenario_id = _label(scenario_id, "release gate manifest scenario ID"); self.version = _text(version, "release gate manifest version", 1024); self.boundary = _text(boundary, "release gate manifest boundary", 2048); self.files = tuple(_text(item, "release gate manifest file", 128) for item in _sequence(files, "release gate manifest files", len(FILES))); self.artifact_addresses = tuple(_address(item, "release gate manifest artifact address") for item in _sequence(artifact_addresses, "release gate manifest artifact addresses", len(ARTIFACT_FILES))); self.content_address = _address(content_address, "release gate manifest address", MANIFEST_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY: raise ValidationError("release gate manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address: raise ValidationError("release gate manifest address does not replay")
        if not _public(self.to_dict()): raise ValidationError("release gate manifest crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GateManifest":
        value = _mapping(value, "release gate manifest"); _strict(value, set(cls.FIELDS), "release gate manifest"); return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: GateManifest) -> str:
    if not isinstance(value, GateManifest): raise ValidationError("release gate manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class GateSummary:
    FIELDS = SUMMARY_FIELDS
    def __init__(self, gate_id: str, scenario_id: str, scenario_address: str, scenario_state: str, ready_count: int, blocked_count: int, minimum_added_margin: int, minimum_removed_margin: int, minimum_changed_margin: int, risk_count: int, disallowed_risk_count: int, audit_accepted: bool, query_complete: bool, query_audit_accepted: bool, accepted: bool, release_ready: bool, state: str, content_address: str) -> None:
        self.gate_id = _label(gate_id, "release gate summary ID"); self.scenario_id = _label(scenario_id, "release gate summary scenario ID"); self.scenario_address = _address(scenario_address, "release gate summary scenario address", scenario_model.SCENARIO_PREFIX); self.scenario_state = _label(scenario_state, "release gate summary scenario state"); self.ready_count = _count(ready_count, "release gate summary ready count", scenario_model.MAX_ENTRIES); self.blocked_count = _count(blocked_count, "release gate summary blocked count", scenario_model.MAX_ENTRIES); self.minimum_added_margin = _signed(minimum_added_margin, "release gate summary added margin"); self.minimum_removed_margin = _signed(minimum_removed_margin, "release gate summary removed margin"); self.minimum_changed_margin = _signed(minimum_changed_margin, "release gate summary changed margin"); self.risk_count = _count(risk_count, "release gate summary risk count", len(scenario_model.RISK_FLAGS)); self.disallowed_risk_count = _count(disallowed_risk_count, "release gate summary disallowed risk count", len(scenario_model.RISK_FLAGS)); self.audit_accepted = _bool(audit_accepted, "release gate summary audit acceptance"); self.query_complete = _bool(query_complete, "release gate summary query completeness"); self.query_audit_accepted = _bool(query_audit_accepted, "release gate summary query audit acceptance"); self.accepted = _bool(accepted, "release gate summary acceptance"); self.release_ready = _bool(release_ready, "release gate summary readiness")
        if state not in STATES: raise ValidationError("release gate summary state is unsupported")
        self.state = state; self.content_address = _address(content_address, "release gate summary address", SUMMARY_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.release_ready != (self.state == "ready"): raise ValidationError("release gate summary readiness does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address: raise ValidationError("release gate summary address does not replay")
        if not _public(self.to_dict()): raise ValidationError("release gate summary crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GateSummary":
        value = _mapping(value, "release gate summary"); _strict(value, set(cls.FIELDS), "release gate summary"); return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: GateSummary) -> str:
    if not isinstance(value, GateSummary): raise ValidationError("release gate summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class ReleaseGate:
    FIELDS = GATE_FIELDS
    def __init__(self, gate_id: str, version: str, boundary: str, scenario_id: str, scenario_address: str, scenario_state: str, scenario_accepted: bool, scenario_release_ready: bool, audit_address: str, query_address: str, query_audit_address: str, audit_accepted: bool, query_complete: bool, query_audit_accepted: bool, policy: Mapping[str, Any] | GatePolicy, checks: Sequence[GateCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, release_ready: bool, state: str, summary: Mapping[str, Any] | GateSummary, manifest: Mapping[str, Any] | GateManifest, content_address: str) -> None:
        self.gate_id = _label(gate_id, "release gate ID"); self.version = _text(version, "release gate version", 1024); self.boundary = _text(boundary, "release gate boundary", 2048); self.scenario_id = _label(scenario_id, "release gate scenario ID"); self.scenario_address = _address(scenario_address, "release gate scenario address", scenario_model.SCENARIO_PREFIX); self.scenario_state = _label(scenario_state, "release gate scenario state"); self.scenario_accepted = _bool(scenario_accepted, "release gate scenario acceptance"); self.scenario_release_ready = _bool(scenario_release_ready, "release gate scenario readiness"); self.audit_address = _address(audit_address, "release gate audit address", scenario_audit_model.AUDIT_PREFIX, required=False); self.query_address = _address(query_address, "release gate query address", scenario_query_model.QUERY_PREFIX, required=False); self.query_audit_address = _address(query_audit_address, "release gate query audit address", scenario_query_audit_model.AUDIT_PREFIX, required=False); self.audit_accepted = _bool(audit_accepted, "release gate audit acceptance"); self.query_complete = _bool(query_complete, "release gate query completeness"); self.query_audit_accepted = _bool(query_audit_accepted, "release gate query audit acceptance"); self.policy = policy if isinstance(policy, GatePolicy) else GatePolicy.from_mapping(_mapping(policy, "release gate policy")); self.checks = tuple(item if isinstance(item, GateCheck) else GateCheck.from_mapping(_mapping(item, "release gate check")) for item in _sequence(checks, "release gate checks", MAX_CHECKS)); self.check_count = _count(check_count, "release gate check count", MAX_CHECKS); self.passed_count = _count(passed_count, "release gate passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "release gate failed count", MAX_CHECKS); self.accepted = _bool(accepted, "release gate acceptance"); self.release_ready = _bool(release_ready, "release gate readiness")
        if state not in STATES: raise ValidationError("release gate state is unsupported")
        self.state = state; self.summary = summary if isinstance(summary, GateSummary) else GateSummary.from_mapping(_mapping(summary, "release gate summary")); self.manifest = manifest if isinstance(manifest, GateManifest) else GateManifest.from_mapping(_mapping(manifest, "release gate manifest")); self.content_address = _address(content_address, "release gate address", GATE_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.policy.scenario_id != self.scenario_id or self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.release_ready != (self.state == "ready") or self.accepted != self.scenario_accepted: raise ValidationError("release gate identity or counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("release gate checks are not canonical")
        expected_summary = (self.gate_id, self.scenario_id, self.scenario_address, self.scenario_state, self.summary.ready_count, self.summary.blocked_count, self.summary.minimum_added_margin, self.summary.minimum_removed_margin, self.summary.minimum_changed_margin, self.summary.risk_count, self.summary.disallowed_risk_count, self.audit_accepted, self.query_complete, self.query_audit_accepted, self.accepted, self.release_ready, self.state)
        if tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1]) != expected_summary or self.summary.content_address != address_summary(self.summary): raise ValidationError("release gate summary does not replay")
        expected_manifest = (self.gate_id, self.scenario_id, VERSION, BOUNDARY, FILES, (self.policy.content_address, address_checks(self.checks), self.summary.content_address)); actual_manifest = (self.manifest.gate_id, self.manifest.scenario_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest): raise ValidationError("release gate manifest does not replay")
        if not self.content_address.startswith("pending:") and address_gate(self) != self.content_address: raise ValidationError("release gate address does not replay")
        if not _public(self.to_dict()): raise ValidationError("release gate crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"gate_id": self.gate_id, "version": self.version, "boundary": self.boundary, "scenario_id": self.scenario_id, "scenario_address": self.scenario_address, "scenario_state": self.scenario_state, "scenario_accepted": self.scenario_accepted, "scenario_release_ready": self.scenario_release_ready, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "audit_accepted": self.audit_accepted, "query_complete": self.query_complete, "query_audit_accepted": self.query_audit_accepted, "policy": self.policy.to_dict(), "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "summary": self.summary.to_dict(), "manifest": self.manifest.to_dict(), "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReleaseGate":
        value = _mapping(value, "release gate"); _strict(value, set(cls.FIELDS), "release gate"); return cls(*(value[field] for field in cls.FIELDS))


def address_gate(value: ReleaseGate) -> str:
    if not isinstance(value, ReleaseGate): raise ValidationError("release gate address requires a typed gate")
    return _address_for(value, GATE_PREFIX)
def build_policy(policy_id: str, scenario_id: str, *, minimum_ready: int = 1, maximum_blocked: int = 0, minimum_added_margin: int = 0, minimum_removed_margin: int = 0, minimum_changed_margin: int = 0, disallowed_risk_flags: Sequence[str] = ("blocked_runtime", "zero_added_margin", "zero_removed_margin", "zero_changed_margin"), require_scenario_accepted: bool = True, require_scenario_release_ready: bool = True, require_audit_accepted: bool = True, require_query_complete: bool = True, require_query_audit_accepted: bool = True) -> GatePolicy:
    return _seal(GatePolicy(policy_id, scenario_id, minimum_ready, maximum_blocked, minimum_added_margin, minimum_removed_margin, minimum_changed_margin, disallowed_risk_flags, require_scenario_accepted, require_scenario_release_ready, require_audit_accepted, require_query_complete, require_query_audit_accepted, f"pending:{POLICY_PREFIX}"), address_policy)
def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> GateCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "severity": "info" if passed else "error", "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = GateCheck(**body); return GateCheck(**(body | {"content_address": address_check(provisional)}))
def build_gate(scenario: scenario_model.PolicyScenario, *, gate_id: str = DEFAULT_GATE_ID, policy: GatePolicy | Mapping[str, Any] | None = None, audit: scenario_audit_model.ScenarioAudit | None = None, query: scenario_query_model.ScenarioQuery | None = None, query_audit: scenario_query_audit_model.QueryAudit | None = None) -> ReleaseGate:
    scenario_model.verify_scenario(scenario); if_audit = audit is not None and isinstance(audit, scenario_audit_model.ScenarioAudit); if_query = query is not None and isinstance(query, scenario_query_model.ScenarioQuery); if_query_audit = query_audit is not None and isinstance(query_audit, scenario_query_audit_model.QueryAudit)
    if audit is not None: scenario_audit_model.verify_audit(audit)
    if query is not None: scenario_query_model.verify_query(query)
    if query_audit is not None: scenario_query_audit_model.verify_audit(query_audit)
    gate_policy = policy if isinstance(policy, GatePolicy) else GatePolicy.from_mapping(_mapping(policy, "release gate policy")) if policy is not None else build_policy(f"{gate_id}-policy", scenario.scenario_id)
    audit_address = audit.content_address if if_audit else ""; query_address = query.content_address if if_query else ""; query_audit_address = query_audit.content_address if if_query_audit else ""; audit_accepted = bool(if_audit and audit.accepted); query_complete = bool(if_query and not query.truncated); query_audit_accepted = bool(if_query_audit and query_audit.accepted); disallowed = tuple(item for item in scenario.risk_flags if item in gate_policy.disallowed_risk_flags); evidence_identity = (not if_audit or (audit.scenario_id == scenario.scenario_id and audit.scenario_address == scenario.content_address)) and (not if_query or (query.scenario_id == scenario.scenario_id and query.scenario_address == scenario.content_address)) and (not if_query_audit or (query_audit.scenario_id == scenario.scenario_id and query_audit.query_id == query.query_id))
    checks = (_check(1, "scenario_present", bool(scenario.scenario_id and scenario.content_address), (scenario.scenario_id, bool(scenario.content_address)), "scenario identity and address", "a scenario must be present"), _check(2, "scenario_acceptance", (not gate_policy.require_scenario_accepted) or scenario.accepted, scenario.accepted, True, "scenario must be accepted by policy"), _check(3, "scenario_readiness", (not gate_policy.require_scenario_release_ready) or scenario.release_ready, scenario.release_ready, True, "scenario must be release-ready"), _check(4, "minimum_ready", scenario.ready_count >= gate_policy.minimum_ready, scenario.ready_count, gate_policy.minimum_ready, "ready runtime count must meet the gate floor"), _check(5, "maximum_blocked", scenario.blocked_count <= gate_policy.maximum_blocked, scenario.blocked_count, gate_policy.maximum_blocked, "blocked runtime count must remain within the gate ceiling"), _check(6, "added_margin_floor", scenario.minimum_added_margin >= gate_policy.minimum_added_margin, scenario.minimum_added_margin, gate_policy.minimum_added_margin, "minimum added budget margin must meet the gate floor"), _check(7, "removed_margin_floor", scenario.minimum_removed_margin >= gate_policy.minimum_removed_margin, scenario.minimum_removed_margin, gate_policy.minimum_removed_margin, "minimum removed budget margin must meet the gate floor"), _check(8, "changed_margin_floor", scenario.minimum_changed_margin >= gate_policy.minimum_changed_margin, scenario.minimum_changed_margin, gate_policy.minimum_changed_margin, "minimum changed budget margin must meet the gate floor"), _check(9, "risk_allowlist", not disallowed, scenario.risk_flags, gate_policy.disallowed_risk_flags, "scenario risk flags must be allowed by the gate"), _check(10, "audit_evidence", (not gate_policy.require_audit_accepted) or audit_accepted, audit_accepted, True, "audited scenario evidence must be accepted"), _check(11, "query_evidence", (not gate_policy.require_query_complete) or if_query, if_query, True, "query evidence must be present"), _check(12, "query_complete", (not gate_policy.require_query_complete) or query_complete, query_complete, True, "query evidence must be complete"), _check(13, "query_audit_evidence", (not gate_policy.require_query_audit_accepted) or query_audit_accepted, query_audit_accepted, True, "query audit evidence must be accepted"), _check(14, "scenario_identity", gate_policy.scenario_id == scenario.scenario_id, (gate_policy.scenario_id, scenario.scenario_id), "matching scenario IDs", "gate policy must target the supplied scenario"), _check(15, "evidence_identity", evidence_identity, True, "matching scenario evidence addresses", "all supplied evidence must link to the supplied scenario"), _check(16, "policy_integrity", address_policy(gate_policy) == gate_policy.content_address, gate_policy.content_address, address_policy(gate_policy), "gate policy address must replay"))
    disposition = all(item.passed for item in checks); checks = checks + (_check(17, "release_disposition", disposition, disposition, True, "release readiness is the conjunction of gate checks"), _check(18, "public_boundary", _public(scenario.to_dict()) and _public(gate_policy.to_dict()) and (audit is None or _public(audit.to_dict())) and (query is None or _public(query.to_dict())) and (query_audit is None or _public(query_audit.to_dict())), True, "public values", "gate inputs must remain value-only")); passed = sum(item.passed for item in checks); failed = MAX_CHECKS - passed; release_ready = all(item.passed for item in checks); state = "ready" if release_ready else "blocked"; summary = _seal(GateSummary(gate_id, scenario.scenario_id, scenario.content_address, scenario.state, scenario.ready_count, scenario.blocked_count, scenario.minimum_added_margin, scenario.minimum_removed_margin, scenario.minimum_changed_margin, len(scenario.risk_flags), len(disallowed), audit_accepted, query_complete, query_audit_accepted, scenario.accepted, release_ready, state, f"pending:{SUMMARY_PREFIX}"), address_summary); manifest = _seal(GateManifest(gate_id, scenario.scenario_id, VERSION, BOUNDARY, FILES, (gate_policy.content_address, address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest); return _seal(ReleaseGate(gate_id, VERSION, BOUNDARY, scenario.scenario_id, scenario.content_address, scenario.state, scenario.accepted, scenario.release_ready, audit_address, query_address, query_audit_address, audit_accepted, query_complete, query_audit_accepted, gate_policy, checks, MAX_CHECKS, passed, failed, scenario.accepted, release_ready, state, summary, manifest, f"pending:{GATE_PREFIX}"), address_gate)
def verify_gate(value: ReleaseGate) -> ReleaseGate:
    if not isinstance(value, ReleaseGate): raise ValidationError("release gate verification requires a typed gate")
    value._validate(); return value
def gate_from_mapping(value: Mapping[str, Any]) -> ReleaseGate: return verify_gate(ReleaseGate.from_mapping(value))
def gate_json(value: ReleaseGate) -> str: return canonical_json(verify_gate(value).to_dict())
def policy_json(value: ReleaseGate) -> str: return canonical_json(verify_gate(value).policy.to_dict())
def checks_json(value: ReleaseGate) -> str:
    value = verify_gate(value); return canonical_json({"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)})
def summary_json(value: ReleaseGate) -> str: return canonical_json(verify_gate(value).summary.to_dict())
def manifest_json(value: ReleaseGate) -> str: return canonical_json(verify_gate(value).manifest.to_dict())
def gate_csv(value: ReleaseGate) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_gate(value).checks); return output.getvalue()
def render_gate_markdown(value: ReleaseGate) -> str:
    value = verify_gate(value); lines = [f"# Release gate {value.gate_id}", "", f"- State: {value.state}", f"- Release ready: {str(value.release_ready).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"] ; lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks); return "\n".join(lines) + "\n"
def _write(path: Path, value: Mapping[str, Any]) -> None: path.write_text(canonical_json(value), encoding="utf-8", newline="\n")
def persist_gate(value: ReleaseGate, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_gate(value); destination = Path(destination); _validate_parent(destination.parent, "release gate destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)): raise ValidationError("release gate destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True); temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-release-gate-", dir=str(destination.parent))); documents = {"manifest.json": value.manifest.to_dict(), "gate.json": value.to_dict(), "policy.json": value.policy.to_dict(), "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES: _write(temporary / name, documents[name])
        if destination.exists(): shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True); raise ValidationError("release gate destination could not be written") from error
    return destination
def _read_json(path: Path) -> Mapping[str, Any]:
    try: value = _strict_json_loads(read_text(path, field="release gate artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error: raise ValidationError("release gate artifact is not valid JSON") from error
    return _mapping(value, "release gate artifact")
def load_gate(destination: str | Path) -> ReleaseGate:
    destination = Path(destination); _validate_parent(destination.parent, "release gate input")
    if not destination.is_dir() or destination.is_symlink(): raise ValidationError("release gate source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children): raise ValidationError("release gate directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="release gate artifact") != serialized or len(serialized.encode("utf-8")) > MAX_GATE_BYTES: raise ValidationError("release gate artifact is non-canonical or exceeds its size bound")
    value = gate_from_mapping(documents["gate.json"]); expected = {"manifest.json": value.manifest.to_dict(), "policy.json": value.policy.to_dict(), "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()): raise ValidationError("release gate component documents do not replay gate.json")
    return verify_gate(value)
def run_gate(scenario: scenario_model.PolicyScenario, *, gate_id: str = DEFAULT_GATE_ID, policy: GatePolicy | Mapping[str, Any] | None = None, audit: scenario_audit_model.ScenarioAudit | None = None, query: scenario_query_model.ScenarioQuery | None = None, query_audit: scenario_query_audit_model.QueryAudit | None = None, destination: str | Path | None = None, overwrite: bool = False) -> ReleaseGate:
    value = build_gate(scenario, gate_id=gate_id, policy=policy, audit=audit, query=query, query_audit=query_audit)
    if destination is not None: persist_gate(value, destination, overwrite=overwrite)
    return value
def policy_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGatePolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "array" if field == "disallowed_risk_flags" else "integer" if field.startswith("minimum") or field.startswith("maximum") else "boolean" if field.startswith("require") else "string"} for field in POLICY_FIELDS}}
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def manifest_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}
def summary_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") or field.endswith("margin") else "boolean" if field in ("audit_accepted", "query_complete", "query_audit_accepted", "accepted", "release_ready") else "string"} for field in SUMMARY_FIELDS}}
def gate_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGate", "type": "object", "additionalProperties": False, "required": list(GATE_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "object" if field in ("policy", "summary", "manifest") else "integer" if field.endswith("count") else "boolean" if field in ("scenario_accepted", "scenario_release_ready", "audit_accepted", "query_complete", "query_audit_accepted", "accepted", "release_ready") else "string"} for field in GATE_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "check_ids": CHECK_IDS, "states": STATES, "max_checks": MAX_CHECKS, "features": ("scenario release promotion gate", "risk allowlists and budget margin floors", "audit and complete-query evidence requirements", "exact five-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "GATE_PREFIX", "POLICY_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_GATE_ID", "FILES", "ARTIFACT_FILES", "STATES", "SEVERITIES", "MAX_CHECKS", "MAX_GATE_BYTES", "POLICY_FIELDS", "CHECK_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "GATE_FIELDS", "CHECK_IDS", "GatePolicy", "GateCheck", "GateManifest", "GateSummary", "ReleaseGate", "address_policy", "address_check", "address_checks", "address_manifest", "address_summary", "address_gate", "build_policy", "build_gate", "verify_gate", "gate_from_mapping", "gate_json", "policy_json", "checks_json", "summary_json", "manifest_json", "gate_csv", "render_gate_markdown", "persist_gate", "load_gate", "run_gate", "policy_schema", "check_schema", "manifest_schema", "summary_schema", "gate_schema", "capabilities"]
