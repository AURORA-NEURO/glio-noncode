"""Independent assurance for policy package registry histories."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history as history_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry as registry_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "entry-order", "ancestry-links", "registry-identity", "latest-linkage", "transition-replay", "transition-counts", "summary-counts", "disposition-replay", "registry-addresses", "entry-addresses", "manifest-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("history_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


def _quality(value: Any) -> tuple[int, int, int, int, int, int]:
    ranks = {"ready": 0, "empty": 1, "review": 2, "blocked": 3}
    return (ranks[value.state], -value.release_ready_count, -value.accepted_count, value.block_count, value.hold_count, value.entry_count)


def _transition(current: Any, previous: Any | None) -> str:
    if previous is None:
        return "initial"
    if _quality(current) < _quality(previous):
        return "improved"
    if _quality(current) > _quality(previous):
        return "regressed"
    fields = ("entry_count", "accepted_count", "release_ready_count", "promote_count", "hold_count", "block_count", "state", "decision", "accepted", "release_ready")
    return "unchanged" if all(getattr(current, field) == getattr(previous, field) for field in fields) else "changed"


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "registry history audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("registry history audit check ID is unsupported")
        self.passed = _bool(passed, "registry history audit check result")
        self.detail = _text(detail, "registry history audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "registry history audit evidence address") for item in _sequence(evidence_addresses, "registry history audit evidence addresses", 12)}))
        if not self.evidence_addresses:
            raise ValidationError("registry history audit checks require evidence")
        self.content_address = _address(content_address, "registry history audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("registry history audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("registry history audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck:
        value = _mapping(value, "registry history audit check")
        _strict(value, set(cls.FIELDS), "registry history audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck):
        raise ValidationError("registry history audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, history_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.history_address = _address(history_address, "registry history audit history address", history_model.HISTORY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck.from_mapping(item) for item in _sequence(checks, "registry history audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "registry history audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "registry history audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "registry history audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "registry history audit acceptance")
        self.content_address = _address(content_address, "registry history audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)):
            raise ValidationError("registry history audit check order is not conserved")
        if tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("registry history audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("registry history audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry history audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("registry history audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit:
        value = _mapping(value, "registry history audit")
        _strict(value, set(cls.FIELDS), "registry history audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit):
        raise ValidationError("registry history audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence) or (history_model.HISTORY_PREFIX + ":empty",), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_history(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit:
    if not isinstance(value, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
        raise ValidationError("registry history audit requires a typed history")
    entries = value.entries
    replayed = tuple(_transition(item, entries[index - 1] if index else None) for index, item in enumerate(entries))
    latest = entries[-1] if entries else None
    expected_latest = (latest.registry_address, latest.entry_count, latest.accepted_count, latest.release_ready_count) if latest else ("", 0, 0, 0)
    expected_state = latest.state if latest else "empty"
    expected_decision = {"empty": "hold", "ready": "promote", "review": "hold", "blocked": "block"}[expected_state]
    expected_acceptance = latest.accepted if latest else False
    expected_readiness = latest.release_ready if latest else False
    entries_evidence = tuple(item.content_address for item in entries[:12]) or (value.content_address,)
    checks = (
        _check(1, "version", value.version == history_model.VERSION, "registry history version is current", (value.content_address,)),
        _check(2, "boundary", value.boundary == history_model.BOUNDARY, "registry history boundary is public and value-free", (value.content_address,)),
        _check(3, "entry-order", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), "registry history entries retain append order", entries_evidence),
        _check(4, "ancestry-links", all(index == 0 or item.previous_registry_address == entries[index - 1].registry_address for index, item in enumerate(entries)), "each registry snapshot links to the immediately previous snapshot", entries_evidence),
        _check(5, "registry-identity", len({item.registry_id for item in entries}) <= 1 and (not entries or value.registry_id == entries[0].registry_id), "history retains one logical registry identity", entries_evidence),
        _check(6, "latest-linkage", (value.latest_registry_address, value.latest_entry_count, value.latest_accepted_count, value.latest_release_ready_count) == expected_latest, "latest registry snapshot linkage replays", (value.content_address,)),
        _check(7, "transition-replay", tuple(item.transition for item in entries) == replayed, "trend transitions replay from adjacent registry summaries", entries_evidence),
        _check(8, "transition-counts", tuple(sum(item.transition == transition for item in entries) for transition in history_model.TRANSITIONS) == (value.initial_count, value.improved_count, value.regressed_count, value.unchanged_count, value.changed_count), "transition totals are conserved", (value.content_address,)),
        _check(9, "summary-counts", (value.summary.entry_count, value.summary.latest_registry_address, value.summary.latest_entry_count, value.summary.latest_accepted_count, value.summary.latest_release_ready_count, value.summary.initial_count, value.summary.improved_count, value.summary.regressed_count, value.summary.unchanged_count, value.summary.changed_count) == (value.entry_count, value.latest_registry_address, value.latest_entry_count, value.latest_accepted_count, value.latest_release_ready_count, value.initial_count, value.improved_count, value.regressed_count, value.unchanged_count, value.changed_count), "history summary counters replay", (value.summary.content_address,)),
        _check(10, "disposition-replay", (value.state, value.decision, value.accepted, value.release_ready) == (expected_state, expected_decision, expected_acceptance, expected_readiness), "latest registry state folds into history disposition", (value.content_address,)),
        _check(11, "registry-addresses", len({item.registry_address for item in entries}) == len(entries) and all(item.registry_address.startswith(registry_model.REGISTRY_PREFIX + ":") for item in entries), "registry snapshots are unique addressed references", entries_evidence),
        _check(12, "entry-addresses", all(history_model.address_entry(item) == item.content_address for item in entries), "every history entry has a stable content address", entries_evidence),
        _check(13, "manifest-linkage", (value.manifest.history_id, value.manifest.registry_id, value.manifest.files, tuple(value.manifest.artifact_addresses)) == (value.history_id, value.registry_id, history_model.FILES, (history_model.address_entries(entries), value.summary.content_address)), "manifest links exact history artifacts", (value.manifest.content_address,)),
        _check(14, "public-boundary", _public(value.to_dict()), "history contains no forbidden public metadata", (value.content_address,)),
        _check(15, "mapping-round-trip", history_model.history_from_mapping(value.to_dict()).content_address == value.content_address, "history mapping round-trips to the same address", (value.content_address,)),
    )
    passed = sum(item.passed for item in checks)
    body = {"history_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return output.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry History Audit", "", f"- History: `{value.history_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 12}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"history_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "operations": ["audit_history", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"], "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_history", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
