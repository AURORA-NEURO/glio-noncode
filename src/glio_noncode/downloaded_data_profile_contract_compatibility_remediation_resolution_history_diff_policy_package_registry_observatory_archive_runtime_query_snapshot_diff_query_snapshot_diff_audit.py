"""Independent replay audit for longitudinal query-snapshot comparisons."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "manifest-files", "endpoint-linkage", "query-shape", "row-counts", "identity-uniqueness", "item-order", "change-counts", "changed-field-count", "direction-replay", "transition-replay", "item-addresses", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("version", "boundary", "diff_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = False) -> str:
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAuditCheck:
    """One addressed audit finding for a handoff comparison."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "comparison audit check ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("comparison audit check ordinal must be positive")
        self.check_id = _label(check_id, "comparison audit check ID", required=True)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("comparison audit check ID is unsupported")
        self.passed = _bool(passed, "comparison audit check result")
        self.detail = _text(detail, "comparison audit check detail", 2048, required=True)
        self.evidence_addresses = tuple(_address(item, "comparison audit evidence address", required=True) for item in _sequence(evidence_addresses, "comparison audit evidence", 8))
        if not self.evidence_addresses:
            raise ValidationError("comparison audit requires evidence")
        self.content_address = _address(content_address, "comparison audit check address", CHECK_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("comparison audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("comparison audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison audit check")
        _strict(value, set(cls.FIELDS), "comparison audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAuditCheck):
        raise ValidationError("comparison audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAudit:
    """A fixed 15-check independent audit of one persisted comparison."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, version: str, boundary: str, diff_address: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[Mapping[str, Any] | DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAuditCheck], content_address: str) -> None:
        self.version = _text(version, "comparison audit version", 512, required=True)
        self.boundary = _text(boundary, "comparison audit boundary", 512, required=True)
        self.diff_address = _address(diff_address, "comparison audit diff address", diff_model.DIFF_PREFIX, required=True)
        self.check_count = _count(check_count, "comparison audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "comparison audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "comparison audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "comparison audit acceptance")
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "comparison audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "comparison audit address", AUDIT_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != MAX_CHECKS or len(self.checks) != self.check_count or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("comparison audit checks do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("comparison audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("comparison audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: [item.to_dict() for item in self.checks] if field == "checks" else getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison audit")
        _strict(value, set(cls.FIELDS), "comparison audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAudit):
        raise ValidationError("comparison audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]):
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _summary_values(value):
    return tuple(value.summary.to_dict()[field] for field in diff_model.SUMMARY_FIELDS if field != "content_address")


def _expected_summary_values(value):
    return tuple(value.to_dict()[field] for field in diff_model.SUMMARY_FIELDS if field != "content_address")


def _direction(left_accepted: bool, right_accepted: bool, changed: bool) -> str:
    if not left_accepted and right_accepted:
        return "improved"
    if left_accepted and not right_accepted:
        return "regressed"
    return "mixed" if changed else "unchanged"


def audit_diff(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff):
    if not isinstance(value, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiff):
        raise ValidationError("comparison audit requires a typed diff")
    value = diff_model.verify_diff(value)
    items = value.items
    addresses = (value.content_address, value.summary.content_address, value.manifest.content_address, diff_model.address_items(items), value.left_snapshot_address, value.right_snapshot_address, value.left_query_address, value.right_query_address)
    identity_unique = len({item.key for item in items}) == len(items)
    item_order = tuple(item.ordinal for item in items) == tuple(range(1, len(items) + 1))
    counts = tuple(sum(item.change == change for item in items) for change in diff_model.CHANGES)
    count_replay = counts == (value.added_count, value.removed_count, value.changed_count, value.unchanged_count) and (sum(bool(item.left_row) for item in items), sum(bool(item.right_row) for item in items)) == (value.left_row_count, value.right_row_count)
    field_replay = value.changed_field_count == sum(len(item.changed_fields) for item in items) and all(item.changed_fields == diff_model._changed_fields(item.left_row, item.right_row) for item in items)
    changed = bool(value.added_count or value.removed_count or value.changed_count)
    endpoint_linkage = all(getattr(value.summary, field) == getattr(value, field) for field in diff_model.SUMMARY_FIELDS if field not in {"diff_id", "content_address"}) and value.summary.diff_id == value.diff_id
    checks = []
    checks.append(_check(1, "version", value.version == diff_model.VERSION and value.boundary == diff_model.BOUNDARY, "comparison version and boundary are current", addresses[:1]))
    checks.append(_check(2, "boundary", _public(value.to_dict()), "comparison contains only public value-free metadata", addresses[:1]))
    checks.append(_check(3, "manifest-files", value.manifest.files == diff_model.FILES and value.manifest.diff_id == value.diff_id, "manifest names the exact four comparison files", (value.manifest.content_address,)))
    checks.append(_check(4, "endpoint-linkage", endpoint_linkage, "both handoff endpoints and summary fields are linked", addresses[4:8]))
    checks.append(_check(5, "query-shape", value.query_shape_match and value.left_query_shape == value.right_query_shape, "both persisted query pages have the same review shape", (value.left_query_address, value.right_query_address)))
    checks.append(_check(6, "row-counts", count_replay, "side row totals and change totals replay", (value.summary.content_address,)))
    checks.append(_check(7, "identity-uniqueness", identity_unique, "stable resource, identity, and field keys are unique", tuple(item.content_address for item in items)[:8] or addresses[:1]))
    checks.append(_check(8, "item-order", item_order, "comparison item ordinals are canonical", tuple(item.content_address for item in items)[:8] or addresses[:1]))
    checks.append(_check(9, "change-counts", all(item.change in diff_model.CHANGES for item in items) and counts == (value.added_count, value.removed_count, value.changed_count, value.unchanged_count), "change classifications conserve every paired row", tuple(item.content_address for item in items)[:8] or addresses[:1]))
    checks.append(_check(10, "changed-field-count", field_replay, "changed-field evidence replays row semantics", tuple(item.content_address for item in items if item.changed_fields)[:8] or addresses[:1]))
    checks.append(_check(11, "direction-replay", value.direction == _direction(value.left_accepted, value.right_accepted, changed), "direction replays acceptance transition and row changes", (value.summary.content_address,)))
    checks.append(_check(12, "transition-replay", value.state_transition == f"{value.left_state}->{value.right_state}", "state transition replays both handoff states", (value.left_snapshot_address, value.right_snapshot_address)))
    checks.append(_check(13, "item-addresses", all(diff_model.address_item(item) == item.content_address for item in items) and diff_model.address_items(items) == value.manifest.artifact_addresses[0] and diff_model.address_summary(value.summary) == value.summary.content_address and diff_model.address_manifest(value.manifest) == value.manifest.content_address, "item, artifact, summary, and manifest addresses replay", addresses[:4]))
    checks.append(_check(14, "public-boundary", _public(value.to_dict()), "comparison contains no forbidden public metadata", (value.content_address,)))
    checks.append(_check(15, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).content_address == value.content_address, "public comparison mapping round-trips", (value.content_address,)))
    passed = sum(item.passed for item in checks)
    body = {"version": VERSION, "boundary": BOUNDARY, "diff_address": value.content_address, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "checks": tuple(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAudit.from_mapping(value)


def audit_json(value) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        row = check.to_dict()
        writer.writerow({field: ";".join(row[field]) if field == "evidence_addresses" else row[field] for field in CHECK_FIELDS})
    return stream.getvalue()


def render_audit_markdown(value) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Runtime Query Snapshot Handoff Comparison Audit", "", f"- Accepted: `{value.accepted}`", f"- Passed: `{value.passed_count}` / `{value.check_count}`", f"- Comparison: `{value.diff_address}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot handoff comparison audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot handoff comparison audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent query-shape verification", "stable row identity and order checks", "change and count conservation", "changed-field replay", "direction and state-transition replay", "manifest and address replay", "public-boundary enforcement", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
