"""Independent audits for D487 gate decision ledgers."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d486_history_diff_runtime_policy_scenario_release_gate as gate_model
from . import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger as ledger_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = ledger_model.VERSION + "-audit-v1"
BOUNDARY = ledger_model.BOUNDARY + "_audit"
AUDIT_PREFIX = ledger_model.LEDGER_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
MAX_CHECKS = 19
CHECK_IDS = ("typed_ledger", "policy_link", "entry_sequence", "entry_addresses", "predecessor_chain", "supersession_replay", "transition_replay", "counter_replay", "summary_replay", "manifest_replay", "head_replay", "policy_replay", "gate_lineage", "check_sequence", "check_addresses", "disposition_replay", "public_boundary", "canonical_ledger", "input_lineage")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("ledger_id", "ledger_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


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
def _public(value: Any) -> bool: return ledger_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class LedgerAuditCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate ledger audit check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "gate ledger audit check ID"); self.passed = _bool(passed, "gate ledger audit result"); self.actual = _text(actual, "gate ledger audit actual", 32768); self.expected = _text(expected, "gate ledger audit expected", 32768); self.detail = _text(detail, "gate ledger audit detail", 4096); self.content_address = _address(content_address, "gate ledger audit check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS: raise ValidationError("gate ledger audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("gate ledger audit check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger audit check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerAuditCheck":
        value = _mapping(value, "gate ledger audit check"); _strict(value, set(cls.FIELDS), "gate ledger audit check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: LedgerAuditCheck) -> str:
    if not isinstance(value, LedgerAuditCheck): raise ValidationError("gate ledger audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class LedgerAudit:
    FIELDS = AUDIT_FIELDS
    def __init__(self, ledger_id: str, ledger_address: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Any, content_address: str) -> None:
        self.ledger_id = _label(ledger_id, "gate ledger audit ledger ID"); self.ledger_address = _address(ledger_address, "gate ledger audit ledger address", ledger_model.LEDGER_PREFIX); self.check_count = _count(check_count, "gate ledger audit check count", MAX_CHECKS); self.passed_count = _count(passed_count, "gate ledger audit passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "gate ledger audit failed count", MAX_CHECKS); self.accepted = _bool(accepted, "gate ledger audit acceptance"); self.checks = tuple(item if isinstance(item, LedgerAuditCheck) else LedgerAuditCheck.from_mapping(_mapping(item, "gate ledger audit check")) for item in _sequence(checks, "gate ledger audit checks", MAX_CHECKS)); self.content_address = _address(content_address, "gate ledger audit address", AUDIT_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks): raise ValidationError("gate ledger audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("gate ledger audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address: raise ValidationError("gate ledger audit address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger audit crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"ledger_id": self.ledger_id, "ledger_address": self.ledger_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerAudit":
        value = _mapping(value, "gate ledger audit"); _strict(value, set(cls.FIELDS), "gate ledger audit"); return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: LedgerAudit) -> str:
    if not isinstance(value, LedgerAudit): raise ValidationError("gate ledger audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)
def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> LedgerAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = LedgerAuditCheck(**body); return LedgerAuditCheck(**(body | {"content_address": address_check(provisional)}))
def audit_ledger(value: ledger_model.GateDecisionLedger, gates: Sequence[gate_model.ReleaseGate] | None = None) -> LedgerAudit:
    ledger_model.verify_ledger(value); entries = value.entries; gate_values = tuple(gates) if gates is not None else (); gate_lineage = gates is None or (len(gate_values) == len(entries) and all(isinstance(item, gate_model.ReleaseGate) and gate_model.verify_gate(item).gate_id == entry.gate_id and item.content_address == entry.gate_address and item.scenario_id == entry.scenario_id for item, entry in zip(gate_values, entries))); predecessor_chain = (not entries) or (not entries[0].predecessor_address and all(item.predecessor_address == entries[index - 1].content_address for index, item in enumerate(entries[1:], 1))); transition_replay = all(item.transition == ledger_model._transition(entries[index - 1] if index else None, item.release_ready) for index, item in enumerate(entries)); head = entries[-1] if entries else None; summary_replay = (value.summary.entry_count, value.summary.ready_count, value.summary.blocked_count, value.summary.accepted_count, value.summary.final_ready, value.summary.state, value.summary.transition, value.summary.superseded_count, value.summary.head_decision_id, value.summary.head_entry_address, value.summary.accepted, value.summary.release_ready) == (value.entry_count, value.ready_count, value.blocked_count, value.accepted_count, value.final_ready, value.state, value.transition, value.superseded_count, value.head_decision_id, value.head_entry_address, value.accepted, value.release_ready); checks = (_finding(1, "typed_ledger", isinstance(value, ledger_model.GateDecisionLedger), type(value).__name__, "GateDecisionLedger", "the audited value must use the typed ledger model"), _finding(2, "policy_link", value.policy.content_address == ledger_model.address_policy(value.policy), value.policy.content_address, "replayed policy address", "ledger policy must be content-addressed"), _finding(3, "entry_sequence", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), [item.ordinal for item in entries], "contiguous entry ordinals", "entries must preserve canonical order"), _finding(4, "entry_addresses", all(ledger_model.address_entry(item) == item.content_address for item in entries), True, "replayed entry addresses", "every entry address must replay"), _finding(5, "predecessor_chain", predecessor_chain, True, "linked predecessor addresses", "the append chain must replay"), _finding(6, "supersession_replay", all(not item.supersedes_decision_id or item.supersedes_entry_address for item in entries), True, "paired supersession addresses", "supersession targets must retain entry addresses"), _finding(7, "transition_replay", transition_replay, [item.transition for item in entries], "deterministic transitions", "promotion and regression transitions must replay"), _finding(8, "counter_replay", value.ready_count + value.blocked_count == value.entry_count and value.accepted_count <= value.entry_count, (value.ready_count, value.blocked_count, value.accepted_count), "conserved counters", "ledger counters must conserve entries"), _finding(9, "summary_replay", summary_replay, value.summary.to_dict(), "replayed summary", "summary must derive from ledger fields"), _finding(10, "manifest_replay", value.manifest.content_address == ledger_model.address_manifest(value.manifest) and value.manifest.artifact_addresses == (value.policy.content_address, ledger_model.address_entries(entries), ledger_model.address_checks(value.checks), value.summary.content_address), value.manifest.to_dict(), "replayed manifest", "manifest must retain component addresses"), _finding(11, "head_replay", (value.head_decision_id, value.head_entry_address) == ((head.decision_id, head.content_address) if head else ("", "")), (value.head_decision_id, value.head_entry_address), "replayed head", "ledger head must identify the final entry"), _finding(12, "policy_replay", value.policy.ledger_id == value.ledger_id, value.policy.ledger_id, value.ledger_id, "policy must target this ledger"), _finding(13, "gate_lineage", gate_lineage, "provided gate lineage" if gates is not None else "embedded entry lineage", "matching gate identities and addresses", "optional gate inputs must replay entry lineage"), _finding(14, "check_sequence", tuple(item.ordinal for item in value.checks) == tuple(range(1, ledger_model.MAX_CHECKS + 1)) and tuple(item.check_id for item in value.checks) == ledger_model.CHECK_IDS, [item.check_id for item in value.checks], ledger_model.CHECK_IDS, "ledger checks must preserve canonical order"), _finding(15, "check_addresses", all(ledger_model.address_check(item) == item.content_address for item in value.checks), True, "replayed check addresses", "every ledger check address must replay"), _finding(16, "disposition_replay", value.release_ready == all(item.passed for item in value.checks) and value.state == ("empty" if not entries else "ready" if entries[-1].release_ready else "blocked"), (value.release_ready, value.state), "replayed disposition", "ledger release status must be deterministic"), _finding(17, "public_boundary", _public(value.to_dict()), True, "public value", "ledger artifacts must contain no private records"), _finding(18, "canonical_ledger", canonical_json(value.to_dict()) == canonical_json(ledger_model.ledger_from_mapping(_strict_json_loads(ledger_model.ledger_json(value))).to_dict()), True, "canonical round-trip", "ledger serialization must be deterministic"), _finding(19, "input_lineage", gates is None or gate_lineage, "provided gate lineage" if gates is not None else "embedded lineage", True, "optional inputs must remain linked")); provisional = LedgerAudit(value.ledger_id, value.content_address, MAX_CHECKS, sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), checks, f"pending:{AUDIT_PREFIX}"); return _seal(provisional, address_audit)
def verify_audit(value: LedgerAudit) -> LedgerAudit:
    if not isinstance(value, LedgerAudit): raise ValidationError("gate ledger audit verification requires a typed audit")
    value._validate(); return value
def audit_from_mapping(value: Mapping[str, Any]) -> LedgerAudit: return LedgerAudit.from_mapping(value)
def audit_json(value: LedgerAudit) -> str: return canonical_json(verify_audit(value).to_dict())
def audit_csv(value: LedgerAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()
def render_audit_markdown(value: LedgerAudit) -> str:
    value = verify_audit(value); lines = [f"# Gate decision ledger audit {value.ledger_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"] ; lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks); return "\n".join(lines) + "\n"
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def audit_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent append-only ledger replay", "gate lineage and head verification", "canonical address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "LedgerAuditCheck", "LedgerAudit", "address_check", "address_audit", "audit_ledger", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
