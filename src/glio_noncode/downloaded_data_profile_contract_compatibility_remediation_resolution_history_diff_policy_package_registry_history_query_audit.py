"""Independent assurance for policy package registry history queries."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_query as query_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-query-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_query_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "row-semantics", "public-boundary", "mapping-round-trip")
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history query audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "registry history query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("registry history query audit check ID is unsupported")
        self.passed = _bool(passed, "registry history query audit check result")
        self.detail = _text(detail, "registry history query audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "registry history query audit evidence address") for item in _sequence(evidence_addresses, "registry history query audit evidence addresses", query_model.MAX_TOTAL_COUNT + 1)}))
        if not self.evidence_addresses:
            raise ValidationError("registry history query audit checks require evidence")
        self.content_address = _address(content_address, "registry history query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("registry history query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("registry history query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck:
        value = _mapping(value, "registry history query audit check")
        _strict(value, set(cls.FIELDS), "registry history query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck):
        raise ValidationError("registry history query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "registry history query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "registry history query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "registry history query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "registry history query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "registry history query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "registry history query audit acceptance")
        self.content_address = _address(content_address, "registry history query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)):
            raise ValidationError("registry history query audit check order is not conserved")
        if tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("registry history query audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("registry history query audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry history query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("registry history query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit:
        value = _mapping(value, "registry history query audit")
        _strict(value, set(cls.FIELDS), "registry history query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit):
        raise ValidationError("registry history query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence) or (query_model.QUERY_PREFIX + ":empty",), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _matches(row: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryRow, query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery) -> bool:
    if query.resource and row.resource != query.resource:
        return False
    if query.registry_id and row.registry_id != query.registry_id:
        return False
    if query.state and row.state != query.state:
        return False
    if query.decision and row.decision != query.decision:
        return False
    if query.accepted is not None and row.accepted != query.accepted:
        return False
    if query.release_ready is not None and row.release_ready != query.release_ready:
        return False
    if query.transition and row.transition != query.transition:
        return False
    if query.text and query.text.casefold() not in " ".join((row.identity, row.registry_id, row.registry_address, row.state, row.decision, row.transition, row.detail)).casefold():
        return False
    return True


def audit_query(value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit:
    if not isinstance(value, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery):
        raise ValidationError("registry history query audit requires a typed query")
    rows = value.rows
    evidence = tuple(item.content_address for item in rows[: query_model.MAX_TOTAL_COUNT + 1]) or (value.content_address,)
    filter_replay = all(_matches(item, value) for item in rows)
    semantics = all(item.release_ready if item.resource == "ready" else item.transition in query_model.TRANSITIONS for item in rows)
    checks = (
        _check(1, "version", value.version == query_model.VERSION, "registry history query version is current", (value.content_address,)),
        _check(2, "boundary", value.boundary == query_model.BOUNDARY, "registry history query boundary is public and value-free", (value.content_address,)),
        _check(3, "resource-order", value.resources == tuple(sorted(value.resources, key=query_model.RESOURCES.index)) and len(value.resources) == len(set(value.resources)), "registry history query resources retain canonical order", (value.content_address,)),
        _check(4, "filter-replay", filter_replay, "registry history query rows satisfy every declared filter", evidence),
        _check(5, "count-replay", value.total_count >= value.matched_count >= value.returned_count == len(rows) and value.next_offset == value.offset + value.returned_count and value.truncated == (value.next_offset < value.matched_count), "registry history query counts and pagination replay", (value.content_address,)),
        _check(6, "row-order", tuple(item.ordinal for item in rows) == tuple(range(1, len(rows) + 1)), "registry history query rows retain page order", evidence),
        _check(7, "row-addresses", len({item.content_address for item in rows}) == len(rows) and all(query_model.address_row(item) == item.content_address for item in rows), "registry history query row addresses replay", evidence),
        _check(8, "row-semantics", semantics, "registry history query rows retain resource semantics", evidence),
        _check(9, "public-boundary", _public(value.to_dict()), "registry history query contains no forbidden public metadata", (value.content_address,)),
        _check(10, "mapping-round-trip", query_model.query_from_mapping(value.to_dict()).content_address == value.content_address, "registry history query mapping round-trips", (value.content_address,)),
    )
    passed = sum(item.passed for item in checks)
    body = {"query_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return output.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry History Query Audit", "", f"- Query: `{value.query_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": query_model.MAX_TOTAL_COUNT + 1}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent history query filter verification", "pagination conservation", "address replay", "resource semantics", "public-boundary enforcement", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
