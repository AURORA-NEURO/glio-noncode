"""Append-only ledger for successive D486 release-gate decisions."""

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

from . import downloaded_data_quality_d486_history_diff_runtime_policy_scenario_release_gate as gate_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = gate_model.VERSION + "-ledger-v1"
BOUNDARY = gate_model.BOUNDARY + "_ledger"
LEDGER_PREFIX = "glio-noncode-d487-history-diff-runtime-policy-scenario-release-gate-ledger"
POLICY_PREFIX = LEDGER_PREFIX + "-policy"
ENTRY_PREFIX = LEDGER_PREFIX + "-entry"
ENTRIES_PREFIX = LEDGER_PREFIX + "-entries"
CHECK_PREFIX = LEDGER_PREFIX + "-check"
CHECKS_PREFIX = LEDGER_PREFIX + "-checks"
MANIFEST_PREFIX = LEDGER_PREFIX + "-manifest"
SUMMARY_PREFIX = LEDGER_PREFIX + "-summary"
DEFAULT_LEDGER_ID = LEDGER_PREFIX
FILES = ("manifest.json", "ledger.json", "policy.json", "entries.json", "checks.json", "summary.json")
ARTIFACT_FILES = ("policy.json", "entries.json", "checks.json", "summary.json")
STATES = ("empty", "ready", "blocked")
TRANSITIONS = ("initial", "promoted", "regressed", "unchanged", "changed")
SEVERITIES = ("info", "error")
MAX_ENTRIES = 128
MAX_CHECKS = 19
MAX_LEDGER_BYTES = 32 * 1024 * 1024
POLICY_FIELDS = ("policy_id", "ledger_id", "minimum_decisions", "minimum_ready", "maximum_blocked", "require_same_scenario", "require_unique_gate_ids", "require_unique_gate_addresses", "require_contiguous_sequence", "require_supersession_links", "require_final_ready", "allow_reopened", "content_address")
ENTRY_FIELDS = ("ordinal", "decision_id", "gate_id", "gate_address", "scenario_id", "scenario_address", "state", "release_ready", "accepted", "passed_count", "failed_count", "transition", "predecessor_address", "supersedes_decision_id", "supersedes_entry_address", "content_address")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "severity", "actual", "expected", "detail", "content_address")
MANIFEST_FIELDS = ("ledger_id", "scenario_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("ledger_id", "scenario_id", "entry_count", "ready_count", "blocked_count", "accepted_count", "final_ready", "state", "transition", "superseded_count", "head_decision_id", "head_entry_address", "accepted", "release_ready", "content_address")
LEDGER_FIELDS = ("ledger_id", "version", "boundary", "policy", "entry_count", "ready_count", "blocked_count", "accepted_count", "final_ready", "state", "transition", "superseded_count", "head_decision_id", "head_entry_address", "accepted", "release_ready", "manifest", "summary", "entries", "checks", "content_address")
CHECK_IDS = ("nonempty", "minimum_decisions", "minimum_ready", "blocked_budget", "same_scenario", "unique_gate_ids", "unique_gate_addresses", "contiguous_sequence", "predecessor_chain", "supersession_links", "transition_replay", "counter_replay", "final_ready_policy", "reopen_policy", "accepted_policy", "head_integrity", "policy_integrity", "release_disposition", "public_boundary")


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
def _public(value: Any) -> bool: return gate_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class LedgerPolicy:
    FIELDS = POLICY_FIELDS
    def __init__(self, policy_id: str, ledger_id: str, minimum_decisions: int, minimum_ready: int, maximum_blocked: int, require_same_scenario: bool, require_unique_gate_ids: bool, require_unique_gate_addresses: bool, require_contiguous_sequence: bool, require_supersession_links: bool, require_final_ready: bool, allow_reopened: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "gate ledger policy ID"); self.ledger_id = _label(ledger_id, "gate ledger policy ledger ID"); self.minimum_decisions = _count(minimum_decisions, "gate ledger minimum decisions", MAX_ENTRIES, lower=1); self.minimum_ready = _count(minimum_ready, "gate ledger minimum ready", MAX_ENTRIES); self.maximum_blocked = _count(maximum_blocked, "gate ledger maximum blocked", MAX_ENTRIES); self.require_same_scenario = _bool(require_same_scenario, "gate ledger same-scenario requirement"); self.require_unique_gate_ids = _bool(require_unique_gate_ids, "gate ledger unique-gate requirement"); self.require_unique_gate_addresses = _bool(require_unique_gate_addresses, "gate ledger unique-address requirement"); self.require_contiguous_sequence = _bool(require_contiguous_sequence, "gate ledger contiguous-sequence requirement"); self.require_supersession_links = _bool(require_supersession_links, "gate ledger supersession requirement"); self.require_final_ready = _bool(require_final_ready, "gate ledger final-readiness requirement"); self.allow_reopened = _bool(allow_reopened, "gate ledger reopened-decision policy"); self.content_address = _address(content_address, "gate ledger policy address", POLICY_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.minimum_ready > self.minimum_decisions: raise ValidationError("gate ledger policy thresholds are inconsistent")
        if not self.content_address.startswith("pending:") and _address_for(self, POLICY_PREFIX) != self.content_address: raise ValidationError("gate ledger policy address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger policy crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerPolicy":
        value = _mapping(value, "gate ledger policy"); _strict(value, set(cls.FIELDS), "gate ledger policy"); return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: LedgerPolicy) -> str:
    if not isinstance(value, LedgerPolicy): raise ValidationError("gate ledger policy address requires a typed policy")
    return _address_for(value, POLICY_PREFIX)


class LedgerEntry:
    FIELDS = ENTRY_FIELDS
    def __init__(self, ordinal: int, decision_id: str, gate_id: str, gate_address: str, scenario_id: str, scenario_address: str, state: str, release_ready: bool, accepted: bool, passed_count: int, failed_count: int, transition: str, predecessor_address: str, supersedes_decision_id: str, supersedes_entry_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate ledger entry ordinal", MAX_ENTRIES, lower=1); self.decision_id = _label(decision_id, "gate ledger decision ID"); self.gate_id = _label(gate_id, "gate ledger gate ID"); self.gate_address = _address(gate_address, "gate ledger gate address", gate_model.GATE_PREFIX); self.scenario_id = _label(scenario_id, "gate ledger scenario ID"); self.scenario_address = _address(scenario_address, "gate ledger scenario address", gate_model.scenario_model.SCENARIO_PREFIX)
        if state not in gate_model.STATES: raise ValidationError("gate ledger entry state is unsupported")
        self.state = state; self.release_ready = _bool(release_ready, "gate ledger entry readiness"); self.accepted = _bool(accepted, "gate ledger entry acceptance"); self.passed_count = _count(passed_count, "gate ledger entry passed count", gate_model.MAX_CHECKS); self.failed_count = _count(failed_count, "gate ledger entry failed count", gate_model.MAX_CHECKS); self.transition = _label(transition, "gate ledger entry transition")
        self.predecessor_address = _address(predecessor_address, "gate ledger predecessor address", ENTRY_PREFIX, required=False); self.supersedes_decision_id = _label(supersedes_decision_id, "gate ledger superseded decision ID", required=False); self.supersedes_entry_address = _address(supersedes_entry_address, "gate ledger superseded entry address", ENTRY_PREFIX, required=False); self.content_address = _address(content_address, "gate ledger entry address", ENTRY_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.transition not in TRANSITIONS or self.release_ready != (self.state == "ready") or self.passed_count + self.failed_count != gate_model.MAX_CHECKS: raise ValidationError("gate ledger entry disposition does not replay")
        if bool(self.supersedes_decision_id) != bool(self.supersedes_entry_address): raise ValidationError("gate ledger supersession fields must be paired")
        if not self.content_address.startswith("pending:") and _address_for(self, ENTRY_PREFIX) != self.content_address: raise ValidationError("gate ledger entry address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger entry crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerEntry":
        value = _mapping(value, "gate ledger entry"); _strict(value, set(cls.FIELDS), "gate ledger entry"); return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: LedgerEntry) -> str:
    if not isinstance(value, LedgerEntry): raise ValidationError("gate ledger entry address requires a typed entry")
    return _address_for(value, ENTRY_PREFIX)
def address_entries(value: Sequence[LedgerEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, LedgerEntry) for item in typed): raise ValidationError("gate ledger entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class LedgerCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate ledger check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "gate ledger check ID"); self.passed = _bool(passed, "gate ledger check result")
        if severity not in SEVERITIES: raise ValidationError("gate ledger check severity is unsupported")
        self.severity = severity; self.actual = _text(actual, "gate ledger check actual", 32768); self.expected = _text(expected, "gate ledger check expected", 32768); self.detail = _text(detail, "gate ledger check detail", 4096); self.content_address = _address(content_address, "gate ledger check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS or (self.passed and self.severity == "error"): raise ValidationError("gate ledger check identity or severity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("gate ledger check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerCheck":
        value = _mapping(value, "gate ledger check"); _strict(value, set(cls.FIELDS), "gate ledger check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: LedgerCheck) -> str:
    if not isinstance(value, LedgerCheck): raise ValidationError("gate ledger check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)
def address_checks(value: Sequence[LedgerCheck]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, LedgerCheck) for item in typed): raise ValidationError("gate ledger checks address requires typed checks")
    return content_hash({"checks": [item.to_dict() for item in typed]}, prefix=CHECKS_PREFIX)


class LedgerManifest:
    FIELDS = MANIFEST_FIELDS
    def __init__(self, ledger_id: str, scenario_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.ledger_id = _label(ledger_id, "gate ledger manifest ID"); self.scenario_id = _label(scenario_id, "gate ledger manifest scenario ID", required=False); self.version = _text(version, "gate ledger manifest version", 1024); self.boundary = _text(boundary, "gate ledger manifest boundary", 2048); self.files = tuple(_text(item, "gate ledger manifest file", 128) for item in _sequence(files, "gate ledger manifest files", len(FILES))); self.artifact_addresses = tuple(_address(item, "gate ledger manifest artifact address") for item in _sequence(artifact_addresses, "gate ledger manifest artifact addresses", len(ARTIFACT_FILES))); self.content_address = _address(content_address, "gate ledger manifest address", MANIFEST_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES) or self.version != VERSION or self.boundary != BOUNDARY: raise ValidationError("gate ledger manifest is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address: raise ValidationError("gate ledger manifest address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger manifest crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerManifest":
        value = _mapping(value, "gate ledger manifest"); _strict(value, set(cls.FIELDS), "gate ledger manifest"); return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: LedgerManifest) -> str:
    if not isinstance(value, LedgerManifest): raise ValidationError("gate ledger manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class LedgerSummary:
    FIELDS = SUMMARY_FIELDS
    def __init__(self, ledger_id: str, scenario_id: str, entry_count: int, ready_count: int, blocked_count: int, accepted_count: int, final_ready: bool, state: str, transition: str, superseded_count: int, head_decision_id: str, head_entry_address: str, accepted: bool, release_ready: bool, content_address: str) -> None:
        self.ledger_id = _label(ledger_id, "gate ledger summary ID"); self.scenario_id = _label(scenario_id, "gate ledger summary scenario ID", required=False); self.entry_count = _count(entry_count, "gate ledger summary entry count", MAX_ENTRIES); self.ready_count = _count(ready_count, "gate ledger summary ready count", MAX_ENTRIES); self.blocked_count = _count(blocked_count, "gate ledger summary blocked count", MAX_ENTRIES); self.accepted_count = _count(accepted_count, "gate ledger summary accepted count", MAX_ENTRIES); self.final_ready = _bool(final_ready, "gate ledger summary final readiness")
        if state not in STATES or transition not in TRANSITIONS: raise ValidationError("gate ledger summary state or transition is unsupported")
        self.state = state; self.transition = transition; self.superseded_count = _count(superseded_count, "gate ledger summary superseded count", MAX_ENTRIES); self.head_decision_id = _label(head_decision_id, "gate ledger summary head decision ID", required=False); self.head_entry_address = _address(head_entry_address, "gate ledger summary head entry address", ENTRY_PREFIX, required=False); self.accepted = _bool(accepted, "gate ledger summary acceptance"); self.release_ready = _bool(release_ready, "gate ledger summary readiness"); self.content_address = _address(content_address, "gate ledger summary address", SUMMARY_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.ready_count + self.blocked_count != self.entry_count or self.accepted_count > self.entry_count or self.final_ready != (self.state == "ready") or self.release_ready and self.entry_count == 0: raise ValidationError("gate ledger summary disposition does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address: raise ValidationError("gate ledger summary address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger summary crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerSummary":
        value = _mapping(value, "gate ledger summary"); _strict(value, set(cls.FIELDS), "gate ledger summary"); return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: LedgerSummary) -> str:
    if not isinstance(value, LedgerSummary): raise ValidationError("gate ledger summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class GateDecisionLedger:
    FIELDS = LEDGER_FIELDS
    def __init__(self, ledger_id: str, version: str, boundary: str, policy: Mapping[str, Any] | LedgerPolicy, entry_count: int, ready_count: int, blocked_count: int, accepted_count: int, final_ready: bool, state: str, transition: str, superseded_count: int, head_decision_id: str, head_entry_address: str, accepted: bool, release_ready: bool, manifest: Mapping[str, Any] | LedgerManifest, summary: Mapping[str, Any] | LedgerSummary, entries: Sequence[LedgerEntry | Mapping[str, Any]], checks: Sequence[LedgerCheck | Mapping[str, Any]], content_address: str) -> None:
        self.ledger_id = _label(ledger_id, "gate ledger ID"); self.version = _text(version, "gate ledger version", 1024); self.boundary = _text(boundary, "gate ledger boundary", 2048); self.policy = policy if isinstance(policy, LedgerPolicy) else LedgerPolicy.from_mapping(_mapping(policy, "gate ledger policy")); self.entry_count = _count(entry_count, "gate ledger entry count", MAX_ENTRIES); self.ready_count = _count(ready_count, "gate ledger ready count", MAX_ENTRIES); self.blocked_count = _count(blocked_count, "gate ledger blocked count", MAX_ENTRIES); self.accepted_count = _count(accepted_count, "gate ledger accepted count", MAX_ENTRIES); self.final_ready = _bool(final_ready, "gate ledger final readiness")
        if state not in STATES or transition not in TRANSITIONS: raise ValidationError("gate ledger state or transition is unsupported")
        self.state = state; self.transition = transition; self.superseded_count = _count(superseded_count, "gate ledger superseded count", MAX_ENTRIES); self.head_decision_id = _label(head_decision_id, "gate ledger head decision ID", required=False); self.head_entry_address = _address(head_entry_address, "gate ledger head entry address", ENTRY_PREFIX, required=False); self.accepted = _bool(accepted, "gate ledger acceptance"); self.release_ready = _bool(release_ready, "gate ledger readiness"); self.manifest = manifest if isinstance(manifest, LedgerManifest) else LedgerManifest.from_mapping(_mapping(manifest, "gate ledger manifest")); self.summary = summary if isinstance(summary, LedgerSummary) else LedgerSummary.from_mapping(_mapping(summary, "gate ledger summary")); self.entries = tuple(item if isinstance(item, LedgerEntry) else LedgerEntry.from_mapping(_mapping(item, "gate ledger entry")) for item in _sequence(entries, "gate ledger entries", MAX_ENTRIES)); self.checks = tuple(item if isinstance(item, LedgerCheck) else LedgerCheck.from_mapping(_mapping(item, "gate ledger check")) for item in _sequence(checks, "gate ledger checks", MAX_CHECKS)); self.content_address = _address(content_address, "gate ledger address", LEDGER_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.policy.ledger_id != self.ledger_id or self.entry_count != len(self.entries) or self.ready_count + self.blocked_count != self.entry_count or self.accepted_count > self.entry_count or self.final_ready != (self.state == "ready") or self.release_ready != all(item.passed for item in self.checks) or self.accepted != (self.entry_count > 0 and self.accepted_count == self.entry_count): raise ValidationError("gate ledger identity or counters do not replay")
        if self.check_count != len(self.checks) if hasattr(self, "check_count") else False: raise ValidationError("gate ledger check count does not replay")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)) or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("gate ledger entries or checks are not canonical")
        expected_summary = (self.ledger_id, self.summary.scenario_id, self.entry_count, self.ready_count, self.blocked_count, self.accepted_count, self.final_ready, self.state, self.transition, self.superseded_count, self.head_decision_id, self.head_entry_address, self.accepted, self.release_ready)
        if tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1]) != expected_summary or self.summary.content_address != address_summary(self.summary): raise ValidationError("gate ledger summary does not replay")
        expected_manifest = (self.ledger_id, self.summary.scenario_id, VERSION, BOUNDARY, FILES, (self.policy.content_address, address_entries(self.entries), address_checks(self.checks), self.summary.content_address)); actual_manifest = (self.manifest.ledger_id, self.manifest.scenario_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest): raise ValidationError("gate ledger manifest does not replay")
        if not self.content_address.startswith("pending:") and address_ledger(self) != self.content_address: raise ValidationError("gate ledger address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger crosses the public boundary")
    @property
    def check_count(self) -> int: return len(self.checks)
    def to_dict(self) -> dict[str, Any]: return {"ledger_id": self.ledger_id, "version": self.version, "boundary": self.boundary, "policy": self.policy.to_dict(), "entry_count": self.entry_count, "ready_count": self.ready_count, "blocked_count": self.blocked_count, "accepted_count": self.accepted_count, "final_ready": self.final_ready, "state": self.state, "transition": self.transition, "superseded_count": self.superseded_count, "head_decision_id": self.head_decision_id, "head_entry_address": self.head_entry_address, "accepted": self.accepted, "release_ready": self.release_ready, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "entries": [item.to_dict() for item in self.entries], "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GateDecisionLedger":
        value = _mapping(value, "gate ledger"); _strict(value, set(cls.FIELDS), "gate ledger"); return cls(*(value[field] for field in cls.FIELDS))


def address_ledger(value: GateDecisionLedger) -> str:
    if not isinstance(value, GateDecisionLedger): raise ValidationError("gate ledger address requires a typed ledger")
    return _address_for(value, LEDGER_PREFIX)
def build_policy(policy_id: str, ledger_id: str, *, minimum_decisions: int = 1, minimum_ready: int = 1, maximum_blocked: int = 0, require_same_scenario: bool = True, require_unique_gate_ids: bool = True, require_unique_gate_addresses: bool = True, require_contiguous_sequence: bool = True, require_supersession_links: bool = False, require_final_ready: bool = True, allow_reopened: bool = False) -> LedgerPolicy:
    return _seal(LedgerPolicy(policy_id, ledger_id, minimum_decisions, minimum_ready, maximum_blocked, require_same_scenario, require_unique_gate_ids, require_unique_gate_addresses, require_contiguous_sequence, require_supersession_links, require_final_ready, allow_reopened, f"pending:{POLICY_PREFIX}"), address_policy)
def _check(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> LedgerCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "severity": "info" if passed else "error", "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = LedgerCheck(**body); return LedgerCheck(**(body | {"content_address": address_check(provisional)}))
def _transition(previous: LedgerEntry | None, current_ready: bool) -> str:
    if previous is None: return "initial"
    if previous.release_ready == current_ready: return "unchanged"
    return "promoted" if current_ready else "regressed"
def _entry(gate: gate_model.ReleaseGate, ordinal: int, predecessor: str, supersedes_decision_id: str, prior: Sequence[LedgerEntry]) -> LedgerEntry:
    superseded_address = next((item.content_address for item in prior if item.decision_id == supersedes_decision_id), "") if supersedes_decision_id else ""; previous = prior[-1] if prior else None
    return _seal(LedgerEntry(ordinal, f"pending-decision-{ordinal}", gate.gate_id, gate.content_address, gate.scenario_id, gate.scenario_address, gate.state, gate.release_ready, gate.accepted, gate.passed_count, gate.failed_count, _transition(previous, gate.release_ready), predecessor, supersedes_decision_id, superseded_address, f"pending:{ENTRY_PREFIX}"), address_entry)
def _assemble(ledger_id: str, policy: LedgerPolicy, entries: Sequence[LedgerEntry]) -> GateDecisionLedger:
    typed = tuple(entries); ready_count = sum(item.release_ready for item in typed); blocked_count = len(typed) - ready_count; accepted_count = sum(item.accepted for item in typed); final = typed[-1] if typed else None; scenario_ids = {item.scenario_id for item in typed}; gate_ids = {item.gate_id for item in typed}; gate_addresses = {item.gate_address for item in typed}; same_scenario = len(scenario_ids) == 1 and bool(typed); unique_ids = len(gate_ids) == len(typed); unique_addresses = len(gate_addresses) == len(typed); contiguous = tuple(item.ordinal for item in typed) == tuple(range(1, len(typed) + 1)); predecessor_chain = (not typed) or (not typed[0].predecessor_address and all(item.predecessor_address == typed[index - 1].content_address for index, item in enumerate(typed[1:], 1))); supersession_targets = [item.supersedes_decision_id for item in typed if item.supersedes_decision_id]; known_prior = {item.decision_id for item in typed}; supersession_links = (not policy.require_supersession_links or len(typed) <= 1 or all(item.supersedes_decision_id in {prior.decision_id for prior in typed[:index]} for index, item in enumerate(typed[1:], 1))) and len(supersession_targets) == len(set(supersession_targets)); transition_replay = all(item.transition == _transition(typed[index - 1] if index else None, item.release_ready) for index, item in enumerate(typed)); reopen = all(not (typed[index - 1].release_ready and not item.release_ready) for index, item in enumerate(typed) if index); head_ok = (not typed and not final) or (final is not None and final.decision_id == typed[-1].decision_id and final.content_address == typed[-1].content_address)
    checks = (_check(1, "nonempty", bool(typed), len(typed), ">= 1", "a gate ledger must contain at least one decision"), _check(2, "minimum_decisions", len(typed) >= policy.minimum_decisions, len(typed), policy.minimum_decisions, "decision count must meet the ledger floor"), _check(3, "minimum_ready", ready_count >= policy.minimum_ready, ready_count, policy.minimum_ready, "ready decision count must meet the ledger floor"), _check(4, "blocked_budget", blocked_count <= policy.maximum_blocked, blocked_count, policy.maximum_blocked, "blocked decisions must remain within budget"), _check(5, "same_scenario", (not policy.require_same_scenario) or same_scenario, sorted(scenario_ids), "one scenario ID", "all decisions must target one scenario"), _check(6, "unique_gate_ids", (not policy.require_unique_gate_ids) or unique_ids, [item.gate_id for item in typed], "unique gate IDs", "gate IDs must not repeat"), _check(7, "unique_gate_addresses", (not policy.require_unique_gate_addresses) or unique_addresses, [item.gate_address for item in typed], "unique gate addresses", "gate addresses must not repeat"), _check(8, "contiguous_sequence", (not policy.require_contiguous_sequence) or contiguous, [item.ordinal for item in typed], "contiguous ordinals", "decision ordinals must be contiguous"), _check(9, "predecessor_chain", predecessor_chain, True, "linked predecessor addresses", "each append must reference the prior head"), _check(10, "supersession_links", supersession_links, [item.supersedes_decision_id for item in typed], "unique prior decisions when required", "supersession targets must point backward without reuse"), _check(11, "transition_replay", transition_replay, [item.transition for item in typed], "deterministic transitions", "promotion and regression transitions must replay"), _check(12, "counter_replay", ready_count + blocked_count == len(typed) and accepted_count <= len(typed), (ready_count, blocked_count, accepted_count), "conserved counters", "ledger counters must conserve decisions"), _check(13, "final_ready_policy", (not policy.require_final_ready) or bool(final and final.release_ready), bool(final and final.release_ready), True, "the ledger head must be ready when required"), _check(14, "reopen_policy", policy.allow_reopened or reopen, reopen, True, "ready decisions must not be reopened when disallowed"), _check(15, "accepted_policy", all(item.accepted for item in typed), accepted_count, len(typed), "all decisions must retain accepted gate evidence"), _check(16, "head_integrity", head_ok, (final.decision_id if final else "", final.content_address if final else ""), "last decision head", "head identity must replay"), _check(17, "policy_integrity", address_policy(policy) == policy.content_address, policy.content_address, address_policy(policy), "ledger policy address must replay"))
    disposition = all(item.passed for item in checks); checks = checks + (_check(18, "release_disposition", disposition, disposition, True, "ledger release readiness is the conjunction of ledger checks"), _check(19, "public_boundary", _public(policy.to_dict()) and all(_public(item.to_dict()) for item in typed), True, "public values", "ledger inputs must remain value-only")); passed = sum(item.passed for item in checks); release_ready = all(item.passed for item in checks); state = "empty" if not typed else "ready" if final and final.release_ready else "blocked"; transition = final.transition if final else "initial"; scenario_id = next(iter(scenario_ids)) if same_scenario else (final.scenario_id if final else ""); superseded_count = sum(bool(item.supersedes_decision_id) for item in typed); head_id = final.decision_id if final else ""; head_address = final.content_address if final else ""; accepted = bool(typed) and accepted_count == len(typed); summary = _seal(LedgerSummary(ledger_id, scenario_id, len(typed), ready_count, blocked_count, accepted_count, bool(final and final.release_ready), state, transition, superseded_count, head_id, head_address, accepted, release_ready, f"pending:{SUMMARY_PREFIX}"), address_summary); manifest = _seal(LedgerManifest(ledger_id, scenario_id, VERSION, BOUNDARY, FILES, (policy.content_address, address_entries(typed), address_checks(checks), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest); return _seal(GateDecisionLedger(ledger_id, VERSION, BOUNDARY, policy, len(typed), ready_count, blocked_count, accepted_count, bool(final and final.release_ready), state, transition, superseded_count, head_id, head_address, accepted, release_ready, manifest, summary, typed, checks, f"pending:{LEDGER_PREFIX}"), address_ledger)
def build_ledger(gates: Sequence[gate_model.ReleaseGate], *, ledger_id: str = DEFAULT_LEDGER_ID, policy: LedgerPolicy | Mapping[str, Any] | None = None, decision_ids: Sequence[str] | None = None, supersedes_decision_ids: Sequence[str] | None = None) -> GateDecisionLedger:
    typed = tuple(gates)
    if len(typed) > MAX_ENTRIES or any(not isinstance(item, gate_model.ReleaseGate) for item in typed): raise ValidationError("gate ledger requires a bounded set of typed gates")
    for item in typed: gate_model.verify_gate(item)
    ledger_policy = policy if isinstance(policy, LedgerPolicy) else LedgerPolicy.from_mapping(_mapping(policy, "gate ledger policy")) if policy is not None else build_policy(f"{ledger_id}-policy", ledger_id, minimum_decisions=max(1, len(typed)))
    ids = tuple(decision_ids) if decision_ids is not None else tuple(f"{ledger_id}-decision-{index}" for index in range(1, len(typed) + 1)); supersedes = tuple(supersedes_decision_ids) if supersedes_decision_ids is not None else tuple("" for _ in typed)
    if len(ids) != len(typed) or len(supersedes) != len(typed) or len(set(ids)) != len(ids): raise ValidationError("gate ledger decision metadata must match the gate count and remain unique")
    entries: list[LedgerEntry] = []
    for index, (gate, decision_id, supersedes_id) in enumerate(zip(typed, ids, supersedes), 1):
        predecessor = entries[-1].content_address if entries else ""; superseded_address = next((item.content_address for item in entries if item.decision_id == supersedes_id), "") if supersedes_id else ""; previous = entries[-1] if entries else None; entry = _seal(LedgerEntry(index, _label(decision_id, "gate ledger decision ID"), gate.gate_id, gate.content_address, gate.scenario_id, gate.scenario_address, gate.state, gate.release_ready, gate.accepted, gate.passed_count, gate.failed_count, _transition(previous, gate.release_ready), predecessor, _label(supersedes_id, "gate ledger superseded decision ID", required=False), superseded_address, f"pending:{ENTRY_PREFIX}"), address_entry); entries.append(entry)
    return _assemble(ledger_id, ledger_policy, entries)
def append_ledger(value: GateDecisionLedger, gate: gate_model.ReleaseGate, *, decision_id: str, expected_head: str, supersedes_decision_id: str = "") -> GateDecisionLedger:
    verify_ledger(value); gate_model.verify_gate(gate)
    if expected_head != value.head_entry_address: raise ValidationError("gate ledger expected head does not match the current head")
    if gate.scenario_id != value.summary.scenario_id and value.summary.scenario_id: raise ValidationError("gate ledger append changes the scenario identity")
    if any(item.decision_id == decision_id for item in value.entries): raise ValidationError("gate ledger append decision ID is already present")
    predecessor = value.head_entry_address; superseded_address = next((item.content_address for item in value.entries if item.decision_id == supersedes_decision_id), "") if supersedes_decision_id else ""; previous = value.entries[-1] if value.entries else None; entry = _seal(LedgerEntry(value.entry_count + 1, _label(decision_id, "gate ledger decision ID"), gate.gate_id, gate.content_address, gate.scenario_id, gate.scenario_address, gate.state, gate.release_ready, gate.accepted, gate.passed_count, gate.failed_count, _transition(previous, gate.release_ready), predecessor, _label(supersedes_decision_id, "gate ledger superseded decision ID", required=False), superseded_address, f"pending:{ENTRY_PREFIX}"), address_entry); return _assemble(value.ledger_id, value.policy, value.entries + (entry,))
def verify_ledger(value: GateDecisionLedger) -> GateDecisionLedger:
    if not isinstance(value, GateDecisionLedger): raise ValidationError("gate ledger verification requires a typed ledger")
    value._validate(); return value
def ledger_from_mapping(value: Mapping[str, Any]) -> GateDecisionLedger: return verify_ledger(GateDecisionLedger.from_mapping(value))
def ledger_json(value: GateDecisionLedger) -> str: return canonical_json(verify_ledger(value).to_dict())
def policy_json(value: GateDecisionLedger) -> str: return canonical_json(verify_ledger(value).policy.to_dict())
def entries_json(value: GateDecisionLedger) -> str:
    value = verify_ledger(value); return canonical_json({"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)})
def checks_json(value: GateDecisionLedger) -> str:
    value = verify_ledger(value); return canonical_json({"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)})
def summary_json(value: GateDecisionLedger) -> str: return canonical_json(verify_ledger(value).summary.to_dict())
def manifest_json(value: GateDecisionLedger) -> str: return canonical_json(verify_ledger(value).manifest.to_dict())
def ledger_csv(value: GateDecisionLedger) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ENTRY_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_ledger(value).entries); return output.getvalue()
def render_ledger_markdown(value: GateDecisionLedger) -> str:
    value = verify_ledger(value); lines = [f"# Gate decision ledger {value.ledger_id}", "", f"- State: {value.state}", f"- Release ready: {str(value.release_ready).lower()}", f"- Decisions: {value.ready_count}/{value.entry_count} ready", f"- Head: {value.head_decision_id}", "", "| Decision | Gate | Transition | State | Supersedes |", "| --- | --- | --- | --- | --- |"] ; lines.extend(f"| {item.decision_id} | {item.gate_id} | {item.transition} | {item.state} | {item.supersedes_decision_id or '-'} |" for item in value.entries); return "\n".join(lines) + "\n"
def _write(path: Path, value: Mapping[str, Any]) -> None: path.write_text(canonical_json(value), encoding="utf-8", newline="\n")
def persist_ledger(value: GateDecisionLedger, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_ledger(value); destination = Path(destination); _validate_parent(destination.parent, "gate ledger destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)): raise ValidationError("gate ledger destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True); temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-gate-ledger-", dir=str(destination.parent))); documents = {"manifest.json": value.manifest.to_dict(), "ledger.json": value.to_dict(), "policy.json": value.policy.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES: _write(temporary / name, documents[name])
        if destination.exists(): shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True); raise ValidationError("gate ledger destination could not be written") from error
    return destination
def _read_json(path: Path) -> Mapping[str, Any]:
    try: value = _strict_json_loads(read_text(path, field="gate ledger artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error: raise ValidationError("gate ledger artifact is not valid JSON") from error
    return _mapping(value, "gate ledger artifact")
def load_ledger(destination: str | Path) -> GateDecisionLedger:
    destination = Path(destination); _validate_parent(destination.parent, "gate ledger input")
    if not destination.is_dir() or destination.is_symlink(): raise ValidationError("gate ledger source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children): raise ValidationError("gate ledger directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="gate ledger artifact") != serialized or len(serialized.encode("utf-8")) > MAX_LEDGER_BYTES: raise ValidationError("gate ledger artifact is non-canonical or exceeds its size bound")
    value = ledger_from_mapping(documents["ledger.json"]); expected = {"manifest.json": value.manifest.to_dict(), "policy.json": value.policy.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "checks.json": {"checks": [item.to_dict() for item in value.checks], "content_address": address_checks(value.checks)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(document) for name, document in expected.items()): raise ValidationError("gate ledger component documents do not replay ledger.json")
    return verify_ledger(value)
def run_ledger(gates: Sequence[gate_model.ReleaseGate], *, ledger_id: str = DEFAULT_LEDGER_ID, policy: LedgerPolicy | Mapping[str, Any] | None = None, decision_ids: Sequence[str] | None = None, supersedes_decision_ids: Sequence[str] | None = None, destination: str | Path | None = None, overwrite: bool = False) -> GateDecisionLedger:
    value = build_ledger(gates, ledger_id=ledger_id, policy=policy, decision_ids=decision_ids, supersedes_decision_ids=supersedes_decision_ids)
    if destination is not None: persist_ledger(value, destination, overwrite=overwrite)
    return value
def policy_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerPolicy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "integer" if field.startswith("minimum") or field.startswith("maximum") else "boolean" if field.startswith("require") or field.startswith("allow") else "string"} for field in POLICY_FIELDS}}
def entry_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerEntry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" or field.endswith("count") else "boolean" if field in ("release_ready", "accepted") else "string"} for field in ENTRY_FIELDS}}
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def manifest_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}
def summary_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("final_ready", "accepted", "release_ready") else "string"} for field in SUMMARY_FIELDS}}
def ledger_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateDecisionLedger", "type": "object", "additionalProperties": False, "required": list(LEDGER_FIELDS), "properties": {field: {"type": "array" if field in ("entries", "checks") else "object" if field in ("policy", "manifest", "summary") else "integer" if field.endswith("count") else "boolean" if field in ("final_ready", "accepted", "release_ready") else "string"} for field in LEDGER_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "check_ids": CHECK_IDS, "states": STATES, "transitions": TRANSITIONS, "max_entries": MAX_ENTRIES, "max_checks": MAX_CHECKS, "features": ("append-only gate decision lineage", "optimistic expected-head appends", "promotion regression and supersession transitions", "exact six-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "LEDGER_PREFIX", "POLICY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "CHECK_PREFIX", "CHECKS_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_LEDGER_ID", "FILES", "ARTIFACT_FILES", "STATES", "TRANSITIONS", "SEVERITIES", "MAX_ENTRIES", "MAX_CHECKS", "MAX_LEDGER_BYTES", "POLICY_FIELDS", "ENTRY_FIELDS", "CHECK_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "LEDGER_FIELDS", "CHECK_IDS", "LedgerPolicy", "LedgerEntry", "LedgerCheck", "LedgerManifest", "LedgerSummary", "GateDecisionLedger", "address_policy", "address_entry", "address_entries", "address_check", "address_checks", "address_manifest", "address_summary", "address_ledger", "build_policy", "build_ledger", "append_ledger", "verify_ledger", "ledger_from_mapping", "ledger_json", "policy_json", "entries_json", "checks_json", "summary_json", "manifest_json", "ledger_csv", "render_ledger_markdown", "persist_ledger", "load_ledger", "run_ledger", "policy_schema", "entry_schema", "check_schema", "manifest_schema", "summary_schema", "ledger_schema", "capabilities"]
