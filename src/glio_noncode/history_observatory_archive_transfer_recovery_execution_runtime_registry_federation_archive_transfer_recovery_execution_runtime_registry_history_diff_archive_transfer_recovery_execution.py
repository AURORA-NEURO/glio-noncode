"""Path-free execution receipts for archive-transfer recovery plans."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer as transfer_model
from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery as recovery_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = recovery_model.VERSION + "-execution-v1"
BOUNDARY = recovery_model.BOUNDARY + "_execution"
EXECUTION_PREFIX = recovery_model.RECOVERY_PREFIX + "-execution"
OUTCOME_PREFIX = EXECUTION_PREFIX + "-outcome"
DEFAULT_EXECUTION_ID = "runtime-registry-history-diff-archive-transfer-recovery-execution"
MAX_OUTCOMES = recovery_model.MAX_ACTIONS
OUTCOME_FIELDS = ("index", "action_address", "content_address", "offset", "size", "status", "reason", "outcome_address")
EXECUTION_FIELDS = (
    "execution_id",
    "version",
    "boundary",
    "recovery_id",
    "recovery_address",
    "transfer_address",
    "archive_address",
    "archive_size",
    "chunk_count",
    "base_received_indices",
    "planned_indices",
    "applied_indices",
    "pending_indices",
    "rejected_indices",
    "current_received_indices",
    "current_missing_indices",
    "planned_bytes",
    "applied_bytes",
    "pending_bytes",
    "rejected_bytes",
    "current_received_bytes",
    "current_remaining_bytes",
    "outcomes",
    "action_count",
    "applied_count",
    "pending_count",
    "rejected_count",
    "state",
    "decision",
    "safe_to_continue",
    "safe_to_assemble",
    "checkpointed",
    "next_index",
    "content_address",
)
STATUSES = ("pending", "applied", "rejected")
STATES = ("planned", "in_progress", "complete", "blocked")
DECISIONS = ("resume", "assemble", "block")
REASONS = {"pending": "awaiting-chunk", "applied": "verified-chunk", "rejected": "receiver-rejected"}


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False, optional: bool = False) -> str:
    value = _text(value, field, required=not optional)
    if optional and value == "":
        return value
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
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


def _indices(value: Any, field: str, maximum: int) -> tuple[int, ...]:
    values = tuple(_count(item, field, maximum) for item in _sequence(value, field, MAX_OUTCOMES))
    if values != tuple(sorted(values)) or len(set(values)) != len(values):
        raise ValidationError(f"{field} must be sorted and unique")
    return values


def _public(value: Any) -> bool:
    return transfer_model._public(value)


class HistoryDiffArchiveTransferRecoveryExecutionOutcome:
    """One deterministic status receipt for a planned recovery action."""

    FIELDS = OUTCOME_FIELDS

    def __init__(self, index: int, action_address: str, content_address: str, offset: int, size: int, status: str, reason: str, outcome_address: str) -> None:
        self.index = _count(index, "execution outcome index", transfer_model.MAX_CHUNKS - 1)
        self.action_address = _address(action_address, "execution action address", recovery_model.ACTION_PREFIX)
        self.content_address = _address(content_address, "execution chunk address", transfer_model.CHUNK_PREFIX)
        self.offset = _count(offset, "execution outcome offset", transfer_model.MAX_TRANSFER_BYTES)
        self.size = _count(size, "execution outcome size", transfer_model.MAX_CHUNK_SIZE, lower=1)
        if status not in STATUSES:
            raise ValidationError("execution outcome status is unsupported")
        self.status = status
        if reason != REASONS[status]:
            raise ValidationError("execution outcome reason does not match status")
        self.reason = reason
        self.outcome_address = _address(outcome_address, "execution outcome address", OUTCOME_PREFIX, allow_pending=True)
        if self.offset + self.size > transfer_model.MAX_TRANSFER_BYTES:
            raise ValidationError("execution outcome range exceeds the transfer bound")
        if not self.outcome_address.startswith("pending:") and address_outcome(self) != self.outcome_address:
            raise ValidationError("execution outcome address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecutionOutcome:
        value = _mapping(value, "execution outcome")
        _strict(value, set(cls.FIELDS), "execution outcome")
        return cls(*(value[field] for field in cls.FIELDS))


class HistoryDiffArchiveTransferRecoveryExecution:
    """A value-free, replayable receipt of recovery-action execution."""

    FIELDS = EXECUTION_FIELDS

    def __init__(self, execution_id: str, version: str, boundary: str, recovery_id: str, recovery_address: str, transfer_address: str, archive_address: str, archive_size: int, chunk_count: int, base_received_indices: Sequence[int], planned_indices: Sequence[int], applied_indices: Sequence[int], pending_indices: Sequence[int], rejected_indices: Sequence[int], current_received_indices: Sequence[int], current_missing_indices: Sequence[int], planned_bytes: int, applied_bytes: int, pending_bytes: int, rejected_bytes: int, current_received_bytes: int, current_remaining_bytes: int, outcomes: Sequence[HistoryDiffArchiveTransferRecoveryExecutionOutcome], action_count: int, applied_count: int, pending_count: int, rejected_count: int, state: str, decision: str, safe_to_continue: bool, safe_to_assemble: bool, checkpointed: bool, next_index: int, content_address: str) -> None:
        self.execution_id = _label(execution_id, "execution ID")
        self.version = _text(version, "execution version", 2048)
        self.boundary = _text(boundary, "execution boundary", 1024)
        self.recovery_id = _label(recovery_id, "execution recovery ID")
        self.recovery_address = _address(recovery_address, "execution recovery address", recovery_model.RECOVERY_PREFIX)
        self.transfer_address = _address(transfer_address, "execution transfer address", transfer_model.TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "execution archive address", transfer_model.archive_model.ARCHIVE_PREFIX)
        self.archive_size = _count(archive_size, "execution archive size", transfer_model.MAX_TRANSFER_BYTES, lower=1)
        self.chunk_count = _count(chunk_count, "execution chunk count", transfer_model.MAX_CHUNKS, lower=1)
        self.base_received_indices = _indices(base_received_indices, "execution base received indices", self.chunk_count - 1)
        self.planned_indices = _indices(planned_indices, "execution planned indices", self.chunk_count - 1)
        self.applied_indices = _indices(applied_indices, "execution applied indices", self.chunk_count - 1)
        self.pending_indices = _indices(pending_indices, "execution pending indices", self.chunk_count - 1)
        self.rejected_indices = _indices(rejected_indices, "execution rejected indices", self.chunk_count - 1)
        self.current_received_indices = _indices(current_received_indices, "execution current received indices", self.chunk_count - 1)
        self.current_missing_indices = _indices(current_missing_indices, "execution current missing indices", self.chunk_count - 1)
        self.planned_bytes = _count(planned_bytes, "execution planned bytes", self.archive_size)
        self.applied_bytes = _count(applied_bytes, "execution applied bytes", self.archive_size)
        self.pending_bytes = _count(pending_bytes, "execution pending bytes", self.archive_size)
        self.rejected_bytes = _count(rejected_bytes, "execution rejected bytes", self.archive_size)
        self.current_received_bytes = _count(current_received_bytes, "execution current received bytes", self.archive_size)
        self.current_remaining_bytes = _count(current_remaining_bytes, "execution current remaining bytes", self.archive_size)
        self.outcomes = tuple(item if isinstance(item, HistoryDiffArchiveTransferRecoveryExecutionOutcome) else HistoryDiffArchiveTransferRecoveryExecutionOutcome.from_mapping(item) for item in _sequence(outcomes, "execution outcomes", MAX_OUTCOMES))
        self.action_count = _count(action_count, "execution action count", MAX_OUTCOMES)
        self.applied_count = _count(applied_count, "execution applied count", MAX_OUTCOMES)
        self.pending_count = _count(pending_count, "execution pending count", MAX_OUTCOMES)
        self.rejected_count = _count(rejected_count, "execution rejected count", MAX_OUTCOMES)
        if state not in STATES or decision not in DECISIONS:
            raise ValidationError("execution state or decision is unsupported")
        self.state = state
        self.decision = decision
        self.safe_to_continue = _bool(safe_to_continue, "execution continuation safety")
        self.safe_to_assemble = _bool(safe_to_assemble, "execution assembly safety")
        self.checkpointed = _bool(checkpointed, "execution checkpoint state")
        self.next_index = _count(next_index + 1, "execution next index", self.chunk_count) - 1
        self.content_address = _address(content_address, "execution content address", EXECUTION_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        base = set(self.base_received_indices)
        planned = set(self.planned_indices)
        applied = set(self.applied_indices)
        pending = set(self.pending_indices)
        rejected = set(self.rejected_indices)
        current_received = set(self.current_received_indices)
        current_missing = set(self.current_missing_indices)
        universe = set(range(self.chunk_count))
        if base | planned != universe or base & planned or applied | pending | rejected != planned or applied & pending or applied & rejected or pending & rejected:
            raise ValidationError("execution index sets are not conserved")
        if current_received != base | applied or current_missing != pending | rejected or current_received & current_missing or current_received | current_missing != universe:
            raise ValidationError("execution current index sets are not conserved")
        if self.outcomes and tuple(item.index for item in self.outcomes) != self.planned_indices:
            raise ValidationError("execution outcomes are not in plan order")
        statuses = {status: {item.index for item in self.outcomes if item.status == status} for status in STATUSES}
        if tuple(item.index for item in self.outcomes) != self.planned_indices or statuses["applied"] != applied or statuses["pending"] != pending or statuses["rejected"] != rejected:
            raise ValidationError("execution outcomes do not replay status sets")
        if self.action_count != len(self.planned_indices) or self.action_count != len(self.outcomes) or self.applied_count != len(applied) or self.pending_count != len(pending) or self.rejected_count != len(rejected):
            raise ValidationError("execution action counts do not replay")
        if self.planned_bytes != self.applied_bytes + self.pending_bytes + self.rejected_bytes or self.current_received_bytes + self.current_remaining_bytes != self.archive_size:
            raise ValidationError("execution byte counts do not conserve the archive")
        if self.applied_bytes + self.recovery_received_bytes != self.current_received_bytes:
            raise ValidationError("execution current received bytes do not replay")
        if self.state != ("blocked" if rejected else "complete" if not pending else "in_progress" if applied else "planned"):
            raise ValidationError("execution state does not follow outcomes")
        if self.decision != ("block" if rejected else "assemble" if not pending else "resume"):
            raise ValidationError("execution decision does not follow outcomes")
        if self.safe_to_continue != (not rejected) or self.safe_to_assemble != (not pending and not rejected):
            raise ValidationError("execution safety projections do not replay")
        expected_next = min(pending) if pending else min(rejected) if rejected else -1
        if self.next_index != expected_next:
            raise ValidationError("execution next index does not replay")
        if not transfer_model._public(self.to_dict()):
            raise ValidationError("execution crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_execution(self) != self.content_address:
            raise ValidationError("execution content address does not replay")

    @property
    def recovery_received_bytes(self) -> int:
        return self.archive_size - self.planned_bytes

    def to_dict(self) -> dict[str, Any]:
        return {"execution_id": self.execution_id, "version": self.version, "boundary": self.boundary, "recovery_id": self.recovery_id, "recovery_address": self.recovery_address, "transfer_address": self.transfer_address, "archive_address": self.archive_address, "archive_size": self.archive_size, "chunk_count": self.chunk_count, "base_received_indices": self.base_received_indices, "planned_indices": self.planned_indices, "applied_indices": self.applied_indices, "pending_indices": self.pending_indices, "rejected_indices": self.rejected_indices, "current_received_indices": self.current_received_indices, "current_missing_indices": self.current_missing_indices, "planned_bytes": self.planned_bytes, "applied_bytes": self.applied_bytes, "pending_bytes": self.pending_bytes, "rejected_bytes": self.rejected_bytes, "current_received_bytes": self.current_received_bytes, "current_remaining_bytes": self.current_remaining_bytes, "outcomes": [item.to_dict() for item in self.outcomes], "action_count": self.action_count, "applied_count": self.applied_count, "pending_count": self.pending_count, "rejected_count": self.rejected_count, "state": self.state, "decision": self.decision, "safe_to_continue": self.safe_to_continue, "safe_to_assemble": self.safe_to_assemble, "checkpointed": self.checkpointed, "next_index": self.next_index, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "outcomes"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecution:
        value = _mapping(value, "recovery execution")
        _strict(value, set(cls.FIELDS), "recovery execution")
        return cls(*(value[field] for field in cls.FIELDS))


def address_outcome(value: HistoryDiffArchiveTransferRecoveryExecutionOutcome) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecutionOutcome):
        raise ValidationError("execution outcome address requires a typed outcome")
    return content_hash(value.to_dict() | {"outcome_address": None}, prefix=OUTCOME_PREFIX)


def address_execution(value: HistoryDiffArchiveTransferRecoveryExecution) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecution):
        raise ValidationError("execution address requires a typed execution")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=EXECUTION_PREFIX)


def _outcomes(recovery: recovery_model.HistoryDiffArchiveTransferRecovery, applied: set[int], rejected: set[int]) -> tuple[HistoryDiffArchiveTransferRecoveryExecutionOutcome, ...]:
    values = []
    for action in recovery.actions:
        status = "applied" if action.index in applied else "rejected" if action.index in rejected else "pending"
        pending = HistoryDiffArchiveTransferRecoveryExecutionOutcome(action.index, action.action_address, action.content_address, action.offset, action.size, status, REASONS[status], "pending:execution-outcome")
        values.append(HistoryDiffArchiveTransferRecoveryExecutionOutcome(pending.index, pending.action_address, pending.content_address, pending.offset, pending.size, pending.status, pending.reason, address_outcome(pending)))
    return tuple(values)


def _build(recovery: recovery_model.HistoryDiffArchiveTransferRecovery, *, applied_indices: Sequence[int], rejected_indices: Sequence[int], execution_id: str, checkpointed: bool) -> HistoryDiffArchiveTransferRecoveryExecution:
    recovery = recovery_model.recovery_from_mapping(recovery.to_dict())
    planned = set(recovery.missing_indices)
    applied = set(_indices(applied_indices, "applied indices", recovery.chunk_count - 1))
    rejected = set(_indices(rejected_indices, "rejected indices", recovery.chunk_count - 1))
    if not applied <= planned or not rejected <= planned or applied & rejected:
        raise ValidationError("execution statuses must address distinct planned chunks")
    pending = planned - applied - rejected
    action_by_index = {item.index: item for item in recovery.actions}
    applied_bytes = sum(action_by_index[index].size for index in applied)
    pending_bytes = sum(action_by_index[index].size for index in pending)
    rejected_bytes = sum(action_by_index[index].size for index in rejected)
    outcomes = _outcomes(recovery, applied, rejected)
    body = {"execution_id": execution_id, "version": VERSION, "boundary": BOUNDARY, "recovery_id": recovery.recovery_id, "recovery_address": recovery.content_address, "transfer_address": recovery.transfer_address, "archive_address": recovery.archive_address, "archive_size": recovery.archive_size, "chunk_count": recovery.chunk_count, "base_received_indices": recovery.received_indices, "planned_indices": recovery.missing_indices, "applied_indices": tuple(sorted(applied)), "pending_indices": tuple(sorted(pending)), "rejected_indices": tuple(sorted(rejected)), "current_received_indices": tuple(sorted(set(recovery.received_indices) | applied)), "current_missing_indices": tuple(sorted(pending | rejected)), "planned_bytes": recovery.remaining_bytes, "applied_bytes": applied_bytes, "pending_bytes": pending_bytes, "rejected_bytes": rejected_bytes, "current_received_bytes": recovery.received_bytes + applied_bytes, "current_remaining_bytes": pending_bytes + rejected_bytes, "outcomes": outcomes, "action_count": len(outcomes), "applied_count": len(applied), "pending_count": len(pending), "rejected_count": len(rejected), "state": "blocked" if rejected else "complete" if not pending else "in_progress" if applied else "planned", "decision": "block" if rejected else "assemble" if not pending else "resume", "safe_to_continue": not rejected, "safe_to_assemble": not pending and not rejected, "checkpointed": checkpointed, "next_index": min(pending) if pending else min(rejected) if rejected else -1}
    provisional = HistoryDiffArchiveTransferRecoveryExecution(**body, content_address="pending:execution")
    return HistoryDiffArchiveTransferRecoveryExecution(**body, content_address=address_execution(provisional))


def build_execution(recovery: recovery_model.HistoryDiffArchiveTransferRecovery, *, applied_indices: Sequence[int] = (), rejected_indices: Sequence[int] = (), execution_id: str = DEFAULT_EXECUTION_ID, checkpointed: bool = False) -> HistoryDiffArchiveTransferRecoveryExecution:
    if not isinstance(recovery, recovery_model.HistoryDiffArchiveTransferRecovery):
        raise ValidationError("execution builder requires a typed recovery")
    return _build(recovery, applied_indices=applied_indices, rejected_indices=rejected_indices, execution_id=execution_id, checkpointed=checkpointed)


def build_execution_from_assembler(recovery: recovery_model.HistoryDiffArchiveTransferRecovery, assembler: transfer_model.HistoryDiffArchiveTransferAssembler, *, execution_id: str = DEFAULT_EXECUTION_ID, checkpointed: bool = True) -> HistoryDiffArchiveTransferRecoveryExecution:
    if not isinstance(recovery, recovery_model.HistoryDiffArchiveTransferRecovery) or not isinstance(assembler, transfer_model.HistoryDiffArchiveTransferAssembler):
        raise ValidationError("assembler execution builder requires typed recovery and assembler")
    transfer_model.verify_transfer(assembler.value)
    if assembler.value.content_address != recovery.transfer_address:
        raise ValidationError("assembler transfer does not match the recovery plan")
    observed = set(assembler.received_indices())
    base = set(recovery.received_indices)
    if not base <= observed or not (observed - base) <= set(recovery.missing_indices):
        raise ValidationError("assembler progress is outside the recovery plan")
    return _build(recovery, applied_indices=tuple(sorted(observed - base)), rejected_indices=(), execution_id=execution_id, checkpointed=checkpointed)


def build_execution_from_directory(recovery: recovery_model.HistoryDiffArchiveTransferRecovery, source: str | Path, *, execution_id: str = DEFAULT_EXECUTION_ID) -> HistoryDiffArchiveTransferRecoveryExecution:
    return build_execution_from_assembler(recovery, transfer_model.load_partial_transfer(source), execution_id=execution_id, checkpointed=True)


def execution_from_mapping(value: Mapping[str, Any]) -> HistoryDiffArchiveTransferRecoveryExecution:
    return HistoryDiffArchiveTransferRecoveryExecution.from_mapping(value)


def verify_execution(value: HistoryDiffArchiveTransferRecoveryExecution) -> HistoryDiffArchiveTransferRecoveryExecution:
    if not isinstance(value, HistoryDiffArchiveTransferRecoveryExecution):
        raise ValidationError("execution verification requires a typed execution")
    value._validate()
    return value


def execution_json(value: HistoryDiffArchiveTransferRecoveryExecution) -> str:
    return canonical_json(execution_from_mapping(value.to_dict()).to_dict())


def execution_csv(value: HistoryDiffArchiveTransferRecoveryExecution) -> str:
    value = execution_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=OUTCOME_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.outcomes:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_execution_markdown(value: HistoryDiffArchiveTransferRecoveryExecution) -> str:
    value = execution_from_mapping(value.to_dict())
    lines = ["# Runtime-registry history-diff archive transfer recovery execution", "", f"- Execution: `{value.execution_id}`", f"- Recovery: `{value.recovery_address}`", f"- State: `{value.state}`", f"- Decision: `{value.decision}`", f"- Applied: `{value.applied_count}/{value.action_count}` actions", f"- Pending: `{value.pending_count}`", f"- Rejected: `{value.rejected_count}`", f"- Safe to assemble: `{str(value.safe_to_assemble).lower()}`", f"- Checkpointed: `{str(value.checkpointed).lower()}`", f"- Next index: `{value.next_index}`", f"- Address: `{value.content_address}`", "", "| index | status | offset | size | action address | outcome address |", "| ---: | --- | ---: | ---: | --- | --- |"]
    lines.extend(f"| {item.index} | {item.status} | {item.offset} | {item.size} | {item.action_address} | {item.outcome_address} |" for item in value.outcomes)
    return "\n".join(lines) + "\n"


def outcome_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime-registry history-diff archive transfer recovery execution outcome", "type": "object", "additionalProperties": False, "required": list(OUTCOME_FIELDS), "properties": {"index": {"type": "integer", "minimum": 0, "maximum": transfer_model.MAX_CHUNKS - 1}, "action_address": {"type": "string", "pattern": "^" + recovery_model.ACTION_PREFIX + ":"}, "content_address": {"type": "string", "pattern": "^" + transfer_model.CHUNK_PREFIX + ":"}, "offset": {"type": "integer", "minimum": 0}, "size": {"type": "integer", "minimum": 1}, "status": {"type": "string", "enum": list(STATUSES)}, "reason": {"type": "string", "enum": list(REASONS.values())}, "outcome_address": {"type": "string", "pattern": "^" + OUTCOME_PREFIX + ":"}}}


def execution_schema() -> dict[str, Any]:
    properties = {"execution_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "recovery_id": {"type": "string"}, "recovery_address": {"type": "string", "pattern": "^" + recovery_model.RECOVERY_PREFIX + ":"}, "transfer_address": {"type": "string", "pattern": "^" + transfer_model.TRANSFER_PREFIX + ":"}, "archive_address": {"type": "string", "pattern": "^" + transfer_model.archive_model.ARCHIVE_PREFIX + ":"}, "archive_size": {"type": "integer", "minimum": 1}, "chunk_count": {"type": "integer", "minimum": 1}, "base_received_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "planned_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "applied_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "pending_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "rejected_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "current_received_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "current_missing_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "planned_bytes": {"type": "integer", "minimum": 0}, "applied_bytes": {"type": "integer", "minimum": 0}, "pending_bytes": {"type": "integer", "minimum": 0}, "rejected_bytes": {"type": "integer", "minimum": 0}, "current_received_bytes": {"type": "integer", "minimum": 0}, "current_remaining_bytes": {"type": "integer", "minimum": 0}, "outcomes": {"type": "array", "items": outcome_schema()}, "action_count": {"type": "integer", "minimum": 0}, "applied_count": {"type": "integer", "minimum": 0}, "pending_count": {"type": "integer", "minimum": 0}, "rejected_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "decision": {"type": "string", "enum": list(DECISIONS)}, "safe_to_continue": {"type": "boolean"}, "safe_to_assemble": {"type": "boolean"}, "checkpointed": {"type": "boolean"}, "next_index": {"type": "integer", "minimum": -1}, "content_address": {"type": "string", "pattern": "^" + EXECUTION_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime-registry history-diff archive transfer recovery execution", "type": "object", "additionalProperties": False, "required": list(EXECUTION_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "execution_prefix": EXECUTION_PREFIX, "outcome_prefix": OUTCOME_PREFIX, "statuses": list(STATUSES), "states": list(STATES), "decisions": list(DECISIONS), "max_outcomes": MAX_OUTCOMES, "features": ["applied pending and rejected outcomes", "assembler-backed verified progress", "byte and index conservation", "resume assemble or block decision", "checkpoint and next-index projections", "canonical JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "DECISIONS", "DEFAULT_EXECUTION_ID", "EXECUTION_FIELDS", "EXECUTION_PREFIX", "MAX_OUTCOMES", "OUTCOME_FIELDS", "OUTCOME_PREFIX", "REASONS", "STATUSES", "STATES", "HistoryDiffArchiveTransferRecoveryExecution", "HistoryDiffArchiveTransferRecoveryExecutionOutcome", "VERSION", "address_execution", "address_outcome", "build_execution", "build_execution_from_assembler", "build_execution_from_directory", "capabilities", "execution_csv", "execution_from_mapping", "execution_json", "execution_schema", "outcome_schema", "render_execution_markdown", "verify_execution"]



