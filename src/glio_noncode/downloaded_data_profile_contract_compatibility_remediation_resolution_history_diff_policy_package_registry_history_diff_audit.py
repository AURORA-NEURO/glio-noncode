"""Independent assurance for policy package registry history diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff as diff_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "identity-linkage", "item-order", "change-replay", "count-replay", "transition-deltas", "direction-replay", "state-transition", "address-replay", "manifest-linkage", "summary-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
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


def _snapshot_quality(snapshot: Mapping[str, Any]) -> tuple[int, int, int, int, int, int]:
    ranks = {"ready": 0, "empty": 1, "review": 2, "blocked": 3}
    return (ranks[snapshot["state"]], -snapshot["release_ready_count"], -snapshot["accepted_count"], snapshot["block_count"], snapshot["hold_count"], snapshot["entry_count"])


def _direction(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff) -> str:
    left = next((item.left_snapshot for item in reversed(value.items) if item.left_snapshot), {"state": value.left_state, "release_ready_count": 0, "accepted_count": 0, "block_count": 0, "hold_count": 0, "entry_count": value.left_entry_count, "registry_id": "", "decision": "hold", "accepted": False, "release_ready": False, "transition": "initial", "promote_count": 0})
    right = next((item.right_snapshot for item in reversed(value.items) if item.right_snapshot), {"state": value.right_state, "release_ready_count": 0, "accepted_count": 0, "block_count": 0, "hold_count": 0, "entry_count": value.right_entry_count, "registry_id": "", "decision": "hold", "accepted": False, "release_ready": False, "transition": "initial", "promote_count": 0})
    if _snapshot_quality(right) < _snapshot_quality(left):
        return "improved"
    if _snapshot_quality(right) > _snapshot_quality(left):
        return "regressed"
    return "mixed" if any(item.change != "unchanged" for item in value.items) else "unchanged"


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history diff audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "registry history diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("registry history diff audit check ID is unsupported")
        self.passed = _bool(passed, "registry history diff audit check result")
        self.detail = _text(detail, "registry history diff audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "registry history diff audit evidence address") for item in _sequence(evidence_addresses, "registry history diff audit evidence addresses", diff_model.MAX_ITEMS + 1)}))
        if not self.evidence_addresses:
            raise ValidationError("registry history diff audit checks require evidence")
        self.content_address = _address(content_address, "registry history diff audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("registry history diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck:
        value = _mapping(value, "registry history diff audit check")
        _strict(value, set(cls.FIELDS), "registry history diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck):
        raise ValidationError("registry history diff audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, diff_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_address = _address(diff_address, "registry history diff audit diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "registry history diff audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "registry history diff audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "registry history diff audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "registry history diff audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "registry history diff audit acceptance")
        self.content_address = _address(content_address, "registry history diff audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)):
            raise ValidationError("registry history diff audit check order is not conserved")
        if tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("registry history diff audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("registry history diff audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("registry history diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit:
        value = _mapping(value, "registry history diff audit")
        _strict(value, set(cls.FIELDS), "registry history diff audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit):
        raise ValidationError("registry history diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence) or (diff_model.DIFF_PREFIX + ":empty",), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_diff(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit:
    if not isinstance(value, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiff):
        raise ValidationError("registry history diff audit requires a typed diff")
    items = value.items
    evidence = tuple(item.content_address for item in items[: diff_model.MAX_ITEMS + 1]) or (value.content_address,)
    expected_changes = []
    for item in items:
        if not item.left_snapshot:
            expected_changes.append("added")
        elif not item.right_snapshot:
            expected_changes.append("removed")
        elif item.left_snapshot == item.right_snapshot and item.left_registry_address == item.right_registry_address:
            expected_changes.append("unchanged")
        else:
            expected_changes.append("changed")
    counts = tuple(expected_changes.count(change) for change in diff_model.CHANGES)
    left_addresses = tuple(item.left_registry_address for item in items if item.left_registry_address)
    right_addresses = tuple(item.right_registry_address for item in items if item.right_registry_address)
    checks = (
        _check(1, "version", value.version == diff_model.VERSION, "registry history diff version is current", (value.content_address,)),
        _check(2, "boundary", value.boundary == diff_model.BOUNDARY, "registry history diff boundary is public and value-free", (value.content_address,)),
        _check(3, "identity-linkage", tuple(item.identity for item in items) == tuple(f"ordinal-{index}" for index in range(1, len(items) + 1)), "diff identities link to ordinal positions", evidence),
        _check(4, "item-order", tuple(item.ordinal for item in items) == tuple(range(1, len(items) + 1)), "diff items retain canonical order", evidence),
        _check(5, "change-replay", tuple(item.change for item in items) == tuple(expected_changes), "added removed changed and unchanged classifications replay", evidence),
        _check(6, "count-replay", counts == (value.added_count, value.removed_count, value.changed_count, value.unchanged_count), "diff item counts are conserved", (value.content_address,)),
        _check(7, "transition-deltas", (value.initial_delta, value.improved_delta, value.regressed_delta, value.unchanged_delta, value.changed_delta) == (value.summary.initial_delta, value.summary.improved_delta, value.summary.regressed_delta, value.summary.unchanged_delta, value.summary.changed_delta), "history transition deltas replay", (value.summary.content_address,)),
        _check(8, "direction-replay", value.direction == _direction(value), "diff direction replays from latest public snapshots", (value.content_address,)),
        _check(9, "state-transition", value.state_transition == f"{value.left_state}->{value.right_state}", "state transition replays", (value.content_address,)),
        _check(10, "address-replay", len(set(left_addresses)) == len(left_addresses) and len(set(right_addresses)) == len(right_addresses), "side snapshot addresses remain unique", evidence),
        _check(11, "manifest-linkage", (value.manifest.diff_id, value.manifest.files, tuple(value.manifest.artifact_addresses)) == (value.diff_id, diff_model.FILES, (diff_model.address_items(items), value.summary.content_address)), "manifest links exact diff artifacts", (value.manifest.content_address,)),
        _check(12, "summary-linkage", value.summary.to_dict() == {field: value.to_dict()[field] for field in diff_model.SUMMARY_FIELDS if field != "content_address"} | {"content_address": value.summary.content_address}, "diff summary mirrors the top-level diff", (value.summary.content_address,)),
        _check(13, "public-boundary", _public(value.to_dict()), "diff contains no forbidden public metadata", (value.content_address,)),
        _check(14, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).content_address == value.content_address, "diff mapping round-trips to the same address", (value.content_address,)),
    )
    passed = sum(item.passed for item in checks)
    body = {"diff_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return output.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry History Diff Audit", "", f"- Diff: `{value.diff_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": diff_model.MAX_ITEMS + 1}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"diff_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent diff classification", "transition delta replay", "direction and state verification", "artifact manifest verification", "public-boundary enforcement", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
