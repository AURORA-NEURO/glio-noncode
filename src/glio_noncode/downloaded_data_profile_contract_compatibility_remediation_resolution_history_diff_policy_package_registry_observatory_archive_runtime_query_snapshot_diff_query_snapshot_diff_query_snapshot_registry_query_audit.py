"""Independent audit for comparison-query snapshot registry queries."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "resource-order",
    "filter-shape",
    "count-conservation",
    "pagination",
    "row-addresses",
    "row-linkage",
    "resource-partitions",
    "summary-projection",
    "mapping-replay",
    "public-boundary",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
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
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry query audit check ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("registry query audit check ordinal must be positive")
        self.check_id = _text(check_id, "registry query audit check ID", 128)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("registry query audit check ID is unsupported")
        self.passed = _bool(passed, "registry query audit check result")
        self.detail = _text(detail, "registry query audit check detail", 1024)
        self.evidence_addresses = tuple(_address(item, "registry query audit evidence address") for item in _sequence(evidence_addresses, "registry query audit evidence", 16))
        if not self.evidence_addresses:
            raise ValidationError("registry query audit evidence must not be empty")
        self.content_address = _address(content_address, "registry query audit check content address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("registry query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("registry query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry query audit check")
        _strict(value, set(cls.FIELDS), "registry query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAuditCheck):
        raise ValidationError("registry query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "registry query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "registry query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "registry query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "registry query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "registry query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "registry query audit acceptance")
        self.content_address = _address(content_address, "registry query audit content address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("registry query audit checks are incomplete or unordered")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("registry query audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("registry query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry query audit")
        _strict(value, set(cls.FIELDS), "registry query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAudit):
        raise ValidationError("registry query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]):
    body = (ordinal, check_id, passed, detail, tuple(evidence) or (query_model.QUERY_PREFIX + ":pending",), CHECK_PREFIX + ":pending")
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAuditCheck(*body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAuditCheck(*body[:-1], address_check(provisional))


def audit_query(value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQuery):
    value = query_model.query_from_mapping(value.to_dict())
    rows = value.rows
    resources = tuple(item.resource for item in rows)
    summary_rows = tuple(item for item in rows if item.resource == "summary")
    non_summary = tuple(item for item in rows if item.resource != "summary")
    checks = (
        ("version", value.content_address.startswith(query_model.QUERY_PREFIX + ":"), "query content address uses the current namespace", (value.content_address,)),
        ("boundary", value.registry_address.startswith(query_model.registry_model.REGISTRY_PREFIX + ":"), "query retains a registry address", (value.registry_address,)),
        ("resource-order", value.resources == tuple(item for item in query_model.RESOURCES if item in value.resources) and all(item in value.resources for item in resources), "resources and row projections use canonical order", (value.content_address,)),
        ("filter-shape", len(value.snapshot_id_filter) <= 256 and len(value.diff_id_filter) <= 256 and len(value.state_filter) <= 256 and len(value.field_filter) <= 1024 and len(value.direction_filter) <= 1024 and len(value.text_filter) <= 1024, "filters remain bounded and canonical", (value.content_address,)),
        ("count-conservation", value.returned_count == len(rows) and value.matched_count <= value.total_count and value.returned_count <= value.matched_count, "query counts are conserved", (value.content_address,)),
        ("pagination", tuple(item.ordinal for item in rows) == tuple(range(value.offset + 1, value.offset + value.returned_count + 1)) and value.returned_count <= value.limit, "page ordinals and limits replay", tuple(item.content_address for item in rows) or (value.content_address,)),
        ("row-addresses", all(query_model.address_row(item) == item.content_address for item in rows), "every query row address replays", tuple(item.content_address for item in rows) or (value.content_address,)),
        ("row-linkage", all(item.entry_ordinal >= 1 and item.snapshot_id and item.snapshot_address and item.diff_id and item.query_address for item in non_summary) and all(not item.entry_ordinal for item in summary_rows), "rows retain valid entry linkage", tuple(item.snapshot_address for item in non_summary) or (value.content_address,)),
        ("resource-partitions", all(item.state == "ready" for item in rows if item.resource == "ready") and all(item.state == "blocked" for item in rows if item.resource == "blocked") and all(item.accepted for item in rows if item.resource == "accepted") and all(not item.accepted for item in rows if item.resource == "rejected"), "partition resources replay their predicates", tuple(item.content_address for item in rows) or (value.content_address,)),
        ("summary-projection", len(summary_rows) <= 1 and all(item.resource == "summary" for item in summary_rows), "summary projection is singular", tuple(item.content_address for item in summary_rows) or (value.content_address,)),
        ("mapping-replay", query_model.query_from_mapping(value.to_dict()).content_address == value.content_address and canonical_json(value.to_dict()) == query_model.query_json(value), ("query mapping and JSON replay the same address"), (value.content_address,)),
        ("public-boundary", _public(value.to_dict()), "query contains only public fields", (value.content_address,)),
    )
    result = tuple(_check(ordinal, check_id, passed, detail, evidence) for ordinal, (check_id, passed, detail, evidence) in enumerate(checks, 1))
    body = (value.content_address, result, MAX_CHECKS, sum(item.passed for item in result), sum(not item.passed for item in result), all(item.passed for item in result), AUDIT_PREFIX + ":pending")
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAudit(*body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAudit(*body[:-1], address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAudit.from_mapping(value)


def audit_json(value) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_audit_markdown(value) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Comparison Query Snapshot Registry Query Audit", "", f"- Query: `{value.query_address}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot registry query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot registry query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "value_free": True, "check_ids": list(CHECK_IDS), "features": ["independent query shape checks", "pagination and count conservation", "row address replay", "partition predicate checks", "mapping and JSON replay", "deterministic JSON CSV and Markdown projections"]}


__all__ = [
    "AUDIT_FIELDS",
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_FIELDS",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "MAX_CHECKS",
    "VERSION",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAudit",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryQueryAuditCheck",
    "address_audit",
    "address_check",
    "audit_csv",
    "audit_from_mapping",
    "audit_json",
    "audit_query",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
]
