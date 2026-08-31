"""Independent audit for history-observatory archive queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive as archive_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_query as query_model
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
    "filter-replay",
    "count-replay",
    "row-order",
    "row-addresses",
    "row-membership",
    "resource-semantics",
    "archive-linkage",
    "public-boundary",
    "mapping-round-trip",
)
MAX_CHECKS = len(CHECK_IDS)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("archive_address", "query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be a public address")
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
    private_markers = ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\")
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return not any(marker in value.casefold() for marker in private_markers)
    return value is None or isinstance(value, (bool, int, float))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAuditCheck:
    """One addressed query assertion."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "query audit ordinal", MAX_CHECKS)
        if self.ordinal == 0 or not isinstance(check_id, str) or check_id not in CHECK_IDS:
            raise ValidationError("query audit check ID is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "query audit result")
        self.detail = _text(detail, "query audit detail", 2048)
        self.evidence_addresses = tuple(sorted({_address(item, "query audit evidence address") for item in _sequence(evidence_addresses, "query audit evidence", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("query audit checks require evidence")
        self.content_address = _address(content_address, "query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("query audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "archive query audit check")
        _strict(value, set(cls.FIELDS), "archive query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAuditCheck):
        raise ValidationError("query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAudit:
    """The receiving-side query audit."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, archive_address: str, query_address: str, checks: Sequence[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.archive_address = _address(archive_address, "query audit archive address", archive_model.ARCHIVE_PREFIX)
        self.query_address = _address(query_address, "query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "query audit acceptance")
        self.content_address = _address(content_address, "query audit content address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("query audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("query audit counters do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("query audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("query audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_address": self.archive_address, "query_address": self.query_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAudit):
        raise ValidationError("query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: tuple[str, ...]):
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAuditCheck(ordinal, check_id, passed, detail, evidence, address_check(provisional))


def _query_kwargs(value):
    return {
        "resources": value.resources,
        "name": value.name_filter,
        "hash": value.hash_filter,
        "observatory_id": value.observatory_id_filter,
        "history_id": value.history_id_filter,
        "registry_id": value.registry_id_filter,
        "state": value.state_filter,
        "accepted": value.accepted_filter,
        "transition": value.transition_filter,
        "trend": value.trend_filter,
        "address": value.address_filter,
        "text": value.text_filter,
        "offset": value.offset,
        "limit": value.limit,
    }


def audit_query(query, archive):
    if not isinstance(query, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQuery):
        raise ValidationError("query audit requires a typed query")
    if not isinstance(archive, archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchive):
        raise ValidationError("query audit requires a typed archive")
    archive_model.verify_archive(archive)
    query_model.query_from_mapping(query.to_dict())
    expected = query_model.query_archive(archive, **_query_kwargs(query))
    rows_are_equal = expected.to_dict()["rows"] == query.to_dict()["rows"]
    row_addresses = tuple(item.content_address for item in query.rows)
    row_replayed = all(query_model.address_row(item) == item.content_address for item in query.rows)
    semantic_ok = all(item.resource in query.resources and (item.resource != "transitions" or item.transition in observatory_model.TRANSITIONS) and (item.resource not in {"members", "histories", "states", "trends"} or item.member_ordinal > 0) for item in query.rows)
    evidence = (archive.content_address, query.content_address)
    checks = (
        ("version", query_model.VERSION == VERSION.removesuffix("-audit-v1"), "query version is current"),
        ("boundary", query_model.BOUNDARY == BOUNDARY.removesuffix("_audit"), "query boundary is public"),
        ("resource-order", query.resources == tuple(sorted(query.resources, key=query_model.RESOURCES.index)), "query resources retain canonical order"),
        ("filter-replay", expected.total_count == query.total_count and expected.matched_count == query.matched_count, "query filters replay against the archive"),
        ("count-replay", expected.returned_count == query.returned_count and query.returned_count == len(query.rows), "query pagination counts replay"),
        ("row-order", tuple(item.ordinal for item in query.rows) == tuple(range(1, query.returned_count + 1)), "query rows retain page order"),
        ("row-addresses", row_replayed and len(set(row_addresses)) == len(row_addresses), "query row addresses replay uniquely"),
        ("row-membership", rows_are_equal, "query rows equal the independently recomputed page"),
        ("resource-semantics", semantic_ok, "query rows retain their resource semantics"),
        ("archive-linkage", query.archive_address == archive.content_address, "query links to the exact archive"),
        ("public-boundary", _public(query.to_dict()), "query is value-free and public"),
        ("mapping-round-trip", query_model.query_from_mapping(query.to_dict()).to_dict() == query.to_dict(), "query mapping round-trips"),
    )
    findings = tuple(_check(index, check_id, passed, detail, evidence) for index, (check_id, passed, detail) in enumerate(checks, 1))
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAudit(query.archive_address, query.content_address, findings, MAX_CHECKS, sum(item.passed for item in findings), sum(not item.passed for item in findings), all(item.passed for item in findings), AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAudit(provisional.archive_address, provisional.query_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]):
    value = _mapping(value, "query audit")
    _strict(value, set(AUDIT_FIELDS), "query audit")
    checks = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "query audit checks", MAX_CHECKS))
    result = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAudit(value["archive_address"], value["query_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])
    if address_audit(result) != result.content_address:
        raise ValidationError("query audit address does not replay")
    return result


def audit_json(value) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Comparison-query history observatory archive query audit", "", f"- Archive: {value.archive_address}", f"- Query: {value.query_address}", f"- Checks: {value.passed_count}/{value.check_count}", f"- Accepted: {value.accepted}", f"- Address: {value.content_address}", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory archive query audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory archive query audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent filter replay", "pagination conservation", "row address verification", "resource semantic checks", "archive linkage verification", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveQueryAuditCheck", "VERSION", "address_audit", "address_check", "audit_from_mapping", "audit_json", "audit_csv", "audit_query", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
