"""Independent audit for persisted runtime-query snapshot-diff query handoffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot as snapshot_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash, hash_bytes


VERSION = snapshot_model.VERSION + "-audit-v1"
BOUNDARY = snapshot_model.BOUNDARY + "_audit"
AUDIT_PREFIX = snapshot_model.SNAPSHOT_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "query-linkage", "query-audit-linkage", "source-linkage", "count-replay", "state-replay", "acceptance-replay", "summary-replay", "manifest-replay", "artifact-replay", "query-mapping", "audit-mapping", "snapshot-mapping", "public-boundary")
MAX_CHECKS = len(CHECK_IDS)
CHECK_FIELDS = ("check_id", "ordinal", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("snapshot_address", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAuditCheck:
    """One addressed audit finding for a diff-query snapshot."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, ordinal: int, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "diff-query snapshot audit check ID", required=True)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("diff-query snapshot audit check ID is unsupported")
        self.ordinal = _count(ordinal, "diff-query snapshot audit check ordinal", MAX_CHECKS)
        if self.ordinal != CHECK_IDS.index(self.check_id) + 1:
            raise ValidationError("diff-query snapshot audit check order is not canonical")
        self.passed = _bool(passed, "diff-query snapshot audit check result")
        self.detail = _text(detail, "diff-query snapshot audit check detail", 2048, required=True)
        self.evidence_addresses = tuple(_address(item, "diff-query snapshot audit evidence address", required=True) for item in _sequence(evidence_addresses, "diff-query snapshot audit evidence", 8))
        if not self.evidence_addresses:
            raise ValidationError("diff-query snapshot audit checks require evidence")
        self.content_address = _address(content_address, "diff-query snapshot audit check address", CHECK_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("diff-query snapshot audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("diff-query snapshot audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "diff-query snapshot audit check")
        _strict(value, set(cls.FIELDS), "diff-query snapshot audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAuditCheck):
        raise ValidationError("diff-query snapshot audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAudit:
    """A fixed 15-check independent audit of one persisted handoff."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, snapshot_address: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[Any], content_address: str) -> None:
        self.snapshot_address = _address(snapshot_address, "diff-query snapshot audit snapshot address", snapshot_model.SNAPSHOT_PREFIX)
        self.version = _text(version, "diff-query snapshot audit version", 512)
        self.boundary = _label(boundary, "diff-query snapshot audit boundary", required=True)
        self.check_count = _count(check_count, "diff-query snapshot audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "diff-query snapshot audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "diff-query snapshot audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "diff-query snapshot audit acceptance")
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAuditCheck.from_mapping(item) for item in _sequence(checks, "diff-query snapshot audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "diff-query snapshot audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != MAX_CHECKS or len(self.checks) != self.check_count or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("diff-query snapshot audit counters or boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("diff-query snapshot audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "checks" else [item.to_dict() for item in self.checks] for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "diff-query snapshot audit")
        _strict(value, set(cls.FIELDS), "diff-query snapshot audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAudit):
        raise ValidationError("diff-query snapshot audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]):
    body = {"check_id": check_id, "ordinal": ordinal, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAuditCheck(**(body | {"content_address": address_check(provisional)}))


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
        provisional = snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotArtifact(receipt.ordinal, receipt.name, len(raw), receipt.hash, snapshot_model.ARTIFACT_PREFIX + ":pending")
        if receipt.size != len(raw) or receipt.hash != hash_bytes(raw, prefix=snapshot_model.ARTIFACT_PREFIX) or receipt.content_address != snapshot_model.address_artifact(provisional):
            return False
    return True


def audit_snapshot(value):
    if not isinstance(value, snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot):
        raise ValidationError("diff-query snapshot audit requires a typed snapshot")
    value = snapshot_model.verify_snapshot(value)
    evidence = (value.content_address, value.diff_address, value.query_address, value.query_audit_address)
    query = value.query
    query_audit = value.query_audit
    checks = []
    checks.append(_check(1, "version", value.version == snapshot_model.VERSION, "snapshot version is current", evidence))
    checks.append(_check(2, "boundary", value.boundary == snapshot_model.BOUNDARY and _public(value.to_dict()), "snapshot boundary is public and value-free", evidence))
    checks.append(_check(3, "query-linkage", query is not None and (query.diff_id, query.diff_address, query.content_address) == (value.diff_id, value.diff_address, value.query_address), "query retains source diff linkage", evidence))
    checks.append(_check(4, "query-audit-linkage", query_audit is not None and (query_audit.query_address, query_audit.content_address, query_audit.accepted) == (value.query_address, value.query_audit_address, value.query_audit_accepted), "query audit retains query linkage and acceptance", evidence))
    source_rows = tuple(query.rows) if query is not None else ()
    source_linkage = query is not None and (not source_rows or all((row.left_snapshot_id, row.right_snapshot_id, row.direction, row.state_transition) == (value.left_snapshot_id, value.right_snapshot_id, value.direction, value.state_transition) for row in source_rows))
    checks.append(_check(5, "source-linkage", source_linkage, "source snapshot identities and transition replay", evidence))
    checks.append(_check(6, "count-replay", query is not None and (query.total_count, query.matched_count, query.returned_count) == (value.query_total_count, value.query_matched_count, value.query_returned_count), "query counts replay", evidence))
    checks.append(_check(7, "state-replay", value.state == ("ready" if value.diff_verified and value.query_audit_accepted else "blocked"), "snapshot state folds verification inputs", evidence))
    checks.append(_check(8, "acceptance-replay", value.accepted == (value.diff_verified and value.query_audit_accepted), "snapshot acceptance folds verification inputs", evidence))
    checks.append(_check(9, "summary-replay", value.summary is not None and value.summary.to_dict() == snapshot_model._build_summary(value).to_dict(), "summary replays from snapshot fields", evidence))
    checks.append(_check(10, "manifest-replay", value.manifest is not None and value.manifest.to_dict() == snapshot_model._build_manifest(value).to_dict(), "manifest replays from artifact receipts", evidence))
    checks.append(_check(11, "artifact-replay", _artifact_replays(value), "all persisted artifact byte receipts replay", evidence))
    checks.append(_check(12, "query-mapping", query is not None and snapshot_model.query_model.query_from_mapping(query.to_dict()).content_address == value.query_address, "query mapping preserves its address", evidence))
    checks.append(_check(13, "audit-mapping", query_audit is not None and snapshot_model.query_audit_model.audit_from_mapping(query_audit.to_dict()).content_address == value.query_audit_address, "query audit mapping preserves its address", evidence))
    checks.append(_check(14, "snapshot-mapping", snapshot_model.snapshot_from_mapping(value.to_dict()).content_address == value.content_address, "snapshot mapping preserves its address", evidence))
    checks.append(_check(15, "public-boundary", _public(value.to_dict()) and all(_public(item.to_dict()) for item in (query, query_audit) if item is not None), "handoff contains no forbidden public metadata", evidence))
    body = {"snapshot_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAudit.from_mapping(value)


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
    lines = ["# Runtime Query Snapshot Diff Query Snapshot Audit", "", f"- Checks: {mark}{value.passed_count}/{value.check_count}{mark}", f"- Accepted: {mark}{value.accepted}{mark}", f"- Address: {mark}{value.content_address}{mark}", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {check.ordinal} | {mark}{check.check_id}{mark} | {mark}{check.passed}{mark} | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff query snapshot audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff query snapshot audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"snapshot_address": {"type": "string", "pattern": "^" + snapshot_model.SNAPSHOT_PREFIX + ":"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent source/query/audit linkage", "count and state conservation", "summary and manifest replay", "byte receipt verification", "mapping address replay", "public-boundary verification", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "audit_snapshot", "capabilities", "check_schema", "render_audit_markdown"]
