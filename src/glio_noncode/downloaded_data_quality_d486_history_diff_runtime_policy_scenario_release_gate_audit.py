"""Independent audits for D486 release gates."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_quality_d486_history_diff_runtime_policy_scenario_release_gate as gate_model
from . import downloaded_data_quality_d485_history_diff_runtime_policy_scenario as scenario_model
from . import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_audit as scenario_audit_model
from . import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query as scenario_query_model
from . import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query_audit as scenario_query_audit_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = gate_model.VERSION + "-audit-v1"
BOUNDARY = gate_model.BOUNDARY + "_audit"
AUDIT_PREFIX = gate_model.GATE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
MAX_CHECKS = 18
CHECK_IDS = ("typed_gate", "policy_link", "scenario_link", "evidence_addresses", "check_sequence", "counter_replay", "summary_replay", "manifest_replay", "disposition_replay", "scenario_state", "evidence_replay", "risk_replay", "margin_replay", "check_addresses", "address_integrity", "public_boundary", "canonical_gate", "input_lineage")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("gate_id", "gate_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


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
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__") or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
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


class GateAuditCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release gate audit check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "release gate audit check ID"); self.passed = _bool(passed, "release gate audit result"); self.actual = _text(actual, "release gate audit actual", 32768); self.expected = _text(expected, "release gate audit expected", 32768); self.detail = _text(detail, "release gate audit detail", 4096); self.content_address = _address(content_address, "release gate audit check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS: raise ValidationError("release gate audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("release gate audit check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("release gate audit check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GateAuditCheck":
        value = _mapping(value, "release gate audit check"); _strict(value, set(cls.FIELDS), "release gate audit check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: GateAuditCheck) -> str:
    if not isinstance(value, GateAuditCheck): raise ValidationError("release gate audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class GateAudit:
    FIELDS = AUDIT_FIELDS
    def __init__(self, gate_id: str, gate_address: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Any, content_address: str) -> None:
        self.gate_id = _label(gate_id, "release gate audit gate ID"); self.gate_address = _address(gate_address, "release gate audit gate address", gate_model.GATE_PREFIX); self.check_count = _count(check_count, "release gate audit check count", MAX_CHECKS); self.passed_count = _count(passed_count, "release gate audit passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "release gate audit failed count", MAX_CHECKS); self.accepted = _bool(accepted, "release gate audit acceptance"); self.checks = tuple(item if isinstance(item, GateAuditCheck) else GateAuditCheck.from_mapping(_mapping(item, "release gate audit check")) for item in _sequence(checks, "release gate audit checks", MAX_CHECKS)); self.content_address = _address(content_address, "release gate audit address", AUDIT_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks): raise ValidationError("release gate audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("release gate audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address: raise ValidationError("release gate audit address does not replay")
        if not _public(self.to_dict()): raise ValidationError("release gate audit crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"gate_id": self.gate_id, "gate_address": self.gate_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GateAudit":
        value = _mapping(value, "release gate audit"); _strict(value, set(cls.FIELDS), "release gate audit"); return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: GateAudit) -> str:
    if not isinstance(value, GateAudit): raise ValidationError("release gate audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)
def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> GateAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = GateAuditCheck(**body); return GateAuditCheck(**(body | {"content_address": address_check(provisional)}))
def audit_gate(value: gate_model.ReleaseGate, scenario: scenario_model.PolicyScenario | None = None, audit: scenario_audit_model.ScenarioAudit | None = None, query: scenario_query_model.ScenarioQuery | None = None, query_audit: scenario_query_audit_model.QueryAudit | None = None) -> GateAudit:
    gate_model.verify_gate(value); if_scenario = scenario is not None and isinstance(scenario, scenario_model.PolicyScenario); if_audit = audit is not None and isinstance(audit, scenario_audit_model.ScenarioAudit); if_query = query is not None and isinstance(query, scenario_query_model.ScenarioQuery); if_query_audit = query_audit is not None and isinstance(query_audit, scenario_query_audit_model.QueryAudit)
    if scenario is not None: scenario_model.verify_scenario(scenario)
    if audit is not None: scenario_audit_model.verify_audit(audit)
    if query is not None: scenario_query_model.verify_query(query)
    if query_audit is not None: scenario_query_audit_model.verify_audit(query_audit)
    scenario_link = (not if_scenario) or (value.scenario_id == scenario.scenario_id and value.scenario_address == scenario.content_address); evidence_addresses = (not if_audit or value.audit_address == audit.content_address) and (not if_query or value.query_address == query.content_address) and (not if_query_audit or value.query_audit_address == query_audit.content_address); evidence_replay = (not if_audit or value.audit_accepted == audit.accepted) and (not if_query or value.query_complete == (not query.truncated)) and (not if_query_audit or value.query_audit_accepted == query_audit.accepted); input_lineage = (not if_scenario or scenario_link) and (not if_audit or (audit.gate_id if hasattr(audit, "gate_id") else "") == "") and (not if_query or query.scenario_id == value.scenario_id) and (not if_query_audit or query_audit.query_id == query.query_id if if_query else True)
    summary_replay = (value.summary.gate_id, value.summary.scenario_id, value.summary.scenario_address, value.summary.scenario_state, value.summary.audit_accepted, value.summary.query_complete, value.summary.query_audit_accepted, value.summary.accepted, value.summary.release_ready, value.summary.state) == (value.gate_id, value.scenario_id, value.scenario_address, value.scenario_state, value.audit_accepted, value.query_complete, value.query_audit_accepted, value.accepted, value.release_ready, value.state)
    checks = (_finding(1, "typed_gate", isinstance(value, gate_model.ReleaseGate), type(value).__name__, "ReleaseGate", "the audited value must use the typed gate model"), _finding(2, "policy_link", value.policy.content_address == gate_model.address_policy(value.policy), value.policy.content_address, "replayed policy address", "gate policy must be content-addressed"), _finding(3, "scenario_link", scenario_link, (value.scenario_id, value.scenario_address), "matching scenario identity", "gate must retain scenario lineage"), _finding(4, "evidence_addresses", evidence_addresses, (value.audit_address, value.query_address, value.query_audit_address), "matching evidence addresses", "gate must retain supplied evidence addresses"), _finding(5, "check_sequence", tuple(item.ordinal for item in value.checks) == tuple(range(1, gate_model.MAX_CHECKS + 1)) and tuple(item.check_id for item in value.checks) == gate_model.CHECK_IDS, [item.check_id for item in value.checks], gate_model.CHECK_IDS, "gate checks must preserve canonical order"), _finding(6, "counter_replay", value.passed_count + value.failed_count == value.check_count and value.passed_count == sum(item.passed for item in value.checks), (value.passed_count, value.failed_count), "replayed check counters", "gate counters must derive from checks"), _finding(7, "summary_replay", summary_replay, value.summary.to_dict(), "replayed gate summary", "summary must derive from gate fields"), _finding(8, "manifest_replay", value.manifest.content_address == gate_model.address_manifest(value.manifest) and value.manifest.artifact_addresses == (value.policy.content_address, gate_model.address_checks(value.checks), value.summary.content_address), value.manifest.to_dict(), "replayed manifest", "manifest must retain component addresses"), _finding(9, "disposition_replay", value.release_ready == all(item.passed for item in value.checks) and value.state == ("ready" if value.release_ready else "blocked"), (value.release_ready, value.state), "replayed gate disposition", "release decision must be deterministic"), _finding(10, "scenario_state", value.scenario_state in scenario_model.STATES, value.scenario_state, scenario_model.STATES, "scenario state must be known"), _finding(11, "evidence_replay", evidence_replay, (value.audit_accepted, value.query_complete, value.query_audit_accepted), "replayed evidence state", "evidence status must replay supplied artifacts"), _finding(12, "risk_replay", (not if_scenario) or value.summary.risk_count == len(scenario.risk_flags), value.summary.risk_count, "scenario risk count", "risk count must link to scenario"), _finding(13, "margin_replay", (not if_scenario) or (value.summary.minimum_added_margin, value.summary.minimum_removed_margin, value.summary.minimum_changed_margin) == (scenario.minimum_added_margin, scenario.minimum_removed_margin, scenario.minimum_changed_margin), value.summary.to_dict(), "scenario margins", "gate margins must link to scenario"), _finding(14, "check_addresses", all(gate_model.address_check(item) == item.content_address for item in value.checks), True, "replayed check addresses", "every gate check address must replay"), _finding(15, "address_integrity", gate_model.address_gate(value) == value.content_address, value.content_address, gate_model.address_gate(value), "gate address must replay"), _finding(16, "public_boundary", _public(value.to_dict()), True, "public value", "gate artifacts must contain no private records"), _finding(17, "canonical_gate", canonical_json(value.to_dict()) == canonical_json(gate_model.gate_from_mapping(_strict_json_loads(gate_model.gate_json(value))).to_dict()), True, "canonical round-trip", "gate serialization must be deterministic"), _finding(18, "input_lineage", input_lineage, True, "matching optional evidence lineage", "optional audit and query inputs must remain linked")); provisional = GateAudit(value.gate_id, value.content_address, MAX_CHECKS, sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), checks, f"pending:{AUDIT_PREFIX}"); return _seal(provisional, address_audit)
def verify_audit(value: GateAudit) -> GateAudit:
    if not isinstance(value, GateAudit): raise ValidationError("release gate audit verification requires a typed audit")
    value._validate(); return value
def audit_from_mapping(value: Mapping[str, Any]) -> GateAudit: return GateAudit.from_mapping(value)
def audit_json(value: GateAudit) -> str: return canonical_json(verify_audit(value).to_dict())
def audit_csv(value: GateAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()
def render_audit_markdown(value: GateAudit) -> str:
    value = verify_audit(value); lines = [f"# Release gate audit {value.gate_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"] ; lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks); return "\n".join(lines) + "\n"
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def audit_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent release gate replay", "scenario and evidence lineage verification", "canonical address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "GateAuditCheck", "GateAudit", "address_check", "address_audit", "audit_gate", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
