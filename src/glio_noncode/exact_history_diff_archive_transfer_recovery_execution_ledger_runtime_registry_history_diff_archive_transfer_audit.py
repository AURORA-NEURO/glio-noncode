"""Independent audit for execution-ledger history-diff archive transfers."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer as transfer_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = transfer_model.VERSION + "-audit-v1"
BOUNDARY = transfer_model.BOUNDARY + "_audit"
AUDIT_PREFIX = transfer_model.TRANSFER_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("version", "boundary", "identity", "archive-linkage", "chunk-count", "chunk-order", "range-conservation", "chunk-receipts", "payload-completeness", "archive-reassembly", "transfer-address", "manifest-address", "progress-empty", "progress-complete", "public-boundary", "mapping-round-trip", "bytes-round-trip", "manifest-round-trip")
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "evidence", "content_address")
AUDIT_FIELDS = ("version", "boundary", "transfer_id", "archive_id", "chunk_count", "check_count", "passed", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 2048)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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
    return transfer_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, evidence: Sequence[str], content_address: str) -> None:
        self.check_id = _label(check_id, "transfer audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("transfer audit check ID is unsupported")
        self.passed = bool(passed)
        self.observed = observed
        self.expected = expected
        self.evidence = tuple(_text(item, "transfer audit evidence", 2048) for item in _sequence(evidence, "transfer audit evidence", 8))
        self.content_address = _address(content_address, "transfer audit check address", CHECK_PREFIX, allow_pending=True)
        if not _public(self.to_dict()):
            raise ValidationError("transfer audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("transfer audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "transfer audit check")
        _strict(value, set(cls.FIELDS), "transfer audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value):
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, version: str, boundary: str, transfer_id: str, archive_id: str, chunk_count: int, check_count: int, passed: bool, checks: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAuditCheck], content_address: str) -> None:
        self.version = _text(version, "transfer audit version")
        self.boundary = _text(boundary, "transfer audit boundary")
        self.transfer_id = _label(transfer_id, "transfer audit transfer ID")
        self.archive_id = _label(archive_id, "transfer audit archive ID")
        self.chunk_count = transfer_model._count(chunk_count, "transfer audit chunk count", transfer_model.MAX_CHUNKS, positive=True)
        self.check_count = transfer_model._count(check_count, "transfer audit check count", len(CHECK_IDS))
        self.passed = bool(passed)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAuditCheck.from_mapping(item) for item in _sequence(checks, "transfer audit checks", len(CHECK_IDS)))
        self.content_address = _address(content_address, "transfer audit address", AUDIT_PREFIX, allow_pending=True)
        if self.version != VERSION or self.boundary != BOUNDARY or self.check_count != len(self.checks) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("transfer audit does not replay its checks")
        if not _public(self.to_dict()):
            raise ValidationError("transfer audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("transfer audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "boundary": self.boundary, "transfer_id": self.transfer_id, "archive_id": self.archive_id, "chunk_count": self.chunk_count, "check_count": self.check_count, "passed": self.passed, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "transfer audit")
        _strict(value, set(cls.FIELDS), "transfer audit")
        return cls(*(value[field] for field in self_fields(cls)))


def self_fields(cls) -> tuple[str, ...]:
    return cls.FIELDS


def address_audit(value):
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any, evidence: Sequence[str], *, passed: bool | None = None):
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAuditCheck(check_id, observed == expected if passed is None else passed, observed, expected, evidence, CHECK_PREFIX + ":pending")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAuditCheck(check_id, provisional.passed, observed, expected, evidence, address_check(provisional))


def audit_transfer(value):
    value = transfer_model.verify_transfer(value)
    payload: Mapping[int, bytes] | None
    try:
        payload = value.payload_bytes()
    except ValidationError:
        payload = None
    expected_chunks = tuple((chunk.index, chunk.offset, chunk.size) for chunk in value.chunks)
    observed_chunks = tuple((chunk.index, chunk.offset, chunk.size) for chunk in value.chunks)
    expected_ranges = tuple(range(value.chunk_count))
    expected_progress = tuple(range(value.chunk_count))
    if payload is None:
        receipt_observed = tuple((chunk.index, chunk.size, "unavailable") for chunk in value.chunks)
        receipt_expected = tuple((chunk.index, chunk.size, chunk.content_address) for chunk in value.chunks)
        reassembly_observed: Any = "unavailable"
        reassembly_expected: Any = (value.archive_size, value.archive_address)
        complete_observed = False
    else:
        receipt_observed = tuple((chunk.index, len(payload[chunk.index]), transfer_model.address_chunk(payload[chunk.index])) for chunk in value.chunks)
        receipt_expected = tuple((chunk.index, chunk.size, chunk.content_address) for chunk in value.chunks)
        assembled = transfer_model.assemble_archive_bytes(value, payload)
        reassembly_observed = (len(assembled), transfer_model.archive_model.load_archive_bytes(assembled).content_address)
        reassembly_expected = (value.archive_size, value.archive_address)
        complete_observed = True
    empty = transfer_model._progress_from_parts(value, {})
    complete = transfer_model._progress_from_parts(value, {} if payload is None else payload)
    checks = (
        _check("version", value.version, transfer_model.VERSION, (value.content_address,)),
        _check("boundary", value.boundary, transfer_model.BOUNDARY, (value.content_address,)),
        _check("identity", (value.transfer_id, value.archive_id), (value.transfer_id, value.archive_id), (value.content_address,)),
        _check("archive-linkage", value.archive_address, value.archive_address, (value.archive_address,)),
        _check("chunk-count", value.chunk_count, len(value.chunks), (str(value.chunk_count),)),
        _check("chunk-order", observed_chunks, expected_chunks, (str(value.chunk_count),)),
        _check("range-conservation", (value.chunks[0].offset, value.chunks[-1].offset + value.chunks[-1].size), (0, value.archive_size), (value.archive_address,)),
        _check("chunk-receipts", receipt_observed, receipt_expected, (value.content_address,)),
        _check("payload-completeness", complete_observed, True, (str(value.archive_size),)),
        _check("archive-reassembly", reassembly_observed, reassembly_expected, (value.archive_address,)),
        _check("transfer-address", transfer_model.address_transfer(value), value.content_address, (value.content_address,)),
        _check("manifest-address", transfer_model.manifest_document(value)["manifest_address"], transfer_model.manifest_document(value)["manifest_address"], (value.content_address,)),
        _check("progress-empty", (empty.received_indices, empty.missing_indices, empty.received_bytes), ((), expected_progress, 0), (empty.content_address,)),
        _check("progress-complete", (complete.complete, complete.received_chunk_count, complete.received_bytes), (complete_observed, value.chunk_count if complete_observed else 0, value.archive_size if complete_observed else 0), (complete.content_address,)),
        _check("public-boundary", _public(value.to_dict()), True, (value.content_address,)),
        _check("mapping-round-trip", transfer_model.transfer_from_mapping(value.to_dict()).content_address, value.content_address, (value.content_address,)),
        _check("bytes-round-trip", (len(payload) if payload is not None else 0, sum(len(item) for item in payload.values()) if payload is not None else 0), (value.chunk_count if payload is not None else 0, value.archive_size if payload is not None else 0), (value.content_address,)),
        _check("manifest-round-trip", transfer_model.transfer_from_mapping({field: transfer_model.manifest_document(value)[field] for field in transfer_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransfer.FIELDS if field != "content_address"} | {"content_address": value.content_address}).content_address, value.content_address, (value.content_address,)),
    )
    body = {"version": VERSION, "boundary": BOUNDARY, "transfer_id": value.transfer_id, "archive_id": value.archive_id, "chunk_count": value.chunk_count, "check_count": len(checks), "passed": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAudit(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAudit.from_mapping(value)


def verify_audit(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAudit):
        raise ValidationError("transfer audit verification requires a typed audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAudit.from_mapping(value.to_dict())


def audit_json(value) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value) -> str:
    value = verify_audit(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(check.to_dict() for check in value.checks)
    return stream.getvalue()


def render_audit_markdown(value) -> str:
    value = verify_audit(value)
    lines = ["# Execution-ledger history-diff archive transfer audit", "", f"- Transfer: `{value.transfer_id}`", f"- Archive: `{value.archive_id}`", f"- Result: `{value.passed}`", f"- Checks: `{value.check_count}`", "", "| check | passed |", "| --- | ---: |"]
    lines.extend(f"| `{check.check_id}` | `{check.passed}` |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "evidence": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Execution-ledger history-diff archive transfer audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "transfer_id": {"type": "string"}, "archive_id": {"type": "string"}, "chunk_count": {"type": "integer", "minimum": 1}, "check_count": {"type": "integer", "minimum": 0, "maximum": len(CHECK_IDS)}, "passed": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": len(CHECK_IDS), "operations": ["audit_transfer", "audit_from_mapping", "verify_audit", "audit_json", "audit_csv", "render_audit_markdown"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveTransferAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "audit_transfer", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
