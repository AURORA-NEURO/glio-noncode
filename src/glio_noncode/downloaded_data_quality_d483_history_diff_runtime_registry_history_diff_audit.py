"""Independent replay audit for D483 runtime registry history diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d482_history_diff_runtime_registry_history as history_model
from . import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff as diff_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("typed_diff", "history_identity", "address_links", "item_sequence", "change_counters", "item_conservation", "snapshot_replay", "changed_field_replay", "source_entry_addresses", "direction_replay", "state_transition", "acceptance_replay", "artifact_addresses", "item_addresses", "public_boundary", "canonical_diff")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("diff_id", "left_history_id", "right_history_id", "diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


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
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__") or not hasattr(value, "__iter__") or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)
def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ValidationError(f"{field} must be an object")
    return value
def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed: raise ValidationError(f"{field} contains unknown or missing fields")
def _public(value: Any) -> bool: return history_model.registry_model.runtime_model.diff_model.history_model.batch_model.runtime_model.diff_model.history_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class AuditCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history diff audit ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "runtime registry history diff audit check ID"); self.passed = _bool(passed, "runtime registry history diff audit result"); self.actual = _text(actual, "runtime registry history diff audit actual", 32768); self.expected = _text(expected, "runtime registry history diff audit expected", 32768); self.detail = _text(detail, "runtime registry history diff audit detail", 4096); self.content_address = _address(content_address, "runtime registry history diff audit check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS: raise ValidationError("runtime registry history diff audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("runtime registry history diff audit check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("runtime registry history diff audit check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "runtime registry history diff audit check"); _strict(value, set(cls.FIELDS), "runtime registry history diff audit check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck): raise ValidationError("runtime registry history diff audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class DiffAudit:
    FIELDS = AUDIT_FIELDS
    def __init__(self, diff_id: str, left_history_id: str, right_history_id: str, diff_address: str, checks: Any, check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "runtime registry history diff audit diff ID"); self.left_history_id = _label(left_history_id, "runtime registry history diff audit left history ID"); self.right_history_id = _label(right_history_id, "runtime registry history diff audit right history ID"); self.diff_address = _address(diff_address, "runtime registry history diff audit diff address", diff_model.DIFF_PREFIX); self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "runtime registry history diff audit check")) for item in _sequence(checks, "runtime registry history diff audit checks", MAX_CHECKS)); self.check_count = _count(check_count, "runtime registry history diff audit check count", MAX_CHECKS); self.passed_count = _count(passed_count, "runtime registry history diff audit passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "runtime registry history diff audit failed count", MAX_CHECKS); self.accepted = _bool(accepted, "runtime registry history diff audit acceptance"); self.content_address = _address(content_address, "runtime registry history diff audit address", AUDIT_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0): raise ValidationError("runtime registry history diff audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("runtime registry history diff audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address: raise ValidationError("runtime registry history diff audit address does not replay")
        if not _public(self.to_dict()): raise ValidationError("runtime registry history diff audit crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"diff_id": self.diff_id, "left_history_id": self.left_history_id, "right_history_id": self.right_history_id, "diff_address": self.diff_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffAudit":
        value = _mapping(value, "runtime registry history diff audit"); _strict(value, set(cls.FIELDS), "runtime registry history diff audit"); return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DiffAudit) -> str:
    if not isinstance(value, DiffAudit): raise ValidationError("runtime registry history diff audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)
def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = AuditCheck(**body); return AuditCheck(**(body | {"content_address": address_check(provisional)}))
def audit_diff(value: diff_model.HistoryDiff, left: history_model.RuntimeRegistryHistory | None = None, right: history_model.RuntimeRegistryHistory | None = None) -> DiffAudit:
    diff_model.verify_diff(value); supplied = (left, right) if left is not None and right is not None else None
    if supplied is not None: history_model.verify_history(left); history_model.verify_history(right)
    item_by_left = {item.snapshot_id: item for item in left.entries} if left is not None else {}; item_by_right = {item.snapshot_id: item for item in right.entries} if right is not None else {}
    checks = (
        _finding(1, "typed_diff", isinstance(value, diff_model.HistoryDiff), type(value).__name__, "HistoryDiff", "the audited value must use the typed diff model"),
        _finding(2, "history_identity", supplied is None or (value.left_history_id, value.right_history_id) == (left.history_id, right.history_id) and left.history_id == right.history_id, (value.left_history_id, value.right_history_id), "same history identity", "both sides must retain one history identity"),
        _finding(3, "address_links", supplied is None or (value.left_history_address, value.right_history_address) == (left.content_address, right.content_address), (value.left_history_address, value.right_history_address), "source history addresses", "diff must retain both source history addresses"),
        _finding(4, "item_sequence", tuple(item.ordinal for item in value.items) == tuple(range(1, value.item_count + 1)) and len({item.identity for item in value.items}) == value.item_count, [item.ordinal for item in value.items], "contiguous unique items", "items must be ordered and identity-unique"),
        _finding(5, "change_counters", (value.added_count, value.removed_count, value.changed_count, value.unchanged_count) == tuple(sum(item.change == change for item in value.items) for change in diff_model.CHANGES), (value.added_count, value.removed_count, value.changed_count, value.unchanged_count), "replayed change counters", "change counters must derive from items"),
        _finding(6, "item_conservation", value.item_count == value.added_count + value.removed_count + value.changed_count + value.unchanged_count, value.item_count, "sum of change counts", "items must be conserved"),
        _finding(7, "snapshot_replay", supplied is None or all((not item.left_snapshot or item.left_snapshot == item_by_left.get(item.identity).to_dict()) and (not item.right_snapshot or item.right_snapshot == item_by_right.get(item.identity).to_dict()) for item in value.items), True, "source snapshots", "item snapshots must replay source entries"),
        _finding(8, "changed_field_replay", all(item.change != "changed" or tuple(field for field in history_model.ENTRY_FIELDS if field != "content_address" and item.left_snapshot.get(field) != item.right_snapshot.get(field)) == item.changed_fields for item in value.items), True, "field-level deltas", "changed fields must be exact"),
        _finding(9, "source_entry_addresses", supplied is None or all((not item.left_entry_address or item.left_entry_address == item_by_left[item.identity].content_address) and (not item.right_entry_address or item.right_entry_address == item_by_right[item.identity].content_address) for item in value.items), True, "source entry addresses", "both entry addresses must replay"),
        _finding(10, "direction_replay", supplied is None or value.direction == diff_model._direction(left, right, value.items), value.direction, "replayed direction", "direction must follow readiness movement"),
        _finding(11, "state_transition", supplied is None or value.state_transition == f"{left.latest_state}->{right.latest_state}", value.state_transition, "source state transition", "state transition must retain both latest states"),
        _finding(12, "acceptance_replay", supplied is None or value.accepted == (left.accepted and right.accepted and bool(value.items)), value.accepted, "source acceptance conjunction", "diff acceptance must derive from both histories"),
        _finding(13, "artifact_addresses", value.manifest.artifact_addresses == (diff_model.address_items(value.items), value.summary.content_address), value.manifest.artifact_addresses, "replayed artifacts", "manifest artifacts must be canonical"),
        _finding(14, "item_addresses", all(diff_model.address_item(item) == item.content_address for item in value.items), True, "replayed item addresses", "every item address must replay"),
        _finding(15, "public_boundary", _public(value.to_dict()), True, "public value", "diff must contain no source paths or private records"),
        _finding(16, "canonical_diff", canonical_json(value.to_dict()) == canonical_json(diff_model.diff_from_mapping(_strict_json_loads(diff_model.diff_json(value))).to_dict()), True, "canonical round-trip", "diff serialization must be deterministic"),
    )
    provisional = DiffAudit(value.diff_id, value.left_history_id, value.right_history_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), f"pending:{AUDIT_PREFIX}"); return _seal(provisional, address_audit)
def verify_audit(value: DiffAudit) -> DiffAudit:
    if not isinstance(value, DiffAudit): raise ValidationError("runtime registry history diff audit verification requires a typed audit")
    value._validate(); return value
def audit_from_mapping(value: Mapping[str, Any]) -> DiffAudit: return DiffAudit.from_mapping(value)
def audit_json(value: DiffAudit) -> str: return canonical_json(verify_audit(value).to_dict())
def audit_csv(value: DiffAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()
def render_audit_markdown(value: DiffAudit) -> str:
    value = verify_audit(value); lines = [f"# Runtime registry history diff audit {value.diff_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"] ; lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks); return "\n".join(lines) + "\n"
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def audit_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent history diff replay", "snapshot and field-level verification", "direction and transition verification", "canonical address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "DiffAudit", "address_check", "address_audit", "audit_diff", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
