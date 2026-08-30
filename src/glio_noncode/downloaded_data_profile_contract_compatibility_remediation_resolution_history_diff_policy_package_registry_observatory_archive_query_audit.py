"""Independent validation for policy registry observatory archive queries.

The audit recomputes query namespaces, canonical resource ordering, filter
semantics, pagination, row addresses, receipt shape, nested-resource rules,
and mapping replay.  It is intentionally independent of archive extraction so
a receiving process can validate a query result offline.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "resource-order", "filter-replay", "count-replay", "row-order", "row-addresses", "resource-semantics", "artifact-replay", "file-replay", "nested-replay", "public-boundary", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
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
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAuditCheck:
    """One addressed archive-query assertion."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "archive query audit ordinal", MAX_CHECKS)
        if self.ordinal < 1 or not isinstance(check_id, str) or check_id not in CHECK_IDS:
            raise ValidationError("archive query audit check ID is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "archive query audit result")
        self.detail = _text(detail, "archive query audit detail", 2048)
        self.evidence_addresses = tuple(sorted({_address(item, "archive query evidence address") for item in _sequence(evidence_addresses, "archive query evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("archive query audit checks require evidence")
        self.content_address = _address(content_address, "archive query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("archive query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("archive query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "archive query audit check")
        _strict(value, set(cls.FIELDS), "archive query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAuditCheck):
        raise ValidationError("archive query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit:
    """The complete independent archive-query audit."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, checks: Sequence[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_address = _address(query_address, "archive query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "archive query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "archive query audit count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "archive query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "archive query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "archive query audit acceptance")
        self.content_address = _address(content_address, "archive query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("archive query audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("archive query audit counters do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("archive query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("archive query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "archive query audit")
        _strict(value, set(cls.FIELDS), "archive query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit):
        raise ValidationError("archive query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: tuple[str, ...]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAuditCheck:
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAuditCheck(ordinal, check_id, passed, detail, evidence, address_check(provisional))


def _filter_match(row: Any, value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery) -> bool:
    if value.name_filter and row.name != value.name_filter or value.hash_filter and row.hash != value.hash_filter or value.observatory_id_filter and row.observatory_id != value.observatory_id_filter or value.history_id_filter and row.history_id != value.history_id_filter or value.state_filter and row.state != value.state_filter or value.decision_filter and row.decision != value.decision_filter or value.accepted_filter is not None and row.accepted != value.accepted_filter or value.release_ready_filter is not None and row.release_ready != value.release_ready_filter or value.transition_filter and row.transition != value.transition_filter or value.trend_filter and row.trend != value.trend_filter:
        return False
    if value.text_filter:
        return value.text_filter.casefold() in " ".join(str(row.to_dict()[field]) for field in query_model.ROW_FIELDS if field != "content_address").casefold()
    return True


def _resource_semantics(row: Any) -> bool:
    if row.resource == "summary":
        return row.name == "" and row.artifact_ordinal == 0 and row.member_ordinal == 0 and row.transition_ordinal == 0
    if row.resource == "manifest":
        return row.name == query_model.archive_model.ARCHIVE_MANIFEST_NAME and row.artifact_ordinal == 0 and row.member_ordinal == 0 and row.transition_ordinal == 0 and row.hash.startswith(query_model.FILE_HASH_PREFIX + ":")
    if row.resource == "artifacts":
        return row.artifact_ordinal > 0 and row.name in query_model.archive_model.ARCHIVE_PAYLOAD_FILES and row.hash.startswith(query_model.archive_model.ARTIFACT_PREFIX + ":")
    if row.resource == "files":
        return row.name in query_model.archive_model.FILES and row.hash
    if row.resource == "observatory":
        return row.name == "" and row.member_ordinal == 0 and row.transition_ordinal == 0
    if row.resource == "members":
        return row.member_ordinal > 0 and row.transition_ordinal == 0 and bool(row.history_id) and bool(row.registry_id)
    if row.resource == "transitions":
        return row.member_ordinal > 0 and row.transition_ordinal > 0 and bool(row.transition)
    return False


def audit_query(value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit:
    if not isinstance(value, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery):
        raise ValidationError("archive query audit requires a typed query")
    value = query_model.query_from_mapping(value.to_dict())
    evidence = (value.content_address, value.archive_address)
    rows = value.rows
    resource_order = value.resources == tuple(item for item in query_model.RESOURCES if item in value.resources)
    filter_ok = all(_filter_match(row, value) for row in rows)
    count_ok = value.returned_count == len(rows) and value.returned_count <= value.limit <= query_model.MAX_LIMIT and value.matched_count <= value.total_count and value.returned_count <= max(0, value.matched_count - value.offset)
    semantics_ok = all(_resource_semantics(row) and row.resource in value.resources for row in rows)
    artifact_rows = tuple(row for row in rows if row.resource == "artifacts")
    artifact_ok = all(row.artifact_ordinal > 0 and row.artifact_ordinal <= len(query_model.archive_model.ARCHIVE_PAYLOAD_FILES) and row.name == query_model.archive_model.ARCHIVE_PAYLOAD_FILES[row.artifact_ordinal - 1] and row.size > 0 for row in artifact_rows)
    file_rows = tuple(row for row in rows if row.resource == "files")
    file_ok = all(row.name in query_model.archive_model.FILES and row.size > 0 and ":" in row.hash for row in file_rows)
    nested_rows = tuple(row for row in rows if row.resource in {"observatory", "members", "transitions"})
    nested_ok = all((row.resource == "observatory" and row.member_ordinal == 0 and row.transition_ordinal == 0) or (row.resource == "members" and row.member_ordinal > 0 and not row.transition) or (row.resource == "transitions" and row.member_ordinal > 0 and row.transition_ordinal > 0 and bool(row.transition)) for row in nested_rows)
    checks = (
        ("version", value.archive_address.startswith(query_model.archive_model.ARCHIVE_PREFIX + ":") and value.content_address.startswith(query_model.QUERY_PREFIX + ":"), "query and archive addresses use the current namespaces"),
        ("boundary", _public(value.to_dict()), "query boundary is public and value-free"),
        ("resource-order", resource_order, "query resources retain canonical order"),
        ("filter-replay", filter_ok, "returned rows satisfy recorded filters"),
        ("count-replay", count_ok, "query counts and pagination replay"),
        ("row-order", tuple(row.ordinal for row in rows) == tuple(range(value.offset + 1, value.offset + value.returned_count + 1)), "query rows retain page order"),
        ("row-addresses", all(query_model.address_row(query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryRow.from_mapping(row.to_dict())) == row.content_address for row in rows), "query row addresses replay"),
        ("resource-semantics", semantics_ok, "query rows retain known resource semantics"),
        ("artifact-replay", artifact_ok, "artifact rows retain bounded receipt shape"),
        ("file-replay", file_ok, "file rows retain bounded member receipts"),
        ("nested-replay", nested_ok, "nested observatory rows retain safe identity shape"),
        ("public-boundary", _public(value.to_dict()), "query contains no forbidden public metadata"),
        ("mapping-round-trip", query_model.address_query(query_model.query_from_mapping(value.to_dict())) == value.content_address, "query mapping round-trips to the same address"),
    )
    result = tuple(_check(index, check_id, passed, detail, evidence) for index, (check_id, passed, detail) in enumerate(checks, 1))
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit(value.content_address, result, MAX_CHECKS, sum(item.passed for item in result), sum(not item.passed for item in result), all(item.passed for item in result), AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit(value.content_address, result, MAX_CHECKS, sum(item.passed for item in result), sum(not item.passed for item in result), all(item.passed for item in result), address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit:
    value = _mapping(value, "archive query audit")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Policy Package Registry Observatory Archive Query Audit", "", f"- Query: `{value.query_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent query replay", "filter and pagination conservation", "row-address verification", "archive receipt shape checks", "nested observatory shape checks", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
