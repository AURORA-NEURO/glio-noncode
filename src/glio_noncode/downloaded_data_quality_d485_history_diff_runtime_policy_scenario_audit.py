"""Independent audits for D485 policy scenarios."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d484_history_diff_runtime_registry_history_diff_runtime as runtime_model
from . import downloaded_data_quality_d485_history_diff_runtime_policy_scenario as scenario_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = scenario_model.VERSION + "-audit-v1"
BOUNDARY = scenario_model.BOUNDARY + "_audit"
AUDIT_PREFIX = scenario_model.SCENARIO_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
MAX_CHECKS = 18
CHECK_IDS = ("typed_scenario", "policy_link", "entry_sequence", "entry_addresses", "counter_replay", "policy_replay", "state_replay", "diff_identity", "direction_link", "transition_link", "runtime_lineage", "margin_replay", "risk_replay", "disposition_link", "check_sequence", "check_addresses", "public_boundary", "canonical_scenario")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("scenario_id", "scenario_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value): raise ValidationError(f"{field} must be bounded public text")
    return value
def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value: raise ValidationError(f"{field} must be a compact label")
    return value
def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
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
def _public(value: Any) -> bool: return scenario_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class AuditCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "policy scenario audit check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "policy scenario audit check ID"); self.passed = _bool(passed, "policy scenario audit result"); self.actual = _text(actual, "policy scenario audit actual", 32768); self.expected = _text(expected, "policy scenario audit expected", 32768); self.detail = _text(detail, "policy scenario audit detail", 4096); self.content_address = _address(content_address, "policy scenario audit check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS: raise ValidationError("policy scenario audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("policy scenario audit check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("policy scenario audit check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "policy scenario audit check"); _strict(value, set(cls.FIELDS), "policy scenario audit check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck): raise ValidationError("policy scenario audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class ScenarioAudit:
    FIELDS = AUDIT_FIELDS
    def __init__(self, scenario_id: str, scenario_address: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[AuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.scenario_id = _label(scenario_id, "policy scenario audit scenario ID"); self.scenario_address = _address(scenario_address, "policy scenario audit scenario address", scenario_model.SCENARIO_PREFIX); self.check_count = _count(check_count, "policy scenario audit check count", MAX_CHECKS); self.passed_count = _count(passed_count, "policy scenario audit passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "policy scenario audit failed count", MAX_CHECKS); self.accepted = _bool(accepted, "policy scenario audit acceptance"); self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "policy scenario audit check")) for item in _sequence(checks, "policy scenario audit checks", MAX_CHECKS)); self.content_address = _address(content_address, "policy scenario audit address", AUDIT_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks): raise ValidationError("policy scenario audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("policy scenario audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address: raise ValidationError("policy scenario audit address does not replay")
        if not _public(self.to_dict()): raise ValidationError("policy scenario audit crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"scenario_id": self.scenario_id, "scenario_address": self.scenario_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ScenarioAudit":
        value = _mapping(value, "policy scenario audit"); _strict(value, set(cls.FIELDS), "policy scenario audit"); return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: ScenarioAudit) -> str:
    if not isinstance(value, ScenarioAudit): raise ValidationError("policy scenario audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)
def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = AuditCheck(**body); return AuditCheck(**(body | {"content_address": address_check(provisional)}))
def audit_scenario(value: scenario_model.PolicyScenario, runtimes: Sequence[runtime_model.HistoryDiffRuntime] | None = None) -> ScenarioAudit:
    scenario_model.verify_scenario(value); entries = value.entries; runtime_values = tuple(runtimes) if runtimes is not None else (); runtime_lineage = runtimes is None or (len(runtime_values) == len(entries) and all(isinstance(item, runtime_model.HistoryDiffRuntime) and runtime_model.verify_runtime(item).runtime_id == entry.runtime_id and item.content_address == entry.runtime_address and item.policy.policy_id == entry.policy_id and item.state_transition == entry.state_transition for item, entry in zip(runtime_values, entries)))
    counter_replay = (value.ready_count, value.blocked_count, value.accepted_count, value.minimum_added_margin, value.minimum_removed_margin, value.minimum_changed_margin) == (sum(item.release_ready for item in entries), sum(not item.release_ready for item in entries), sum(item.accepted for item in entries), min((item.added_margin for item in entries), default=0), min((item.removed_margin for item in entries), default=0), min((item.changed_margin for item in entries), default=0)); expected_state = "empty" if not entries else "ready" if value.blocked_count == 0 else "blocked" if value.ready_count == 0 else "mixed"
    checks = (_finding(1, "typed_scenario", isinstance(value, scenario_model.PolicyScenario), type(value).__name__, "PolicyScenario", "the audited value must use the typed scenario model"), _finding(2, "policy_link", value.policy.content_address == scenario_model.address_policy(value.policy), value.policy.content_address, "replayed policy address", "scenario policy must be content-addressed"), _finding(3, "entry_sequence", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), [item.ordinal for item in entries], "contiguous entry ordinals", "entries must preserve canonical order"), _finding(4, "entry_addresses", all(scenario_model.address_entry(item) == item.content_address for item in entries), True, "replayed entry addresses", "every entry address must replay"), _finding(5, "counter_replay", counter_replay, (value.ready_count, value.blocked_count, value.accepted_count), "replayed scenario counters", "summary counters must derive from entries"), _finding(6, "policy_replay", scenario_model.address_policy(value.policy) == value.policy.content_address, value.policy.content_address, scenario_model.address_policy(value.policy), "policy address must replay"), _finding(7, "state_replay", value.state == expected_state and value.summary.state == value.state and value.release_ready == all(item.passed for item in value.checks), (value.state, value.summary.state, value.release_ready), expected_state, "state and readiness must replay"), _finding(8, "diff_identity", bool(entries) and all(item.diff_id == value.diff_id for item in entries) or not entries, [item.diff_id for item in entries], value.diff_id, "all entries must link to the scenario diff"), _finding(9, "direction_link", bool(entries) and all(item.direction == value.direction for item in entries) or not entries, [item.direction for item in entries], value.direction, "all entries must link to the scenario direction"), _finding(10, "transition_link", bool(entries) and all(item.state_transition == value.state_transition for item in entries) or not entries, [item.state_transition for item in entries], value.state_transition, "all entries must link to the scenario transition"), _finding(11, "runtime_lineage", runtime_lineage, "provided runtime lineage" if runtimes is not None else "embedded entry lineage", "matching runtime identities and addresses", "optional runtime inputs must replay entry lineage"), _finding(12, "margin_replay", all(item.added_margin >= -runtime_model.diff_model.MAX_ITEMS and item.removed_margin >= -runtime_model.diff_model.MAX_ITEMS and item.changed_margin >= -runtime_model.diff_model.MAX_ITEMS for item in entries), True, "bounded budget margins", "budget margins must remain bounded"), _finding(13, "risk_replay", value.risk_flags == scenario_model._derived_risks(entries, value.ready_count, value.blocked_count), value.risk_flags, "derived risk flags", "scenario risks must replay"), _finding(14, "disposition_link", value.accepted == (bool(entries) and value.accepted_count == len(entries)) and value.release_ready == all(item.passed for item in value.checks), (value.accepted, value.release_ready), "replayed disposition", "accepted and release readiness must be deterministic"), _finding(15, "check_sequence", tuple(item.ordinal for item in value.checks) == tuple(range(1, scenario_model.MAX_CHECKS + 1)) and tuple(item.check_id for item in value.checks) == scenario_model.CHECK_IDS, [item.check_id for item in value.checks], scenario_model.CHECK_IDS, "scenario checks must preserve canonical order"), _finding(16, "check_addresses", all(scenario_model.address_check(item) == item.content_address for item in value.checks), True, "replayed check addresses", "scenario check addresses must replay"), _finding(17, "public_boundary", _public(value.to_dict()), True, "public value", "scenario artifacts must contain no private records"), _finding(18, "canonical_scenario", canonical_json(value.to_dict()) == canonical_json(scenario_model.scenario_from_mapping(_strict_json_loads(scenario_model.scenario_json(value))).to_dict()), True, "canonical round-trip", "scenario serialization must be deterministic")); provisional = ScenarioAudit(value.scenario_id, value.content_address, MAX_CHECKS, sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), checks, f"pending:{AUDIT_PREFIX}"); return _seal(provisional, address_audit)
def verify_audit(value: ScenarioAudit) -> ScenarioAudit:
    if not isinstance(value, ScenarioAudit): raise ValidationError("policy scenario audit verification requires a typed audit")
    value._validate(); return value
def audit_from_mapping(value: Mapping[str, Any]) -> ScenarioAudit: return ScenarioAudit.from_mapping(value)
def audit_json(value: ScenarioAudit) -> str: return canonical_json(verify_audit(value).to_dict())
def audit_csv(value: ScenarioAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()
def render_audit_markdown(value: ScenarioAudit) -> str:
    value = verify_audit(value); lines = [f"# Policy scenario audit {value.scenario_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"] ; lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks); return "\n".join(lines) + "\n"
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "PolicyScenarioAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def audit_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "PolicyScenarioAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent scenario replay", "optional runtime lineage verification", "canonical address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "ScenarioAudit", "address_check", "address_audit", "audit_scenario", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
