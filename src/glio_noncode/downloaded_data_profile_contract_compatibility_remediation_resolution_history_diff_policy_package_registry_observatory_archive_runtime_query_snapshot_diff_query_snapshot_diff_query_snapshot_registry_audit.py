"""Independent audit for comparison-query snapshot registries."""

from __future__ import annotations

import csv
import io
import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = registry_model.VERSION + "-audit-v1"
BOUNDARY = registry_model.BOUNDARY + "_audit"
AUDIT_PREFIX = registry_model.REGISTRY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "entry-order",
    "entry-identity",
    "snapshot-linkage",
    "query-counts",
    "state-fold",
    "acceptance-fold",
    "diff-conservation",
    "query-conservation",
    "entries-replay",
    "summary-replay",
    "manifest-replay",
    "artifact-receipts",
    "registry-address",
    "public-boundary",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("registry_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry audit check ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("registry audit check ordinal must be positive")
        self.check_id = _text(check_id, "registry audit check ID", 128)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("registry audit check ID is unsupported")
        self.passed = _bool(passed, "registry audit check result")
        self.detail = _text(detail, "registry audit check detail", 1024)
        self.evidence_addresses = tuple(_address(item, "registry audit evidence address") for item in _sequence(evidence_addresses, "registry audit evidence", 16))
        if not self.evidence_addresses:
            raise ValidationError("registry audit evidence must not be empty")
        self.content_address = _address(content_address, "registry audit check content address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("registry audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("registry audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry audit check")
        _strict(value, set(cls.FIELDS), "registry audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAuditCheck):
        raise ValidationError("registry audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, registry_address: str, checks: Sequence[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.registry_address = _address(registry_address, "registry audit registry address", registry_model.REGISTRY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAuditCheck.from_mapping(item) for item in _sequence(checks, "registry audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "registry audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "registry audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "registry audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "registry audit acceptance")
        self.content_address = _address(content_address, "registry audit content address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("registry audit checks are incomplete or unordered")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("registry audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("registry audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry audit")
        _strict(value, set(cls.FIELDS), "registry audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAudit):
        raise ValidationError("registry audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]):
    body = (ordinal, check_id, passed, detail, tuple(evidence) or (registry_model.REGISTRY_PREFIX + ":pending",), CHECK_PREFIX + ":pending")
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAuditCheck(*body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAuditCheck(*body[:-1], address_check(provisional))


def _artifact_receipts(value) -> bool:
    payloads = {
        "entries.json": canonical_json(value.entries.to_dict()).encode("utf-8"),
        "summary.json": canonical_json(value.summary.to_dict()).encode("utf-8"),
    }
    if tuple(item.name for item in value.manifest.artifacts) != registry_model.MANIFEST_ARTIFACT_FILES:
        return False
    return all(
        len(payloads[item.name]) == item.size
        and hashlib.sha256(payloads[item.name]).hexdigest() == item.digest
        and registry_model.address_artifact(item) == item.content_address
        for item in value.manifest.artifacts
    )


def audit_registry(value: registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry):
    value = registry_model.verify_registry(value)
    entries = value.entries.entries
    expected_state = "empty" if not entries else "ready" if all(item.state == "ready" for item in entries) else "blocked" if all(item.state == "blocked" for item in entries) else "mixed"
    checks = (
        ("version", value.version == registry_model.VERSION, "registry version is current", (value.content_address,)),
        ("boundary", value.boundary == registry_model.BOUNDARY, "registry boundary is current", (value.content_address,)),
        ("entry-order", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), "entries are consecutively ordered", tuple(item.content_address for item in entries)),
        ("entry-identity", len({item.snapshot_id for item in entries}) == len(entries) and len({item.snapshot_address for item in entries}) == len(entries), "snapshot identities are unique", tuple(item.snapshot_address for item in entries)),
        ("snapshot-linkage", all(item.snapshot_address.startswith(registry_model.snapshot_model.SNAPSHOT_PREFIX + ":") and ":" in item.diff_address and ":" in item.query_address and ":" in item.query_audit_address for item in entries), "entries retain addressed snapshot, diff, query, and audit linkage", tuple(item.snapshot_address for item in entries)),
        ("query-counts", all(item.query_matched_count <= item.query_total_count and item.query_returned_count <= item.query_matched_count and item.query_returned_count <= item.limit for item in entries), "query counts remain bounded and conserved", tuple(item.query_address for item in entries)),
        ("state-fold", value.state == expected_state and value.summary.state == expected_state, "registry state folds entry states", (value.summary.content_address,)),
        ("acceptance-fold", value.accepted == bool(entries and all(item.accepted for item in entries)) and value.summary.accepted == value.accepted, "registry acceptance folds entry acceptance", (value.summary.content_address,)),
        ("diff-conservation", value.distinct_diff_count == len({item.diff_id for item in entries}), "distinct diff count is conserved", (value.content_address,)),
        ("query-conservation", value.distinct_query_count == len({item.query_address for item in entries}) and value.total_query_rows == sum(item.query_total_count for item in entries) and value.matched_query_rows == sum(item.query_matched_count for item in entries) and value.returned_query_rows == sum(item.query_returned_count for item in entries), "query counts and distinct query identities are conserved", (value.content_address,)),
        ("entries-replay", registry_model.address_entries(entries) == value.entries.content_address, "entries address replays", (value.entries.content_address,)),
        ("summary-replay", registry_model.address_summary(value.summary) == value.summary.content_address, "summary address replays", (value.summary.content_address,)),
        ("manifest-replay", registry_model.address_manifest(value.manifest) == value.manifest.content_address and value.manifest.files == registry_model.FILES, "manifest address and file order replay", (value.manifest.content_address,)),
        ("artifact-receipts", _artifact_receipts(value), "manifest byte receipts replay", tuple(item.content_address for item in value.manifest.artifacts)),
        ("registry-address", registry_model.address_registry(value) == value.content_address, "registry address replays", (value.content_address,)),
        ("public-boundary", _public(value.to_dict()), "registry contains only public fields", (value.content_address,)),
    )
    result = tuple(_check(ordinal, check_id, passed, detail, evidence) for ordinal, (check_id, passed, detail, evidence) in enumerate(checks, 1))
    body = (value.content_address, result, MAX_CHECKS, sum(item.passed for item in result), sum(not item.passed for item in result), all(item.passed for item in result), AUDIT_PREFIX + ":pending")
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAudit(*body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAudit(*body[:-1], address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAudit.from_mapping(value)


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
    lines = ["# Comparison Query Snapshot Registry Audit", "", f"- Registry: `{value.registry_address}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot registry audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot registry audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"registry_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "value_free": True, "check_ids": list(CHECK_IDS), "features": ["independent entry identity checks", "state and acceptance folding checks", "query-count conservation", "manifest byte receipt replay", "canonical registry-address replay", "deterministic JSON CSV and Markdown projections"]}


__all__ = [
    "AUDIT_FIELDS",
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_FIELDS",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "MAX_CHECKS",
    "VERSION",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAudit",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryAuditCheck",
    "address_audit",
    "address_check",
    "audit_csv",
    "audit_from_mapping",
    "audit_json",
    "audit_registry",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
]
