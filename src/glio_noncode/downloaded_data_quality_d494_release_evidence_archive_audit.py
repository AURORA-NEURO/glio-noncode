"""Independent integrity and lineage audit for D494 evidence archives."""
from __future__ import annotations

# ruff: noqa: E501, I001
import csv
import hashlib
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d494_release_evidence_archive as archive_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = archive_model.VERSION + "-audit-v1"
BOUNDARY = archive_model.BOUNDARY + "_audit"
AUDIT_PREFIX = archive_model.ARCHIVE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "typed_archive", "manifest_identity", "member_inventory", "payload_digests",
    "comparison_link", "strict_runtime_link", "release_runtime_link", "policy_order",
    "strict_audit_link", "release_audit_link", "query_replay", "release_disposition",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("bundle_id", "archive_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _address(value: Any, field: str, prefix: str) -> str:
    if not isinstance(value, str) or (not value.startswith("pending:") and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _strict(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    if set(value) != expected:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "D494 audit ordinal", MAX_CHECKS)
        self.check_id = check_id
        self.passed = passed
        self.actual = actual
        self.expected = expected
        self.detail = detail
        self.content_address = _address(content_address, "D494 check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.check_id, str) or not self.check_id or not isinstance(self.passed, bool):
            raise ValidationError("D494 audit check identity or result is invalid")
        if not all(isinstance(x, str) for x in (self.actual, self.expected, self.detail)):
            raise ValidationError("D494 audit evidence must be text")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("D494 check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in CHECK_FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        _strict(value, set(cls.FIELDS), "D494 audit check")
        return cls(*(value[key] for key in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("D494 addressing requires a typed audit check")
    return _address_for(value, CHECK_PREFIX)


class ArchiveAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, bundle_id: str, archive_address: str, checks: Sequence[AuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.bundle_id = bundle_id
        self.archive_address = _address(archive_address, "D494 archive address", archive_model.ARCHIVE_PREFIX)
        self.checks = tuple(x if isinstance(x, AuditCheck) else AuditCheck.from_mapping(x) for x in checks)
        self.check_count = _count(check_count, "D494 check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "D494 passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "D494 failed count", MAX_CHECKS)
        self.accepted = accepted
        self.content_address = _address(content_address, "D494 audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.bundle_id, str) or not self.bundle_id or not isinstance(self.accepted, bool):
            raise ValidationError("D494 audit identity or disposition is invalid")
        if tuple(x.ordinal for x in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(x.check_id for x in self.checks) != CHECK_IDS:
            raise ValidationError("D494 audit sequence is not canonical")
        if (self.check_count, self.passed_count, self.failed_count, self.accepted) != (
            len(self.checks), sum(x.passed for x in self.checks), sum(not x.passed for x in self.checks), all(x.passed for x in self.checks),
        ):
            raise ValidationError("D494 audit counters do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("D494 audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"bundle_id": self.bundle_id, "archive_address": self.archive_address,
                "checks": [x.to_dict() for x in self.checks], "check_count": self.check_count,
                "passed_count": self.passed_count, "failed_count": self.failed_count,
                "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ArchiveAudit":
        _strict(value, set(cls.FIELDS), "D494 archive audit")
        return cls(*(value[key] for key in cls.FIELDS))


def address_audit(value: ArchiveAudit) -> str:
    if not isinstance(value, ArchiveAudit):
        raise ValidationError("D494 addressing requires a typed archive audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed),
            "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail,
            "content_address": f"pending:{CHECK_PREFIX}"}
    item = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(item)}))


def audit_archive(value: archive_model.EvidenceArchive) -> ArchiveAudit:
    archive_model.verify_archive(value)
    manifest = value.manifest
    linked = archive_model._replay_members(value)
    summary = linked["summary"]
    strict = linked["strict_runtime"]
    release = linked["release_runtime"]
    strict_audit = linked["strict_audit"]
    release_audit = linked["release_audit"]
    query = linked["query"]
    query_audit = linked["query_audit"]
    expected_sizes = tuple(item.size for item in manifest.files)
    actual_sizes = tuple(len(item) for item in value.payloads)
    expected_digests = tuple(item.sha256 for item in manifest.files)
    actual_digests = tuple(hashlib.sha256(item).hexdigest() for item in value.payloads)
    complete_query = archive_model._query_complete(query)
    release_ready = release.release_ready and strict_audit.accepted and release_audit.accepted and query_audit.accepted and complete_query
    checks = (
        _finding(1, "typed_archive", isinstance(value, archive_model.EvidenceArchive), type(value).__name__, "EvidenceArchive", "bundle is represented by the typed archive model"),
        _finding(2, "manifest_identity", (manifest.version, manifest.boundary, manifest.content_address == archive_model.address_manifest(manifest)), (manifest.version, manifest.boundary, manifest.content_address), (archive_model.VERSION, archive_model.BOUNDARY, archive_model.address_manifest(manifest)), "version, boundary, and manifest address replay"),
        _finding(3, "member_inventory", tuple(item.path for item in manifest.files) == archive_model.FILE_NAMES and manifest.file_count == len(archive_model.FILE_NAMES), [item.path for item in manifest.files], archive_model.FILE_NAMES, "only the fixed allowlisted evidence members are present"),
        _finding(4, "payload_digests", expected_sizes == actual_sizes and expected_digests == actual_digests, (actual_sizes, actual_digests), (expected_sizes, expected_digests), "each payload matches its manifest size and SHA-256"),
        _finding(5, "comparison_link", (summary["diff_id"], summary["diff_address"]) == (manifest.diff_id, manifest.diff_address), (summary["diff_id"], summary["diff_address"]), (manifest.diff_id, manifest.diff_address), "redacted summary binds both runtimes to one comparison"),
        _finding(6, "strict_runtime_link", (strict.runtime_id, strict.content_address, strict.diff_address) == (manifest.strict_runtime_id, manifest.strict_runtime_address, manifest.diff_address), (strict.runtime_id, strict.content_address, strict.diff_address), (manifest.strict_runtime_id, manifest.strict_runtime_address, manifest.diff_address), "strict result retains the source diff lineage"),
        _finding(7, "release_runtime_link", (release.runtime_id, release.content_address, release.diff_address) == (manifest.release_runtime_id, manifest.release_runtime_address, manifest.diff_address), (release.runtime_id, release.content_address, release.diff_address), (manifest.release_runtime_id, manifest.release_runtime_address, manifest.diff_address), "release result retains the source diff lineage"),
        _finding(8, "policy_order", archive_model._strict_policy(strict.policy, release.policy), "strict policy", "at least as restrictive as release policy", "strict budgets and gates cannot be looser"),
        _finding(9, "strict_audit_link", (strict_audit.runtime_address, strict_audit.content_address) == (manifest.strict_runtime_address, manifest.strict_audit_address), (strict_audit.runtime_address, strict_audit.content_address), (manifest.strict_runtime_address, manifest.strict_audit_address), "strict audit is bound to the exact strict runtime"),
        _finding(10, "release_audit_link", (release_audit.runtime_address, release_audit.content_address) == (manifest.release_runtime_address, manifest.release_audit_address), (release_audit.runtime_address, release_audit.content_address), (manifest.release_runtime_address, manifest.release_audit_address), "release audit is bound to the exact release runtime"),
        _finding(11, "query_replay", query_audit.accepted and query_audit.query_address == query.content_address and query.runtime_address == release.content_address, (query_audit.accepted, query_audit.query_address, query.runtime_address), (True, query.content_address, release.content_address), "query and its audit replay from the release runtime"),
        _finding(12, "release_disposition", (manifest.state, manifest.release_ready) == (("ready", True) if release_ready else ("blocked", False)), (manifest.state, manifest.release_ready), ("ready", True) if release_ready else ("blocked", False), "bundle readiness follows release policy and evidence completeness"),
    )
    result = ArchiveAudit(manifest.bundle_id, value.content_address, checks, len(checks), sum(x.passed for x in checks), sum(not x.passed for x in checks), all(x.passed for x in checks), f"pending:{AUDIT_PREFIX}")
    return ArchiveAudit.from_mapping(result.to_dict() | {"content_address": address_audit(result)})


def verify_audit(value: ArchiveAudit) -> ArchiveAudit:
    if not isinstance(value, ArchiveAudit):
        raise ValidationError("D494 verification requires a typed archive audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> ArchiveAudit:
    return ArchiveAudit.from_mapping(value)


def audit_json(value: ArchiveAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: ArchiveAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: ArchiveAudit) -> str:
    value = verify_audit(value)
    lines = [f"# D494 evidence archive audit {value.bundle_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "D494ArchiveAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent manifest and payload checks", "source lineage and strictness replay", "runtime and query audit linkage", "release disposition replay", "JSON CSV Markdown output")}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "ArchiveAudit", "address_check", "address_audit", "audit_archive", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "audit_schema", "capabilities"]
