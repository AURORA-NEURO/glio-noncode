"""Independent assurance checks for observatory query projections."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "resource-semantics", "address-replay", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: tuple[str, ...] | list[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "query audit check ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("query audit check ordinal must be positive")
        self.check_id = _text(check_id, "query audit check ID", 128)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("query audit check ID is unsupported")
        self.passed = _bool(passed, "query audit result")
        self.detail = _text(detail, "query audit detail")
        if not isinstance(evidence_addresses, (tuple, list)) or not evidence_addresses:
            raise ValidationError("query audit evidence is required")
        self.evidence_addresses = tuple(_address(item, "query audit evidence address") for item in evidence_addresses)
        self.content_address = _address(content_address, "query audit check content address", CHECK_PREFIX)
        if not _public(self.to_dict()):
            raise ValidationError("query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "query audit check")
        _strict(value, set(cls.FIELDS), "query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: Any) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAuditCheck):
        raise ValidationError("query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: tuple[Any, ...] | list[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "query audit address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAuditCheck.from_mapping(item) for item in checks)
        self.check_count = _count(check_count, "query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "query audit acceptance")
        self.content_address = _address(content_address, "query audit content address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("query audit checks are not complete or ordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("query audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "query audit")
        _strict(value, set(cls.FIELDS), "query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: Any) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAudit):
        raise ValidationError("query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: tuple[str, ...]) -> Any:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": evidence, "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_query(value: Any):
    if not isinstance(value, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQuery):
        raise ValidationError("query audit requires a typed query")
    value = query_model.query_from_mapping(value.to_dict())
    evidence = (value.content_address,)
    def filter_match(row: Any) -> bool:
        if value.history_id_filter and row.history_id != value.history_id_filter or value.registry_id_filter and row.registry_id != value.registry_id_filter or value.state_filter and row.state != value.state_filter or value.accepted_filter is not None and row.accepted != value.accepted_filter or value.transition_filter and row.transition != value.transition_filter or value.trend_filter and row.trend != value.trend_filter:
            return False
        if value.address_filter and value.address_filter not in {row.content_address, row.history_address, row.registry_address}:
            return False
        if value.text_filter and value.text_filter.casefold() not in " ".join(str(row.to_dict()[field]) for field in query_model.ROW_FIELDS if field != "content_address").casefold():
            return False
        return True
    rows = value.rows
    semantics = all((row.resource == "summary" and row.member_ordinal == 0 and row.snapshot_ordinal == 0) or (row.resource in {"members", "empty", "ready", "blocked", "mixed", "stable", "improved", "regressed", "changed"} and row.member_ordinal > 0) or (row.resource in {"transitions", "initial", "improved", "regressed", "unchanged", "changed"} and row.snapshot_ordinal > 0) for row in rows)
    checks = (
        ("version", value.content_address.startswith(query_model.QUERY_PREFIX + ":"), "query address uses the active namespace"),
        ("boundary", _public(value.to_dict()), "query boundary is public and value-free"),
        ("resource-order", value.resources == tuple(item for item in query_model.RESOURCES if item in value.resources), "resources retain canonical order"),
        ("filter-replay", all(filter_match(row) for row in rows), "returned rows satisfy recorded filters"),
        ("count-replay", value.returned_count == len(rows) and value.returned_count <= value.limit <= query_model.MAX_LIMIT and value.matched_count <= value.total_count and value.returned_count <= max(0, value.matched_count - value.offset), "query counts and pagination replay"),
        ("row-order", tuple(row.ordinal for row in rows) == tuple(range(value.offset + 1, value.offset + value.returned_count + 1)), "query rows retain page order"),
        ("row-addresses", all(query_model.address_row(query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryRow.from_mapping(row.to_dict())) == row.content_address for row in rows), "query row addresses replay"),
        ("resource-semantics", semantics and all(row.resource in value.resources for row in rows), "query rows retain known resource semantics"),
        ("address-replay", not value.address_filter or all(value.address_filter in {row.content_address, row.history_address, row.registry_address} for row in rows), "address filter replay is conserved"),
        ("public-boundary", _public(value.to_dict()), "query contains no forbidden public metadata"),
        ("mapping-round-trip", query_model.address_query(query_model.query_from_mapping(value.to_dict())) == value.content_address, "query mapping round-trips to the same address"),
    )
    result = tuple(_check(index, check_id, passed, detail, evidence) for index, (check_id, passed, detail) in enumerate(checks, 1))
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAudit(value.content_address, result, MAX_CHECKS, sum(item.passed for item in result), sum(not item.passed for item in result), all(item.passed for item in result), AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAudit(value.content_address, result, MAX_CHECKS, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAudit.from_mapping(value)


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
    lines = ["# Downloaded Data Comparison Query Snapshot Registry History Observatory Query Audit", "", f"Query: {value.query_address}", f"Checks: {value.passed_count}/{value.check_count}", f"Accepted: {value.accepted}", f"Address: {value.content_address}", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent filter replay", "pagination conservation", "resource semantics", "address replay", "public-boundary verification", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]

