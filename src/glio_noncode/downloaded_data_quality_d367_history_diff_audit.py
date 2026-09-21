"""Independent replay audit for runtime registry history diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d367_history_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("item_count", "ordinals", "change_counts", "item_addresses", "identity_order", "paired_fields", "snapshot_boundary", "summary_replay", "manifest_replay", "history_identity", "history_addresses", "direction_replay", "state_transition", "accepted_replay", "diff_address", "public_boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("diff_id", "registry_id", "diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


def _public(value: Any) -> bool:
    return diff_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history diff audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "runtime registry history diff audit check ID")
        self.passed = _bool(passed, "runtime registry history diff audit result")
        self.actual = _text(actual, "runtime registry history diff audit actual", 32768)
        self.expected = _text(expected, "runtime registry history diff audit expected", 32768)
        self.detail = _text(detail, "runtime registry history diff audit detail", 4096)
        self.content_address = _address(content_address, "runtime registry history diff audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("runtime registry history diff audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history diff audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "runtime registry history diff audit check")
        _strict(value, set(cls.FIELDS), "runtime registry history diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("runtime registry history diff audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class DiffAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, diff_id: str, registry_id: str, diff_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "runtime registry history diff audit diff ID")
        self.registry_id = _label(registry_id, "runtime registry history diff audit registry ID")
        self.diff_address = _address(diff_address, "runtime registry history diff audit diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "runtime registry history diff audit check")) for item in _sequence(checks, "runtime registry history diff audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "runtime registry history diff audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry history diff audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry history diff audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry history diff audit acceptance")
        self.content_address = _address(content_address, "runtime registry history diff audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry history diff audit checks are incomplete or out of order")
        if (self.passed_count, self.failed_count) != (sum(item.passed for item in self.checks), sum(not item.passed for item in self.checks)):
            raise ValidationError("runtime registry history diff audit counters do not replay")
        if self.accepted != (self.failed_count == 0) or any(item.content_address != address_check(item) for item in self.checks):
            raise ValidationError("runtime registry history diff audit disposition or check addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history diff audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiffAudit":
        value = _mapping(value, "runtime registry history diff audit")
        _strict(value, set(cls.FIELDS), "runtime registry history diff audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DiffAudit) -> str:
    if not isinstance(value, DiffAudit):
        raise ValidationError("runtime registry history diff audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    return AuditCheck(ordinal, check_id, passed, canonical_json(actual), canonical_json(expected), detail, f"pending:{CHECK_PREFIX}")


def audit_diff(value: diff_model.HistoryDiff) -> DiffAudit:
    diff_model.verify_diff(value)
    items = value.items
    counts = tuple(sum(item.change == change for item in items) for change in diff_model.CHANGES)
    expected_summary = (value.diff_id, value.registry_id, value.left_history_id, value.right_history_id, value.left_history_address, value.right_history_address, value.summary.left_entry_count, value.summary.right_entry_count, value.added_count, value.removed_count, value.changed_count, value.unchanged_count, value.direction, value.state_transition, value.accepted)
    actual_summary = tuple(getattr(value.summary, field) for field in diff_model.SUMMARY_FIELDS[:-1])
    expected_manifest = (value.diff_id, value.left_history_id, value.right_history_id, diff_model.VERSION, diff_model.BOUNDARY, diff_model.FILES, (diff_model.address_items(items), value.summary.content_address))
    actual_manifest = (value.manifest.diff_id, value.manifest.left_history_id, value.manifest.right_history_id, value.manifest.version, value.manifest.boundary, value.manifest.files, value.manifest.artifact_addresses)
    allowed = tuple(field for field in diff_model.history_model.ENTRY_FIELDS if field != "content_address")
    checks = (
        _finding(1, "item_count", value.item_count == len(items), value.item_count, len(items), "item count must replay"),
        _finding(2, "ordinals", tuple(item.ordinal for item in items) == tuple(range(1, len(items) + 1)), tuple(item.ordinal for item in items), "contiguous ordinals", "item ordinals must be contiguous"),
        _finding(3, "change_counts", counts == (value.added_count, value.removed_count, value.changed_count, value.unchanged_count), counts, (value.added_count, value.removed_count, value.changed_count, value.unchanged_count), "change counts must replay"),
        _finding(4, "item_addresses", all(item.content_address == diff_model.address_item(item) for item in items), "replayed", "canonical", "item addresses must replay"),
        _finding(5, "identity_order", tuple(item.identity for item in items) == tuple(f"ordinal-{index}" for index in range(1, len(items) + 1)), tuple(item.identity for item in items), "ordinal identities", "item identities must be stable"),
        _finding(6, "paired_fields", all(item.change in ("added", "removed") or tuple(field for field in allowed if item.left_snapshot.get(field) != item.right_snapshot.get(field)) == item.changed_fields for item in items), "replayed", "field deltas", "changed fields must replay"),
        _finding(7, "snapshot_boundary", all(_public(item.left_snapshot) and _public(item.right_snapshot) for item in items), True, True, "snapshots must remain value-only"),
        _finding(8, "summary_replay", actual_summary == expected_summary and value.summary.content_address == diff_model.address_summary(value.summary), actual_summary, expected_summary, "summary fields and address must replay"),
        _finding(9, "manifest_replay", actual_manifest == expected_manifest and value.manifest.content_address == diff_model.address_manifest(value.manifest), actual_manifest, expected_manifest, "manifest fields and address must replay"),
        _finding(10, "history_identity", value.registry_id == value.summary.registry_id, value.registry_id, value.summary.registry_id, "registry identity must replay"),
        _finding(11, "history_addresses", value.left_history_address != value.right_history_address or value.left_history_id == value.right_history_id, (value.left_history_id, value.right_history_id), "same or distinct addressed histories", "history links must be explicit"),
        _finding(12, "direction_replay", value.direction in diff_model.DIRECTIONS, value.direction, diff_model.DIRECTIONS, "direction must be supported"),
        _finding(13, "state_transition", len(value.state_transition.split("->")) == 2 and all(part in diff_model.history_model.STATES for part in value.state_transition.split("->")), value.state_transition, "state->state", "state transition must be explicit"),
        _finding(14, "accepted_replay", value.accepted == value.summary.accepted, value.accepted, value.summary.accepted, "accepted diff must preserve both histories"),
        _finding(15, "diff_address", value.content_address == diff_model.address_diff(value), value.content_address, diff_model.address_diff(value), "diff address must replay"),
        _finding(16, "public_boundary", _public(value.to_dict()), True, True, "diff audit output must remain value-only and path-free"),
    )
    sealed = tuple(_seal(item, address_check) for item in checks)
    passed = sum(item.passed for item in sealed)
    return _seal(DiffAudit(value.diff_id, value.registry_id, value.content_address, sealed, len(sealed), passed, len(sealed) - passed, passed == len(sealed), f"pending:{AUDIT_PREFIX}"), address_audit)


def verify_audit(value: DiffAudit) -> DiffAudit:
    if not isinstance(value, DiffAudit):
        raise ValidationError("runtime registry history diff audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> DiffAudit:
    return DiffAudit.from_mapping(value)


def audit_json(value: DiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: DiffAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()


def render_audit_markdown(value: DiffAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Runtime registry history diff audit {value.diff_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent diff replay", "field-delta verification", "direction and state-transition verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "DiffAudit", "address_check", "address_audit", "audit_diff", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
