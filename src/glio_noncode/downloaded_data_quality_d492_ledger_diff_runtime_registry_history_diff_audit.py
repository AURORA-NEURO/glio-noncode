"""Independent replay audit for D492 runtime registry history diffs."""
from __future__ import annotations

# ruff: noqa: E501, I001
import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_quality_d491_ledger_diff_runtime_registry_history as history_model
from . import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as diff_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("typed_diff", "history_identity", "source_addresses", "item_sequence", "snapshot_identity", "change_replay", "field_delta_replay", "counter_replay", "source_history_replay", "direction_replay", "state_transition", "acceptance_replay", "artifact_addresses", "item_addresses", "public_boundary", "canonical_diff")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("diff_id", "left_history_id", "right_history_id", "diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)

def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(c) < 32 and c not in "\n\t" for c in value): raise ValidationError(f"{field} must be bounded public text")
    return value
def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(c.isspace() for c in value) or "/" in value or "\\" in value or '"' in value: raise ValidationError(f"{field} must be a compact label")
    return value
def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"): return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix and not value.startswith(prefix + ":")): raise ValidationError(f"{field} has the wrong namespace")
    return value
def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= maximum: raise ValidationError(f"{field} is outside its bound")
    return value
def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool): raise ValidationError(f"{field} must be boolean")
    return value
def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__") or not hasattr(value, "__iter__") or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)
def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ValidationError(f"{field} must be an object")
    return value
def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed: raise ValidationError(f"{field} contains unknown or missing fields")
def _public(value: Any) -> bool: return history_model.registry_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value

class AuditCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "D492 audit ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "D492 check ID"); self.passed = _bool(passed, "D492 check result"); self.actual = _text(actual, "D492 actual", 32768); self.expected = _text(expected, "D492 expected", 32768); self.detail = _text(detail, "D492 detail", 4096); self.content_address = _address(content_address, "D492 check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS: raise ValidationError("D492 check ID is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("D492 check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D492 check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "D492 audit check"); _strict(value, set(cls.FIELDS), "D492 audit check"); return cls(*(value[f] for f in cls.FIELDS))

def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck): raise ValidationError("D492 check addressing requires a typed check")
    return _address_for(value, CHECK_PREFIX)

