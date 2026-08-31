"""Independent assurance receipt for history-diff archive-transfer recovery-execution runtime-registry history diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry_history as history_model
from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "history-addresses",
    "identity",
    "item-count",
    "item-order",
    "item-membership",
    "change-replay",
    "field-replay",
    "direction",
    "summary-linkage",
    "items-linkage",
    "manifest-linkage",
    "acceptance",
    "public-boundary",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("diff_address", "diff_id", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
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


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAuditCheck:
    """One independently addressed history-diff finding."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history diff audit ordinal", MAX_CHECKS, lower=1)
        if check_id not in CHECK_IDS:
            raise ValidationError("runtime registry history diff audit check ID is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "runtime registry history diff audit result")
        self.detail = _text(detail, "runtime registry history diff audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "runtime registry history diff audit evidence address") for item in _sequence(evidence_addresses, "runtime registry history diff audit evidence addresses", 128))
        self.content_address = _address(content_address, "runtime registry history diff audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime registry history diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAuditCheck:
        value = _mapping(value, "runtime registry history diff audit check")
        _strict(value, set(cls.FIELDS), "runtime registry history diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAuditCheck) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAuditCheck):
        raise ValidationError("runtime registry history diff audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit:
    """A fixed-size independently recomputed history-diff audit."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, diff_address: str, diff_id: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.diff_address = _address(diff_address, "runtime registry history diff audit diff address", diff_model.DIFF_PREFIX)
        self.diff_id = _label(diff_id, "runtime registry history diff audit diff ID")
        self.version = _text(version, "runtime registry history diff audit version", 1024)
        self.boundary = _text(boundary, "runtime registry history diff audit boundary", 1024)
        self.check_count = _count(check_count, "runtime registry history diff audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry history diff audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry history diff audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry history diff audit acceptance")
        self.checks = tuple(item if isinstance(item, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAuditCheck) else HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime registry history diff audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "runtime registry history diff audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime registry history diff audit version or boundary is unsupported")
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks) or tuple(check.ordinal for check in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(check.check_id for check in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry history diff audit counts or order do not replay")
        if self.accepted != (self.check_count == MAX_CHECKS and self.failed_count == 0):
            raise ValidationError("runtime registry history diff audit acceptance does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime registry history diff audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [check.to_dict() for check in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit:
        value = _mapping(value, "runtime registry history diff audit")
        _strict(value, set(cls.FIELDS), "runtime registry history diff audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit):
        raise ValidationError("runtime registry history diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _latest(value: Mapping[str, Any], side: str) -> Mapping[str, Any]:
    for item in reversed(value["items"]):
        snapshot = item[f"{side}_snapshot"]
        if snapshot:
            return snapshot
    return {}


def _quality(value: Mapping[str, Any], history_entry_count: int) -> tuple[int, int, int, int, int, int]:
    ranks = {"ready": 0, "empty": 1, "blocked": 2}
    return (ranks[value.get("state", "empty")], -int(value.get("ready_count", 0)), -int(value.get("accepted_count", 0)), int(value.get("blocked_count", 0)), -int(value.get("entry_count", 0)), history_entry_count)


def _expected_direction(value: diff_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> str:
    left = value.to_dict()
    right = value.to_dict()
    left_latest = _latest(left, "left")
    right_latest = _latest(right, "right")
    left_quality = _quality(left_latest, value.summary.left_entry_count)
    right_quality = _quality(right_latest, value.summary.right_entry_count)
    if right_quality < left_quality:
        return "improved"
    if right_quality > left_quality:
        return "regressed"
    return "changed" if any(item.change != "unchanged" for item in value.items) else "unchanged"


def _check(check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAuditCheck:
    body = {"ordinal": CHECK_IDS.index(check_id) + 1, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAuditCheck(**body)
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_diff(value: diff_model.HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit:
    value = diff_model.verify_diff(value)
    body = value.to_dict()
    evidence = (value.content_address, value.summary.content_address, value.manifest.content_address, value.items.content_address) if hasattr(value.items, "content_address") else (value.content_address, value.summary.content_address, value.manifest.content_address)
    items = value.items
    expected_counts = {change: sum(item.change == change for item in items) for change in diff_model.CHANGES}
    checks = (
        _check("version", value.version == diff_model.VERSION, "diff version matches the history-diff contract", evidence),
        _check("boundary", value.boundary == diff_model.BOUNDARY, "diff boundary matches the history-diff contract", evidence),
        _check("history-addresses", value.left_history_address.startswith(history_model.HISTORY_PREFIX + ":") and value.right_history_address.startswith(history_model.HISTORY_PREFIX + ":"), "both history inputs retain their addressed identities", (value.left_history_address, value.right_history_address)),
        _check("identity", value.left_history_id == value.summary.left_history_id and value.right_history_id == value.summary.right_history_id, "summary and diff history identities agree", (value.content_address, value.summary.content_address)),
        _check("item-count", value.item_count == len(items) and value.item_count == max(value.summary.left_entry_count, value.summary.right_entry_count), "item count spans the baseline and candidate history lengths", evidence),
        _check("item-order", tuple(item.ordinal for item in items) == tuple(range(1, len(items) + 1)) and tuple(item.identity for item in items) == tuple(f"ordinal-{index:08d}" for index in range(1, len(items) + 1)), "items preserve contiguous stable ordinal identities", (items[0].content_address, items[-1].content_address) if items else evidence),
        _check("item-membership", all((item.change == "added" and not item.left_snapshot and item.right_snapshot) or (item.change == "removed" and item.left_snapshot and not item.right_snapshot) or (item.change in ("changed", "unchanged") and item.left_snapshot and item.right_snapshot) for item in items), "each item has the snapshot membership required by its change class", tuple(item.content_address for item in items)[:4] or evidence),
        _check("change-replay", all(item.change == ("added" if not item.left_snapshot else "removed" if not item.right_snapshot else "changed" if item.left_snapshot != item.right_snapshot else "unchanged") for item in items), "change classes replay from snapshot presence and equality", tuple(item.content_address for item in items)[:4] or evidence),
        _check("field-replay", all(tuple(field for field in history_model.ENTRY_FIELDS if field != "content_address" and item.left_snapshot.get(field) != item.right_snapshot.get(field)) == item.changed_fields for item in items if item.left_snapshot and item.right_snapshot), "changed-field projections replay from paired snapshots", tuple(item.content_address for item in items)[:4] or evidence),
        _check("direction", value.direction == _expected_direction(value), "latest-state quality and semantic change replay the diff direction", (value.summary.content_address, value.content_address)),
        _check("summary-linkage", (value.summary.left_history_address, value.summary.right_history_address, value.summary.added_count, value.summary.removed_count, value.summary.changed_count, value.summary.unchanged_count, value.summary.direction, value.summary.accepted) == (value.left_history_address, value.right_history_address, value.added_count, value.removed_count, value.changed_count, value.unchanged_count, value.direction, value.accepted), "summary metrics and acceptance link to the diff", (value.summary.content_address, value.content_address)),
        _check("items-linkage", (value.added_count, value.removed_count, value.changed_count, value.unchanged_count) == tuple(expected_counts[change] for change in diff_model.CHANGES), "diff counters conserve every item change class", (items.content_address, value.content_address) if hasattr(items, "content_address") else evidence),
        _check("manifest-linkage", value.manifest.files == diff_model.FILES and tuple(value.manifest.artifact_addresses) == (diff_model.address_items(items), value.summary.content_address), "manifest preserves the exact package and component addresses", (value.manifest.content_address, diff_model.address_items(items)),),
        _check("acceptance", value.accepted == (_latest(body, "left").get("accepted", False) and _latest(body, "right").get("accepted", False)), "diff acceptance conserves both latest history acceptance results", (value.left_history_address, value.right_history_address)),
        _check("public-boundary", _public(value.to_dict()), "diff projections contain only bounded public data", evidence),
        _check("mapping-round-trip", diff_model.diff_from_mapping(diff_model.diff_json(value) and json.loads(diff_model.diff_json(value))).to_dict() == value.to_dict(), "canonical mapping round trip preserves the diff", (value.content_address,)),
    )
    accepted = all(check.passed for check in checks)
    audit_body = {"diff_address": value.content_address, "diff_id": value.diff_id, "version": VERSION, "boundary": BOUNDARY, "check_count": len(checks), "passed_count": sum(check.passed for check in checks), "failed_count": sum(not check.passed for check in checks), "accepted": accepted, "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit(**audit_body)
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit(**(audit_body | {"content_address": address_audit(provisional)}))


def verify_audit(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit):
        raise ValidationError("runtime registry history diff audit verification requires a typed audit")
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit:
    return HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit.from_mapping(value)


def audit_json(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit) -> str:
    value = verify_audit(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(check.to_dict()[field] for field in CHECK_FIELDS) for check in value.checks)
    return output.getvalue()


def render_audit_markdown(value: HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# History-diff archive-transfer recovery-execution runtime-registry history diff audit", "", f"- Diff: {value.diff_id}", f"- Checks: {value.passed_count}/{value.check_count}", f"- Accepted: {value.accepted}", f"- Address: {value.content_address}", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {check.ordinal} | {check.check_id} | {check.passed} | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "HistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"diff_address": {"type": "string"}, "diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "maxItems": MAX_CHECKS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "operations": ["audit", "verify", "csv", "markdown", "schema", "capabilities"]}
