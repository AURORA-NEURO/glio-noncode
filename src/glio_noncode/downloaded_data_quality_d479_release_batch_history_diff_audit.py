"""Independent audit projections for D479 release-batch history diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_quality_d477_release_batch as batch_model
from . import downloaded_data_quality_d478_release_batch_history as history_model
from . import downloaded_data_quality_d479_release_batch_history_diff as diff_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("typed_diff", "diff_address", "history_identity", "history_links", "item_sequence", "change_counts", "field_order", "snapshot_rules", "direction_replay", "summary_replay", "manifest_replay", "item_addresses", "history_addresses", "acceptance_replay", "public_boundary", "canonical_diff")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("diff_id", "diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
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
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__") or not hasattr(value, "__iter__") or len(value) > maximum:
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
    return history_model.batch_model.runtime_model.diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release batch history diff audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "release batch history diff audit check ID")
        self.passed = _bool(passed, "release batch history diff audit result")
        self.actual = _text(actual, "release batch history diff audit actual", 32768)
        self.expected = _text(expected, "release batch history diff audit expected", 32768)
        self.detail = _text(detail, "release batch history diff audit detail", 4096)
        self.content_address = _address(content_address, "release batch history diff audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("release batch history diff audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("release batch history diff audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch history diff audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "release batch history diff audit check")
        _strict(value, set(cls.FIELDS), "release batch history diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("release batch history diff audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class DiffAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, diff_id: str, diff_address: str, checks: Any, check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "release batch history diff audit diff ID")
        self.diff_address = _address(diff_address, "release batch history diff audit diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "release batch history diff audit check")) for item in _sequence(checks, "release batch history diff audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "release batch history diff audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "release batch history diff audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "release batch history diff audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "release batch history diff audit acceptance")
        self.content_address = _address(content_address, "release batch history diff audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("release batch history diff audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("release batch history diff audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("release batch history diff audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release batch history diff audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "diff_address": self.diff_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffAudit":
        value = _mapping(value, "release batch history diff audit")
        _strict(value, set(cls.FIELDS), "release batch history diff audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DiffAudit) -> str:
    if not isinstance(value, DiffAudit):
        raise ValidationError("release batch history diff audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_diff(value: diff_model.HistoryDiff, left: history_model.ReleaseBatchHistory | None = None, right: history_model.ReleaseBatchHistory | None = None) -> DiffAudit:
    diff_model.verify_diff(value)
    if left is not None:
        history_model.verify_history(left)
    if right is not None:
        history_model.verify_history(right)
    histories_match = left is None or right is None or (left.history_id == right.history_id == value.left_history_id == value.right_history_id and left.content_address == value.left_history_address and right.content_address == value.right_history_address)
    items = value.items
    fields = tuple(field for field in history_model.ENTRY_FIELDS if field != "content_address")
    field_order = all(item.changed_fields == tuple(field for field in fields if field in item.changed_fields) for item in items)
    snapshot_rules = all((item.change == "added" and not item.left_snapshot and bool(item.right_snapshot)) or (item.change == "removed" and bool(item.left_snapshot) and not item.right_snapshot) or (item.change in ("changed", "unchanged") and bool(item.left_snapshot) and bool(item.right_snapshot)) for item in items)
    expected_direction = value.direction
    if left is not None and right is not None:
        expected_direction = "improved" if (not left.latest_release_ready and right.latest_release_ready) else "regressed" if (left.latest_release_ready and not right.latest_release_ready) else "unchanged" if not any(item.change != "unchanged" for item in items) else "changed"
    checks = (
        _finding(1, "typed_diff", isinstance(value, diff_model.HistoryDiff), type(value).__name__, "HistoryDiff", "the audited value must use the typed diff model"),
        _finding(2, "diff_address", diff_model.address_diff(value) == value.content_address, value.content_address, diff_model.address_diff(value), "the root diff address must replay"),
        _finding(3, "history_identity", value.left_history_id == value.right_history_id, (value.left_history_id, value.right_history_id), "same history ID", "baseline and candidate must be versions of one history"),
        _finding(4, "history_links", histories_match, (value.left_history_address, value.right_history_address), "supplied history addresses", "optional source histories must match retained links"),
        _finding(5, "item_sequence", tuple(item.ordinal for item in items) == tuple(range(1, len(items) + 1)), [item.ordinal for item in items], "contiguous ordinals", "diff items must preserve deterministic order"),
        _finding(6, "change_counts", (value.added_count, value.removed_count, value.changed_count, value.unchanged_count) == tuple(sum(item.change == change for item in items) for change in diff_model.CHANGES), value.summary.to_dict(), "replayed change counts", "summary counters must derive from items"),
        _finding(7, "field_order", field_order, [item.changed_fields for item in items], "history field order", "field deltas must remain canonical"),
        _finding(8, "snapshot_rules", snapshot_rules, [item.change for item in items], "valid snapshot pairing", "added, removed, changed, and unchanged items must carry the right snapshots"),
        _finding(9, "direction_replay", value.direction == expected_direction and value.state_transition == (f"{left.latest_state}->{right.latest_state}" if left is not None and right is not None else value.state_transition), (value.direction, value.state_transition), expected_direction, "direction and state transition must explain the histories"),
        _finding(10, "summary_replay", value.summary.content_address == diff_model.address_summary(value.summary), value.summary.content_address, diff_model.address_summary(value.summary), "summary address must replay"),
        _finding(11, "manifest_replay", value.manifest.content_address == diff_model.address_manifest(value.manifest), value.manifest.content_address, diff_model.address_manifest(value.manifest), "manifest address must replay"),
        _finding(12, "item_addresses", all(diff_model.address_item(item) == item.content_address for item in items), True, "replayed item addresses", "every item must be independently addressed"),
        _finding(13, "history_addresses", value.left_history_address != value.right_history_address, (value.left_history_address, value.right_history_address), "distinct baseline and candidate addresses", "the diff should compare distinct history snapshots"),
        _finding(14, "acceptance_replay", value.accepted == (value.summary.accepted and bool(items)), value.accepted, "summary acceptance", "diff acceptance must follow its summary"),
        _finding(15, "public_boundary", _public(value.to_dict()), True, "public value", "diffs must contain no source paths or private records"),
        _finding(16, "canonical_diff", canonical_json(value.to_dict()) == canonical_json(diff_model.diff_from_mapping(_strict_json_loads(diff_model.diff_json(value))).to_dict()), True, "canonical round-trip", "diff serialization must be deterministic"),
    )
    provisional = DiffAudit(value.diff_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), f"pending:{AUDIT_PREFIX}")
    return _seal(provisional, address_audit)


def verify_audit(value: DiffAudit) -> DiffAudit:
    if not isinstance(value, DiffAudit):
        raise ValidationError("release batch history diff audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> DiffAudit:
    return DiffAudit.from_mapping(value)


def audit_json(value: DiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: DiffAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: DiffAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Release batch history diff audit {value.diff_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchHistoryDiffAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseBatchHistoryDiffAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}, "$defs": {"check": check_schema()}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent history diff replay", "snapshot pairing and field-delta verification", "direction and state-transition verification", "canonical evidence round-trip", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "DiffAudit", "address_check", "address_audit", "audit_diff", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
