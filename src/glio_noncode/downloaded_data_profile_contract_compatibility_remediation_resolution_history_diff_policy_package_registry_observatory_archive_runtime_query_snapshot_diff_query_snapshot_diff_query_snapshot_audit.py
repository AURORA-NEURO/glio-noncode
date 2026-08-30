"""Independent assurance for comparison-query snapshot handoffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query as query_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_audit as query_audit_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot as snapshot_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash, hash_bytes


VERSION = snapshot_model.VERSION + "-audit-v1"
BOUNDARY = snapshot_model.BOUNDARY + "_audit"
AUDIT_PREFIX = snapshot_model.SNAPSHOT_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version", "boundary", "query-linkage", "query-audit-linkage", "filter-replay", "count-replay",
    "state-replay", "acceptance-replay", "summary-replay", "manifest-replay", "artifact-replay",
    "query-mapping", "audit-mapping", "snapshot-mapping", "public-boundary",
)
MAX_CHECKS = len(CHECK_IDS)
CHECK_FIELDS = ("check_id", "ordinal", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("snapshot_address", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = False) -> str:
    value = _text(value, field, 4096, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
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
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAuditCheck:
    """One addressed check in the independent handoff audit."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, ordinal: int, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "comparison-query snapshot audit check ID", required=True)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("comparison-query snapshot audit check ID is unsupported")
        self.ordinal = _count(ordinal, "comparison-query snapshot audit check ordinal", MAX_CHECKS, positive=True)
        self.passed = _bool(passed, "comparison-query snapshot audit check result")
        self.detail = _text(detail, "comparison-query snapshot audit check detail", 2048, required=True)
        self.evidence_addresses = tuple(_address(item, "comparison-query snapshot audit evidence address", required=True) for item in _sequence(evidence_addresses, "comparison-query snapshot audit evidence", 8))
        if not self.evidence_addresses:
            raise ValidationError("comparison-query snapshot audit checks require evidence")
        self.content_address = _address(content_address, "comparison-query snapshot audit check address", CHECK_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("comparison-query snapshot audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("comparison-query snapshot audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison-query snapshot audit check")
        if set(value) != set(cls.FIELDS):
            raise ValidationError("comparison-query snapshot audit check contains unknown or missing fields")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAuditCheck):
        raise ValidationError("comparison-query snapshot audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAudit:
    """A fixed 15-check independent audit of one comparison-query handoff."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, snapshot_address: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[Any], content_address: str) -> None:
        self.snapshot_address = _address(snapshot_address, "comparison-query snapshot audit snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=True)
        self.version = _text(version, "comparison-query snapshot audit version", 512, required=True)
        self.boundary = _label(boundary, "comparison-query snapshot audit boundary", required=True)
        self.check_count = _count(check_count, "comparison-query snapshot audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "comparison-query snapshot audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "comparison-query snapshot audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "comparison-query snapshot audit acceptance")
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAuditCheck.from_mapping(item) for item in _sequence(checks, "comparison-query snapshot audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "comparison-query snapshot audit address", AUDIT_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != MAX_CHECKS or len(self.checks) != self.check_count or tuple(item.check_id for item in self.checks) != CHECK_IDS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("comparison-query snapshot audit counters or boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("comparison-query snapshot audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "checks" else [item.to_dict() for item in self.checks] for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison-query snapshot audit")
        if set(value) != set(cls.FIELDS):
            raise ValidationError("comparison-query snapshot audit contains unknown or missing fields")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAudit):
        raise ValidationError("comparison-query snapshot audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]):
    body = {"check_id": check_id, "ordinal": ordinal, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _artifact_replays(value) -> bool:
    if value.manifest is None or value.query is None or value.query_audit is None:
        return False
    try:
        documents = snapshot_model._documents(value)
        expected = snapshot_model._build_manifest(value)
    except ValidationError:
        return False
    if expected.to_dict() != value.manifest.to_dict():
        return False
    for receipt in value.manifest.artifacts:
        raw = documents[receipt.name]
        provisional = snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotArtifact(receipt.ordinal, receipt.name, len(raw), receipt.hash, snapshot_model.ARTIFACT_PREFIX + ":pending")
        if receipt.size != len(raw) or receipt.hash != hash_bytes(raw, prefix=snapshot_model.ARTIFACT_PREFIX) or receipt.content_address != snapshot_model.address_artifact(provisional):
            return False
    return True


def _shape_replays(value, query) -> bool:
    if query is None:
        return False
    return (value.diff_id, value.diff_address, value.query_address, value.resources, value.change_filter, value.source_resource_filter, value.key_filter, value.identity_filter, value.field_filter, value.direction_filter, value.state_transition_filter, value.address_filter, value.text_filter, value.offset, value.limit, value.query_total_count, value.query_matched_count, value.query_returned_count) == (query.diff_id, query.diff_address, query.content_address, query.resources, query.change_filter, query.source_resource_filter, query.key_filter, query.identity_filter, query.field_filter, query.direction_filter, query.state_transition_filter, query.address_filter, query.text_filter, query.offset, query.limit, query.total_count, query.matched_count, query.returned_count)


def audit_snapshot(value):
    if not isinstance(value, snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot):
        raise ValidationError("comparison-query snapshot audit requires a typed snapshot")
    value = snapshot_model.verify_snapshot(value)
    query = value.query
    query_audit = value.query_audit
    evidence = (value.content_address, value.diff_address, value.query_address, value.query_audit_address)
    checks = []
    checks.append(_check(1, "version", value.version == snapshot_model.VERSION, "snapshot version is current", evidence))
    checks.append(_check(2, "boundary", value.boundary == snapshot_model.BOUNDARY and _public(value.to_dict()), "snapshot boundary is public and value-free", evidence))
    checks.append(_check(3, "query-linkage", query is not None and (query.diff_id, query.diff_address, query.content_address) == (value.diff_id, value.diff_address, value.query_address), "query retains comparison and address linkage", evidence))
    checks.append(_check(4, "query-audit-linkage", query_audit is not None and (query_audit.query_address, query_audit.content_address, query_audit.accepted) == (value.query_address, value.query_audit_address, value.accepted), "query audit retains query linkage and acceptance", evidence))
    checks.append(_check(5, "filter-replay", _shape_replays(value, query), "all query filters and page bounds replay", evidence))
    checks.append(_check(6, "count-replay", query is not None and (value.query_total_count, value.query_matched_count, value.query_returned_count) == (query.total_count, query.matched_count, query.returned_count), "query counts replay", evidence))
    checks.append(_check(7, "state-replay", value.state == ("ready" if query_audit is not None and query_audit.accepted else "blocked"), "handoff state folds query assurance", evidence))
    checks.append(_check(8, "acceptance-replay", value.accepted == (query_audit is not None and query_audit.accepted), "handoff acceptance folds query assurance", evidence))
    checks.append(_check(9, "summary-replay", value.summary is not None and value.summary.to_dict() == snapshot_model._build_summary(value).to_dict(), "summary replays from handoff fields", evidence))
    checks.append(_check(10, "manifest-replay", value.manifest is not None and value.manifest.to_dict() == snapshot_model._build_manifest(value).to_dict(), "manifest replays from artifact receipts", evidence))
    checks.append(_check(11, "artifact-replay", _artifact_replays(value), "all artifact byte receipts replay", evidence))
    checks.append(_check(12, "query-mapping", query is not None and query_model.query_from_mapping(query.to_dict()).content_address == value.query_address, "query mapping preserves its address", evidence))
    checks.append(_check(13, "audit-mapping", query_audit is not None and query_audit_model.audit_from_mapping(query_audit.to_dict()).content_address == value.query_audit_address, "query audit mapping preserves its address", evidence))
    checks.append(_check(14, "snapshot-mapping", snapshot_model.snapshot_from_mapping(value.to_dict()).content_address == value.content_address, "snapshot mapping preserves its address", evidence))
    checks.append(_check(15, "public-boundary", _public(value.to_dict()) and all(_public(item.to_dict()) for item in (query, query_audit) if item is not None), "handoff contains no forbidden public metadata", evidence))
    body = {"snapshot_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAudit.from_mapping(value)


def audit_json(value) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        writer.writerow(check.to_dict())
    return stream.getvalue()


def render_audit_markdown(value) -> str:
    value = audit_from_mapping(value.to_dict())
    mark = chr(96)
    lines = ["# Comparison Query Snapshot Audit", "", f"- Checks: {mark}{value.passed_count}/{value.check_count}{mark}", f"- Accepted: {mark}{value.accepted}{mark}", f"- Address: {mark}{value.content_address}{mark}", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {check.ordinal} | {mark}{check.check_id}{mark} | {mark}{check.passed}{mark} | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"snapshot_address": {"type": "string", "pattern": "^" + snapshot_model.SNAPSHOT_PREFIX + ":"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent query handoff verification", "source comparison and filter linkage", "count and state conservation", "manifest and byte receipt replay", "mapping address replay", "public-boundary verification", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "audit_snapshot", "capabilities", "check_schema", "render_audit_markdown"]
