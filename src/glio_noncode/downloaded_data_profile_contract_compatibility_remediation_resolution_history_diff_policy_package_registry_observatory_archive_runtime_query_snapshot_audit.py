"""Independent audit for persisted archive-runtime query snapshots."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_audit as query_audit_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot as snapshot_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = snapshot_model.VERSION + "-audit-v1"
BOUNDARY = snapshot_model.BOUNDARY + "_audit"
AUDIT_PREFIX = snapshot_model.SNAPSHOT_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version-boundary", "snapshot-address", "query-linkage", "query-audit-linkage", "count-replay", "acceptance-folding", "state-replay", "query-audit-replay", "manifest-files", "manifest-address", "summary-address", "public-boundary", "mapping-round-trip", "artifact-receipts", "content-order")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("snapshot_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAuditCheck:
    """One addressed snapshot-audit assertion."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "snapshot audit ordinal", MAX_CHECKS)
        if self.ordinal < 1 or not isinstance(check_id, str) or check_id not in CHECK_IDS:
            raise ValidationError("snapshot audit check ID is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "snapshot audit result")
        self.detail = _text(detail, "snapshot audit detail", 2048)
        self.evidence_addresses = tuple(sorted({_address(item, "snapshot audit evidence address") for item in _sequence(evidence_addresses, "snapshot audit evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("snapshot audit checks require evidence")
        self.content_address = _address(content_address, "snapshot audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("snapshot audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("snapshot audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot audit check")
        _strict(value, set(cls.FIELDS), "snapshot audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAuditCheck):
        raise ValidationError("snapshot audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit:
    """The complete independent snapshot audit."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, snapshot_address: str, checks: Sequence[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.snapshot_address = _address(snapshot_address, "snapshot audit snapshot address", snapshot_model.SNAPSHOT_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAuditCheck.from_mapping(item) for item in _sequence(checks, "snapshot audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "snapshot audit count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "snapshot audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "snapshot audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "snapshot audit acceptance")
        self.content_address = _address(content_address, "snapshot audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("snapshot audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("snapshot audit counters do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("snapshot audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("snapshot audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_address": self.snapshot_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot audit")
        _strict(value, set(cls.FIELDS), "snapshot audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit):
        raise ValidationError("snapshot audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: tuple[str, ...]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAuditCheck:
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAuditCheck(ordinal, check_id, passed, detail, evidence, address_check(provisional))


def audit_snapshot(value: snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit:
    if not isinstance(value, snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot):
        raise ValidationError("snapshot audit requires a typed snapshot")
    value = snapshot_model.verify_snapshot(value)
    evidence = (value.content_address, value.runtime_address, value.query_address, value.query_audit_address)
    query = value.query
    query_audit = value.query_audit
    manifest = value.manifest
    summary = value.summary
    query_replay = query is not None and query.runtime_address == value.runtime_address and query.content_address == value.query_address and (value.query_total_count, value.query_matched_count, value.query_returned_count) == (query.total_count, query.matched_count, query.returned_count)
    query_audit_replay = query_audit is not None and query_audit.query_address == value.query_address and query_audit.content_address == value.query_audit_address and query_audit.accepted == value.query_audit_accepted
    expected_query_audit = query_audit_model.audit_query(query) if query is not None else None
    manifest_replay = manifest is not None and manifest.to_dict() == snapshot_model.manifest_document(value)
    summary_replay = summary is not None and summary.to_dict() == snapshot_model.summary_document(value)
    artifact_replay = manifest is not None and len(manifest.artifacts) == len(snapshot_model.ARTIFACT_FILES) and tuple(item.name for item in manifest.artifacts) == snapshot_model.ARTIFACT_FILES and all(item.size > 0 and item.hash.startswith(snapshot_model.ARTIFACT_PREFIX + ":") and item.content_address.startswith(snapshot_model.ARTIFACT_PREFIX + ":") for item in manifest.artifacts)
    checks = (
        ("version-boundary", value.version == snapshot_model.VERSION and value.boundary == snapshot_model.BOUNDARY, "snapshot version and boundary are current"),
        ("snapshot-address", snapshot_model.address_snapshot(value) == value.content_address, "snapshot content address replays"),
        ("query-linkage", query_replay, "snapshot retains the exact runtime query address and counts"),
        ("query-audit-linkage", query_audit_replay, "snapshot retains the exact query-audit address and acceptance"),
        ("count-replay", value.query_total_count >= value.query_matched_count >= value.query_returned_count, "snapshot query counters are bounded and ordered"),
        ("acceptance-folding", value.accepted == (value.runtime_accepted and value.query_audit_accepted), "snapshot acceptance folds runtime and query-audit acceptance"),
        ("state-replay", value.state == ("ready" if value.accepted else "blocked"), "snapshot state replays acceptance"),
        ("query-audit-replay", expected_query_audit is not None and expected_query_audit.content_address == value.query_audit_address and expected_query_audit.accepted == value.query_audit_accepted, "independent query audit replays its address"),
        ("manifest-files", manifest is not None and manifest.files == snapshot_model.FILES and manifest.artifacts and manifest.snapshot_address == value.content_address, "manifest names the exact snapshot files"),
        ("manifest-address", manifest_replay, "manifest receipts and address replay"),
        ("summary-address", summary_replay, "summary receipt and address replay"),
        ("public-boundary", _public(value.to_dict()) and (manifest is None or _public(manifest.to_dict())) and (summary is None or _public(summary.to_dict())), "snapshot documents contain no forbidden public metadata"),
        ("mapping-round-trip", snapshot_model.address_snapshot(snapshot_model.snapshot_from_mapping(value.to_dict())) == value.content_address, "snapshot mapping round-trips"),
        ("artifact-receipts", artifact_replay, "artifact receipts retain positive sizes and approved addresses"),
        ("content-order", manifest is not None and tuple(item.ordinal for item in manifest.artifacts) == tuple(range(1, len(snapshot_model.ARTIFACT_FILES) + 1)), "artifact ordinals retain canonical order"),
    )
    checks_value = tuple(_check(index, check_id, passed, detail, evidence) for index, (check_id, passed, detail) in enumerate(checks, 1))
    passed = sum(item.passed for item in checks_value)
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit(value.content_address, checks_value, MAX_CHECKS, passed, MAX_CHECKS - passed, passed == MAX_CHECKS, AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit(value.content_address, checks_value, MAX_CHECKS, passed, MAX_CHECKS - passed, passed == MAX_CHECKS, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]):
    value = _mapping(value, "snapshot audit")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    mark = chr(96)
    lines = ["# Policy Package Registry Observatory Archive Runtime Query Snapshot Audit", "", f"- Snapshot: {mark}{value.snapshot_address}{mark}", f"- Checks: {mark}{value.passed_count}/{value.check_count}{mark}", f"- Accepted: {mark}{value.accepted}{mark}", f"- Address: {mark}{value.content_address}{mark}", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | {mark}{item.check_id}{mark} | {mark}{item.passed}{mark} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"snapshot_address": {"type": "string", "pattern": "^" + snapshot_model.SNAPSHOT_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent snapshot address replay", "query and audit lineage replay", "exact manifest and summary checks", "acceptance and state folding", "artifact receipt verification", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "audit_snapshot", "capabilities", "check_schema", "render_audit_markdown"]
