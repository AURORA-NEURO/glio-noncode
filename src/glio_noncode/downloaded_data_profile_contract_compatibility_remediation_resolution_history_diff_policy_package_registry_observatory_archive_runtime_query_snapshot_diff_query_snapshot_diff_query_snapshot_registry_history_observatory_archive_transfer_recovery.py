"""Path-free recovery plans for history-observatory archive transfers."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer as transfer_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = transfer_model.VERSION + "-recovery-v1"
BOUNDARY = transfer_model.BOUNDARY + "_recovery"
RECOVERY_PREFIX = transfer_model.TRANSFER_PREFIX + "-recovery"
ACTION_PREFIX = RECOVERY_PREFIX + "-action"
DEFAULT_RECOVERY_ID = "comparison-query-snapshot-registry-history-observatory-archive-transfer-recovery"
MAX_ACTIONS = transfer_model.MAX_CHUNKS
ACTION_FIELDS = ("index", "offset", "size", "content_address", "action_address")
RECOVERY_FIELDS = (
    "recovery_id",
    "version",
    "boundary",
    "transfer_id",
    "transfer_address",
    "archive_address",
    "archive_size",
    "chunk_count",
    "received_indices",
    "missing_indices",
    "received_bytes",
    "remaining_bytes",
    "actions",
    "action_count",
    "state",
    "decision",
    "safe_to_resume",
    "checkpointed",
    "next_index",
    "content_address",
)
STATES = ("partial", "complete")
DECISIONS = ("resume", "assemble")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class RecoveryAction:
    """One addressed request for a missing transfer chunk."""

    FIELDS = ACTION_FIELDS

    def __init__(self, index: int, offset: int, size: int, content_address: str, action_address: str) -> None:
        self.index = _count(index, "recovery action index", transfer_model.MAX_CHUNKS - 1)
        self.offset = _count(offset, "recovery action offset", transfer_model.MAX_TRANSFER_BYTES)
        self.size = _count(size, "recovery action size", transfer_model.MAX_CHUNK_SIZE, positive=True)
        self.content_address = _address(content_address, "recovery chunk address", transfer_model.CHUNK_PREFIX)
        self.action_address = _address(action_address, "recovery action address", ACTION_PREFIX, allow_pending=True)
        if self.offset + self.size > transfer_model.MAX_TRANSFER_BYTES:
            raise ValidationError("recovery action range exceeds the transfer bound")
        if not self.action_address.startswith("pending:") and address_action(self) != self.action_address:
            raise ValidationError("recovery action address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryAction":
        value = _mapping(value, "recovery action")
        _strict(value, set(cls.FIELDS), "recovery action")
        return cls(*(value[field] for field in cls.FIELDS))


class TransferRecovery:
    """A deterministic, value-free receiver recovery snapshot."""

    FIELDS = RECOVERY_FIELDS

    def __init__(self, recovery_id: str, version: str, boundary: str, transfer_id: str, transfer_address: str, archive_address: str, archive_size: int, chunk_count: int, received_indices: Sequence[int], missing_indices: Sequence[int], received_bytes: int, remaining_bytes: int, actions: Sequence[RecoveryAction], action_count: int, state: str, decision: str, safe_to_resume: bool, checkpointed: bool, next_index: int, content_address: str) -> None:
        self.recovery_id = _label(recovery_id, "recovery ID")
        self.version = _text(version, "recovery version", 2048)
        self.boundary = _text(boundary, "recovery boundary", 1024)
        self.transfer_id = _label(transfer_id, "recovery transfer ID")
        self.transfer_address = _address(transfer_address, "recovery transfer address", transfer_model.TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "recovery archive address", transfer_model.archive_model.ARCHIVE_PREFIX)
        self.archive_size = _count(archive_size, "recovery archive size", transfer_model.MAX_TRANSFER_BYTES, positive=True)
        self.chunk_count = _count(chunk_count, "recovery chunk count", transfer_model.MAX_CHUNKS, positive=True)
        self.received_indices = tuple(_count(item, "recovery received index", self.chunk_count - 1) for item in _sequence(received_indices, "recovery received indices", MAX_ACTIONS))
        self.missing_indices = tuple(_count(item, "recovery missing index", self.chunk_count - 1) for item in _sequence(missing_indices, "recovery missing indices", MAX_ACTIONS))
        self.received_bytes = _count(received_bytes, "recovery received bytes", self.archive_size)
        self.remaining_bytes = _count(remaining_bytes, "recovery remaining bytes", self.archive_size)
        self.actions = tuple(item if isinstance(item, RecoveryAction) else RecoveryAction.from_mapping(item) for item in _sequence(actions, "recovery actions", MAX_ACTIONS))
        self.action_count = _count(action_count, "recovery action count", MAX_ACTIONS)
        if state not in STATES or decision not in DECISIONS:
            raise ValidationError("recovery state or decision is unsupported")
        self.state = state
        self.decision = decision
        self.safe_to_resume = _bool(safe_to_resume, "recovery resume safety")
        self.checkpointed = _bool(checkpointed, "recovery checkpoint state")
        self.next_index = _count(next_index + 1, "recovery next index", self.chunk_count) - 1
        self.content_address = _address(content_address, "recovery content address", RECOVERY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        received = tuple(self.received_indices)
        missing = tuple(self.missing_indices)
        universe = set(range(self.chunk_count))
        if received != tuple(sorted(received)) or missing != tuple(sorted(missing)) or set(received) & set(missing) or set(received) | set(missing) != universe:
            raise ValidationError("recovery index sets are not conserved")
        if self.action_count != len(self.actions) or self.action_count != len(missing) or tuple(item.index for item in self.actions) != missing:
            raise ValidationError("recovery actions do not cover missing chunks")
        if self.received_bytes + self.remaining_bytes != self.archive_size:
            raise ValidationError("recovery byte counts do not conserve archive size")
        if self.state != ("complete" if not missing else "partial") or self.decision != ("assemble" if not missing else "resume"):
            raise ValidationError("recovery state does not follow missing chunks")
        if self.next_index != (missing[0] if missing else -1) or not self.safe_to_resume:
            raise ValidationError("recovery next action or safety state is invalid")
        if not transfer_model._public(self.to_dict()):
            raise ValidationError("recovery crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_recovery(self) != self.content_address:
            raise ValidationError("recovery content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"recovery_id": self.recovery_id, "version": self.version, "boundary": self.boundary, "transfer_id": self.transfer_id, "transfer_address": self.transfer_address, "archive_address": self.archive_address, "archive_size": self.archive_size, "chunk_count": self.chunk_count, "received_indices": self.received_indices, "missing_indices": self.missing_indices, "received_bytes": self.received_bytes, "remaining_bytes": self.remaining_bytes, "actions": [item.to_dict() for item in self.actions], "action_count": self.action_count, "state": self.state, "decision": self.decision, "safe_to_resume": self.safe_to_resume, "checkpointed": self.checkpointed, "next_index": self.next_index, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "actions"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TransferRecovery":
        value = _mapping(value, "transfer recovery")
        _strict(value, set(cls.FIELDS), "transfer recovery")
        return cls(value["recovery_id"], value["version"], value["boundary"], value["transfer_id"], value["transfer_address"], value["archive_address"], value["archive_size"], value["chunk_count"], value["received_indices"], value["missing_indices"], value["received_bytes"], value["remaining_bytes"], tuple(RecoveryAction.from_mapping(item) for item in _sequence(value["actions"], "recovery actions", MAX_ACTIONS)), value["action_count"], value["state"], value["decision"], value["safe_to_resume"], value["checkpointed"], value["next_index"], value["content_address"])


def address_action(value: RecoveryAction) -> str:
    if not isinstance(value, RecoveryAction):
        raise ValidationError("recovery action address requires a typed action")
    return content_hash(value.to_dict() | {"action_address": None}, prefix=ACTION_PREFIX)


def address_recovery(value: TransferRecovery) -> str:
    if not isinstance(value, TransferRecovery):
        raise ValidationError("recovery address requires a typed recovery")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RECOVERY_PREFIX)


def _actions(transfer: transfer_model.ArchiveTransfer, missing: Sequence[int]) -> tuple[RecoveryAction, ...]:
    values = []
    for index in missing:
        chunk = transfer.chunks[index]
        pending = RecoveryAction(chunk.index, chunk.offset, chunk.size, chunk.content_address, "pending:recovery-action")
        values.append(RecoveryAction(pending.index, pending.offset, pending.size, pending.content_address, address_action(pending)))
    return tuple(values)


def build_recovery(value: transfer_model.ArchiveTransfer | transfer_model.TransferAssembler, *, recovery_id: str = DEFAULT_RECOVERY_ID, checkpointed: bool = False) -> TransferRecovery:
    if isinstance(value, transfer_model.TransferAssembler):
        transfer = value.value
        parts = dict(value._parts)
    elif isinstance(value, transfer_model.ArchiveTransfer):
        transfer = value
        parts = dict(value._payload)
    else:
        raise ValidationError("recovery builder requires a typed transfer or assembler")
    transfer_model.verify_transfer(transfer)
    received = tuple(sorted(parts))
    missing = tuple(index for index in range(transfer.chunk_count) if index not in parts)
    received_bytes = sum(transfer.chunks[index].size for index in received)
    actions = _actions(transfer, missing)
    body = {"recovery_id": recovery_id, "version": VERSION, "boundary": BOUNDARY, "transfer_id": transfer.transfer_id, "transfer_address": transfer.content_address, "archive_address": transfer.archive_address, "archive_size": transfer.archive_size, "chunk_count": transfer.chunk_count, "received_indices": received, "missing_indices": missing, "received_bytes": received_bytes, "remaining_bytes": transfer.archive_size - received_bytes, "actions": actions, "action_count": len(actions), "state": "complete" if not missing else "partial", "decision": "assemble" if not missing else "resume", "safe_to_resume": True, "checkpointed": checkpointed, "next_index": missing[0] if missing else -1}
    provisional = TransferRecovery(**body, content_address="pending:recovery")
    return TransferRecovery(**body, content_address=address_recovery(provisional))


def build_recovery_from_directory(source: str | Path, *, recovery_id: str = DEFAULT_RECOVERY_ID) -> TransferRecovery:
    return build_recovery(transfer_model.load_partial_transfer(source), recovery_id=recovery_id, checkpointed=True)


def recovery_from_mapping(value: Mapping[str, Any]) -> TransferRecovery:
    return TransferRecovery.from_mapping(value)


def recovery_json(value: TransferRecovery) -> str:
    return canonical_json(recovery_from_mapping(value.to_dict()).to_dict())


def recovery_csv(value: TransferRecovery) -> str:
    value = recovery_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ACTION_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.actions:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_recovery_markdown(value: TransferRecovery) -> str:
    value = recovery_from_mapping(value.to_dict())
    lines = ["# History observatory archive transfer recovery", "", f"- Recovery: `{value.recovery_id}`", f"- Transfer: `{value.transfer_address}`", f"- State: `{value.state}`", f"- Decision: `{value.decision}`", f"- Received: `{len(value.received_indices)}/{value.chunk_count}` chunks", f"- Remaining bytes: `{value.remaining_bytes}`", f"- Next index: `{value.next_index}`", f"- Checkpointed: `{str(value.checkpointed).lower()}`", f"- Address: `{value.content_address}`", "", "| index | offset | size | chunk address | action address |", "| ---: | ---: | ---: | --- | --- |"]
    lines.extend(f"| {item.index} | {item.offset} | {item.size} | {item.content_address} | {item.action_address} |" for item in value.actions)
    return "\n".join(lines) + "\n"


def action_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "History observatory archive transfer recovery action", "type": "object", "additionalProperties": False, "required": list(ACTION_FIELDS), "properties": {"index": {"type": "integer", "minimum": 0, "maximum": transfer_model.MAX_CHUNKS - 1}, "offset": {"type": "integer", "minimum": 0}, "size": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + transfer_model.CHUNK_PREFIX + ":"}, "action_address": {"type": "string", "pattern": "^" + ACTION_PREFIX + ":"}}}


def recovery_schema() -> dict[str, Any]:
    properties = {"recovery_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "transfer_id": {"type": "string"}, "transfer_address": {"type": "string", "pattern": "^" + transfer_model.TRANSFER_PREFIX + ":"}, "archive_address": {"type": "string", "pattern": "^" + transfer_model.archive_model.ARCHIVE_PREFIX + ":"}, "archive_size": {"type": "integer", "minimum": 1}, "chunk_count": {"type": "integer", "minimum": 1}, "received_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "missing_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "received_bytes": {"type": "integer", "minimum": 0}, "remaining_bytes": {"type": "integer", "minimum": 0}, "actions": {"type": "array", "items": action_schema()}, "action_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "decision": {"type": "string", "enum": list(DECISIONS)}, "safe_to_resume": {"type": "boolean"}, "checkpointed": {"type": "boolean"}, "next_index": {"type": "integer", "minimum": -1}, "content_address": {"type": "string", "pattern": "^" + RECOVERY_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "History observatory archive transfer recovery", "type": "object", "additionalProperties": False, "required": list(RECOVERY_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "recovery_prefix": RECOVERY_PREFIX, "action_prefix": ACTION_PREFIX, "states": list(STATES), "decisions": list(DECISIONS), "max_actions": MAX_ACTIONS, "features": ["addressed missing-chunk actions", "resume-or-assemble decision", "safe continuation flag", "checkpoint state", "next-index projection", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["ACTION_FIELDS", "ACTION_PREFIX", "BOUNDARY", "DEFAULT_RECOVERY_ID", "DECISIONS", "MAX_ACTIONS", "RECOVERY_FIELDS", "RECOVERY_PREFIX", "STATES", "RecoveryAction", "TransferRecovery", "VERSION", "action_schema", "address_action", "address_recovery", "build_recovery", "build_recovery_from_directory", "capabilities", "recovery_csv", "recovery_from_mapping", "recovery_json", "recovery_schema", "render_recovery_markdown"]
