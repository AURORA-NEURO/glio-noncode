"""Independent audit for comparison-query snapshot registry history queries."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_query as query_model
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
    "row-order",
    "row-addresses",
    "row-linkage",
    "resource-semantics",
    "mapping-replay",
    "public-boundary",
)
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
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
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
        self.ordinal = _count(ordinal, "history query audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "history query audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("history query audit check ID is unsupported")
        self.passed = _bool(passed, "history query audit result")
        self.detail = _text(detail, "history query audit detail", 4096)
        self.evidence_addresses = tuple(_address(item, "history query audit evidence address") for item in _sequence(evidence_addresses, "history query audit evidence", 32))
        self.content_address = _address(content_address, "history query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("history query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("history query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history query audit check")
        _strict(value, set(cls.FIELDS), "history query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck):
        raise ValidationError("history query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "history query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "history query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "history query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "history query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "history query audit acceptance")
        self.content_address = _address(content_address, "history query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("history query audit accounting does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("history query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": [check.to_dict() for check in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history query audit")
        _strict(value, set(cls.FIELDS), "history query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit):
        raise ValidationError("history query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]):
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _canonical_resources(resources: Sequence[str]) -> bool:
    return bool(resources) and len(set(resources)) == len(resources) and all(resource in query_model.RESOURCES for resource in resources) and tuple(resources) == tuple(resource for resource in query_model.RESOURCES if resource in resources)


def _row_matches_filters(row: Mapping[str, Any], query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery) -> bool:
    if query.resource and row["resource"] != query.resource or query.registry_id and row["registry_id"] != query.registry_id or query.state and row["state"] != query.state or query.accepted is not None and row["accepted"] != query.accepted or query.transition and row["transition"] != query.transition:
        return False
    if query.address_filter and query.address_filter not in " ".join((row["history_address"], row["registry_address"], row["previous_registry_address"], row["content_address"])):
        return False
    if query.text_filter and query.text_filter.casefold() not in json.dumps(row, ensure_ascii=False, sort_keys=True).casefold():
        return False
    return True


def audit_query(value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery):
    if not isinstance(value, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQuery):
        raise ValidationError("history query audit requires a typed query")
    rows = value.rows
    evidence = (value.content_address,)
    checks = [
        _check(1, "version", value.version == query_model.VERSION, "history query version is current", evidence),
        _check(2, "boundary", value.boundary == query_model.BOUNDARY and _public(value.to_dict()), "history query boundary is public and value-free", evidence),
        _check(3, "resource-order", _canonical_resources(value.resources), "history query resources retain canonical order", evidence),
        _check(4, "filter-shape", (not value.resource or value.resource in query_model.RESOURCES) and (not value.state or value.state in query_model.STATES) and (not value.transition or value.transition in query_model.TRANSITIONS), "history query filters use known bounded enums", evidence),
        _check(5, "count-conservation", value.returned_count == len(rows) and value.returned_count <= value.matched_count <= value.total_count, "history query counts are conserved", evidence),
        _check(6, "pagination", value.next_offset == value.offset + value.returned_count and value.truncated == (value.next_offset < value.offset + value.matched_count) and value.returned_count <= value.limit, "history query pagination is bounded", evidence),
        _check(7, "row-order", tuple(row.ordinal for row in rows) == tuple(range(value.offset + 1, value.offset + value.returned_count + 1)), "history query rows retain page order", tuple(row.content_address for row in rows)),
        _check(8, "row-addresses", all(query_model.address_row(row) == row.content_address for row in rows), "history query row addresses replay", tuple(row.content_address for row in rows)),
        _check(9, "row-linkage", all(row.history_address == value.history_address for row in rows), "history query rows retain the source history address", tuple(row.content_address for row in rows)),
        _check(10, "resource-semantics", all(row.resource in value.resources and _row_matches_filters(row.to_dict(), value) for row in rows), "history query rows retain resource and filter semantics", tuple(row.content_address for row in rows)),
        _check(11, "mapping-replay", query_model.query_from_mapping(value.to_dict()).content_address == value.content_address, "history query mapping round-trips", evidence),
        _check(12, "public-boundary", _public(value.to_dict()), "history query contains no forbidden public metadata", evidence),
    ]
    body = {"query_address": value.content_address, "checks": tuple(checks), "check_count": len(checks), "passed_count": sum(check.passed for check in checks), "failed_count": sum(not check.passed for check in checks), "accepted": all(check.passed for check in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryQueryAudit.from_mapping(value)


def audit_json(value) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value) -> str:
    typed = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    for check in typed.checks:
        body = check.to_dict()
        writer.writerow(json.dumps(body[field], ensure_ascii=False, sort_keys=True) if isinstance(body[field], (tuple, list, dict)) else body[field] for field in CHECK_FIELDS)
    return output.getvalue()


def render_audit_markdown(value) -> str:
    typed = audit_from_mapping(value.to_dict())
    lines = ["# Comparison-Query Snapshot Registry History Query Audit", "", f"- Query: `{typed.query_address}`", f"- Checks: `{typed.passed_count}/{typed.check_count}`", f"- Accepted: `{typed.accepted}`", f"- Address: `{typed.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {check.ordinal} | `{check.check_id}` | `{check.passed}` | {check.detail} |" for check in typed.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "value_free": True, "operations": ["audit", "json", "csv", "markdown", "schema"]}
