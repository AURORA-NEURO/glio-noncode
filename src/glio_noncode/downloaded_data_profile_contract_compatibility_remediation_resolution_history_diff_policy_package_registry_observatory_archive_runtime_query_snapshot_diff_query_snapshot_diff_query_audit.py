"""Independent replay audit for query-snapshot comparison queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "comparison-linkage", "change-replay", "field-replay", "public-boundary", "mapping-round-trip")
MAX_CHECKS = len(CHECK_IDS)
CHECK_FIELDS = ("check_id", "ordinal", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAuditCheck:
    """One independently addressed query audit result."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, ordinal: int, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "comparison query audit check ID", required=True)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("comparison query audit check ID is unsupported")
        self.ordinal = _count(ordinal, "comparison query audit check ordinal", MAX_CHECKS)
        if self.ordinal != CHECK_IDS.index(self.check_id) + 1:
            raise ValidationError("comparison query audit check order is not canonical")
        self.passed = _bool(passed, "comparison query audit check result")
        self.detail = _text(detail, "comparison query audit check detail", 2048, required=True)
        self.evidence_addresses = tuple(_address(item, "comparison query audit evidence address", required=True) for item in _sequence(evidence_addresses, "comparison query audit evidence", 8))
        self.content_address = _address(content_address, "comparison query audit check address", CHECK_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("comparison query audit check is incomplete")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("comparison query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison query audit check")
        _strict(value, set(cls.FIELDS), "comparison query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAuditCheck):
        raise ValidationError("comparison query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAudit:
    """A fixed-vocabulary, independent audit of a comparison query."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[Any], content_address: str) -> None:
        self.query_address = _address(query_address, "comparison query audit query address", query_model.QUERY_PREFIX, required=True)
        self.version = _text(version, "comparison query audit version", 512, required=True)
        self.boundary = _label(boundary, "comparison query audit boundary", required=True)
        self.check_count = _count(check_count, "comparison query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "comparison query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "comparison query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "comparison query audit acceptance")
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "comparison query audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "comparison query audit address", AUDIT_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != MAX_CHECKS or len(self.checks) != self.check_count or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("comparison query audit counters or boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("comparison query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "checks" else [item.to_dict() for item in self.checks] for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison query audit")
        _strict(value, set(cls.FIELDS), "comparison query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAudit):
        raise ValidationError("comparison query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]):
    body = {"check_id": check_id, "ordinal": ordinal, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _filter_matches(row: Mapping[str, Any], value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery) -> bool:
    if value.change_filter and row["change"] != value.change_filter or value.source_resource_filter and row["source_resource"] != value.source_resource_filter or value.key_filter and row["key"] != value.key_filter or value.identity_filter and row["identity"] != value.identity_filter or value.field_filter and row["field"] != value.field_filter or value.direction_filter and row["direction"] != value.direction_filter or value.state_transition_filter and row["state_transition"] != value.state_transition_filter:
        return False
    if value.address_filter and value.address_filter not in {row["address"], row["item_address"], row["left_row_address"], row["right_row_address"]}:
        return False
    return not value.text_filter or value.text_filter.casefold() in " ".join(str(row[key]) for key in query_model.ROW_FIELDS if key != "content_address").casefold()


def audit_query(value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery):
    value = query_model.verify_query(value)
    evidence = (value.content_address, value.diff_address)
    rows = tuple(row.to_dict() for row in value.rows)
    checks: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAuditCheck] = []
    checks.append(_check(1, "version", value.version == query_model.VERSION, "query version is current", evidence))
    checks.append(_check(2, "boundary", value.boundary == query_model.BOUNDARY and _public(value.to_dict()), "query boundary is public and value-free", evidence))
    checks.append(_check(3, "resource-order", value.resources == tuple(item for item in query_model.RESOURCES if item in value.resources), "query resources retain canonical order", evidence))
    checks.append(_check(4, "filter-replay", all(_filter_matches(row, value) for row in rows), "returned rows satisfy every declared filter", tuple(row["content_address"] for row in rows[:4]) or evidence))
    checks.append(_check(5, "count-replay", value.returned_count == len(value.rows) and value.matched_count <= value.total_count and value.returned_count <= max(0, value.matched_count - value.offset), "query counts and pagination bounds replay", evidence))
    checks.append(_check(6, "row-order", tuple(row.ordinal for row in value.rows) == tuple(range(value.offset + 1, value.offset + value.returned_count + 1)), "query rows retain page order", tuple(row["content_address"] for row in rows[:4]) or evidence))
    checks.append(_check(7, "row-addresses", all(query_model.address_row(row) == row.content_address for row in value.rows), "query row addresses replay canonically", tuple(row["content_address"] for row in rows[:4]) or evidence))
    checks.append(_check(8, "comparison-linkage", all(row["diff_id"] == value.diff_id and row["left_snapshot_id"] and row["right_snapshot_id"] for row in rows), "query rows retain comparison endpoint linkage", tuple(row["content_address"] for row in rows[:4]) or evidence))
    checks.append(_check(9, "change-replay", all(row["resource"] == "summary" or row["resource"] in {"items", "field-changes"} or row["change"] == row["resource"] for row in rows), "change-class resources retain their declared classification", tuple(row["content_address"] for row in rows[:4]) or evidence))
    checks.append(_check(10, "field-replay", all((row["resource"] == "field-changes") == bool(row["field"]) and (not row["field"] or row["change"] in {"added", "removed", "changed"}) for row in rows), "field-change rows retain added/removed/changed field semantics", tuple(row["content_address"] for row in rows[:4]) or evidence))
    checks.append(_check(11, "public-boundary", _public(value.to_dict()), "query contains no forbidden public metadata", evidence))
    checks.append(_check(12, "mapping-round-trip", query_model.query_from_mapping(value.to_dict()).content_address == value.content_address, "query mapping round-trips to the same address", evidence))
    body = {"query_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAudit.from_mapping(value)


def audit_json(value):
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value):
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        writer.writerow(check.to_dict())
    return stream.getvalue()


def render_audit_markdown(value):
    value = audit_from_mapping(value.to_dict())
    mark = chr(96)
    lines = ["# Policy Package Registry Observatory Archive Runtime Query Snapshot Diff Query Audit", "", f"- Checks: {mark}{value.passed_count}/{value.check_count}{mark}", f"- Accepted: {mark}{value.accepted}{mark}", f"- Address: {mark}{value.content_address}{mark}", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {check.ordinal} | {mark}{check.check_id}{mark} | {mark}{check.passed}{mark} | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot diff query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot diff query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent filter replay", "pagination and row-address replay", "comparison endpoint linkage verification", "change and field semantics", "public-boundary verification", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
