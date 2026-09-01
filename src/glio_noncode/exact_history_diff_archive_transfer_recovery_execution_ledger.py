"""Append-only execution ledger for exact archive-transfer recovery receipts."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution as execution_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

VERSION = execution_model.VERSION + "-ledger-v1"
BOUNDARY = execution_model.BOUNDARY + "_ledger"
LEDGER_PREFIX = execution_model.EXECUTION_PREFIX + "-ledger"
ENTRY_PREFIX = LEDGER_PREFIX + "-entry"
ENTRIES_PREFIX = LEDGER_PREFIX + "-entries"
SUMMARY_PREFIX = LEDGER_PREFIX + "-summary"
MANIFEST_PREFIX = LEDGER_PREFIX + "-manifest"
ARTIFACT_PREFIX = LEDGER_PREFIX + "-artifact"
DEFAULT_LEDGER_ID = "runtime-registry-history-diff-archive-transfer-recovery-execution-ledger"
INITIAL_HEAD = LEDGER_PREFIX + ":empty"
FILES = ("manifest.json", "ledger.json", "entries.json", "summary.json")
ARTIFACT_FILES = FILES[1:]
STATES = execution_model.STATES
DECISIONS = execution_model.DECISIONS
TRANSITIONS = ("initial",) + DECISIONS
MAX_ENTRIES = 256
MAX_LEDGER_BYTES = 16 * 1024 * 1024

ENTRY_FIELDS = (
    "ordinal", "ledger_id", "recovery_id", "execution_id", "execution_address",
    "recovery_address", "transfer_address", "archive_address", "archive_size",
    "state", "decision", "transition", "accepted", "applied_count", "pending_count",
    "rejected_count", "current_received_bytes", "current_remaining_bytes",
    "safe_to_continue", "safe_to_assemble", "checkpointed", "previous_execution_address",
    "previous_entry_address", "evidence_addresses", "content_address",
)
ENTRIES_FIELDS = ("entries", "content_address")
SUMMARY_FIELDS = (
    "ledger_id", "recovery_id", "recovery_address", "transfer_address", "archive_address",
    "archive_size", "entry_count", "latest_execution_id", "latest_execution_address",
    "latest_state", "latest_decision", "head_address", "initial_count", "resume_count",
    "assemble_count", "block_count", "planned_count", "in_progress_count", "complete_count",
    "blocked_count", "state", "accepted", "content_address",
)
MANIFEST_FIELDS = ("ledger_id", "version", "boundary", "files", "artifacts", "ledger_address", "manifest_address")
ARTIFACT_FIELDS = ("ordinal", "name", "size", "hash", "content_address")
LEDGER_FIELDS = (
    "ledger_id", "version", "boundary", "recovery_id", "recovery_address", "transfer_address",
    "archive_address", "archive_size", "entry_count", "latest_execution_id", "latest_execution_address",
    "latest_state", "latest_decision", "head_address", "initial_count", "resume_count", "assemble_count",
    "block_count", "planned_count", "in_progress_count", "complete_count", "blocked_count", "state",
    "accepted", "entries", "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True, allow_pending: bool = False) -> str:
    value = _text(value, field, 4096, required=required)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if not value:
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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


def _public(value: Any) -> bool:
    return execution_model.transfer_model._public(value)


def _namespace(prefix: str) -> str:
    return prefix + ":"


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry:
    """One addressed execution snapshot in append order."""

    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, ledger_id: str, recovery_id: str, execution_id: str, execution_address: str, recovery_address: str, transfer_address: str, archive_address: str, archive_size: int, state: str, decision: str, transition: str, accepted: bool, applied_count: int, pending_count: int, rejected_count: int, current_received_bytes: int, current_remaining_bytes: int, safe_to_continue: bool, safe_to_assemble: bool, checkpointed: bool, previous_execution_address: str, previous_entry_address: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger entry ordinal", MAX_ENTRIES, lower=1)
        self.ledger_id = _label(ledger_id, "ledger entry ID")
        self.recovery_id = _label(recovery_id, "ledger entry recovery ID")
        self.execution_id = _label(execution_id, "ledger entry execution ID")
        self.execution_address = _address(execution_address, "ledger entry execution address", execution_model.EXECUTION_PREFIX)
        self.recovery_address = _address(recovery_address, "ledger entry recovery address", execution_model.recovery_model.RECOVERY_PREFIX)
        self.transfer_address = _address(transfer_address, "ledger entry transfer address", execution_model.transfer_model.TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "ledger entry archive address", execution_model.transfer_model.archive_model.ARCHIVE_PREFIX)
        self.archive_size = _count(archive_size, "ledger entry archive size", MAX_LEDGER_BYTES, lower=1)
        if state not in STATES:
            raise ValidationError("ledger entry state is unsupported")
        self.state = state
        if decision not in DECISIONS:
            raise ValidationError("ledger entry decision is unsupported")
        self.decision = decision
        if transition not in TRANSITIONS:
            raise ValidationError("ledger entry transition is unsupported")
        self.transition = transition
        self.accepted = _bool(accepted, "ledger entry acceptance")
        self.applied_count = _count(applied_count, "ledger entry applied count", MAX_ENTRIES)
        self.pending_count = _count(pending_count, "ledger entry pending count", MAX_ENTRIES)
        self.rejected_count = _count(rejected_count, "ledger entry rejected count", MAX_ENTRIES)
        self.current_received_bytes = _count(current_received_bytes, "ledger entry received bytes", MAX_LEDGER_BYTES)
        self.current_remaining_bytes = _count(current_remaining_bytes, "ledger entry remaining bytes", MAX_LEDGER_BYTES)
        self.safe_to_continue = _bool(safe_to_continue, "ledger entry continuation safety")
        self.safe_to_assemble = _bool(safe_to_assemble, "ledger entry assembly safety")
        self.checkpointed = _bool(checkpointed, "ledger entry checkpoint")
        self.previous_execution_address = _address(previous_execution_address, "ledger entry previous execution address", execution_model.EXECUTION_PREFIX, required=False)
        self.previous_entry_address = _address(previous_entry_address, "ledger entry previous entry address", ENTRY_PREFIX, required=False)
        self.evidence_addresses = tuple(_address(item, "ledger entry evidence address") for item in _sequence(evidence_addresses, "ledger entry evidence addresses", 8))
        self.content_address = _address(content_address, "ledger entry content address", ENTRY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        expected_decision = "block" if self.state == "blocked" else "assemble" if self.state == "complete" else "resume"
        if self.decision != expected_decision or self.accepted != (self.state != "blocked"):
            raise ValidationError("ledger entry state projections do not replay")
        if self.applied_count + self.pending_count + self.rejected_count == 0 and not (self.state == "complete" and self.current_remaining_bytes == 0 and self.safe_to_assemble):
            raise ValidationError("ledger entry has an invalid empty outcome plan")
        if self.current_received_bytes + self.current_remaining_bytes != self.archive_size:
            raise ValidationError("ledger entry byte totals do not conserve the archive")
        if self.safe_to_continue != (self.rejected_count == 0) or self.safe_to_assemble != (self.pending_count == 0 and self.rejected_count == 0):
            raise ValidationError("ledger entry safety projections do not replay")
        if self.transition == "initial" and (self.previous_execution_address or self.previous_entry_address):
            raise ValidationError("initial ledger entry cannot have ancestry")
        if self.transition != "initial" and (not self.previous_execution_address or not self.previous_entry_address):
            raise ValidationError("non-initial ledger entry requires ancestry")
        if len(self.evidence_addresses) != 4:
            raise ValidationError("ledger entry evidence must retain four addresses")
        if self.evidence_addresses[0] != self.execution_address or self.evidence_addresses[1] != self.recovery_address or self.evidence_addresses[2] != self.transfer_address or self.evidence_addresses[3] != self.archive_address:
            raise ValidationError("ledger entry evidence does not replay component addresses")
        if not _public(self.to_dict()):
            raise ValidationError("ledger entry crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_entry(self) != self.content_address:
            raise ValidationError("ledger entry content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry":
        value = _mapping(value, "ledger entry")
        _strict(value, set(cls.FIELDS), "ledger entry")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntries:
    """The independently addressed entry projection."""

    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry.from_mapping(item) for item in _sequence(entries, "ledger entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "ledger entries content address", ENTRIES_PREFIX, allow_pending=True)
        if not self.content_address.startswith("pending:") and address_entries(self) != self.content_address:
            raise ValidationError("ledger entries content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntries":
        value = _mapping(value, "ledger entries")
        _strict(value, set(cls.FIELDS), "ledger entries")
        return cls(tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry.from_mapping(item) for item in _sequence(value["entries"], "ledger entries", MAX_ENTRIES)), value["content_address"])


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact:
    """One exact byte receipt for a persisted ledger projection."""

    FIELDS = ARTIFACT_FIELDS

    def __init__(self, ordinal: int, name: str, size: int, hash: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger artifact ordinal", len(ARTIFACT_FILES), lower=1)
        if name not in ARTIFACT_FILES:
            raise ValidationError("ledger artifact name is unsupported")
        self.name = name
        self.size = _count(size, "ledger artifact size", MAX_LEDGER_BYTES, lower=1)
        self.hash = _address(hash, "ledger artifact hash", ARTIFACT_PREFIX)
        self.content_address = _address(content_address, "ledger artifact content address", ARTIFACT_PREFIX, allow_pending=True)
        if not self.content_address.startswith("pending:") and address_artifact(self) != self.content_address:
            raise ValidationError("ledger artifact content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact":
        value = _mapping(value, "ledger artifact")
        _strict(value, set(cls.FIELDS), "ledger artifact")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerManifest:
    """The exact-file manifest for a persisted execution ledger."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, ledger_id: str, version: str, boundary: str, files: Sequence[str], artifacts: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact], ledger_address: str, manifest_address: str) -> None:
        self.ledger_id = _label(ledger_id, "ledger manifest ID")
        self.version = _text(version, "ledger manifest version", 2048)
        self.boundary = _text(boundary, "ledger manifest boundary", 1024)
        if tuple(files) != FILES:
            raise ValidationError("ledger manifest files are not canonical")
        self.files = tuple(files)
        self.artifacts = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact.from_mapping(item) for item in _sequence(artifacts, "ledger manifest artifacts", len(ARTIFACT_FILES)))
        if tuple(item.ordinal for item in self.artifacts) != tuple(range(1, len(ARTIFACT_FILES) + 1)) or tuple(item.name for item in self.artifacts) != ARTIFACT_FILES:
            raise ValidationError("ledger manifest artifacts are not ordered")
        self.ledger_address = _address(ledger_address, "ledger manifest ledger address", LEDGER_PREFIX)
        self.manifest_address = _address(manifest_address, "ledger manifest address", MANIFEST_PREFIX, allow_pending=True)
        if not self.manifest_address.startswith("pending:") and address_manifest(self) != self.manifest_address:
            raise ValidationError("ledger manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"ledger_id": self.ledger_id, "version": self.version, "boundary": self.boundary, "files": self.files, "artifacts": [item.to_dict() for item in self.artifacts], "ledger_address": self.ledger_address, "manifest_address": self.manifest_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerManifest":
        value = _mapping(value, "ledger manifest")
        _strict(value, set(cls.FIELDS), "ledger manifest")
        return cls(value["ledger_id"], value["version"], value["boundary"], value["files"], tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact.from_mapping(item) for item in _sequence(value["artifacts"], "ledger manifest artifacts", len(ARTIFACT_FILES))), value["ledger_address"], value["manifest_address"])


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedger:
    """An immutable, path-free chain of execution receipts."""

    FIELDS = LEDGER_FIELDS

    def __init__(self, ledger_id: str, version: str, boundary: str, recovery_id: str, recovery_address: str, transfer_address: str, archive_address: str, archive_size: int, entry_count: int, latest_execution_id: str, latest_execution_address: str, latest_state: str, latest_decision: str, head_address: str, initial_count: int, resume_count: int, assemble_count: int, block_count: int, planned_count: int, in_progress_count: int, complete_count: int, blocked_count: int, state: str, accepted: bool, entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry], content_address: str) -> None:
        self.ledger_id = _label(ledger_id, "ledger ID")
        self.version = _text(version, "ledger version", 2048)
        self.boundary = _text(boundary, "ledger boundary", 1024)
        self.recovery_id = _label(recovery_id, "ledger recovery ID", required=False)
        self.recovery_address = _address(recovery_address, "ledger recovery address", execution_model.recovery_model.RECOVERY_PREFIX, required=False)
        self.transfer_address = _address(transfer_address, "ledger transfer address", execution_model.transfer_model.TRANSFER_PREFIX, required=False)
        self.archive_address = _address(self._empty_if_zero(archive_address, archive_size), "ledger archive address", execution_model.transfer_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.archive_size = _count(archive_size, "ledger archive size", MAX_LEDGER_BYTES)
        self.entry_count = _count(entry_count, "ledger entry count", MAX_ENTRIES)
        self.latest_execution_id = _label(latest_execution_id, "ledger latest execution ID", required=False)
        self.latest_execution_address = _address(latest_execution_address, "ledger latest execution address", execution_model.EXECUTION_PREFIX, required=False)
        self.latest_state = _text(latest_state, "ledger latest state", 32, required=False)
        self.latest_decision = _text(latest_decision, "ledger latest decision", 32, required=False)
        self.head_address = _address(head_address, "ledger head address")
        self.initial_count = _count(initial_count, "ledger initial count", MAX_ENTRIES)
        self.resume_count = _count(resume_count, "ledger resume count", MAX_ENTRIES)
        self.assemble_count = _count(assemble_count, "ledger assemble count", MAX_ENTRIES)
        self.block_count = _count(block_count, "ledger block count", MAX_ENTRIES)
        self.planned_count = _count(planned_count, "ledger planned count", MAX_ENTRIES)
        self.in_progress_count = _count(in_progress_count, "ledger in-progress count", MAX_ENTRIES)
        self.complete_count = _count(complete_count, "ledger complete count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "ledger blocked count", MAX_ENTRIES)
        self.state = _text(state, "ledger state", 32)
        self.accepted = _bool(accepted, "ledger acceptance")
        self.entries = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry.from_mapping(item) for item in _sequence(entries, "ledger entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "ledger content address", LEDGER_PREFIX, allow_pending=True)
        self._validate()

    @staticmethod
    def _empty_if_zero(value: str, size: int) -> str:
        return value if size else ""

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger version or boundary is not current")
        if self.entry_count != len(self.entries):
            raise ValidationError("ledger entry count does not replay")
        if self.entry_count == 0:
            if any((self.recovery_id, self.recovery_address, self.transfer_address, self.archive_address, self.latest_execution_id, self.latest_execution_address, self.latest_state, self.latest_decision)) or self.archive_size != 0 or self.head_address != INITIAL_HEAD or self.state != "empty" or self.accepted or any((self.initial_count, self.resume_count, self.assemble_count, self.block_count, self.planned_count, self.in_progress_count, self.complete_count, self.blocked_count)):
                raise ValidationError("empty ledger projections do not replay")
        else:
            if not all((self.recovery_id, self.recovery_address, self.transfer_address, self.archive_address)) or self.archive_size < 1:
                raise ValidationError("non-empty ledger identity is incomplete")
            transition_counts = {transition: sum(item.transition == transition for item in self.entries) for transition in TRANSITIONS}
            state_counts = {state: sum(item.state == state for item in self.entries) for state in STATES}
            if (self.initial_count, self.resume_count, self.assemble_count, self.block_count) != tuple(transition_counts[item] for item in TRANSITIONS) or (self.planned_count, self.in_progress_count, self.complete_count, self.blocked_count) != tuple(state_counts[item] for item in STATES):
                raise ValidationError("ledger counters do not replay")
            for ordinal, item in enumerate(self.entries, 1):
                if item.ordinal != ordinal or item.ledger_id != self.ledger_id or item.recovery_id != self.recovery_id or item.recovery_address != self.recovery_address or item.transfer_address != self.transfer_address or item.archive_address != self.archive_address or item.archive_size != self.archive_size:
                    raise ValidationError("ledger entry identity does not replay")
                if address_entry(item) != item.content_address:
                    raise ValidationError("ledger entry address does not replay")
                expected_transition = "initial" if ordinal == 1 else item.decision
                if item.transition != expected_transition:
                    raise ValidationError("ledger transition does not replay")
                if ordinal == 1 and (item.previous_entry_address or item.previous_execution_address):
                    raise ValidationError("ledger first entry has unexpected ancestry")
                if ordinal > 1 and (item.previous_entry_address != self.entries[ordinal - 2].content_address or item.previous_execution_address != self.entries[ordinal - 2].execution_address):
                    raise ValidationError("ledger ancestry does not replay")
            latest = self.entries[-1]
            if (self.latest_execution_id, self.latest_execution_address, self.latest_state, self.latest_decision, self.head_address, self.state, self.accepted) != (latest.execution_id, latest.execution_address, latest.state, latest.decision, latest.content_address, latest.state, latest.accepted):
                raise ValidationError("ledger latest projection does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_ledger(self) != self.content_address:
            raise ValidationError("ledger content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS if field != "entries"} | {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        body = {field: getattr(self, field) for field in SUMMARY_FIELDS if field != "content_address"}
        return body | {"content_address": content_hash(body | {"content_address": None}, prefix=SUMMARY_PREFIX)}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedger":
        value = _mapping(value, "execution ledger")
        _strict(value, set(cls.FIELDS), "execution ledger")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry):
        raise ValidationError("ledger entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def address_entries(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntries) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntries):
        raise ValidationError("ledger entries address requires a typed projection")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRIES_PREFIX)


def address_artifact(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact):
        raise ValidationError("ledger artifact address requires a typed artifact")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARTIFACT_PREFIX)


def address_summary(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value) | {"content_address": None}, prefix=SUMMARY_PREFIX)


def address_manifest(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerManifest) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerManifest):
        raise ValidationError("ledger manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"manifest_address": None}, prefix=MANIFEST_PREFIX)


def address_ledger(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedger):
        raise ValidationError("ledger address requires a typed ledger")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=LEDGER_PREFIX)


def entry_from_execution(execution: execution_model.ExactHistoryDiffArchiveTransferRecoveryExecution, ledger_id: str, ordinal: int, previous: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry | None = None) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry:
    execution = execution_model.execution_from_mapping(execution.to_dict()) if isinstance(execution, execution_model.ExactHistoryDiffArchiveTransferRecoveryExecution) else execution_model.execution_from_mapping(execution)
    body = {"ordinal": ordinal, "ledger_id": ledger_id, "recovery_id": execution.recovery_id, "execution_id": execution.execution_id, "execution_address": execution.content_address, "recovery_address": execution.recovery_address, "transfer_address": execution.transfer_address, "archive_address": execution.archive_address, "archive_size": execution.archive_size, "state": execution.state, "decision": execution.decision, "transition": "initial" if previous is None else execution.decision, "accepted": execution.state != "blocked", "applied_count": execution.applied_count, "pending_count": execution.pending_count, "rejected_count": execution.rejected_count, "current_received_bytes": execution.current_received_bytes, "current_remaining_bytes": execution.current_remaining_bytes, "safe_to_continue": execution.safe_to_continue, "safe_to_assemble": execution.safe_to_assemble, "checkpointed": execution.checkpointed, "previous_execution_address": "" if previous is None else previous.execution_address, "previous_entry_address": "" if previous is None else previous.content_address, "evidence_addresses": (execution.content_address, execution.recovery_address, execution.transfer_address, execution.archive_address)}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry(**body, content_address="pending:ledger-entry")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry(**body, content_address=address_entry(provisional))


def _assemble(ledger_id: str, entries: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedger:
    entries = tuple(entries)
    if not entries:
        body = {"ledger_id": ledger_id, "version": VERSION, "boundary": BOUNDARY, "recovery_id": "", "recovery_address": "", "transfer_address": "", "archive_address": "", "archive_size": 0, "entry_count": 0, "latest_execution_id": "", "latest_execution_address": "", "latest_state": "", "latest_decision": "", "head_address": INITIAL_HEAD, "initial_count": 0, "resume_count": 0, "assemble_count": 0, "block_count": 0, "planned_count": 0, "in_progress_count": 0, "complete_count": 0, "blocked_count": 0, "state": "empty", "accepted": False}
    else:
        first, latest = entries[0], entries[-1]
        body = {"ledger_id": ledger_id, "version": VERSION, "boundary": BOUNDARY, "recovery_id": first.recovery_id, "recovery_address": first.recovery_address, "transfer_address": first.transfer_address, "archive_address": first.archive_address, "archive_size": first.archive_size, "entry_count": len(entries), "latest_execution_id": latest.execution_id, "latest_execution_address": latest.execution_address, "latest_state": latest.state, "latest_decision": latest.decision, "head_address": latest.content_address, "initial_count": sum(item.transition == "initial" for item in entries), "resume_count": sum(item.transition == "resume" for item in entries), "assemble_count": sum(item.transition == "assemble" for item in entries), "block_count": sum(item.transition == "block" for item in entries), "planned_count": sum(item.state == "planned" for item in entries), "in_progress_count": sum(item.state == "in_progress" for item in entries), "complete_count": sum(item.state == "complete" for item in entries), "blocked_count": sum(item.state == "blocked" for item in entries), "state": latest.state, "accepted": latest.accepted}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedger(**body, entries=entries, content_address="pending:ledger")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedger(**body, entries=entries, content_address=address_ledger(provisional))


def build_ledger(executions: Sequence[execution_model.ExactHistoryDiffArchiveTransferRecoveryExecution], *, ledger_id: str = DEFAULT_LEDGER_ID) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedger:
    executions = _sequence(executions, "ledger executions", MAX_ENTRIES)
    ledger_id = _label(ledger_id, "ledger ID")
    entries: list[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry] = []
    for ordinal, execution in enumerate(executions, 1):
        entry = entry_from_execution(execution, ledger_id, ordinal, entries[-1] if entries else None)
        if any(item.execution_address == entry.execution_address for item in entries):
            raise ValidationError("ledger execution addresses must be unique")
        entries.append(entry)
    return _assemble(ledger_id, entries)


def append_execution(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger, execution: execution_model.ExactHistoryDiffArchiveTransferRecoveryExecution, *, expected_head_address: str | None = None) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedger:
    value = verify_ledger(value)
    if expected_head_address is not None and expected_head_address != value.head_address:
        raise ValidationError("ledger head guard does not match")
    entry = entry_from_execution(execution, value.ledger_id, value.entry_count + 1, value.entries[-1] if value.entries else None)
    if any(item.execution_address == entry.execution_address for item in value.entries):
        raise ValidationError("ledger execution addresses must be unique")
    if value.entry_count and (entry.recovery_address, entry.transfer_address, entry.archive_address, entry.archive_size) != (value.recovery_address, value.transfer_address, value.archive_address, value.archive_size):
        raise ValidationError("ledger execution identity does not match")
    return _assemble(value.ledger_id, value.entries + (entry,))


def verify_ledger(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedger:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedger):
        raise ValidationError("ledger verification requires a typed ledger")
    value._validate()
    return value


def ledger_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedger:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedger.from_mapping(value)


def ledger_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> str:
    return canonical_json(ledger_from_mapping(value.to_dict()).to_dict())


def entries_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> str:
    value = verify_ledger(value)
    projection = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntries(value.entries, "pending:ledger-entries")
    projection = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntries(value.entries, address_entries(projection))
    return canonical_json(projection.to_dict())


def summary_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> str:
    return canonical_json(verify_ledger(value).summary())


def ledger_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> str:
    value = verify_ledger(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ENTRY_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.entries:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_ledger_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> str:
    value = verify_ledger(value)
    lines = ["# Exact archive-transfer recovery execution ledger", "", f"- Ledger: `{value.ledger_id}`", f"- Entries: `{value.entry_count}`", f"- State: `{value.state}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Head: `{value.head_address}`", f"- Address: `{value.content_address}`", "", "| # | execution | transition | state | decision | accepted | previous entry |", "| ---: | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.execution_id}` | `{item.transition}` | `{item.state}` | `{item.decision}` | `{str(item.accepted).lower()}` | `{item.previous_entry_address or '—'}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def _documents(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> dict[str, bytes]:
    return {"ledger.json": canonical_bytes(value.to_dict()), "entries.json": canonical_bytes(json.loads(entries_json(value))), "summary.json": canonical_bytes(json.loads(summary_json(value)))}


def _build_manifest(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerManifest:
    documents = _documents(value)
    receipts = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact(index, name, len(documents[name]), hash_bytes(documents[name], prefix=ARTIFACT_PREFIX), "pending:ledger-artifact") for index, name in enumerate(ARTIFACT_FILES, 1))
    receipts = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact(item.ordinal, item.name, item.size, item.hash, address_artifact(item)) for item in receipts)
    body = {"ledger_id": value.ledger_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": receipts, "ledger_address": value.content_address}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerManifest(**body, manifest_address="pending:ledger-manifest")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerManifest(**body, manifest_address=address_manifest(provisional))


def manifest_document(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger) -> dict[str, Any]:
    return _build_manifest(verify_ledger(value)).to_dict()


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {} for field in ENTRY_FIELDS}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger entries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "maxItems": MAX_ENTRIES, "items": entry_schema()}, "content_address": {"type": "string", "pattern": "^" + ENTRIES_PREFIX + ":"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {} for field in SUMMARY_FIELDS}}


def manifest_schema() -> dict[str, Any]:
    artifact = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger artifact", "type": "object", "additionalProperties": False, "required": list(ARTIFACT_FIELDS), "properties": {field: {} for field in ARTIFACT_FIELDS}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"ledger_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "items": artifact, "minItems": len(ARTIFACT_FILES), "maxItems": len(ARTIFACT_FILES)}, "ledger_address": {"type": "string", "pattern": "^" + LEDGER_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def ledger_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact archive-transfer recovery execution ledger", "type": "object", "additionalProperties": False, "required": list(LEDGER_FIELDS), "properties": {field: {} for field in LEDGER_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "ledger_prefix": LEDGER_PREFIX, "entry_prefix": ENTRY_PREFIX, "entries_prefix": ENTRIES_PREFIX, "summary_prefix": SUMMARY_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "transitions": TRANSITIONS, "states": STATES, "decisions": DECISIONS, "files": FILES, "features": ("append-only addressed execution snapshots", "optimistic head guards", "ancestry and counter conservation", "exact four-file atomic persistence", "canonical reload and byte receipts", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


def _write(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)


def persist_ledger(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedger, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_ledger(value)
    documents = _documents(value)
    manifest = _build_manifest(value)
    members = {"manifest.json": canonical_bytes(manifest.to_dict()), **documents}
    target = Path(destination)
    if target.exists():
        if not overwrite:
            raise ValidationError("ledger destination exists; explicit overwrite is required")
        if target.is_symlink() or not target.is_dir():
            raise ValidationError("ledger destination must be a regular directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
    try:
        for filename in FILES:
            _write(temporary / filename, members[filename])
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("ledger could not be persisted atomically") from error
    return target


def _read_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = _mapping(json.loads(raw.decode("utf-8")), f"ledger member {path.name}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"ledger member {path.name} is not valid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"ledger member {path.name} is not canonical")
    return value, raw


def load_ledger(destination: str | Path) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedger:
    root = Path(destination)
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("ledger source must be a regular directory")
    entries = tuple(root.iterdir())
    if tuple(sorted(item.name for item in entries)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in entries):
        raise ValidationError("ledger directory has an unexpected file set")
    manifest_raw, manifest_bytes = _read_json(root / "manifest.json")
    manifest = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerManifest.from_mapping(manifest_raw)
    ledger_raw, _ = _read_json(root / "ledger.json")
    value = ledger_from_mapping(ledger_raw)
    entries_raw, _ = _read_json(root / "entries.json")
    projection = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntries.from_mapping(entries_raw)
    summary_raw, summary_bytes = _read_json(root / "summary.json")
    if tuple(item.to_dict() for item in projection.entries) != tuple(item.to_dict() for item in value.entries) or canonical_bytes(projection.to_dict()) != canonical_bytes(json.loads(entries_json(value))) or summary_bytes != canonical_bytes(json.loads(summary_json(value))):
        raise ValidationError("ledger projections do not replay")
    expected_manifest = _build_manifest(value)
    if manifest.to_dict() != expected_manifest.to_dict() or manifest_bytes != canonical_bytes(expected_manifest.to_dict()):
        raise ValidationError("ledger manifest does not replay")
    documents = _documents(value)
    expected_members = {"manifest.json": canonical_bytes(expected_manifest.to_dict()), **documents}
    for filename in FILES:
        if (root / filename).read_bytes() != expected_members[filename]:
            raise ValidationError(f"ledger member {filename} does not replay")
    for receipt in manifest.artifacts:
        raw = expected_members[receipt.name]
        expected = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact(receipt.ordinal, receipt.name, len(raw), hash_bytes(raw, prefix=ARTIFACT_PREFIX), "pending:ledger-artifact")
        if receipt.size != expected.size or receipt.hash != expected.hash or receipt.content_address != address_artifact(expected):
            raise ValidationError("ledger artifact receipt does not replay")
    return verify_ledger(value)


def run_ledger(source: str | Path | ExactHistoryDiffArchiveTransferRecoveryExecutionLedger | execution_model.ExactHistoryDiffArchiveTransferRecoveryExecution, *, ledger_id: str = DEFAULT_LEDGER_ID, destination: str | Path | None = None, overwrite: bool = False) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedger:
    if isinstance(source, (str, Path)):
        path = Path(source)
        if path.is_dir() and tuple(sorted(item.name for item in path.iterdir())) == tuple(sorted(FILES)):
            value = load_ledger(path)
        else:
            raw, _ = _read_json(path)
            value = ledger_from_mapping(raw) if "entries" in raw else build_ledger((execution_model.execution_from_mapping(raw),), ledger_id=ledger_id)
    elif isinstance(source, ExactHistoryDiffArchiveTransferRecoveryExecutionLedger):
        value = verify_ledger(source)
    else:
        value = build_ledger((source,), ledger_id=ledger_id)
    if destination is not None:
        persist_ledger(value, destination, overwrite=overwrite)
    return value


__all__ = ["ARTIFACT_FIELDS", "ARTIFACT_FILES", "ARTIFACT_PREFIX", "BOUNDARY", "DEFAULT_LEDGER_ID", "DECISIONS", "ENTRIES_FIELDS", "ENTRIES_PREFIX", "ENTRY_FIELDS", "ENTRY_PREFIX", "FILES", "INITIAL_HEAD", "LEDGER_FIELDS", "LEDGER_PREFIX", "MANIFEST_FIELDS", "MANIFEST_PREFIX", "MAX_ENTRIES", "MAX_LEDGER_BYTES", "STATES", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "TRANSITIONS", "VERSION", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedger", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerArtifact", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntries", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerEntry", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerManifest", "address_artifact", "address_entries", "address_entry", "address_ledger", "address_manifest", "address_summary", "append_execution", "build_ledger", "capabilities", "entries_json", "entries_schema", "entry_from_execution", "entry_schema", "ledger_csv", "ledger_from_mapping", "ledger_json", "ledger_schema", "load_ledger", "manifest_document", "manifest_schema", "persist_ledger", "render_ledger_markdown", "run_ledger", "summary_json", "summary_schema", "verify_ledger"]
