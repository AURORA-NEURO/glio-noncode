"""Independent audits for archive-transfer recovery receipts."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery as recovery_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = recovery_model.VERSION + "-audit-v1"
BOUNDARY = recovery_model.BOUNDARY + "_audit"
AUDIT_PREFIX = recovery_model.RECOVERY_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
CHECK_IDS = (
    "recovery-address",
    "public-boundary",
    "index-conservation",
    "action-conservation",
    "receipt-conservation",
    "byte-conservation",
    "transfer-link",
    "archive-link",
    "state-semantics",
    "mapping-round-trip",
    "resumed-shape",
    "path-free",
)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded string")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field)
    if value.endswith(":pending"):
        return value
    if not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64:
        raise ValidationError(f"{field} has an invalid address")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} has undeclared or missing fields")


def _public(value: Any) -> bool:
    forbidden = ("agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user", "path", "directory", "filename")
    if isinstance(value, Mapping):
        return all(not any(word in str(key).lower() for word in forbidden) and _public(item) for key, item in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(item) for item in value)
    return True


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAuditFinding:
    """One independently recomputed recovery property."""

    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence: str, content_address: str) -> None:
        if not isinstance(ordinal, int) or ordinal < 1 or ordinal > len(CHECK_IDS) or check_id not in CHECK_IDS or not isinstance(passed, bool):
            raise ValidationError("recovery audit finding identity is invalid")
        self.ordinal = ordinal
        self.check_id = _text(check_id, "recovery audit check", 128)
        self.passed = passed
        self.detail = _text(detail, "recovery audit detail")
        self.evidence = _text(evidence, "recovery audit evidence")
        if ":" not in self.evidence or len(self.evidence.rsplit(":", 1)[-1]) != 64:
            raise ValidationError("recovery audit evidence must be an addressed value")
        self.content_address = _address(content_address, "recovery finding address", FINDING_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAuditFinding":
        value = _mapping(value, "recovery audit finding")
        if set(value) != set(cls.FIELDS):
            raise ValidationError("recovery audit finding fields are not exact")
        return cls(*(value[field] for field in cls.FIELDS))


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit:
    """A fixed twelve-check audit over a recovery receipt."""

    FIELDS = ("recovery_address", "transfer_address", "archive_address", "resumed", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")

    def __init__(self, recovery_address: str, transfer_address: str, archive_address: str, resumed: bool, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAuditFinding], content_address: str) -> None:
        self.recovery_address = _address(recovery_address, "recovery audit recovery address", recovery_model.RECOVERY_PREFIX)
        self.transfer_address = _address(transfer_address, "recovery audit transfer address", recovery_model.transfer_model.TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "recovery audit archive address", recovery_model.archive_model.ARCHIVE_PREFIX)
        if not isinstance(resumed, bool) or not isinstance(accepted, bool):
            raise ValidationError("recovery audit states must be boolean")
        self.resumed = resumed
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("recovery audit counters are not conserved")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("recovery audit check order is not exact")
        self.content_address = _address(content_address, "recovery audit address", AUDIT_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"recovery_address": self.recovery_address, "transfer_address": self.transfer_address, "archive_address": self.archive_address, "resumed": self.resumed, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("recovery_address", "transfer_address", "archive_address", "resumed", "check_count", "passed_count", "failed_count", "accepted", "content_address")}


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAuditFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, detail: str, evidence: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAuditFinding(ordinal, check_id, passed, detail, evidence, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAuditFinding(ordinal, check_id, passed, detail, evidence, address_finding(provisional))


def audit_recovery(value: recovery_model.RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit:
    recovery_model.verify_recovery(value)
    indices_ok = tuple(sorted(value.received_indices)) == value.received_indices and tuple(sorted(value.missing_indices)) == value.missing_indices and not set(value.received_indices) & set(value.missing_indices) and set(value.received_indices) | set(value.missing_indices) == set(range(value.chunk_count))
    actions_ok = tuple(item.index for item in value.actions) == value.missing_indices and value.action_count == len(value.actions)
    receipts_ok = all(item.content_address.startswith(recovery_model.transfer_model.CHUNK_PREFIX + ":") for item in value.actions)
    bytes_ok = value.received_bytes <= value.chunk_count * recovery_model.transfer_model.MAX_CHUNK_SIZE
    transfer_ok = value.transfer_address.startswith(recovery_model.transfer_model.TRANSFER_PREFIX + ":")
    archive_ok = value.archive_address.startswith(recovery_model.archive_model.ARCHIVE_PREFIX + ":")
    resumed_ok = (not value.resumed) or (value.complete and bool(value.resumed_transfer_address) and value.persisted)
    checks = (
        _finding(1, "recovery-address", recovery_model.address_recovery(value) == value.content_address, "recovery address reproduces", value.transfer_address),
        _finding(2, "public-boundary", _public(value.to_dict()), "recovery output contains public values", value.content_address),
        _finding(3, "index-conservation", indices_ok, "received and missing indices partition the transfer", value.transfer_address),
        _finding(4, "action-conservation", actions_ok, "every missing index has one ordered recovery action", value.transfer_address),
        _finding(5, "receipt-conservation", receipts_ok, "recovery actions retain chunk receipts", value.archive_address),
        _finding(6, "byte-conservation", bytes_ok, "received byte total remains bounded", value.transfer_address),
        _finding(7, "transfer-link", transfer_ok, "recovery links to an addressed transfer", value.transfer_address),
        _finding(8, "archive-link", archive_ok, "recovery links to an addressed archive", value.archive_address),
        _finding(9, "state-semantics", value.complete == (not value.missing_indices), "completion follows missing indices", value.content_address),
        _finding(10, "mapping-round-trip", recovery_model.recovery_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "recovery mapping replays", value.content_address),
        _finding(11, "resumed-shape", resumed_ok, "resumed receipts carry a persisted complete transfer", value.content_address),
        _finding(12, "path-free", _public(value.to_dict()), "recovery receipt contains no local paths", value.content_address),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit(value.content_address, value.transfer_address, value.archive_address, value.resumed, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), checks, AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit(provisional.recovery_address, provisional.transfer_address, provisional.archive_address, provisional.resumed, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, provisional.checks, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit:
    value = _mapping(value, "recovery audit")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit.FIELDS), "recovery audit")
    checks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAuditFinding.from_mapping(item) for item in _sequence(value["checks"], "recovery audit checks", len(CHECK_IDS)))
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit(value["recovery_address"], value["transfer_address"], value["archive_address"], value["resumed"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], checks, value["content_address"]))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit) or address_audit(value) != value.content_address:
        raise ValidationError("recovery audit address does not replay")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "check_id", "passed", "detail", "evidence", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Transfer Recovery Audit", "", f"- Accepted: `{value.accepted}`", f"- Resumed: `{value.resumed}`", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"title": "Certificate Observatory Transfer Recovery Audit Finding", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"title": "Certificate Observatory Transfer Recovery Audit", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit.FIELDS), "properties": {"recovery_address": {"type": "string"}, "transfer_address": {"type": "string"}, "archive_address": {"type": "string"}, "resumed": {"type": "boolean"}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "operations": ("audit", "serialize", "verify"), "public_fields": RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAudit.FIELDS}
