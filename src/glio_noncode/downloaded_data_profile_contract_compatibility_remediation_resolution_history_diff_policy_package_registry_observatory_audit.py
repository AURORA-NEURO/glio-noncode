"""Independent assurance for the policy package registry observatory."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory as observatory_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = observatory_model.VERSION + "-audit-v1"
BOUNDARY = observatory_model.BOUNDARY + "_audit"
AUDIT_PREFIX = observatory_model.OBSERVATORY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "member-order", "member-identity", "history-linkage", "member-counts", "transition-order", "transition-linkage", "transition-counts", "state-fold", "decision-fold", "acceptance-fold", "readiness-fold", "artifact-linkage", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("observatory_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: tuple[str, ...] | list[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory audit check ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("observatory audit check ordinal must be positive")
        self.check_id = _text(check_id, "observatory audit check ID", 128)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("observatory audit check ID is unsupported")
        self.passed = _bool(passed, "observatory audit check result")
        self.detail = _text(detail, "observatory audit check detail", 4096)
        if not isinstance(evidence_addresses, (list, tuple)) or not evidence_addresses:
            raise ValidationError("observatory audit check evidence is required")
        self.evidence_addresses = tuple(_address(item, "observatory audit evidence address") for item in evidence_addresses)
        self.content_address = _address(content_address, "observatory audit check content address", CHECK_PREFIX)
        if not _public(self.to_dict()):
            raise ValidationError("observatory audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("observatory audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory audit check")
        _strict(value, set(cls.FIELDS), "observatory audit check")
        return cls(value["ordinal"], value["check_id"], value["passed"], value["detail"], value["evidence_addresses"], value["content_address"])


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAuditCheck):
        raise ValidationError("observatory audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, observatory_address: str, checks: tuple[Any, ...] | list[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.observatory_address = _address(observatory_address, "observatory audit address", observatory_model.OBSERVATORY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAuditCheck.from_mapping(item) for item in checks)
        self.check_count = _count(check_count, "observatory audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "observatory audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "observatory audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "observatory audit acceptance")
        self.content_address = _address(content_address, "observatory audit content address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("observatory audit checks are not complete or ordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("observatory audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("observatory audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"observatory_address": self.observatory_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory audit")
        _strict(value, set(cls.FIELDS), "observatory audit")
        return cls(value["observatory_address"], value["checks"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit):
        raise ValidationError("observatory audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: tuple[str, ...]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAuditCheck:
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAuditCheck(ordinal, check_id, passed, detail, evidence, address_check(provisional))


def audit_observatory(value: observatory_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit:
    if not isinstance(value, observatory_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory):
        raise ValidationError("observatory audit requires a typed observatory")
    value = observatory_model.observatory_from_mapping(value.to_dict())
    evidence = (value.content_address,)
    member_ids = tuple(item.history_id for item in value.members)
    member_addresses = tuple(item.history_address for item in value.members)
    transition_ids = tuple((item.history_id, item.snapshot_ordinal) for item in value.transitions)
    transition_counts_by_member = {ordinal: sum(item.member_ordinal == ordinal for item in value.transitions) for ordinal in range(1, value.member_count + 1)}
    expected_transition_count = sum(item.snapshot_count for item in value.members)
    checks = (
        ("version", value.version == observatory_model.VERSION, "observatory version is current"),
        ("boundary", value.boundary == observatory_model.BOUNDARY and _public(value.to_dict()), "observatory boundary is public and value-free"),
        ("member-order", tuple(item.ordinal for item in value.members) == tuple(range(1, value.member_count + 1)), "member ordinals are contiguous"),
        ("member-identity", len(set(member_ids)) == value.member_count and len(set(member_addresses)) == value.member_count, "member history identities and addresses are unique"),
        ("history-linkage", all(item.history_address.startswith(observatory_model.history_model.HISTORY_PREFIX + ":") for item in value.members), "member history addresses retain the history namespace"),
        ("member-counts", value.member_count == len(value.members) and value.accepted_member_count == sum(item.latest_accepted for item in value.members) and value.release_ready_member_count == sum(item.latest_release_ready for item in value.members), "member and readiness counters replay"),
        ("transition-order", tuple(item.ordinal for item in value.transitions) == tuple(range(1, value.transition_count + 1)) and all(item.snapshot_ordinal >= 1 and item.member_ordinal <= value.member_count for item in value.transitions), "transition ordinals and member references are bounded"),
        ("transition-linkage", all(item.history_id in member_ids and item.history_address == value.members[item.member_ordinal - 1].history_address for item in value.transitions), "transitions link to their member histories"),
        ("transition-counts", value.transition_count == len(value.transitions) and value.total_snapshot_count == expected_transition_count and value.transition_count == expected_transition_count and all(transition_counts_by_member[item.ordinal] == item.snapshot_count for item in value.members) and len(set(transition_ids)) == value.transition_count, "transition totals and per-member snapshot rows replay"),
        ("state-fold", value.state == observatory_model.fold_state(tuple(item.latest_state for item in value.members)) and value.empty_count == sum(item.latest_state == "empty" for item in value.members) and value.ready_count == sum(item.latest_state == "ready" for item in value.members) and value.review_count == sum(item.latest_state == "review" for item in value.members) and value.blocked_count == sum(item.latest_state == "blocked" for item in value.members) and value.mixed_count == sum(item.latest_state == "mixed" for item in value.members), "observatory state fold and partitions replay"),
        ("decision-fold", value.decision == observatory_model.fold_decision(tuple(item.latest_decision for item in value.members)) and value.promote_count == sum(item.latest_decision == "promote" for item in value.members) and value.hold_count == sum(item.latest_decision == "hold" for item in value.members) and value.block_count == sum(item.latest_decision == "block" for item in value.members) and value.mixed_decision_count == sum(item.latest_decision == "mixed" for item in value.members), "observatory decision fold and partitions replay"),
        ("acceptance-fold", value.accepted == (bool(value.member_count) and value.accepted_member_count == value.member_count), "observatory acceptance folds latest members"),
        ("readiness-fold", value.release_ready == (bool(value.member_count) and value.release_ready_member_count == value.member_count), "observatory readiness folds latest members"),
        ("artifact-linkage", value.manifest.artifact_addresses == (observatory_model.address_members(value.members), observatory_model.address_transitions(value.transitions), value.summary.content_address), "manifest addresses replay nested artifacts"),
        ("public-boundary", _public(value.to_dict()), "observatory contains no forbidden public metadata"),
        ("mapping-round-trip", observatory_model.address_observatory(observatory_model.observatory_from_mapping(value.to_dict())) == value.content_address, "observatory mapping round-trips to the same address"),
    )
    result = tuple(_check(index, check_id, passed, detail, evidence) for index, (check_id, passed, detail) in enumerate(checks, 1))
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit(value.content_address, result, MAX_CHECKS, sum(item.passed for item in result), sum(not item.passed for item in result), all(item.passed for item in result), AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit(value.content_address, result, MAX_CHECKS, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry Observatory Audit", "", f"- Observatory: `{value.observatory_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry observatory audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry observatory audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"observatory_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent member conservation", "state and decision fold replay", "transition linkage", "manifest linkage", "public-boundary verification", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_observatory", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
