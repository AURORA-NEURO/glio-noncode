"""Independent audit for persisted archive inspection runtime queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive as archive_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_audit as archive_audit_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime as runtime_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query as query_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_query_audit as archive_query_audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version-boundary", "resource-order", "page-counts", "row-order", "filter-replay", "row-addresses", "resource-semantics", "runtime-lineage", "component-conservation", "component-order", "artifact-receipts", "public-boundary", "mapping-round-trip", "page-bound", "address-namespaces")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAuditCheck:
    """One addressed runtime-query audit assertion."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime query audit ordinal", MAX_CHECKS)
        if self.ordinal < 1 or not isinstance(check_id, str) or check_id not in CHECK_IDS:
            raise ValidationError("runtime query audit check ID is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "runtime query audit result")
        self.detail = _text(detail, "runtime query audit detail", 2048)
        self.evidence_addresses = tuple(sorted({_address(item, "runtime query evidence address") for item in _sequence(evidence_addresses, "runtime query evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("runtime query audit checks require evidence")
        self.content_address = _address(content_address, "runtime query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "runtime query audit check")
        _strict(value, set(cls.FIELDS), "runtime query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAuditCheck):
        raise ValidationError("runtime query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit:
    """The complete independent runtime-query audit."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "runtime query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "runtime query audit count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime query audit acceptance")
        self.content_address = _address(content_address, "runtime query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("runtime query audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("runtime query audit counters do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "runtime query audit")
        _strict(value, set(cls.FIELDS), "runtime query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit):
        raise ValidationError("runtime query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: tuple[str, ...]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAuditCheck:
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAuditCheck(ordinal, check_id, passed, detail, evidence, address_check(provisional))


def _matches(row: Any, value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery) -> bool:
    if value.stage_filter and row.stage != value.stage_filter or value.state_filter and row.state != value.state_filter or value.accepted_filter is not None and row.accepted != value.accepted_filter or value.component_filter and row.component != value.component_filter or value.address_filter and row.address != value.address_filter or value.name_filter and row.name != value.name_filter:
        return False
    if value.text_filter:
        return value.text_filter.casefold() in " ".join(str(row.to_dict()[field]) for field in query_model.ROW_FIELDS if field != "content_address").casefold()
    return True


def _semantics(row: Any) -> bool:
    if row.resource == "summary":
        return not row.stage and not row.component and not row.name and row.count == len(runtime_model.STAGES)
    if row.resource == "stages":
        return row.stage in runtime_model.STAGES and not row.component and not row.name and row.address
    if row.resource in {"links", "components"}:
        return row.component in query_model.COMPONENTS and not row.stage and not row.name and row.address
    if row.resource == "artifacts":
        return row.name in runtime_model.ARTIFACT_FILES and row.size > 0 and row.hash.startswith(runtime_model.ARTIFACT_PREFIX + ":") and not row.stage and not row.component
    return False


def audit_query(value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit:
    if not isinstance(value, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery):
        raise ValidationError("runtime query audit requires a typed query")
    value = query_model.query_from_mapping(value.to_dict())
    evidence = (value.content_address, value.runtime_address)
    rows = value.rows
    resource_order = value.resources == tuple(item for item in query_model.RESOURCES if item in value.resources)
    filter_ok = all(_matches(row, value) for row in rows)
    count_ok = value.total_count >= value.matched_count >= value.returned_count == len(rows) and value.returned_count <= value.limit <= query_model.MAX_LIMIT and value.returned_count <= max(0, value.matched_count - value.offset)
    row_order = tuple(row.ordinal for row in rows) == tuple(range(value.offset + 1, value.offset + value.returned_count + 1))
    row_addresses = all(query_model.address_row(query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow.from_mapping(row.to_dict())) == row.content_address for row in rows)
    semantics = all(_semantics(row) for row in rows)
    lineage = all(row.runtime_id == value.runtime_id and row.archive_id and row.version and row.boundary for row in rows)
    links = tuple(row for row in rows if row.resource == "links")
    components = tuple(row for row in rows if row.resource == "components")
    component_order = tuple(row.component for row in links) == tuple(item for item in query_model.COMPONENTS if item in {row.component for row in links}) and tuple(row.component for row in components) == tuple(item for item in query_model.COMPONENTS if item in {row.component for row in components})
    component_conservation = len(links) == len(components) or not links or not components
    artifacts = tuple(row for row in rows if row.resource == "artifacts")
    artifact_order = tuple(row.name for row in artifacts) == tuple(item for item in runtime_model.ARTIFACT_FILES if item in {row.name for row in artifacts})
    artifact_receipts = all(row.size > 0 and ":" in row.hash and row.address.startswith(runtime_model.ARTIFACT_PREFIX + ":") for row in artifacts)
    namespaces = all(row.address.startswith(tuple(prefix + ":" for prefix in (runtime_model.RUNTIME_PREFIX, runtime_model.STAGE_PREFIX, runtime_model.ARTIFACT_PREFIX, archive_model.ARCHIVE_PREFIX, archive_audit_model.AUDIT_PREFIX, archive_query_audit_model.query_model.QUERY_PREFIX, archive_query_audit_model.AUDIT_PREFIX))) for row in rows)
    checks = (
        ("version-boundary", value.runtime_address.startswith(runtime_model.RUNTIME_PREFIX + ":") and value.content_address.startswith(query_model.QUERY_PREFIX + ":"), "query and runtime addresses use current namespaces"),
        ("resource-order", resource_order, "selected resources retain canonical order"),
        ("page-counts", count_ok, "query counts and pagination conserve bounded rows"),
        ("row-order", row_order, "returned rows retain page order"),
        ("filter-replay", filter_ok, "returned rows satisfy recorded filters"),
        ("row-addresses", row_addresses, "row content addresses replay"),
        ("resource-semantics", semantics, "rows retain resource-specific identity"),
        ("runtime-lineage", lineage, "rows retain runtime identity and public lineage"),
        ("component-conservation", component_conservation, "link and component projections conserve their available rows"),
        ("component-order", component_order, "component projections retain canonical order"),
        ("artifact-receipts", artifact_order and artifact_receipts, "artifact rows retain canonical order and positive receipt measurements"),
        ("public-boundary", _public(value.to_dict()), "query contains no forbidden public metadata"),
        ("mapping-round-trip", query_model.address_query(query_model.query_from_mapping(value.to_dict())) == value.content_address, "query mapping round-trips to its address"),
        ("page-bound", value.offset <= query_model.MAX_TOTAL_COUNT and value.returned_count <= query_model.MAX_LIMIT, "offset and page size remain bounded"),
        ("address-namespaces", namespaces, "row source addresses use approved public namespaces"),
    )
    checks_value = tuple(_check(index, check_id, passed, detail, evidence) for index, (check_id, passed, detail) in enumerate(checks, 1))
    passed = sum(item.passed for item in checks_value)
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit(value.content_address, checks_value, MAX_CHECKS, passed, MAX_CHECKS - passed, passed == MAX_CHECKS, AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit(value.content_address, checks_value, MAX_CHECKS, passed, MAX_CHECKS - passed, passed == MAX_CHECKS, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit.from_mapping(_mapping(value, "runtime query audit"))


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Policy Package Registry Observatory Archive Runtime Query Audit", "", f"- Query: {chr(96)}{value.query_address}{chr(96)}", f"- Checks: {chr(96)}{value.passed_count}/{value.check_count}{chr(96)}", f"- Accepted: {chr(96)}{value.accepted}{chr(96)}", f"- Address: {chr(96)}{value.content_address}{chr(96)}", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | {chr(96)}{item.check_id}{chr(96)} | {chr(96)}{item.passed}{chr(96)} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent runtime-query replay", "filter and pagination conservation", "row-address verification", "component lineage checks", "runtime artifact receipt checks", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
