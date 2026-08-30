"""Independent audit of complete and partial archive transfers.

Transfer manifests can be inspected before all chunks arrive.  The audit
keeps that state explicit: range checks and received receipts may pass while
assembly and nested archive replay remain failed.  This makes resumable
transport operationally useful without treating an incomplete handoff as a
verified archive.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_transfer as transfer_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = transfer_model.VERSION + "-audit-v1"
BOUNDARY = transfer_model.BOUNDARY + "_audit"
AUDIT_PREFIX = transfer_model.TRANSFER_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = ("transfer-address", "range-conservation", "public-boundary", "manifest-address", "chunk-receipts", "received-indexes", "progress-conservation", "archive-size", "assembly-complete", "nested-archive", "mapping-round-trip", "address-replay", "path-free", "state-semantics")


def _text(value: Any, field: str, maximum: int = 2048) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field)
    if ":" not in value or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
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
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return transfer_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1 or ordinal > len(CHECK_IDS) or check_id not in CHECK_IDS:
            raise ValidationError("transfer finding identity is invalid")
        self.ordinal = ordinal
        self.check_id = check_id
        self.passed = _bool(passed, "transfer finding pass state")
        self.detail = _text(detail, "transfer finding detail")
        self.evidence_address = _address(evidence_address, "transfer finding evidence")
        self.content_address = _address(content_address, "transfer finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("transfer finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAuditFinding":
        value = _mapping(value, "transfer audit finding")
        _strict(value, set(cls.FIELDS), "transfer audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit:
    FIELDS = ("transfer_address", "archive_address", "state", "complete", "received_count", "missing_count", "received_bytes", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, transfer_address: str, archive_address: str, state: str, complete: bool, received_count: int, missing_count: int, received_bytes: int, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.transfer_address = _address(transfer_address, "audit transfer address", transfer_model.TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "audit archive address", archive_model.ARCHIVE_PREFIX)
        if state not in ("complete", "incomplete") or not isinstance(complete, bool) or state != ("complete" if complete else "incomplete"):
            raise ValidationError("transfer audit state does not match completion")
        self.state = state
        self.complete = complete
        self.received_count = _count(received_count, "audit received count", transfer_model.MAX_CHUNKS)
        self.missing_count = _count(missing_count, "audit missing count", transfer_model.MAX_CHUNKS)
        self.received_bytes = _count(received_bytes, "audit received bytes", transfer_model.MAX_TRANSFER_BYTES)
        self.checks = tuple(checks)
        self.check_count = _count(check_count, "audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "transfer audit acceptance")
        self.content_address = _address(content_address, "transfer audit address", AUDIT_PREFIX)
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("transfer audit checks or counters are not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("transfer audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("transfer audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_address": self.transfer_address, "archive_address": self.archive_address, "state": self.state, "complete": self.complete, "received_count": self.received_count, "missing_count": self.missing_count, "received_bytes": self.received_bytes, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("transfer_address", "archive_address", "state", "complete", "received_count", "missing_count", "received_bytes", "check_count", "passed_count", "failed_count", "accepted", "content_address")}


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAuditFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, detail: str, evidence: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAuditFinding(ordinal, check_id, passed, detail, evidence, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAuditFinding(ordinal, check_id, passed, detail, evidence, address_finding(provisional))


def audit_transfer(value: transfer_model.RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer | transfer_model.TransferAssembler) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit:
    assembler = value if isinstance(value, transfer_model.TransferAssembler) else transfer_model.TransferAssembler(value, value._payload)
    transfer = assembler.value
    progress = assembler.progress()
    address_ok = transfer_model.address_transfer(transfer) == transfer.content_address
    range_ok = transfer.chunk_count == len(transfer.chunks) and transfer.chunks[-1].offset + transfer.chunks[-1].size == transfer.archive_size
    receipt_ok = all(index in assembler._parts and transfer_model.address_chunk(assembler._parts[index]) == transfer.chunks[index].content_address for index in assembler.received_indices())
    indexes_ok = tuple(sorted(assembler.received_indices())) == progress.received_indices and not set(progress.received_indices) & set(progress.missing_indices)
    progress_ok = progress.received_bytes == sum(len(assembler._parts[index]) for index in assembler.received_indices())
    nested_ok = False
    if progress.complete:
        try:
            nested_ok = archive_model.load_archive_bytes(assembler.finalize()).content_address == transfer.archive_address
        except ValidationError:
            nested_ok = False
    mapping_ok = transfer_model.transfer_from_mapping(transfer.to_dict()).to_dict() == transfer.to_dict()
    checks = (
        _finding(1, "transfer-address", address_ok, "transfer address reproduces", transfer.content_address),
        _finding(2, "range-conservation", range_ok, "chunk ranges cover the declared archive bytes", transfer.archive_address),
        _finding(3, "public-boundary", _public(transfer.to_dict()), "transfer manifest contains public values", transfer.content_address),
        _finding(4, "manifest-address", transfer_model.manifest_document(transfer)["manifest_address"] == content_hash(transfer_model.manifest_document(transfer) | {"manifest_address": None}, prefix=transfer_model.MANIFEST_PREFIX), "manifest address reproduces", transfer.content_address),
        _finding(5, "chunk-receipts", receipt_ok, "received chunks match declared receipts", transfer.content_address),
        _finding(6, "received-indexes", indexes_ok, "received and missing indices are ordered and disjoint", progress.content_address),
        _finding(7, "progress-conservation", progress_ok, "received byte count equals retained chunk bytes", progress.content_address),
        _finding(8, "archive-size", progress.received_bytes <= transfer.archive_size, "received bytes do not exceed archive size", transfer.archive_address),
        _finding(9, "assembly-complete", progress.complete, "all chunks are present" if progress.complete else "assembly remains incomplete", progress.content_address),
        _finding(10, "nested-archive", nested_ok, "assembled bytes reload as the addressed archive", transfer.archive_address),
        _finding(11, "mapping-round-trip", mapping_ok, "transfer manifest mapping replays", transfer.content_address),
        _finding(12, "address-replay", transfer_model.address_progress(progress) == progress.content_address, "progress address reproduces", progress.content_address),
        _finding(13, "path-free", _public(progress.to_dict()), "progress output contains no local paths", progress.content_address),
        _finding(14, "state-semantics", progress.complete == (not progress.missing_indices), "completion state follows the missing-index set", progress.content_address),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit(transfer.content_address, transfer.archive_address, "complete" if progress.complete else "incomplete", progress.complete, len(progress.received_indices), len(progress.missing_indices), progress.received_bytes, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit(provisional.transfer_address, provisional.archive_address, provisional.state, provisional.complete, provisional.received_count, provisional.missing_count, provisional.received_bytes, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_transfer_directory(source: str, *, partial: bool = False) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit:
    value = transfer_model.load_partial_transfer(source) if partial else transfer_model.load_transfer(source)
    return audit_transfer(value)


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit:
    value = _mapping(value, "transfer audit")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit.FIELDS), "transfer audit")
    checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAuditFinding.from_mapping(item) for item in _sequence(value["checks"], "transfer audit checks", len(CHECK_IDS)))
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit(value["transfer_address"], value["archive_address"], value["state"], value["complete"], value["received_count"], value["missing_count"], value["received_bytes"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"]))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("transfer audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "check_id", "passed", "detail", "evidence_address", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow({key: item.to_dict()[key] for key in writer.fieldnames})
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Archive Transfer Audit", "", f"- State: `{value.state}`", f"- Complete: `{value.complete}`", f"- Received chunks: `{value.received_count}`", f"- Missing chunks: `{value.missing_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit.FIELDS), "properties": {"transfer_address": {"type": "string"}, "archive_address": {"type": "string"}, "state": {"type": "string", "enum": ["complete", "incomplete"]}, "complete": {"type": "boolean"}, "received_count": {"type": "integer"}, "missing_count": {"type": "integer"}, "received_bytes": {"type": "integer"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("complete and partial transfer audits", "range and receipt conservation", "addressable findings", "nested archive replay", "explicit incomplete state", "path-free JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "audit_transfer", "audit_transfer_directory", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
