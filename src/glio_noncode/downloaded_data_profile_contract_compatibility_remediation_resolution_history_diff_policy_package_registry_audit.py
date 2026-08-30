"""Independent verification for the policy-package admission registry."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry as registry_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "exact-files", "entry-count", "entry-identities", "entry-order", "entry-addresses", "package-linkage", "state-replay", "count-replay", "readiness-replay", "manifest-linkage", "summary-linkage", "mapping-round-trip", "public-boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("registry_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if any(char.isspace() for char in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _label(value, field)
    if ":" not in value or (prefix and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be an addressed public receipt")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} must be a bounded count")
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "policy package registry audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "policy package registry audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("policy package registry audit check ID is unsupported")
        self.passed = _bool(passed, "policy package registry audit check result")
        self.detail = _text(detail, "policy package registry audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "policy package registry audit evidence address") for item in _sequence(evidence_addresses, "policy package registry audit evidence addresses", registry_model.MAX_ENTRIES + 4)}))
        if not self.evidence_addresses:
            raise ValidationError("policy package registry audit checks require evidence")
        self.content_address = _address(content_address, "policy package registry audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("policy package registry audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("policy package registry audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck:
        value = _mapping(value, "policy package registry audit check")
        _strict(value, set(cls.FIELDS), "policy package registry audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck):
        raise ValidationError("policy package registry audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, registry_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.registry_address = _address(registry_address, "policy package registry audit registry address", registry_model.REGISTRY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck.from_mapping(item) for item in _sequence(checks, "policy package registry audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "policy package registry audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "policy package registry audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "policy package registry audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "policy package registry audit acceptance")
        self.content_address = _address(content_address, "policy package registry audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.check_count == MAX_CHECKS and self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("policy package registry audit counts or boundary do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("policy package registry audit checks are not complete and ordered")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("policy package registry audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("registry_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit:
        value = _mapping(value, "policy package registry audit")
        _strict(value, set(cls.FIELDS), "policy package registry audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit):
        raise ValidationError("policy package registry audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_registry(value: registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit:
    if not isinstance(value, registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry):
        raise ValidationError("policy package registry audit requires a typed registry")
    entries = value.entries
    identities = tuple((item.package_id, item.package_address) for item in entries)
    expected_state = registry_model.STATES[0] if not entries else "blocked" if any(not item.accepted or item.decision == "block" for item in entries) else "ready" if all(item.release_ready for item in entries) else "review"
    checks = (
        _check(1, "version", value.version == registry_model.VERSION, "registry version is current", (value.content_address,)),
        _check(2, "boundary", value.boundary == registry_model.BOUNDARY and registry_model._public(value.to_dict()), "registry boundary is public and value-free", (value.content_address,)),
        _check(3, "exact-files", value.manifest.files == registry_model.FILES and len(value.manifest.artifact_addresses) == len(registry_model.MANIFEST_ARTIFACT_FILES), "registry manifest closes the exact four-file set", (value.manifest.content_address,)),
        _check(4, "entry-count", value.entry_count == len(entries) <= registry_model.MAX_ENTRIES, "registry entry count is conserved", (value.content_address,)),
        _check(5, "entry-identities", len(identities) == len(set(identities)), "package identities and addresses are unique", tuple(item.content_address for item in entries) or (value.content_address,)),
        _check(6, "entry-order", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)) and identities == tuple(sorted(identities)), "registry entries retain canonical order", tuple(item.content_address for item in entries) or (value.content_address,)),
        _check(7, "entry-addresses", all(registry_model.address_entry(item) == item.content_address for item in entries), "registry entry addresses replay", tuple(item.content_address for item in entries) or (value.content_address,)),
        _check(8, "package-linkage", all(item.package_address.startswith(registry_model.package_model.PACKAGE_PREFIX + ":") and item.runtime_address and item.policy_audit_address and item.runtime_audit_address for item in entries), "entries retain addressed package linkage", tuple(item.package_address for item in entries) or (value.content_address,)),
        _check(9, "state-replay", value.state == expected_state and value.summary.state == expected_state, "registry state folds entry posture", (value.content_address, value.summary.content_address)),
        _check(10, "count-replay", (value.accepted_count, value.release_ready_count, value.promote_count, value.hold_count, value.block_count) == (sum(item.accepted for item in entries), sum(item.release_ready for item in entries), sum(item.decision == "promote" for item in entries), sum(item.decision == "hold" for item in entries), sum(item.decision == "block" for item in entries)), "registry counters replay entries", (value.content_address,)),
        _check(11, "readiness-replay", value.accepted == (not entries or all(item.accepted for item in entries)) and value.release_ready == (bool(entries) and all(item.release_ready for item in entries)), "registry acceptance and readiness replay entries", (value.content_address,)),
        _check(12, "manifest-linkage", tuple(value.manifest.artifact_addresses) == (registry_model.address_entries(entries), value.summary.content_address), "manifest artifact addresses replay", (value.manifest.content_address, value.summary.content_address)),
        _check(13, "summary-linkage", value.summary.registry_id == value.registry_id and value.summary.entry_count == value.entry_count, "summary retains registry identity and counts", (value.summary.content_address,)),
        _check(14, "mapping-round-trip", registry_model.registry_from_mapping(value.to_dict()).content_address == value.content_address, "registry mapping round-trips to the same address", (value.content_address,)),
        _check(15, "public-boundary", registry_model._public(value.to_dict()), "registry contains no forbidden public metadata", (value.content_address,)),
    )
    passed = sum(item.passed for item in checks)
    body = {"registry_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address"))
    for item in value.checks:
        writer.writerow((item.ordinal, item.check_id, item.passed, item.detail, json.dumps(item.evidence_addresses, ensure_ascii=False), item.content_address))
    return output.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry Audit", "", f"- Registry: `{value.registry_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"registry_address": {"type": "string"}, "checks": {"type": "array", "items": {"$ref": "#/$defs/check"}}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}, "$defs": {"check": check_schema()}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "check_count": MAX_CHECKS, "features": ["independent registry counter replay", "duplicate identity detection", "state and readiness conservation", "manifest and summary linkage checks", "canonical mapping replay", "public-boundary enforcement", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_registry", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
