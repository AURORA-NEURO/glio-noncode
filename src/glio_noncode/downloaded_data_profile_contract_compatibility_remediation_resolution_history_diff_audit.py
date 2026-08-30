"""Independent assurance for remediation-resolution history diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff as diff_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "history-linkage", "item-order", "change-replay", "attribute-replay", "counts", "aggregate-replay", "direction-replay", "item-addresses", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "history diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("history diff audit check ID is unsupported")
        self.passed = _bool(passed, "history diff audit check result")
        self.detail = _text(detail, "history diff audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "history diff audit evidence address") for item in _sequence(evidence_addresses, "history diff audit evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("history diff audit checks require evidence")
        self.content_address = _address(content_address, "history diff audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("history diff audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("history diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck:
        value = _mapping(value, "history diff audit check")
        _strict(value, set(cls.FIELDS), "history diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck):
        raise ValidationError("history diff audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, diff_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_address = _address(diff_address, "history diff audit diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "history diff audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "history diff audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "history diff audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history diff audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "history diff audit acceptance")
        self.content_address = _address(content_address, "history diff audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("history diff audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("history diff audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("history diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit:
        value = _mapping(value, "history diff audit")
        _strict(value, set(cls.FIELDS), "history diff audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit):
        raise ValidationError("history diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence) or (diff_model.DIFF_PREFIX + ":empty",), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _expected_attributes(item: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem) -> tuple[str, ...]:
    if item.change in {"added", "removed"}:
        return ()
    left = {key: value for key, value in item.left_snapshot.items() if key != "content_address"}
    right = {key: value for key, value in item.right_snapshot.items() if key != "content_address"}
    return tuple(name for name in diff_model.CHANGED_ATTRIBUTES if left.get(name) != right.get(name))


def _direction(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff) -> str:
    return diff_model._direction(value.left_latest_required_open_count, value.right_latest_required_open_count, value.left_release_ready, value.right_release_ready)


def audit_diff(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit:
    if not isinstance(value, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff):
        raise ValidationError("history diff audit requires a typed diff")
    counts = tuple(sum(item.change == change for item in value.items) for change in diff_model.CHANGES)
    checks = (
        _check(1, "version", value.version == diff_model.VERSION, "history diff version is current", (value.content_address,)),
        _check(2, "boundary", value.boundary == diff_model.BOUNDARY, "history diff boundary is public and value-free", (value.content_address,)),
        _check(3, "history-linkage", all(address.startswith("glio-noncode-download-profile-contract-compatibility-remediation-resolution-history:") for address in (value.left_history_address, value.right_history_address)), "both history addresses retain the public history namespace", (value.left_history_address, value.right_history_address)),
        _check(4, "item-order", tuple(item.ordinal for item in value.items) == tuple(range(1, len(value.items) + 1)) and len({item.identity for item in value.items}) == len(value.items), "diff items retain stable ordinal identities", tuple(item.content_address for item in value.items[:8]) or (value.content_address,)),
        _check(5, "change-replay", all(item.change == ("added" if not item.left_snapshot else "removed" if not item.right_snapshot else "unchanged" if not item.changed_attributes else "changed") for item in value.items), "each item change replays from its two snapshots", tuple(item.content_address for item in value.items[:8]) or (value.content_address,)),
        _check(6, "attribute-replay", all(item.changed_attributes == _expected_attributes(item) for item in value.items), "changed attributes replay from value-free snapshots", tuple(item.content_address for item in value.items[:8]) or (value.content_address,)),
        _check(7, "counts", counts == (value.added_count, value.removed_count, value.changed_count, value.unchanged_count), "diff change counts are conserved", (value.content_address,)),
        _check(8, "aggregate-replay", value.improved_delta == value.right_improved_count - value.left_improved_count and value.regressed_delta == value.right_regressed_count - value.left_regressed_count and value.left_entry_count == value.left_initial_count + value.left_improved_count + value.left_regressed_count + value.left_unchanged_count and value.right_entry_count == value.right_initial_count + value.right_improved_count + value.right_regressed_count + value.right_unchanged_count, "history transition totals and deltas replay", (value.content_address,)),
        _check(9, "direction-replay", value.direction == _direction(value), "latest open-count and readiness direction replays", (value.content_address,)),
        _check(10, "item-addresses", all(diff_model.address_item(item) == item.content_address for item in value.items), "every diff item has a stable content address", tuple(item.content_address for item in value.items[:8]) or (value.content_address,)),
        _check(11, "public-boundary", _public(value.to_dict()), "history diff contains no forbidden public metadata", (value.content_address,)),
        _check(12, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).content_address == value.content_address, "history diff mapping round-trips to the same address", (value.content_address,)),
    )
    passed = sum(item.passed for item in checks)
    body = {"diff_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Diff Audit", "", f"- Diff: `{value.diff_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"diff_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_diff", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
