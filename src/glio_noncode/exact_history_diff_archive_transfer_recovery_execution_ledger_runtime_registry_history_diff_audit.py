"""Independent replay audit for execution-ledger runtime registry history diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "identity", "history-linkage", "item-order", "change-replay", "field-replay", "counts-replay", "direction-replay", "acceptance-replay", "items-address", "summary-address", "manifest-address", "artifact-receipts", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "evidence", "content_address")
AUDIT_FIELDS = ("version", "boundary", "diff_id", "registry_id", "item_count", "check_count", "passed", "checks", "content_address")
MAX_TEXT = 4096


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, evidence: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "registry history diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("registry history diff audit check ID is unsupported")
        self.passed = _bool(passed, "registry history diff audit result")
        self.observed = observed
        self.expected = expected
        self.evidence = tuple(_text(item, "registry history diff audit evidence", 2048) for item in _sequence(evidence, "registry history diff audit evidence", 8))
        self.content_address = _address(content_address, "registry history diff audit check address", CHECK_PREFIX, allow_pending=True)
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("registry history diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff audit check")
        _strict(value, set(cls.FIELDS), "registry history diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, version: str, boundary: str, diff_id: str, registry_id: str, item_count: int, check_count: int, passed: bool, checks: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAuditCheck], content_address: str) -> None:
        self.version = _text(version, "registry history diff audit version", 1024)
        self.boundary = _text(boundary, "registry history diff audit boundary", 1024)
        self.diff_id = _label(diff_id, "registry history diff audit diff ID")
        self.registry_id = _label(registry_id, "registry history diff audit registry ID")
        self.item_count = _count(item_count, "registry history diff audit item count", diff_model.MAX_ITEMS)
        self.check_count = _count(check_count, "registry history diff audit check count", len(CHECK_IDS))
        self.passed = _bool(passed, "registry history diff audit passed")
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "registry history diff audit checks", len(CHECK_IDS)))
        self.content_address = _address(content_address, "registry history diff audit address", AUDIT_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or tuple(item.check_id for item in self.checks) != CHECK_IDS or not self.checks or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("registry history diff audit does not replay its checks")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("registry history diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "diff_id": self.diff_id, "registry_id": self.registry_id, "item_count": self.item_count, "check_count": self.check_count, "passed": self.passed, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry history diff audit")
        _strict(value, set(cls.FIELDS), "registry history diff audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any, evidence: Sequence[str]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAuditCheck:
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAuditCheck(check_id, observed == expected, observed, expected, evidence, CHECK_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAuditCheck(check_id, provisional.passed, observed, expected, evidence, address_check(provisional))


def _latest(items: Sequence[diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItem], side: str) -> Mapping[str, Any]:
    field = "left_snapshot" if side == "left" else "right_snapshot"
    for item in reversed(items):
        snapshot = getattr(item, field)
        if snapshot:
            return snapshot
    return {}


def _quality(snapshot: Mapping[str, Any], entry_count: int) -> tuple[int, int, int, int, int, int]:
    state = snapshot.get("state", "empty")
    ranks = {"ready": 0, "empty": 1, "blocked": 2}
    return (ranks.get(state, 2), -int(snapshot.get("ready_count", 0)), -int(snapshot.get("accepted_count", 0)), int(snapshot.get("blocked_count", 0)), -int(snapshot.get("entry_count", 0)), entry_count)


def _expected_direction(value: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff) -> str:
    left, right = _latest(value.items, "left"), _latest(value.items, "right")
    if _quality(right, value.summary.right_entry_count) < _quality(left, value.summary.left_entry_count):
        return "improved"
    if _quality(right, value.summary.right_entry_count) > _quality(left, value.summary.left_entry_count):
        return "regressed"
    return "changed" if any(item.change != "unchanged" for item in value.items) else "unchanged"


def audit_diff(value: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff):
    value = diff_model.verify_diff(value)
    expected_changes = []
    for item in value.items:
        left, right = item.left_snapshot, item.right_snapshot
        expected_change = "added" if left == {} else "removed" if right == {} else "changed" if left != right else "unchanged"
        expected_fields = diff_model._changed_fields(left, right) if left and right else ()
        expected_changes.append((expected_change, tuple(expected_fields)))
    checks = (
        _check("version", value.version, diff_model.VERSION, (value.content_address,)),
        _check("boundary", value.boundary, diff_model.BOUNDARY, (value.content_address,)),
        _check("identity", (value.registry_id, value.diff_id, value.left_history_id, value.right_history_id), (value.registry_id, value.diff_id, value.left_history_id, value.right_history_id), (value.content_address,)),
        _check("history-linkage", (value.summary.left_history_address, value.summary.right_history_address, value.left_history_address, value.right_history_address), (value.left_history_address, value.right_history_address, value.left_history_address, value.right_history_address), (value.summary.content_address,)),
        _check("item-order", tuple(item.ordinal for item in value.items), tuple(range(1, value.item_count + 1)), (diff_model.address_items(value.items),)),
        _check("change-replay", tuple((item.change, item.changed_fields) for item in value.items), tuple(expected_changes), tuple(item.content_address for item in value.items)),
        _check("field-replay", tuple(tuple(diff_model._changed_fields(item.left_snapshot, item.right_snapshot)) if item.left_snapshot and item.right_snapshot else () for item in value.items), tuple(item.changed_fields for item in value.items), tuple(item.content_address for item in value.items)),
        _check("counts-replay", (value.added_count, value.removed_count, value.changed_count, value.unchanged_count), tuple(sum(item.change == change for item in value.items) for change in diff_model.CHANGES), (value.summary.content_address,)),
        _check("direction-replay", value.direction, _expected_direction(value), (value.summary.content_address,)),
        _check("acceptance-replay", value.accepted, value.summary.accepted, (value.summary.content_address,)),
        _check("items-address", diff_model.address_items(value.items), diff_model.ITEMS_PREFIX + ":" + diff_model.address_items(value.items).split(":", 1)[1], (value.content_address,)),
        _check("summary-address", diff_model.address_summary(value.summary), value.summary.content_address, (value.summary.content_address,)),
        _check("manifest-address", diff_model.address_manifest(value.manifest), value.manifest.manifest_address, (value.manifest.manifest_address,)),
        _check("artifact-receipts", tuple((item.ordinal, item.name, item.size, item.content_address) for item in value.manifest.artifacts), ((1, "items.json", value.manifest.artifacts[0].size, diff_model.address_items(value.items)), (2, "summary.json", value.manifest.artifacts[1].size, value.summary.content_address)), (value.manifest.manifest_address,)),
        _check("public-boundary", _public(value.to_dict()), True, (value.content_address,)),
        _check("mapping-round-trip", diff_model.diff_json(diff_model.diff_from_mapping(value.to_dict())), diff_model.diff_json(value), (value.content_address,)),
    )
    body = {"version": VERSION, "boundary": BOUNDARY, "diff_id": value.diff_id, "registry_id": value.registry_id, "item_count": value.item_count, "check_count": len(checks), "passed": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAudit(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAudit(**(body | {"content_address": address_audit(provisional)}))


def verify_audit(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAudit):
        raise ValidationError("registry history diff audit verification requires a typed audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAudit.from_mapping(value)


def audit_json(value) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value) -> str:
    value = verify_audit(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return output.getvalue()


def render_audit_markdown(value) -> str:
    value = verify_audit(value)
    lines = ["# Execution-ledger runtime registry history diff audit", "", f"- Diff: {value.diff_id}", f"- Registry: {value.registry_id}", f"- Passed: {value.passed}", f"- Address: {value.content_address}", "", "| check | passed | observed | expected |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {item.passed} | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "evidence": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "diff_id": {"type": "string"}, "registry_id": {"type": "string"}, "item_count": {"type": "integer", "minimum": 0}, "check_count": {"const": len(CHECK_IDS)}, "passed": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": len(CHECK_IDS), "operations": ("audit_diff", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAuditCheck", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffAudit", "address_check", "address_audit", "audit_diff", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
