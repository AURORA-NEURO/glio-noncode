"""Independent operator audit for observatory archive transfers.

The transfer module proves byte identity when a receiver has all chunks. This
module adds an addressed, path-free audit projection that can also describe a
valid partial receiver state. It never changes a transfer or repairs a chunk:
it recomputes the public transfer graph, range conservation, received receipts,
progress conservation, nested archive linkage when complete, and public-boundary
status. Partial transfers remain inspectable and explicitly fail the
completion check until the assembler can reassemble the nested archive.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer as transfer_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = transfer_model.VERSION + "-audit-v1"
BOUNDARY = transfer_model.BOUNDARY + "_audit"
AUDIT_PREFIX = transfer_model.TRANSFER_PREFIX + "-audit"
AUDIT_CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("transfer-address", "range-conservation", "public-boundary", "manifest-address", "chunk-receipts", "progress-conservation", "nested-archive", "assembly-complete")
STATES = ("complete", "incomplete")


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


class TransferAuditCheck:
    """One independently addressed transfer audit assertion."""

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str) -> None:
        self.check_id = _text(check_id, "audit check ID", 128)
        self.passed = passed if isinstance(passed, bool) else (_ for _ in ()).throw(ValidationError("audit check pass state must be boolean"))
        self.detail = _text(detail, "audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "audit check evidence address", 2048)
        self.content_address = content_hash({"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address}, prefix=AUDIT_CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TransferAuditCheck":
        value = _mapping(value, "audit check")
        _strict(value, {"check_id", "passed", "detail", "evidence_address", "content_address"}, "audit check")
        result = cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"])
        if value["content_address"] != result.content_address:
            raise ValidationError("audit check content address mismatch")
        return result


class TransferAudit:
    """Public audit report for complete or partial transfer state."""

    def __init__(self, transfer_address: str, archive_address: str, state: str, complete: bool, check_count: int, passed_count: int, failed_count: int, checks: Sequence[TransferAuditCheck], content_address: str) -> None:
        self.transfer_address = transfer_address
        self.archive_address = archive_address
        self.state = state
        self.complete = complete
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.transfer_address, "audit transfer address", transfer_model.TRANSFER_PREFIX)
        _address(self.archive_address, "audit archive address", transfer_model.archive_model.ARCHIVE_PREFIX)
        if self.state not in STATES or not isinstance(self.complete, bool) or self.state != ("complete" if self.complete else "incomplete"):
            raise ValidationError("audit state does not match completion")
        _count(self.check_count, "audit check count", len(CHECK_IDS))
        if self.check_count != len(self.checks) or tuple(check.check_id for check in self.checks) != CHECK_IDS:
            raise ValidationError("audit check set is invalid")
        _count(self.passed_count, "audit passed count", len(CHECK_IDS))
        _count(self.failed_count, "audit failed count", len(CHECK_IDS))
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("audit check counts are not conserved")
        by_id = {check.check_id: check for check in self.checks}
        if by_id["assembly-complete"].passed != self.complete or (self.complete and not by_id["nested-archive"].passed):
            raise ValidationError("audit completion does not match its checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "audit content address")
        else:
            _address(self.content_address, "audit content address", AUDIT_PREFIX)
        if not transfer_model._public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("audit content address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_address": self.transfer_address, "archive_address": self.archive_address, "state": self.state, "complete": self.complete, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("transfer_address", "archive_address", "state", "complete", "check_count", "passed_count", "failed_count", "content_address")}


def address_audit(value: TransferAudit) -> str:
    if not isinstance(value, TransferAudit):
        raise ValidationError("audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: str) -> TransferAuditCheck:
    return TransferAuditCheck(check_id, passed, detail, evidence)


def _build_audit(assembler: transfer_model.TransferAssembler) -> TransferAudit:
    value = assembler.value
    progress = assembler.progress()
    manifest = transfer_model.manifest_document(value)
    all_ranges = value.chunk_count == len(value.chunks) and sum(chunk.size for chunk in value.chunks) == value.archive_size and all(chunk.offset == sum(previous.size for previous in value.chunks[:chunk.index]) for chunk in value.chunks)
    public = transfer_model._public(value.to_dict())
    receipts = all(address == transfer_model.address_chunk(assembler._parts[index]) for index, address in ((index, value.chunks[index].content_address) for index in assembler.received_indices()))
    progress_ok = progress.received_bytes == sum(value.chunks[index].size for index in progress.received_indices) and set(progress.received_indices) | set(progress.missing_indices) == set(range(value.chunk_count))
    nested_ok = True
    if progress.complete:
        try:
            assembled = assembler.finalize()
            nested_ok = transfer_model.archive_model.verify_archive_bytes(assembled).content_address == value.archive_address
        except ValidationError:
            nested_ok = False
    else:
        nested_ok = False
    checks = (
        _check("transfer-address", transfer_model.address_transfer(value) == value.content_address, "transfer address reproduces from the public projection", value.content_address),
        _check("range-conservation", all_ranges, "declared chunk ranges conserve the archive byte count", value.archive_address),
        _check("public-boundary", public, "transfer projection contains only public fields", value.content_address),
        _check("manifest-address", manifest["manifest_address"] == transfer_model.content_hash(dict(manifest) | {"manifest_address": None}, prefix=transfer_model.TRANSFER_MANIFEST_PREFIX), "manifest address reproduces from canonical manifest fields", manifest["manifest_address"]),
        _check("chunk-receipts", receipts, "every received chunk matches its declared content address", value.content_address),
        _check("progress-conservation", progress_ok, "received and missing indices conserve the transfer range", progress.content_address),
        _check("nested-archive", nested_ok, "reassembly preserves the verified nested archive address" if progress.complete else "nested archive verification is deferred until all chunks arrive", value.archive_address),
        _check("assembly-complete", progress.complete, "all chunks are present and finalization is available", progress.content_address),
    )
    body = {"transfer_address": value.content_address, "archive_address": value.archive_address, "state": "complete" if progress.complete else "incomplete", "complete": progress.complete, "check_count": len(checks), "passed_count": sum(check.passed for check in checks), "failed_count": sum(not check.passed for check in checks), "checks": checks}
    provisional = TransferAudit(**body, content_address="pending:audit")
    return TransferAudit(**body, content_address=address_audit(provisional))


def audit_transfer(value: transfer_model.ArchiveTransfer | transfer_model.TransferAssembler) -> TransferAudit:
    if isinstance(value, transfer_model.TransferAssembler):
        assembler = value
    elif isinstance(value, transfer_model.ArchiveTransfer):
        assembler = transfer_model.TransferAssembler(value)
        if value._payload:
            assembler.add_chunks(value.payload_bytes())
    else:
        raise ValidationError("transfer audit requires a typed transfer or assembler")
    assembler.value._validate()
    return _build_audit(assembler)


def audit_transfer_directory(source: str) -> TransferAudit:
    return audit_transfer(transfer_model.load_transfer(source))


def audit_partial_transfer_directory(source: str) -> TransferAudit:
    return audit_transfer(transfer_model.load_partial_transfer(source))


def audit_from_mapping(value: Mapping[str, Any]) -> TransferAudit:
    value = _mapping(value, "transfer audit")
    _strict(value, {"transfer_address", "archive_address", "state", "complete", "check_count", "passed_count", "failed_count", "checks", "content_address"}, "transfer audit")
    checks = tuple(TransferAuditCheck.from_mapping(item) for item in value["checks"])
    return TransferAudit(value["transfer_address"], value["archive_address"], value["state"], value["complete"], value["check_count"], value["passed_count"], value["failed_count"], checks, value["content_address"])


def verify_audit(value: TransferAudit) -> TransferAudit:
    if not isinstance(value, TransferAudit):
        raise ValidationError("audit verification requires a typed audit")
    value._validate()
    return value


def audit_json(value: TransferAudit) -> str:
    verify_audit(value)
    return canonical_json(value.to_dict())


def render_audit_markdown(value: TransferAudit) -> str:
    verify_audit(value)
    lines = ["# Assurance history observatory archive transfer audit", "", f"- State: `{value.state}`", f"- Transfer: `{value.transfer_address}`", f"- Archive: `{value.archive_address}`", f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed", f"- Content address: `{value.content_address}`", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    fields = {"check_id": {"type": "string", "minLength": 1, "maxLength": 128}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^glio-noncode-assurance-history-observatory-archive-transfer-audit-check:"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def audit_schema() -> dict[str, Any]:
    fields = {"transfer_address": {"type": "string"}, "archive_address": {"type": "string"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "check_count": {"type": "integer", "minimum": len(CHECK_IDS), "maximum": len(CHECK_IDS)}, "passed_count": {"type": "integer", "minimum": 0, "maximum": len(CHECK_IDS)}, "failed_count": {"type": "integer", "minimum": 0, "maximum": len(CHECK_IDS)}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS), "items": check_schema()}, "content_address": {"type": "string", "pattern": "^glio-noncode-assurance-history-observatory-archive-transfer-audit:"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "checks": CHECK_IDS, "states": STATES, "features": ("independent transfer graph replay", "partial-transfer progress audit", "nested archive reassembly audit", "addressed check receipts", "path-free JSON and Markdown projection"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_CHECK_PREFIX",
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "STATES",
    "VERSION",
    "TransferAudit",
    "TransferAuditCheck",
    "address_audit",
    "audit_from_mapping",
    "audit_json",
    "audit_partial_transfer_directory",
    "audit_schema",
    "audit_transfer",
    "audit_transfer_directory",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
