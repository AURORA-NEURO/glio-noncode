"""Independent replay audit for runtime-query snapshot diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff as diff_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot as snapshot_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version-boundary", "identity-order", "snapshot-linkage", "query-linkage", "row-pairing", "change-replay", "count-replay", "field-delta-replay", "direction-replay", "state-transition", "manifest-files", "manifest-addresses", "summary-replay", "mapping-round-trip", "public-boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("version", "boundary", "diff_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
MAX_CHECKS = len(CHECK_IDS)


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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "snapshot diff audit check ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("snapshot diff audit check ordinal must be positive")
        self.check_id = _label(check_id, "snapshot diff audit check ID", required=True)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("snapshot diff audit check ID is unsupported")
        self.passed = _bool(passed, "snapshot diff audit check result")
        self.detail = _text(detail, "snapshot diff audit check detail", 2048, required=True)
        self.evidence_addresses = tuple(_address(item, "snapshot diff audit evidence address", required=True) for item in _sequence(evidence_addresses, "snapshot diff audit evidence", diff_model.MAX_ITEMS + 3))
        if not self.evidence_addresses:
            raise ValidationError("snapshot diff audit requires evidence")
        self.content_address = _address(content_address, "snapshot diff audit check address", CHECK_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("snapshot diff audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("snapshot diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot diff audit check")
        _strict(value, set(cls.FIELDS), "snapshot diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck):
        raise ValidationError("snapshot diff audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, version: str, boundary: str, diff_address: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[Mapping[str, Any] | DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck], content_address: str) -> None:
        self.version = _text(version, "snapshot diff audit version", 512, required=True)
        self.boundary = _text(boundary, "snapshot diff audit boundary", 512, required=True)
        self.diff_address = _address(diff_address, "snapshot diff audit diff address", diff_model.DIFF_PREFIX, required=True)
        self.check_count = _count(check_count, "snapshot diff audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "snapshot diff audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "snapshot diff audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "snapshot diff audit acceptance")
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "snapshot diff audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "snapshot diff audit address", AUDIT_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("snapshot diff audit checks do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("snapshot diff audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("snapshot diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: [item.to_dict() for item in self.checks] if field == "checks" else getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot diff audit")
        _strict(value, set(cls.FIELDS), "snapshot diff audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAudit):
        raise ValidationError("snapshot diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _row_identity(row: Mapping[str, Any]) -> str:
    return "|".join(str(row[field]) for field in ("resource", "stage", "component", "name"))


def _semantic(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(row[field] for field in diff_model.SEMANTIC_ROW_FIELDS)


def _changed_fields(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[str, ...]:
    if not left:
        return diff_model.SEMANTIC_ROW_FIELDS if right else ()
    if not right:
        return diff_model.SEMANTIC_ROW_FIELDS
    return tuple(field for field in diff_model.SEMANTIC_ROW_FIELDS if left[field] != right[field])


def _direction(left_accepted: bool, right_accepted: bool, changed: bool) -> str:
    if not left_accepted and right_accepted:
        return "improved"
    if left_accepted and not right_accepted:
        return "regressed"
    return "mixed" if changed else "unchanged"


def audit_diff(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff):
    if not isinstance(value, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff):
        raise ValidationError("snapshot diff audit requires a typed diff")
    value = diff_model.diff_from_mapping(value.to_dict())
    checks: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck] = []
    items = value.items
    addresses = (value.content_address, value.left_snapshot_address, value.right_snapshot_address, value.left_query_address, value.right_query_address, value.manifest.content_address, value.summary.content_address, diff_model.address_items(items))
    identity_order = tuple(item.ordinal for item in items) == tuple(range(1, len(items) + 1)) and len({item.identity for item in items}) == len(items)
    row_pairing = all((not item.left_row or item.left_row_address == item.left_row["content_address"]) and (not item.right_row or item.right_row_address == item.right_row["content_address"]) and item.identity == _row_identity(item.left_row or item.right_row) for item in items)
    change_replay = all(item.change == ("added" if not item.left_row else "removed" if not item.right_row else "unchanged" if _semantic(item.left_row) == _semantic(item.right_row) else "changed") for item in items)
    count_replay = (tuple(sum(item.change == change for item in items) for change in diff_model.CHANGES) == (value.added_count, value.removed_count, value.changed_count, value.unchanged_count) and (sum(bool(item.left_row) for item in items), sum(bool(item.right_row) for item in items)) == (value.left_row_count, value.right_row_count))
    field_replay = all(item.changed_fields == _changed_fields(item.left_row, item.right_row) for item in items) and value.changed_field_count == sum(len(item.changed_fields) for item in items)
    changed = bool(value.added_count or value.removed_count or value.changed_count)
    summary_replay = value.summary.to_dict() == {field: getattr(value, field) for field in diff_model.SUMMARY_FIELDS if field != "content_address"} | {"content_address": value.summary.content_address}
    checks.append(_check(1, "version-boundary", value.version == diff_model.VERSION and value.boundary == diff_model.BOUNDARY, "diff version and boundary are current", addresses[:1]))
    checks.append(_check(2, "identity-order", identity_order, "stable row identities and ordinals replay", tuple(item.content_address for item in items) or addresses[:1]))
    checks.append(_check(3, "snapshot-linkage", all(item and item.startswith(snapshot_model.SNAPSHOT_PREFIX + ":") for item in (value.left_snapshot_address, value.right_snapshot_address)) and bool(value.left_snapshot_id and value.right_snapshot_id), "both snapshot identities and addresses are retained", addresses[1:3]))
    checks.append(_check(4, "query-linkage", all(item and item.startswith(snapshot_model.query_model.QUERY_PREFIX + ":") for item in (value.left_query_address, value.right_query_address)), "both query addresses are retained", addresses[3:5]))
    checks.append(_check(5, "row-pairing", row_pairing, "paired rows retain their derived row addresses", tuple(item.left_row_address or item.right_row_address for item in items) or addresses[:1]))
    checks.append(_check(6, "change-replay", change_replay, "added, removed, changed, and unchanged classifications replay", tuple(item.content_address for item in items) or addresses[:1]))
    checks.append(_check(7, "count-replay", count_replay, "change and side row counts replay", (value.summary.content_address,)))
    checks.append(_check(8, "field-delta-replay", field_replay, "changed-field evidence replays row semantics", tuple(item.content_address for item in items if item.change == "changed") or addresses[:1]))
    checks.append(_check(9, "direction-replay", value.direction == _direction(value.left_accepted, value.right_accepted, changed), "direction replays acceptance transition and structural changes", (value.summary.content_address,)))
    checks.append(_check(10, "state-transition", value.state_transition == f"{value.left_state}->{value.right_state}", "state transition replays both snapshot states", (value.left_snapshot_address, value.right_snapshot_address)))
    checks.append(_check(11, "manifest-files", value.manifest.files == diff_model.FILES and value.manifest.diff_id == value.diff_id, "manifest names the exact four diff files", (value.manifest.content_address,)))
    checks.append(_check(12, "manifest-addresses", value.manifest.artifact_addresses == (diff_model.address_items(items), value.summary.content_address) and diff_model.address_manifest(value.manifest) == value.manifest.content_address, "manifest artifact and address receipts replay", (value.manifest.content_address, diff_model.address_items(items), value.summary.content_address)))
    checks.append(_check(13, "summary-replay", summary_replay, "summary fields replay the diff", (value.summary.content_address,)))
    checks.append(_check(14, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).content_address == value.content_address, "public diff mapping round-trips", (value.content_address,)))
    checks.append(_check(15, "public-boundary", _public(value.to_dict()), "diff contains no forbidden public metadata", (value.content_address,)))
    passed = sum(item.passed for item in checks)
    body = {"version": VERSION, "boundary": BOUNDARY, "diff_address": value.content_address, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "checks": tuple(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        writer.writerow({field: ";".join(row[field]) if field == "evidence_addresses" else row[field] for field in CHECK_FIELDS})
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Runtime Query Snapshot Diff Audit", "", f"- Accepted: `{value.accepted}`", f"- Passed: `{value.passed_count}` / `{value.check_count}`", f"- Diff: `{value.diff_address}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent snapshot diff replay", "stable identity verification", "change and count conservation", "changed-field replay", "direction and state-transition replay", "manifest address replay", "public-boundary enforcement", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
