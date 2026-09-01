"""Independent replay audit for history-diff ZIP archives."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = archive_model.VERSION + "-audit-v1"
BOUNDARY = archive_model.BOUNDARY + "_audit"
AUDIT_PREFIX = archive_model.ARCHIVE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "identity", "member-vocabulary", "member-order", "size-replay", "receipt-replay", "archive-address", "manifest-address", "zip-replay", "nested-diff", "nested-manifest", "nested-items", "nested-summary", "public-boundary", "raw-availability", "bytes-round-trip", "mapping-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "evidence", "content_address")
AUDIT_FIELDS = ("version", "boundary", "archive_id", "diff_id", "artifact_count", "check_count", "passed", "checks", "content_address")
MAX_TEXT = 4096


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 4096)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return archive_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, evidence: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "history diff archive audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("history diff archive audit check ID is unsupported")
        self.passed = bool(passed)
        self.observed = observed
        self.expected = expected
        self.evidence = tuple(_text(item, "history diff archive audit evidence", 2048) for item in _sequence(evidence, "history diff archive audit evidence", 8))
        self.content_address = _address(content_address, "history diff archive audit check address", CHECK_PREFIX, allow_pending=True)
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("history diff archive audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history diff archive audit check")
        _strict(value, set(cls.FIELDS), "history diff archive audit check")
        return cls(value["check_id"], value["passed"], value["observed"], value["expected"], value["evidence"], value["content_address"])


def address_check(value):
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, version: str, boundary: str, archive_id: str, diff_id: str, artifact_count: int, check_count: int, passed: bool, checks: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAuditCheck], content_address: str) -> None:
        self.version = _text(version, "history diff archive audit version", 2048)
        self.boundary = _text(boundary, "history diff archive audit boundary", 2048)
        self.archive_id = _label(archive_id, "history diff archive audit archive ID")
        self.diff_id = _label(diff_id, "history diff archive audit diff ID")
        self.artifact_count = _count(artifact_count, "history diff archive audit artifact count", len(archive_model.EMBEDDED_FILES))
        self.check_count = _count(check_count, "history diff archive audit check count", len(CHECK_IDS))
        self.passed = bool(passed)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAuditCheck.from_mapping(item) for item in _sequence(checks, "history diff archive audit checks", len(CHECK_IDS)))
        self.content_address = _address(content_address, "history diff archive audit address", AUDIT_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or tuple(item.check_id for item in self.checks) != CHECK_IDS or not self.checks or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("history diff archive audit does not replay its checks")
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("history diff archive audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "archive_id": self.archive_id, "diff_id": self.diff_id, "artifact_count": self.artifact_count, "check_count": self.check_count, "passed": self.passed, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history diff archive audit")
        _strict(value, set(cls.FIELDS), "history diff archive audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value):
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any, evidence: Sequence[str]):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAuditCheck(check_id, observed == expected, observed, expected, evidence, CHECK_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAuditCheck(check_id, provisional.passed, observed, expected, evidence, address_check(provisional))


def audit_archive(value):
    value = archive_model.verify_archive(value)
    raw = value.embedded_bytes() if value.diff is not None else {}
    manifest = archive_model.manifest_document(value)
    expected_raw = archive_model._embedded_diff(value.diff) if value.diff is not None else {}
    nested_manifest = raw.get(archive_model.EMBEDDED_PREFIX + "manifest.json", b"")
    nested_diff = raw.get(archive_model.EMBEDDED_PREFIX + "diff.json", b"")
    nested_items = raw.get(archive_model.EMBEDDED_PREFIX + "items.json", b"")
    nested_summary = raw.get(archive_model.EMBEDDED_PREFIX + "summary.json", b"")
    checks = (
        _check("version", value.version, archive_model.VERSION, (value.content_address,)),
        _check("boundary", value.boundary, archive_model.BOUNDARY, (value.content_address,)),
        _check("identity", (value.archive_id, value.diff_id, value.diff_address), (value.archive_id, value.diff_id, value.diff_address), (value.content_address,)),
        _check("member-vocabulary", (value.artifact_count, value.files), (len(archive_model.EMBEDDED_FILES), archive_model.EMBEDDED_FILES), (value.content_address,)),
        _check("member-order", tuple(item.index for item in value.artifacts), tuple(range(len(archive_model.EMBEDDED_FILES))), (value.content_address,)),
        _check("size-replay", value.archive_size, len(archive_model._zip_bytes_unchecked(value)) if value.diff is not None else value.archive_size, (value.content_address,)),
        _check("receipt-replay", tuple((item.name, item.size, item.hash) for item in value.artifacts), tuple((name, len(raw[name]), archive_model.hash_bytes(raw[name], prefix=archive_model.ARTIFACT_PREFIX)) for name in archive_model.EMBEDDED_FILES) if raw else tuple((item.name, item.size, item.hash) for item in value.artifacts), (value.content_address,)),
        _check("archive-address", archive_model.address_archive(value), value.content_address, (value.content_address,)),
        _check("manifest-address", manifest["manifest_address"], archive_model.content_hash(manifest | {"manifest_address": None}, prefix=archive_model.MANIFEST_PREFIX), (value.content_address,)),
        _check("zip-replay", (len(archive_model.archive_bytes(value)), archive_model.hash_bytes(archive_model.archive_bytes(value), prefix=archive_model.ARTIFACT_PREFIX)) if value.diff is not None else (0, ""), (value.archive_size, archive_model.hash_bytes(archive_model.archive_bytes(value), prefix=archive_model.ARTIFACT_PREFIX)) if value.diff is not None else (0, ""), (value.content_address,)),
        _check("nested-diff", archive_model.hash_bytes(nested_diff, prefix=archive_model.ARTIFACT_PREFIX) if nested_diff else "", archive_model.hash_bytes(expected_raw.get(archive_model.EMBEDDED_PREFIX + "diff.json", b""), prefix=archive_model.ARTIFACT_PREFIX) if expected_raw.get(archive_model.EMBEDDED_PREFIX + "diff.json", b"") else "", (value.diff_address,)),
        _check("nested-manifest", archive_model.hash_bytes(nested_manifest, prefix=archive_model.ARTIFACT_PREFIX) if nested_manifest else "", archive_model.hash_bytes(expected_raw.get(archive_model.EMBEDDED_PREFIX + "manifest.json", b""), prefix=archive_model.ARTIFACT_PREFIX) if expected_raw.get(archive_model.EMBEDDED_PREFIX + "manifest.json", b"") else "", (value.diff_address,)),
        _check("nested-items", archive_model.hash_bytes(nested_items, prefix=archive_model.ARTIFACT_PREFIX) if nested_items else "", archive_model.hash_bytes(expected_raw.get(archive_model.EMBEDDED_PREFIX + "items.json", b""), prefix=archive_model.ARTIFACT_PREFIX) if expected_raw.get(archive_model.EMBEDDED_PREFIX + "items.json", b"") else "", (value.diff_address,)),
        _check("nested-summary", archive_model.hash_bytes(nested_summary, prefix=archive_model.ARTIFACT_PREFIX) if nested_summary else "", archive_model.hash_bytes(expected_raw.get(archive_model.EMBEDDED_PREFIX + "summary.json", b""), prefix=archive_model.ARTIFACT_PREFIX) if expected_raw.get(archive_model.EMBEDDED_PREFIX + "summary.json", b"") else "", (value.diff_address,)),
        _check("public-boundary", _public(value.to_dict()), True, (value.content_address,)),
        _check("raw-availability", set(raw), set(archive_model.EMBEDDED_FILES), (value.content_address,)),
        _check("bytes-round-trip", archive_model.load_archive_bytes(archive_model.archive_bytes(value)).content_address if value.diff is not None else "", value.content_address if value.diff is not None else "", (value.content_address,)),
        _check("mapping-round-trip", archive_model.archive_from_mapping(value.to_dict()).content_address, value.content_address, (value.content_address,)),
    )
    body = {"version": VERSION, "boundary": BOUNDARY, "archive_id": value.archive_id, "diff_id": value.diff_id, "artifact_count": value.artifact_count, "check_count": len(checks), "passed": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAudit(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAudit(**(body | {"content_address": address_audit(provisional)}))


def verify_audit(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAudit):
        raise ValidationError("history diff archive audit verification requires a typed audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAudit.from_mapping(value)


def audit_json(value) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value) -> str:
    value = verify_audit(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value) -> str:
    value = verify_audit(value)
    lines = ["# Execution-ledger registry history diff archive audit", "", f"- Archive: `{value.archive_id}`", f"- Checks: `{value.check_count}`", f"- Passed: `{value.passed}`", f"- Address: `{value.content_address}`", "", "| # | check | passed |", "| ---: | --- | --- |"]
    lines.extend(f"| {index} | `{item.check_id}` | `{item.passed}` |" for index, item in enumerate(value.checks, 1))
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffArchiveAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "evidence": {"type": "array", "items": {"type": "string"}, "maxItems": 8}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffArchiveAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "archive_id": {"type": "string"}, "diff_id": {"type": "string"}, "artifact_count": {"type": "integer", "minimum": 0}, "check_count": {"type": "integer", "const": len(CHECK_IDS)}, "passed": {"type": "boolean"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS), "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "features": ["independent member replay", "nested diff projection replay", "ZIP size and receipt verification", "canonical mapping replay"]}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveAuditCheck", "VERSION", "address_audit", "address_check", "audit_archive", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