class DiffAudit:
    FIELDS = AUDIT_FIELDS
    def __init__(self, diff_id: str, left_history_id: str, right_history_id: str, diff_address: str, checks: Any, check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "D492 audit diff ID"); self.left_history_id = _label(left_history_id, "D492 audit left history ID"); self.right_history_id = _label(right_history_id, "D492 audit right history ID"); self.diff_address = _address(diff_address, "D492 audited address", diff_model.DIFF_PREFIX); self.checks = tuple(x if isinstance(x, AuditCheck) else AuditCheck.from_mapping(_mapping(x, "D492 audit check")) for x in _sequence(checks, "D492 checks", MAX_CHECKS)); self.check_count = _count(check_count, "D492 check count", MAX_CHECKS); self.passed_count = _count(passed_count, "D492 passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "D492 failed count", MAX_CHECKS); self.accepted = _bool(accepted, "D492 audit acceptance"); self.content_address = _address(content_address, "D492 audit address", AUDIT_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(x.passed for x in self.checks) or self.accepted != (self.failed_count == 0): raise ValidationError("D492 audit counters do not replay")
        if tuple(x.ordinal for x in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(x.check_id for x in self.checks) != CHECK_IDS: raise ValidationError("D492 audit check ordering is not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address: raise ValidationError("D492 audit address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D492 audit crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"diff_id": self.diff_id, "left_history_id": self.left_history_id, "right_history_id": self.right_history_id, "diff_address": self.diff_address, "checks": [x.to_dict() for x in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffAudit":
        value = _mapping(value, "D492 audit"); _strict(value, set(cls.FIELDS), "D492 audit"); return cls(*(value[f] for f in cls.FIELDS))

def address_audit(value: DiffAudit) -> str:
    if not isinstance(value, DiffAudit): raise ValidationError("D492 audit addressing requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)

def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; item = AuditCheck(**body); return AuditCheck(**(body | {"content_address": address_check(item)}))

def audit_diff(value: diff_model.HistoryDiff, left: history_model.RuntimeRegistryHistory | None = None, right: history_model.RuntimeRegistryHistory | None = None) -> DiffAudit:
    diff_model.verify_diff(value)
    if (left is None) != (right is None): raise ValidationError("D492 source replay requires both histories or neither")
    if left is not None:
        history_model.verify_history(left); history_model.verify_history(right)
    ids = (value.left_history_id, value.right_history_id)
    source_ids = (left.history_id, right.history_id) if left is not None else ids
    source_addresses = (left.content_address, right.content_address) if left is not None else (value.left_history_address, value.right_history_address)
    expected_items = diff_model.build_diff(left, right, diff_id=value.diff_id).items if left is not None else value.items
    fields = tuple(f for f in history_model.ENTRY_FIELDS if f != "content_address")
    change_replay = all((item.change == "added" and not item.left_snapshot and bool(item.right_snapshot)) or (item.change == "removed" and bool(item.left_snapshot) and not item.right_snapshot) or (item.change == "changed" and bool(item.left_snapshot) and bool(item.right_snapshot) and item.left_snapshot != item.right_snapshot) or (item.change == "unchanged" and item.left_snapshot == item.right_snapshot and bool(item.left_snapshot)) for item in value.items)
    delta_replay = all(item.changed_fields == tuple(f for f in fields if item.left_snapshot.get(f) != item.right_snapshot.get(f)) for item in value.items if item.change == "changed") and all(not item.changed_fields for item in value.items if item.change != "changed")
    if left is not None:
        direction = diff_model._direction(left, right, expected_items)
    else:
        left_state, right_state = value.state_transition.split("->", 1)
        left_ready, right_ready = left_state == "ready", right_state == "ready"
        direction = ("improved" if right_ready else "regressed") if left_ready != right_ready else ("unchanged" if not any(x.change != "unchanged" for x in value.items) else "changed")
    transition = f"{left.latest_state}->{right.latest_state}" if left is not None else value.state_transition
    acceptance = bool(left.accepted and right.accepted and value.items) if left is not None else bool(value.summary.left_entry_count and value.summary.right_entry_count and value.items)
    checks = (
        _finding(1, "typed_diff", isinstance(value, diff_model.HistoryDiff), type(value).__name__, "HistoryDiff", "comparison uses the typed D492 model"),
        _finding(2, "history_identity", value.left_history_id == value.right_history_id, ids, "same history identity", "baseline and candidate must belong to one history"),
        _finding(3, "source_addresses", (value.left_history_id, value.right_history_id, value.left_history_address, value.right_history_address) == (source_ids[0], source_ids[1], source_addresses[0], source_addresses[1]), (value.left_history_id, value.right_history_id, value.left_history_address, value.right_history_address), (source_ids[0], source_ids[1], source_addresses[0], source_addresses[1]), "both source history identities and addresses must match"),
        _finding(4, "item_sequence", (tuple(x.ordinal for x in value.items), len({x.identity for x in value.items})) == (tuple(range(1, value.item_count + 1)), value.item_count), [x.ordinal for x in value.items], "contiguous unique identities", "items preserve deterministic order"),
        _finding(5, "snapshot_identity", all((not x.left_snapshot or x.left_snapshot.get("snapshot_id") == x.identity) and (not x.right_snapshot or x.right_snapshot.get("snapshot_id") == x.identity) for x in value.items), True, "snapshot IDs match item identities", "items align source snapshots by stable ID"),
        _finding(6, "change_replay", change_replay, [x.change for x in value.items], "snapshot-presence and equality replay", "change type follows the paired snapshots"),
        _finding(7, "field_delta_replay", delta_replay, [x.changed_fields for x in value.items], "exact changed field sets", "field deltas must be complete and ordered"),
        _finding(8, "counter_replay", (value.item_count, value.added_count, value.removed_count, value.changed_count, value.unchanged_count), (len(value.items), sum(x.change == "added" for x in value.items), sum(x.change == "removed" for x in value.items), sum(x.change == "changed" for x in value.items), sum(x.change == "unchanged" for x in value.items)), "counts derive from item classifications", "summary counters conserve the aligned snapshots"),
        _finding(9, "source_history_replay", [x.to_dict() for x in value.items] == [x.to_dict() for x in expected_items], "matched source histories" if left is not None else "detached evidence", "independent baseline/candidate replay" if left is not None else "source pair not supplied", "when supplied, both histories independently reproduce every item"),
        _finding(10, "direction_replay", value.direction == direction, value.direction, direction, "readiness movement determines comparison direction"),
        _finding(11, "state_transition", value.state_transition == transition, value.state_transition, transition, "transition retains both latest states"),
        _finding(12, "acceptance_replay", value.accepted == acceptance, value.accepted, acceptance, "acceptance derives from nonempty accepted source histories"),
        _finding(13, "artifact_addresses", value.manifest.artifact_addresses == (diff_model.address_items(value.items), value.summary.content_address), value.manifest.artifact_addresses, "replayed artifact addresses", "manifest points to canonical components"),
        _finding(14, "item_addresses", all(diff_model.address_item(x) == x.content_address for x in value.items), True, "all item addresses replay", "item addresses are independently verifiable"),
        _finding(15, "public_boundary", _public(value.to_dict()), True, "public value", "comparison contains no local paths or private records"),
        _finding(16, "canonical_diff", canonical_json(value.to_dict()) == canonical_json(diff_model.diff_from_mapping(_strict_json_loads(diff_model.diff_json(value))).to_dict()), True, "canonical round-trip", "serialization is deterministic and schema strict"),
    )
    audit = DiffAudit(value.diff_id, value.left_history_id, value.right_history_id, value.content_address, checks, len(checks), sum(x.passed for x in checks), sum(not x.passed for x in checks), all(x.passed for x in checks), f"pending:{AUDIT_PREFIX}")
    return _seal(audit, address_audit)

def verify_audit(value: DiffAudit) -> DiffAudit:
    if not isinstance(value, DiffAudit): raise ValidationError("D492 verification requires a typed audit")
    value._validate(); return value
def audit_from_mapping(value: Mapping[str, Any]) -> DiffAudit: return DiffAudit.from_mapping(value)
def audit_json(value: DiffAudit) -> str: return canonical_json(verify_audit(value).to_dict())
def audit_csv(value: DiffAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(x.to_dict() for x in verify_audit(value).checks); return output.getvalue()
def render_audit_markdown(value: DiffAudit) -> str:
    value = verify_audit(value); lines = [f"# D492 diff audit {value.diff_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {x.check_id} | {str(x.passed).lower()} | {x.detail} |" for x in value.checks); return "\n".join(lines) + "\n"
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryDiffAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {f: {"type": "integer" if f == "ordinal" else "boolean" if f == "passed" else "string"} for f in CHECK_FIELDS}}
def audit_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryDiffAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {f: {"type": "array" if f == "checks" else "integer" if f.endswith("count") else "boolean" if f == "accepted" else "string"} for f in AUDIT_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent snapshot-diff replay", "source-history lineage checks", "field-delta verification", "direction and transition checks", "canonical addresses and serialization"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}

__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "DiffAudit", "address_check", "address_audit", "audit_diff", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
