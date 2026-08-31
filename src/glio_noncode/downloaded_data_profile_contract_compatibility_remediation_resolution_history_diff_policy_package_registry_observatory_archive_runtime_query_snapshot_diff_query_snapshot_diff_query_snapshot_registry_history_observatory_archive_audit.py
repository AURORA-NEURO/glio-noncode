"""Independent audit for history-observatory ZIP archives."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash, hash_bytes

VERSION = archive_model.VERSION + "-audit-v1"
BOUNDARY = archive_model.BOUNDARY + "_audit"
AUDIT_PREFIX = archive_model.ARCHIVE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "member-vocabulary",
    "artifact-order",
    "artifact-receipts",
    "manifest-address",
    "manifest-members",
    "observatory-identity",
    "observatory-projection",
    "nested-observatory-audit",
    "canonical-archive-size",
    "archive-replay",
    "mapping-round-trip",
    "json-round-trip",
    "public-boundary",
    "size-conservation",
    "transport-safety",
)
MAX_CHECKS = len(CHECK_IDS)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("archive_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be a public content address")
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
        lowered = value.casefold()
        return not any(marker in lowered for marker in private_markers)
    return value is None or isinstance(value, (bool, int, float))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAuditCheck:
    """One addressed archive assertion."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "archive audit ordinal", MAX_CHECKS)
        if self.ordinal == 0 or not isinstance(check_id, str) or check_id not in CHECK_IDS:
            raise ValidationError("archive audit check ID is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "archive audit result")
        self.detail = _text(detail, "archive audit detail", 2048)
        self.evidence_addresses = tuple(sorted({_address(item, "archive audit evidence address") for item in _sequence(evidence_addresses, "archive audit evidence", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("archive audit checks require evidence")
        self.content_address = _address(content_address, "archive audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("archive audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("archive audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "archive audit check")
        _strict(value, set(cls.FIELDS), "archive audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAuditCheck):
        raise ValidationError("archive audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAudit:
    """The receiving-side archive audit with independent replay checks."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, archive_address: str, checks: Sequence[Any], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.archive_address = _address(archive_address, "archive audit archive address", archive_model.ARCHIVE_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAuditCheck.from_mapping(item) for item in _sequence(checks, "archive audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "archive audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "archive audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "archive audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "archive audit acceptance")
        self.content_address = _address(content_address, "archive audit content address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("archive audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("archive audit counters do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("archive audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("archive audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_address": self.archive_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAudit):
        raise ValidationError("archive audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: tuple[str, ...]):
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAuditCheck(ordinal, check_id, passed, detail, evidence, address_check(provisional))


def _replays_payload(value) -> bool:
    if value.observatory is None:
        return False
    try:
        return value.payload_bytes() == archive_model._observatory_payload(value.observatory)
    except (KeyError, ValidationError):
        return False


def _replays_receipts(value) -> bool:
    try:
        payload = value.payload_bytes()
    except ValidationError:
        return False
    return all(item.size == len(payload[item.name]) and item.hash == hash_bytes(payload[item.name], prefix=archive_model.ARTIFACT_PREFIX) for item in value.artifacts)


def _zip_size(value) -> int:
    try:
        return len(archive_model.archive_bytes(value))
    except ValidationError:
        return 0


def audit_archive(value):
    if not isinstance(value, archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchive):
        raise ValidationError("archive audit requires a typed archive")
    archive_model.verify_archive(value)
    manifest = archive_model.manifest_document(value)
    payload_ok = _replays_payload(value)
    receipt_ok = _replays_receipts(value)
    zip_size = _zip_size(value)
    nested_audit_ok = False
    if value.observatory is not None:
        try:
            nested_audit_ok = observatory_model.observatory_from_mapping(value.observatory.to_dict()).accepted and _public(value.observatory.to_dict())
        except ValidationError:
            nested_audit_ok = False
    evidence = (value.content_address,)
    checks = (
        ("version", value.version == archive_model.VERSION, "archive version is current"),
        ("boundary", value.boundary == archive_model.BOUNDARY, "archive boundary is public"),
        ("member-vocabulary", value.files == archive_model.ARCHIVE_PAYLOAD_FILES and value.artifact_count == len(archive_model.ARCHIVE_PAYLOAD_FILES), "archive payload vocabulary is exact"),
        ("artifact-order", tuple(item.index for item in value.artifacts) == tuple(range(len(archive_model.ARCHIVE_PAYLOAD_FILES))) and tuple(item.name for item in value.artifacts) == archive_model.ARCHIVE_PAYLOAD_FILES, "artifact order is deterministic"),
        ("artifact-receipts", receipt_ok, "every embedded member matches its byte receipt"),
        ("manifest-address", manifest["manifest_address"] == content_hash(dict(manifest) | {"manifest_address": None}, prefix=archive_model.MANIFEST_PREFIX), "manifest address reproduces canonically"),
        ("manifest-members", tuple(manifest["files"]) == archive_model.ARCHIVE_PAYLOAD_FILES and manifest["archive_address"] == value.content_address, "manifest repeats archive identity and members"),
        ("observatory-identity", value.observatory is not None and value.observatory.observatory_id == value.observatory_id and value.observatory.content_address == value.observatory_address, "nested observatory identity replays"),
        ("observatory-projection", payload_ok, "all embedded observatory projections replay"),
        ("nested-observatory-audit", nested_audit_ok, "nested observatory remains accepted and public"),
        ("canonical-archive-size", zip_size > 0, "canonical archive bytes can be generated"),
        ("archive-replay", zip_size == value.archive_size and zip_size > 0, "ZIP size agrees with the envelope receipt"),
        ("mapping-round-trip", archive_model.archive_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "archive mapping round-trips"),
            ("json-round-trip", archive_model.archive_from_mapping(value.to_dict()).to_dict() == archive_model.archive_from_mapping(json.loads(archive_model.archive_json(value))).to_dict(), "archive JSON round-trips"),
        ("public-boundary", _public(value.to_dict()), "archive envelope is value-free and public"),
        ("size-conservation", value.archive_size > 0 and sum(item.size for item in value.artifacts) > 0, "archive and member sizes are positive"),
        ("transport-safety", all(item.name in archive_model.ARCHIVE_PAYLOAD_FILES and item.name == item.name.replace("\\", "/") for item in value.artifacts), "all transport members are safe regular names"),
    )
    findings = tuple(_check(index, check_id, passed, detail, evidence) for index, (check_id, passed, detail) in enumerate(checks, 1))
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAudit(value.content_address, findings, MAX_CHECKS, sum(item.passed for item in findings), sum(not item.passed for item in findings), all(item.passed for item in findings), AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAudit(provisional.archive_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]):
    value = _mapping(value, "archive audit")
    _strict(value, set(AUDIT_FIELDS), "archive audit")
    checks = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "archive audit checks", MAX_CHECKS))
    result = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAudit(value["archive_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])
    if address_audit(result) != result.content_address:
        raise ValidationError("archive audit address does not replay")
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
    lines = ["# Comparison-query history observatory archive audit", "", f"- Archive: {value.archive_address}", f"- Checks: {value.passed_count}/{value.check_count}", f"- Accepted: {value.accepted}", f"- Address: {value.content_address}", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory archive audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query history observatory archive audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "features": ["independent envelope replay", "embedded projection verification", "byte receipt verification", "canonical ZIP size verification", "transport safety checks", "JSON CSV and Markdown projections"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryArchiveAuditCheck", "VERSION", "address_audit", "address_check", "audit_archive", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
