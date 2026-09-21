"""Independent audits for D488 gate-decision ledger diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger as ledger_model
from . import downloaded_data_quality_d488_gate_decision_ledger_diff as diff_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
MAX_CHECKS = 16
CHECK_IDS = ("typed_diff", "ledger_identity", "item_sequence", "classification_replay", "field_delta_replay", "address_integrity", "direction_replay", "transition_replay", "policy_replay", "summary_replay", "manifest_replay", "check_sequence", "check_addresses", "public_boundary", "canonical_diff", "input_lineage")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("diff_id", "diff_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


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
def _public(value: Any) -> bool: return diff_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class DiffAuditCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff audit check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "ledger diff audit check ID"); self.passed = _bool(passed, "ledger diff audit result"); self.actual = _text(actual, "ledger diff audit actual", 32768); self.expected = _text(expected, "ledger diff audit expected", 32768); self.detail = _text(detail, "ledger diff audit detail", 4096); self.content_address = _address(content_address, "ledger diff audit check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS: raise ValidationError("ledger diff audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("ledger diff audit check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("ledger diff audit check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffAuditCheck":
        value = _mapping(value, "ledger diff audit check"); _strict(value, set(cls.FIELDS), "ledger diff audit check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DiffAuditCheck) -> str:
    if not isinstance(value, DiffAuditCheck): raise ValidationError("ledger diff audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class DiffAudit:
    FIELDS = AUDIT_FIELDS
    def __init__(self, diff_id: str, diff_address: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Any, content_address: str) -> None:
        self.diff_id = _label(diff_id, "ledger diff audit diff ID"); self.diff_address = _address(diff_address, "ledger diff audit diff address", diff_model.DIFF_PREFIX); self.check_count = _count(check_count, "ledger diff audit check count", MAX_CHECKS); self.passed_count = _count(passed_count, "ledger diff audit passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "ledger diff audit failed count", MAX_CHECKS); self.accepted = _bool(accepted, "ledger diff audit acceptance"); self.checks = tuple(item if isinstance(item, DiffAuditCheck) else DiffAuditCheck.from_mapping(_mapping(item, "ledger diff audit check")) for item in _sequence(checks, "ledger diff audit checks", MAX_CHECKS)); self.content_address = _address(content_address, "ledger diff audit address", AUDIT_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks): raise ValidationError("ledger diff audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("ledger diff audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address: raise ValidationError("ledger diff audit address does not replay")
        if not _public(self.to_dict()): raise ValidationError("ledger diff audit crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"diff_id": self.diff_id, "diff_address": self.diff_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffAudit":
        value = _mapping(value, "ledger diff audit"); _strict(value, set(cls.FIELDS), "ledger diff audit"); return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DiffAudit) -> str:
    if not isinstance(value, DiffAudit): raise ValidationError("ledger diff audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)
def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> DiffAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = DiffAuditCheck(**body); return DiffAuditCheck(**(body | {"content_address": address_check(provisional)}))
def audit_diff(
    value: diff_model.LedgerDiff,
    left: ledger_model.GateDecisionLedger | None = None,
    right: ledger_model.GateDecisionLedger | None = None,
) -> DiffAudit:
    diff_model.verify_diff(value)
    left_value = left
    right_value = right
    if_lineage = left is None and right is None
    if left is not None:
        ledger_model.verify_ledger(left)
    if right is not None:
        ledger_model.verify_ledger(right)

    ledger_identity = (
        (left is None or (left.ledger_id == value.left_ledger_id and left.content_address == value.left_ledger_address))
        and (right is None or (right.ledger_id == value.right_ledger_id and right.content_address == value.right_ledger_address))
    )
    classification = (
        (value.added_count, value.removed_count, value.changed_count, value.unchanged_count)
        == tuple(sum(item.change == change for item in value.items) for change in diff_model.CHANGES)
    )
    fields = tuple(field for field in ledger_model.ENTRY_FIELDS if field != "content_address")
    field_delta = all(
        item.change != "changed"
        or tuple(field for field in fields if item.left_snapshot.get(field) != item.right_snapshot.get(field)) == item.changed_fields
        for item in value.items
    )
    direction = (
        (not left_value or not right_value)
        or value.direction == diff_model._direction(left_value, right_value, value.items)
    )
    checks = (
        _finding(1, "typed_diff", isinstance(value, diff_model.LedgerDiff), type(value).__name__, "LedgerDiff", "the audited value must use the typed diff model"),
        _finding(2, "ledger_identity", ledger_identity, (value.left_ledger_id, value.right_ledger_id), "matching ledger identities and addresses", "diff must retain both ledger lineages"),
        _finding(3, "item_sequence", tuple(item.ordinal for item in value.items) == tuple(range(1, value.item_count + 1)), [item.ordinal for item in value.items], "contiguous item ordinals", "items must preserve canonical order"),
        _finding(4, "classification_replay", classification and value.item_count == len(value.items), (value.added_count, value.removed_count, value.changed_count, value.unchanged_count), "replayed classifications", "change counters must derive from items"),
        _finding(5, "field_delta_replay", field_delta, [item.changed_fields for item in value.items], "field-level deltas", "changed items must retain exact changed fields"),
        _finding(6, "address_integrity", all((not item.left_snapshot or item.left_entry_address) and (not item.right_snapshot or item.right_entry_address) for item in value.items), True, "retained entry addresses", "snapshots must retain source addresses"),
        _finding(7, "direction_replay", direction, value.direction, "replayed direction", "direction must derive from ledger dispositions"),
        _finding(8, "transition_replay", (not left_value or not right_value) or value.state_transition == f"{left_value.state}->{right_value.state}", value.state_transition, "ledger state transition", "state transition must retain both states"),
        _finding(9, "policy_replay", value.policy.left_ledger_id == value.left_ledger_id and value.policy.right_ledger_id == value.right_ledger_id and diff_model.address_policy(value.policy) == value.policy.content_address, value.policy.to_dict(), "replayed policy", "policy identity and address must replay"),
        _finding(10, "summary_replay", value.summary.content_address == diff_model.address_summary(value.summary) and value.summary.left_ledger_address == value.left_ledger_address and value.summary.right_ledger_address == value.right_ledger_address, value.summary.to_dict(), "replayed summary", "summary must retain ledger identities"),
        _finding(11, "manifest_replay", value.manifest.content_address == diff_model.address_manifest(value.manifest) and value.manifest.artifact_addresses == (value.policy.content_address, diff_model.address_items(value.items), diff_model.address_checks(value.checks), value.summary.content_address), value.manifest.to_dict(), "replayed manifest", "manifest must retain component addresses"),
        _finding(12, "check_sequence", tuple(item.ordinal for item in value.checks) == tuple(range(1, diff_model.MAX_CHECKS + 1)) and tuple(item.check_id for item in value.checks) == diff_model.CHECK_IDS, [item.check_id for item in value.checks], diff_model.CHECK_IDS, "diff checks must preserve canonical order"),
        _finding(13, "check_addresses", all(diff_model.address_check(item) == item.content_address for item in value.checks), True, "replayed check addresses", "every diff check address must replay"),
        _finding(14, "public_boundary", _public(value.to_dict()), True, "public value", "diff artifacts must contain no private records"),
        _finding(15, "canonical_diff", canonical_json(value.to_dict()) == canonical_json(diff_model.diff_from_mapping(_strict_json_loads(diff_model.diff_json(value))).to_dict()), True, "canonical round-trip", "diff serialization must be deterministic"),
        _finding(16, "input_lineage", if_lineage or ledger_identity, "provided ledger lineage" if not if_lineage else "embedded lineage", True, "optional ledger inputs must remain linked"),
    )
    provisional = DiffAudit(
        value.diff_id,
        value.content_address,
        MAX_CHECKS,
        sum(item.passed for item in checks),
        sum(not item.passed for item in checks),
        all(item.passed for item in checks),
        checks,
        f"pending:{AUDIT_PREFIX}",
    )
    return _seal(provisional, address_audit)
def verify_audit(value: DiffAudit) -> DiffAudit:
    if not isinstance(value, DiffAudit): raise ValidationError("ledger diff audit verification requires a typed audit")
    value._validate(); return value
def audit_from_mapping(value: Mapping[str, Any]) -> DiffAudit: return DiffAudit.from_mapping(value)
def audit_json(value: DiffAudit) -> str: return canonical_json(verify_audit(value).to_dict())
def audit_csv(value: DiffAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()
def render_audit_markdown(value: DiffAudit) -> str:
    value = verify_audit(value); lines = [f"# Gate ledger diff audit {value.diff_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"] ; lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks); return "\n".join(lines) + "\n"
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def audit_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent baseline-candidate ledger diff replay", "field delta and lineage verification", "canonical address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "DiffAuditCheck", "DiffAudit", "address_check", "address_audit", "audit_diff", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
