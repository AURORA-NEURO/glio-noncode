"""Independent assurance checks for the history observatory."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = observatory_model.VERSION + "-audit-v1"
BOUNDARY = observatory_model.BOUNDARY + "_audit"
AUDIT_PREFIX = observatory_model.OBSERVATORY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version", "boundary", "member-order", "member-identity", "history-linkage",
    "member-counts", "transition-order", "transition-linkage",
    "transition-counts", "metric-fold", "state-fold", "acceptance-fold",
    "artifact-linkage", "public-boundary", "mapping-round-trip",
)
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
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: tuple[str, ...] | list[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory audit check ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("observatory audit check ordinal must be positive")
        self.check_id = _text(check_id, "observatory audit check ID", 128)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("observatory audit check ID is unsupported")
        self.passed = _bool(passed, "observatory audit result")
        self.detail = _text(detail, "observatory audit detail")
        if not isinstance(evidence_addresses, (tuple, list)) or not evidence_addresses:
            raise ValidationError("observatory audit evidence is required")
        self.evidence_addresses = tuple(_address(item, "observatory audit evidence address") for item in evidence_addresses)
        self.content_address = _address(content_address, "observatory audit check content address", CHECK_PREFIX)
        if not _public(self.to_dict()):
            raise ValidationError("observatory audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("observatory audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory audit check")
        _strict(value, set(cls.FIELDS), "observatory audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAuditCheck):
        raise ValidationError("observatory audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, observatory_address: str, checks: tuple[Any, ...] | list[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.observatory_address = _address(observatory_address, "observatory audit address", observatory_model.OBSERVATORY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAuditCheck.from_mapping(item) for item in checks)
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
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAudit):
        raise ValidationError("observatory audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: tuple[str, ...]) -> Any:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": evidence, "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_observatory(value: Any):
    if not isinstance(value, observatory_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatory):
        raise ValidationError("observatory audit requires a typed observatory")
    value = observatory_model.observatory_from_mapping(value.to_dict())
    evidence = (value.content_address,)
    member_map = {item.ordinal: item for item in value.members}
    expected_transition_counts = {name: sum(item.transition == name for item in value.transitions) for name in observatory_model.TRANSITIONS}
    actual_transition_counts = {name: getattr(value, name + "_count") for name in observatory_model.TRANSITIONS}
    expected_metrics = {name: sum(getattr(item, name) for item in value.transitions) for name in ("total_query_rows", "matched_query_rows", "returned_query_rows")}
    checks = (
        ("version", value.version == observatory_model.VERSION, "observatory version uses the active contract"),
        ("boundary", value.boundary == observatory_model.BOUNDARY, "observatory boundary uses the active namespace"),
        ("member-order", tuple(item.ordinal for item in value.members) == tuple(range(1, value.member_count + 1)), "member ordinals are contiguous"),
        ("member-identity", len({item.history_id for item in value.members}) == value.member_count and len({item.history_address for item in value.members}) == value.member_count, "history identities and addresses are unique"),
        ("history-linkage", all(item.history_address.startswith(observatory_model.history_model.HISTORY_PREFIX + ":") for item in value.members), "members retain addressed history linkage"),
        ("member-counts", all(item.snapshot_count == item.initial_count + item.improved_count + item.regressed_count + item.unchanged_count + item.changed_count and item.latest_entry_count >= item.latest_ready_count + item.latest_blocked_count and item.latest_entry_count >= item.latest_accepted_count + item.latest_rejected_count for item in value.members), "member receipt counters are conserved"),
        ("transition-order", tuple(item.ordinal for item in value.transitions) == tuple(range(1, value.transition_count + 1)), "transition ordinals are contiguous"),
        ("transition-linkage", all(item.member_ordinal in member_map and item.history_id == member_map[item.member_ordinal].history_id and item.history_address == member_map[item.member_ordinal].history_address for item in value.transitions), "transitions link to their member history"),
        ("transition-counts", all(actual_transition_counts[name] == expected_transition_counts[name] for name in observatory_model.TRANSITIONS), "transition categories are conserved"),
        ("metric-fold", all(getattr(value, name + "_query_rows") == expected_metrics[name + "_query_rows"] for name in ("total", "matched", "returned")), "query-row totals fold from transitions"),
        ("state-fold", value.state == observatory_model.fold_state(tuple(item.latest_state for item in value.members)), "state folds from latest member states"),
        ("acceptance-fold", value.accepted == (bool(value.members) and all(item.latest_accepted for item in value.members)), "acceptance folds from latest member acceptance"),
        ("artifact-linkage", value.manifest.artifact_addresses == (observatory_model.address_members(value.members), observatory_model.address_transitions(value.transitions), value.summary.content_address), "manifest links every public artifact"),
        ("public-boundary", _public(value.to_dict()), "observatory contains only public bounded data"),
        ("mapping-round-trip", observatory_model.address_observatory(observatory_model.observatory_from_mapping(value.to_dict())) == value.content_address, "observatory mapping round-trips to its address"),
    )
    result = tuple(_check(index, check_id, passed, detail, evidence) for index, (check_id, passed, detail) in enumerate(checks, 1))
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAudit(value.content_address, result, MAX_CHECKS, sum(item.passed for item in result), sum(not item.passed for item in result), all(item.passed for item in result), AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAudit(value.content_address, result, MAX_CHECKS, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAudit.from_mapping(value)


def audit_json(value: Any) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: Any) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_audit_markdown(value: Any) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Comparison Query Snapshot Registry History Observatory Audit", "", f"Observatory: {value.observatory_address}", f"Checks: {value.passed_count}/{value.check_count}", f"Accepted: {value.accepted}", f"Address: {value.content_address}", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"observatory_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent counter replay", "history linkage checks", "artifact linkage checks", "public-boundary verification", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_observatory", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]

