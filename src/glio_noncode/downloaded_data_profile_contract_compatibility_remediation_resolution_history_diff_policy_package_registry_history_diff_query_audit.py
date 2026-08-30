"""Independent assurance for policy package registry history diff queries."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff_query as query_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-query-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "change-semantics", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _label(value, field)
    if ":" not in value or (prefix and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be an addressed public receipt")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} must be a bounded count")
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
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history diff query audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "registry history diff query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("registry history diff query audit check ID is unsupported")
        self.passed = _bool(passed, "registry history diff query audit check result")
        self.detail = _text(detail, "registry history diff query audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "registry history diff query audit evidence address") for item in _sequence(evidence_addresses, "registry history diff query audit evidence addresses", query_model.MAX_TOTAL_COUNT + 1)}))
        if not self.evidence_addresses:
            raise ValidationError("registry history diff query audit checks require evidence")
        self.content_address = _address(content_address, "registry history diff query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("registry history diff query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck:
        value = _mapping(value, "registry history diff query audit check")
        _strict(value, set(cls.FIELDS), "registry history diff query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck):
        raise ValidationError("registry history diff query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "registry history diff query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "registry history diff query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "registry history diff query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "registry history diff query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "registry history diff query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "registry history diff query audit acceptance")
        self.content_address = _address(content_address, "registry history diff query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)):
            raise ValidationError("registry history diff query audit check order is not conserved")
        if tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("registry history diff query audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("registry history diff query audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry history diff query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("registry history diff query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit:
        value = _mapping(value, "registry history diff query audit")
        _strict(value, set(cls.FIELDS), "registry history diff query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit):
        raise ValidationError("registry history diff query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence) or (query_model.QUERY_PREFIX + ":empty",), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _matches(row: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryRow, query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery) -> bool:
    if query.resource and row.resource != query.resource:
        return False
    if query.change and row.change != query.change:
        return False
    if query.text and query.text.casefold() not in " ".join((row.identity, row.change, row.left_registry_address, row.right_registry_address, row.detail)).casefold():
        return False
    return True


def audit_query(value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit:
    if not isinstance(value, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQuery):
        raise ValidationError("registry history diff query audit requires a typed query")
    rows = value.rows
    evidence = tuple(item.content_address for item in rows[: query_model.MAX_TOTAL_COUNT + 1]) or (value.content_address,)
    filter_replay = all(_matches(item, value) for item in rows)
    semantics = all(item.resource == "summary" or item.resource == "items" or item.change == item.resource for item in rows)
    checks = (
        _check(1, "version", value.version == query_model.VERSION, "registry history diff query version is current", (value.content_address,)),
        _check(2, "boundary", value.boundary == query_model.BOUNDARY, "registry history diff query boundary is public and value-free", (value.content_address,)),
        _check(3, "resource-order", value.resources == tuple(sorted(value.resources, key=query_model.RESOURCES.index)) and len(value.resources) == len(set(value.resources)), "registry history diff query resources retain canonical order", (value.content_address,)),
        _check(4, "filter-replay", filter_replay, "registry history diff query rows satisfy every declared filter", evidence),
        _check(5, "count-replay", value.total_count >= value.matched_count >= value.returned_count == len(rows) and value.next_offset == value.offset + value.returned_count and value.truncated == (value.next_offset < value.matched_count), "registry history diff query counts and pagination replay", (value.content_address,)),
        _check(6, "row-order", tuple(item.ordinal for item in rows) == tuple(range(1, len(rows) + 1)), "registry history diff query rows retain page order", evidence),
        _check(7, "row-addresses", len({item.content_address for item in rows}) == len(rows) and all(query_model.address_row(item) == item.content_address for item in rows), "registry history diff query row addresses replay", evidence),
        _check(8, "change-semantics", semantics, "registry history diff query rows retain change-resource semantics", evidence),
        _check(9, "public-boundary", _public(value.to_dict()), "registry history diff query contains no forbidden public metadata", (value.content_address,)),
        _check(10, "mapping-round-trip", query_model.query_from_mapping(value.to_dict()).content_address == value.content_address, "registry history diff query mapping round-trips", (value.content_address,)),
    )
    passed = sum(item.passed for item in checks)
    body = {"query_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return output.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry History Diff Query Audit", "", f"- Query: `{value.query_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": query_model.MAX_TOTAL_COUNT + 1}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history diff query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent diff query filter verification", "pagination conservation", "change-resource semantics", "row address replay", "public-boundary enforcement", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
