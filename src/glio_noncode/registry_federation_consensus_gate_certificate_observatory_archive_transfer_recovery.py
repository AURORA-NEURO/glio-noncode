"""Resumable recovery receipts for certificate-observatory archive transfers.

The transfer module deliberately keeps a complete manifest separate from the
receiver's progress. This module supplies the next operational boundary: a
path-free receipt describing what a receiver has, what it still needs, and
whether the missing ranges were filled from a separately addressed archive.
Recovery never trusts a directory name or an unverified byte stream. It loads
the partial manifest, loads the source ZIP through the archive verifier,
reconstructs the expected transfer from the source bytes, compares every
public transfer field, and validates each missing chunk before persisting the
completed directory.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_transfer as transfer_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = transfer_model.VERSION + "-recovery-v1"
BOUNDARY = transfer_model.BOUNDARY + "_recovery"
RECOVERY_PREFIX = transfer_model.TRANSFER_PREFIX + "-recovery"
ACTION_PREFIX = RECOVERY_PREFIX + "-action"
DEFAULT_RECOVERY_ID = "certificate-observatory-archive-transfer-recovery"
MAX_ACTIONS = transfer_model.MAX_CHUNKS
MAX_TEXT = 1024
RECOVERY_FIELDS = (
    "recovery_id",
    "version",
    "boundary",
    "transfer_id",
    "transfer_address",
    "archive_address",
    "chunk_count",
    "received_indices",
    "missing_indices",
    "received_bytes",
    "actions",
    "action_count",
    "complete",
    "resumed",
    "resumed_transfer_address",
    "persisted",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValidationError(f"{field} must be a bounded string")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if any(character in value for character in "\\/\r\n\t"):
        raise ValidationError(f"{field} contains unsafe characters")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, pending: bool = True) -> str:
    value = _text(value, field, 4096)
    if pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unexpected address prefix")
    if ":" not in value or len(value.rsplit(":", 1)[-1]) != 64:
        raise ValidationError(f"{field} is not a content address")
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


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction:
    """One missing addressed chunk that a recovery operation may request."""

    FIELDS = ("index", "offset", "size", "content_address", "action_address")

    def __init__(self, index: int, offset: int, size: int, content_address: str, action_address: str = ACTION_PREFIX + ":pending") -> None:
        self.index = _count(index, "recovery action index", transfer_model.MAX_CHUNKS - 1)
        self.offset = _count(offset, "recovery action offset", transfer_model.MAX_TRANSFER_BYTES)
        self.size = _count(size, "recovery action size", transfer_model.MAX_CHUNK_SIZE, positive=True)
        self.content_address = _address(content_address, "recovery chunk address", transfer_model.CHUNK_PREFIX, pending=False)
        self.action_address = _address(action_address, "recovery action address", ACTION_PREFIX)
        if self.offset + self.size > transfer_model.MAX_TRANSFER_BYTES:
            raise ValidationError("recovery action range exceeds transfer bounds")
        if not self.action_address.endswith(":pending") and address_action(self) != self.action_address:
            raise ValidationError("recovery action address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction":
        value = _mapping(value, "recovery action")
        _strict(value, set(cls.FIELDS), "recovery action")
        return cls(value["index"], value["offset"], value["size"], value["content_address"], value["action_address"])


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery:
    """A deterministic, public recovery snapshot for a transfer receiver."""

    FIELDS = RECOVERY_FIELDS

    def __init__(self, recovery_id: str, version: str, boundary: str, transfer_id: str, transfer_address: str, archive_address: str, chunk_count: int, received_indices: Sequence[int], missing_indices: Sequence[int], received_bytes: int, actions: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction], action_count: int, complete: bool, resumed: bool, resumed_transfer_address: str, persisted: bool, content_address: str = RECOVERY_PREFIX + ":pending") -> None:
        self.recovery_id = _label(recovery_id, "recovery ID")
        self.version = _text(version, "recovery version")
        self.boundary = _text(boundary, "recovery boundary")
        self.transfer_id = _label(transfer_id, "recovery transfer ID")
        self.transfer_address = _address(transfer_address, "recovery transfer address", transfer_model.TRANSFER_PREFIX, pending=False)
        self.archive_address = _address(archive_address, "recovery archive address", archive_model.ARCHIVE_PREFIX, pending=False)
        self.chunk_count = _count(chunk_count, "recovery chunk count", transfer_model.MAX_CHUNKS, positive=True)
        self.received_indices = tuple(_count(item, "recovery received index", transfer_model.MAX_CHUNKS - 1) for item in _sequence(received_indices, "recovery received indices", MAX_ACTIONS))
        self.missing_indices = tuple(_count(item, "recovery missing index", transfer_model.MAX_CHUNKS - 1) for item in _sequence(missing_indices, "recovery missing indices", MAX_ACTIONS))
        self.received_bytes = _count(received_bytes, "recovery received bytes", transfer_model.MAX_TRANSFER_BYTES)
        self.actions = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction) else RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction.from_mapping(item) for item in _sequence(actions, "recovery actions", MAX_ACTIONS))
        self.action_count = _count(action_count, "recovery action count", MAX_ACTIONS)
        self.complete = _bool(complete, "recovery completion")
        self.resumed = _bool(resumed, "recovery resumed state")
        self.resumed_transfer_address = _address(resumed_transfer_address, "recovered transfer address", transfer_model.TRANSFER_PREFIX, pending=False) if resumed_transfer_address else ""
        self.persisted = _bool(persisted, "recovery persisted state")
        self.content_address = _address(content_address, "recovery content address", RECOVERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.action_count != len(self.actions) or self.action_count != len(self.missing_indices):
            raise ValidationError("recovery action count is not conserved")
        if tuple(sorted(self.received_indices)) != self.received_indices or tuple(sorted(self.missing_indices)) != self.missing_indices or set(self.received_indices) & set(self.missing_indices) or set(self.received_indices) | set(self.missing_indices) != set(range(self.chunk_count)):
            raise ValidationError("recovery index sets are not conserved")
        if tuple(item.index for item in self.actions) != self.missing_indices:
            raise ValidationError("recovery actions do not cover missing indices")
        if self.complete != (not self.missing_indices):
            raise ValidationError("recovery completion does not follow missing indices")
        if self.resumed and (not self.complete or not self.resumed_transfer_address or not self.persisted):
            raise ValidationError("resumed recovery must be complete, addressed, and persisted")
        if not self.resumed and self.resumed_transfer_address:
            raise ValidationError("pending recovery cannot carry a resumed transfer address")
        if not _public(self.to_dict()):
            raise ValidationError("recovery crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_recovery(self) != self.content_address:
            raise ValidationError("recovery content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"recovery_id": self.recovery_id, "version": self.version, "boundary": self.boundary, "transfer_id": self.transfer_id, "transfer_address": self.transfer_address, "archive_address": self.archive_address, "chunk_count": self.chunk_count, "received_indices": self.received_indices, "missing_indices": self.missing_indices, "received_bytes": self.received_bytes, "actions": tuple(item.to_dict() for item in self.actions), "action_count": self.action_count, "complete": self.complete, "resumed": self.resumed, "resumed_transfer_address": self.resumed_transfer_address, "persisted": self.persisted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("recovery_id", "transfer_id", "transfer_address", "archive_address", "chunk_count", "received_bytes", "action_count", "complete", "resumed", "resumed_transfer_address", "persisted", "content_address")}


def address_action(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction):
        raise ValidationError("recovery action address requires a typed action")
    return content_hash(value.to_dict() | {"action_address": None}, prefix=ACTION_PREFIX)


def address_recovery(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery):
        raise ValidationError("recovery address requires a typed recovery")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RECOVERY_PREFIX)


def _actions(transfer: transfer_model.RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer, missing: Sequence[int]) -> tuple[RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction, ...]:
    values = []
    for index in missing:
        chunk = transfer.chunks[index]
        pending = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction(chunk.index, chunk.offset, chunk.size, chunk.content_address)
        values.append(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction(pending.index, pending.offset, pending.size, pending.content_address, address_action(pending)))
    return tuple(values)


def build_recovery(value: transfer_model.RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer | transfer_model.TransferAssembler, *, recovery_id: str = DEFAULT_RECOVERY_ID) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery:
    assembler = value if isinstance(value, transfer_model.TransferAssembler) else transfer_model.TransferAssembler(value, value._payload)
    transfer = assembler.value
    progress = assembler.progress()
    actions = _actions(transfer, progress.missing_indices)
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery(recovery_id, VERSION, BOUNDARY, transfer.transfer_id, transfer.content_address, transfer.archive_address, transfer.chunk_count, progress.received_indices, progress.missing_indices, progress.received_bytes, actions, len(actions), progress.complete, False, "", False)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery(provisional.recovery_id, provisional.version, provisional.boundary, provisional.transfer_id, provisional.transfer_address, provisional.archive_address, provisional.chunk_count, provisional.received_indices, provisional.missing_indices, provisional.received_bytes, provisional.actions, provisional.action_count, provisional.complete, provisional.resumed, provisional.resumed_transfer_address, provisional.persisted, address_recovery(provisional))


def build_resumed_recovery(before: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery, transfer: transfer_model.RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer, *, persisted: bool = True) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery:
    transfer_model.verify_transfer(transfer)
    if before.archive_address != transfer.archive_address or before.transfer_id != transfer.transfer_id:
        raise ValidationError("resumed transfer does not match recovery receipt")
    indices = tuple(range(transfer.chunk_count))
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery(before.recovery_id, VERSION, BOUNDARY, transfer.transfer_id, before.transfer_address, transfer.archive_address, transfer.chunk_count, indices, (), transfer.archive_size, (), 0, True, True, transfer.content_address, persisted)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery(provisional.recovery_id, provisional.version, provisional.boundary, provisional.transfer_id, provisional.transfer_address, provisional.archive_address, provisional.chunk_count, provisional.received_indices, provisional.missing_indices, provisional.received_bytes, provisional.actions, provisional.action_count, provisional.complete, provisional.resumed, provisional.resumed_transfer_address, provisional.persisted, address_recovery(provisional))


def resume_transfer(partial_source: str | Path, archive_source: str | Path | bytes, *, destination: str | Path | None = None, recovery_id: str = DEFAULT_RECOVERY_ID, overwrite: bool = False) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery:
    assembler = transfer_model.load_partial_transfer(partial_source)
    before = build_recovery(assembler, recovery_id=recovery_id)
    archive = archive_model.load_archive(archive_source)
    if archive.content_address != before.archive_address:
        raise ValidationError("recovery source archive address does not match the partial transfer")
    expected = transfer_model.build_transfer(archive, transfer_id=before.transfer_id, chunk_size=assembler.value.chunk_size)
    if expected.to_dict() != assembler.value.to_dict():
        raise ValidationError("recovery source does not reproduce the transfer manifest")
    for index in before.missing_indices:
        assembler.add_chunk(index, transfer_model.chunk_bytes(expected, index))
    if not assembler.complete:
        raise ValidationError("recovery did not fill every missing chunk")
    assembler.finalize()
    if destination is not None:
        transfer_model.write_transfer(expected, destination, overwrite=overwrite)
    resumed = build_resumed_recovery(before, expected, persisted=destination is not None and Path(destination).is_dir())
    return resumed


def build_recovery_from_directory(source: str | Path, *, recovery_id: str = DEFAULT_RECOVERY_ID, partial: bool = True) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery:
    value = transfer_model.load_partial_transfer(source) if partial else transfer_model.load_transfer(source)
    return build_recovery(value, recovery_id=recovery_id)


def recovery_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery:
    value = _mapping(value, "transfer recovery")
    _strict(value, set(RECOVERY_FIELDS), "transfer recovery")
    actions = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction.from_mapping(item) for item in _sequence(value["actions"], "recovery actions", MAX_ACTIONS))
    return verify_recovery(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery(value["recovery_id"], value["version"], value["boundary"], value["transfer_id"], value["transfer_address"], value["archive_address"], value["chunk_count"], value["received_indices"], value["missing_indices"], value["received_bytes"], actions, value["action_count"], value["complete"], value["resumed"], value["resumed_transfer_address"], value["persisted"], value["content_address"]))


def verify_recovery(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery):
        raise ValidationError("transfer recovery verification requires a typed receipt")
    value._validate()
    return value


def recovery_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery) -> str:
    return canonical_json(verify_recovery(value).to_dict())


def recovery_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery) -> str:
    value = verify_recovery(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("index", "offset", "size", "content_address", "action_address"), lineterminator="\n")
    writer.writeheader()
    for item in value.actions:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_recovery_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecovery) -> str:
    value = verify_recovery(value)
    lines = ["# Certificate Observatory Transfer Recovery", "", f"- Recovery: `{value.recovery_id}`", f"- Transfer: `{value.transfer_address}`", f"- Archive: `{value.archive_address}`", f"- Received bytes: `{value.received_bytes}`", f"- Missing chunks: `{value.action_count}`", f"- Complete: `{value.complete}`", f"- Resumed: `{value.resumed}`", f"- Address: `{value.content_address}`", "", "| index | offset | bytes | chunk receipt | action receipt |", "| ---: | ---: | ---: | --- | --- |"]
    lines.extend(f"| `{item.index}` | `{item.offset}` | `{item.size}` | `{item.content_address}` | `{item.action_address}` |" for item in value.actions)
    return "\n".join(lines) + "\n"


def action_schema() -> dict[str, Any]:
    return {"title": "Certificate Observatory Transfer Recovery Action", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction.FIELDS), "properties": {"index": {"type": "integer", "minimum": 0}, "offset": {"type": "integer", "minimum": 0}, "size": {"type": "integer", "minimum": 1}, "content_address": {"type": "string"}, "action_address": {"type": "string"}}}


def recovery_schema() -> dict[str, Any]:
    return {"title": "Certificate Observatory Transfer Recovery", "type": "object", "additionalProperties": False, "required": list(RECOVERY_FIELDS), "properties": {"recovery_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "transfer_id": {"type": "string"}, "transfer_address": {"type": "string"}, "archive_address": {"type": "string"}, "chunk_count": {"type": "integer", "minimum": 1}, "received_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "missing_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "received_bytes": {"type": "integer", "minimum": 0}, "actions": {"type": "array", "items": action_schema()}, "action_count": {"type": "integer", "minimum": 0}, "complete": {"type": "boolean"}, "resumed": {"type": "boolean"}, "resumed_transfer_address": {"type": "string"}, "persisted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": ("summary", "actions", "missing", "evidence"), "operations": ("build", "inspect", "resume", "verify", "serialize"), "limits": {"max_actions": MAX_ACTIONS, "max_transfer_bytes": transfer_model.MAX_TRANSFER_BYTES}, "public_fields": RECOVERY_FIELDS}
