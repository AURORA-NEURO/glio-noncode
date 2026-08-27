"""Append-only history for catalog packet-review release-gate decisions."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_ENTRY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
    + "-entry"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
    + "-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_VERIFICATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
    + "-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_DOCUMENT = "history.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES = 256
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_CHECKS = 16


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryDecision(
    StrEnum
):
    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"
    SUPERSEDE = "supersede"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryState(
    StrEnum
):
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    value = _text(value, field, 512)
    if ":" not in value:
        raise ValidationError(f"{field} must be addressed")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).casefold()
            if lowered in {"agent", "language", "model", "user"} or lowered.endswith(
                ("_agent", "_language", "_model", "_user")
            ):
                return False
            if not _public(item):
                return False
    elif isinstance(value, (tuple, list)):
        return all(_public(item) for item in value)
    return True


def _decision(value: Any, field: str = "history decision") -> str:
    value = _text(value, field, 32)
    if value not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryDecision
    }:
        raise ValidationError(f"{field} is invalid")
    return value


def _state(value: Any, field: str = "history state") -> str:
    value = _text(value, field, 32)
    if value not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryState
    }:
        raise ValidationError(f"{field} is invalid")
    return value


def _state_for(decision: str, accepted: bool, release_ready: bool) -> str:
    if not accepted:
        return "blocked"
    if release_ready:
        return "ready"
    return "held"


def _event_is_closed(decision: str, state: str, accepted: bool, release_ready: bool) -> bool:
    if decision == "promote":
        return accepted and release_ready and state == "ready"
    if decision in {"hold", "supersede"}:
        return accepted and not release_ready and state == "held"
    return decision == "block" and not accepted and not release_ready and state == "blocked"


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_entry(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_ENTRY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry:
    """One immutable historical projection of a verified gate decision."""

    def __init__(
        self,
        *,
        ordinal: int,
        gate_address: str,
        decision: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        previous_head_address: str | None,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.gate_address = gate_address
        self.decision = decision
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.previous_head_address = previous_head_address
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "history entry ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES
            - 1,
        )
        _address(self.gate_address, "history entry gate address")
        decision = _decision(self.decision)
        state = _state(self.state)
        _bool(self.accepted, "history entry accepted")
        _bool(self.release_ready, "history entry release-ready")
        _address(self.previous_head_address, "history entry previous head address", optional=True)
        _text(self.detail, "history entry detail")
        _address(self.content_address, "history entry content address")
        if not _event_is_closed(decision, state, self.accepted, self.release_ready):
            raise ValidationError("history entry decision closure is invalid")
        if self.ordinal == 0 and self.previous_head_address is not None:
            raise ValidationError("first history entry cannot have a previous head")
        if self.ordinal > 0 and self.previous_head_address is None:
            raise ValidationError("continued history entry requires a previous head")
        if not _public(self.to_dict()):
            raise ValidationError("history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "gate_address": self.gate_address,
            "decision": self.decision,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "previous_head_address": self.previous_head_address,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryCheck:
    """An addressed, explainable history verification check."""

    def __init__(
        self,
        *,
        ordinal: int,
        kind: str,
        passed: bool,
        expected: Any,
        observed: Any,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.kind = kind
        self.passed = passed
        self.expected = expected
        self.observed = observed
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "history check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "history check kind", 256)
        _bool(self.passed, "history check passed")
        _text(self.detail, "history check detail")
        _address(self.content_address, "history check content address")
        if not _public(self.to_dict()):
            raise ValidationError("history check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "state": "passed" if self.passed else "failed",
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryVerification:
    """Verification receipt for an append-only gate history."""

    def __init__(
        self,
        *,
        history_address: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.history_address = history_address
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.history_address, "history verification history address")
        _count(
            self.check_count,
            "history verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_CHECKS,
        )
        if self.check_count != len(self.checks) or self.check_count == 0:
            raise ValidationError("history verification checks are not conserved")
        if (self.passed_count, self.failed_count) != (
            sum(item.passed for item in self.checks),
            sum(not item.passed for item in self.checks),
        ):
            raise ValidationError("history verification counts are not conserved")
        _count(self.passed_count, "history verification passed count", self.check_count)
        _count(self.failed_count, "history verification failed count", self.check_count)
        _bool(self.accepted, "history verification accepted")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("history verification acceptance is not conserved")
        for ordinal, check in enumerate(self.checks):
            if (
                check.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("history verification check address is invalid")
        _address(self.content_address, "history verification content address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_address": self.history_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory:
    """A durable, path-free, append-only sequence of gate decisions."""

    def __init__(
        self,
        *,
        history_id: str,
        version: str,
        boundary: str,
        gate_address: str,
        head_address: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        entry_count: int,
        promote_count: int,
        hold_count: int,
        block_count: int,
        supersede_count: int,
        entries: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.history_id = history_id
        self.version = version
        self.boundary = boundary
        self.gate_address = gate_address
        self.head_address = head_address
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.entry_count = entry_count
        self.promote_count = promote_count
        self.hold_count = hold_count
        self.block_count = block_count
        self.supersede_count = supersede_count
        self.entries = tuple(entries)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.history_id, "history ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_VERSION
        ):
            raise ValidationError("history version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_BOUNDARY
        ):
            raise ValidationError("history boundary is invalid")
        _address(self.gate_address, "history gate address")
        _address(self.head_address, "history head address")
        _state(self.state)
        _bool(self.accepted, "history accepted")
        _bool(self.release_ready, "history release-ready")
        _count(
            self.entry_count,
            "history entry count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES,
        )
        if self.entry_count != len(self.entries) or self.entry_count == 0:
            raise ValidationError("history entries are not conserved")
        for ordinal, entry in enumerate(self.entries):
            if entry.ordinal != ordinal:
                raise ValidationError("history entry ordinals are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_entry(
                    entry
                )
                != entry.content_address
            ):
                raise ValidationError("history entry address is invalid")
            if (
                ordinal > 0
                and entry.previous_head_address != self.entries[ordinal - 1].content_address
            ):
                raise ValidationError("history entry previous head is not continuous")
        head = self.entries[-1]
        if self.head_address != head.content_address or self.gate_address != head.gate_address:
            raise ValidationError("history head projection is not conserved")
        counts = {
            "promote": sum(item.decision == "promote" for item in self.entries),
            "hold": sum(item.decision == "hold" for item in self.entries),
            "block": sum(item.decision == "block" for item in self.entries),
            "supersede": sum(item.decision == "supersede" for item in self.entries),
        }
        if (self.promote_count, self.hold_count, self.block_count, self.supersede_count) != tuple(
            counts[item] for item in ("promote", "hold", "block", "supersede")
        ):
            raise ValidationError("history decision counts are not conserved")
        for value, field in (
            (self.promote_count, "history promote count"),
            (self.hold_count, "history hold count"),
            (self.block_count, "history block count"),
            (self.supersede_count, "history supersede count"),
        ):
            _count(value, field, self.entry_count)
        if (self.state, self.accepted, self.release_ready) != (
            head.state,
            head.accepted,
            head.release_ready,
        ):
            raise ValidationError("history head state is not conserved")
        _address(self.content_address, "history content address")
        if not _public(self.to_dict()):
            raise ValidationError("history crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id,
            "version": self.version,
            "boundary": self.boundary,
            "gate_address": self.gate_address,
            "head_address": self.head_address,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "entry_count": self.entry_count,
            "promote_count": self.promote_count,
            "hold_count": self.hold_count,
            "block_count": self.block_count,
            "supersede_count": self.supersede_count,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        return body


def _entry(
    ordinal: int,
    gate: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    previous_head_address: str | None,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry:
    body = {
        "ordinal": ordinal,
        "gate_address": gate.content_address,
        "decision": gate.decision,
        "state": gate.state,
        "accepted": gate.accepted,
        "release_ready": gate.release_ready,
        "previous_head_address": previous_head_address,
        "detail": _text(detail, "history entry detail"),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry(
        **body, content_address="pending:entry"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_entry(
            provisional
        ),
    )


def _check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryCheck:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "passed": passed,
        "expected": json.loads(canonical_json(expected)),
        "observed": json.loads(canonical_json(observed)),
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_check(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
    gate: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    *,
    history_id: str = "glio-noncode-review-store-catalog-packet-review-gate-history",
    detail: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory:
    if not isinstance(
        gate,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    ):
        raise ValidationError("gate history requires a typed gate")
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
        gate
    ).accepted:
        raise ValidationError("gate history requires a structurally verified gate")
    entry = _entry(0, gate, None, detail or f"recorded {gate.decision} gate decision")
    body = {
        "history_id": _text(history_id, "history ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_BOUNDARY,
        "gate_address": entry.gate_address,
        "head_address": entry.content_address,
        "state": entry.state,
        "accepted": entry.accepted,
        "release_ready": entry.release_ready,
        "entry_count": 1,
        "promote_count": int(entry.decision == "promote"),
        "hold_count": int(entry.decision == "hold"),
        "block_count": int(entry.decision == "block"),
        "supersede_count": int(entry.decision == "supersede"),
        "entries": (entry,),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory(
        **body, content_address="pending:history"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            provisional
        ),
    )


def append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
    history: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
    gate: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    *,
    expected_head_address: str | None = None,
    detail: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory:
    if not isinstance(
        history,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
    ) or not isinstance(
        gate,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    ):
        raise ValidationError("history append requires typed history and gate")
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
        gate
    ).accepted:
        raise ValidationError("history append requires a structurally verified gate")
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
        history
    ).accepted:
        raise ValidationError("history append requires a structurally verified history")
    if expected_head_address is not None and expected_head_address != history.head_address:
        raise ValidationError("history append expected head is stale")
    if any(item.gate_address == gate.content_address for item in history.entries):
        raise ValidationError("history append would duplicate a gate")
    if (
        history.entry_count
        >= MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES
    ):
        raise ValidationError("history entry limit is exhausted")
    entry = _entry(
        history.entry_count,
        gate,
        history.head_address,
        detail or f"appended {gate.decision} gate decision",
    )
    entries = history.entries + (entry,)
    body = {
        "history_id": history.history_id,
        "version": history.version,
        "boundary": history.boundary,
        "gate_address": entry.gate_address,
        "head_address": entry.content_address,
        "state": entry.state,
        "accepted": entry.accepted,
        "release_ready": entry.release_ready,
        "entry_count": len(entries),
        "promote_count": sum(item.decision == "promote" for item in entries),
        "hold_count": sum(item.decision == "hold" for item in entries),
        "block_count": sum(item.decision == "block" for item in entries),
        "supersede_count": sum(item.decision == "supersede" for item in entries),
        "entries": entries,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory(
        **body, content_address="pending:history"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
    left_directory: str | Path,
    right_directory: str | Path,
    **kwargs: Any,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory:
    """Load two persisted packets, build their gate, and record its first event."""

    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate import (
        build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_from_directories,
    )

    gate_kwargs = {
        key: kwargs.pop(key)
        for key in (
            "diff_id",
            "review_id",
            "assurance_id",
            "gate_id",
            "decision",
            "decision_id",
            "detail",
        )
        if key in kwargs
    }
    history_id = kwargs.pop(
        "history_id", "glio-noncode-review-store-catalog-packet-review-gate-history"
    )
    history_detail = kwargs.pop("history_detail", None)
    if kwargs:
        raise ValidationError(f"unknown gate history build options: {sorted(kwargs)}")
    gate = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_from_directories(
        left_directory,
        right_directory,
        **gate_kwargs,
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
        gate,
        history_id=history_id,
        detail=history_detail,
    )


def _history_checks(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
    supplied_gate: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate
    | None = None,
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryCheck,
    ...,
]:
    entries = value.entries
    head = entries[-1]
    checks = [
        _check(
            0,
            "aggregate-address",
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
                value
            )
            == value.content_address,
            value.content_address,
            value.content_address,
            "history aggregate address is recomputed",
        ),
        _check(
            1,
            "entry-conservation",
            value.entry_count == len(entries)
            and 0
            < value.entry_count
            <= MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES,
            value.entry_count,
            len(entries),
            "entry count is bounded and conserved",
        ),
        _check(
            2,
            "entry-addresses",
            all(
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_entry(
                    item
                )
                == item.content_address
                for item in entries
            ),
            True,
            tuple(item.content_address for item in entries),
            "entry addresses are independently recomputed",
        ),
        _check(
            3,
            "head-continuity",
            all(
                item.ordinal == ordinal
                and (
                    ordinal == 0
                    or item.previous_head_address == entries[ordinal - 1].content_address
                )
                for ordinal, item in enumerate(entries)
            ),
            tuple(item.content_address for item in entries[:-1]),
            tuple(item.previous_head_address for item in entries[1:]),
            "append-only previous-head links are continuous",
        ),
        _check(
            4,
            "decision-closure",
            all(
                _event_is_closed(item.decision, item.state, item.accepted, item.release_ready)
                for item in entries
            ),
            True,
            tuple(
                (item.decision, item.state, item.accepted, item.release_ready) for item in entries
            ),
            "every historical decision maps to one closed state",
        ),
        _check(
            5,
            "decision-counts",
            value.promote_count + value.hold_count + value.block_count + value.supersede_count
            == value.entry_count,
            value.entry_count,
            value.promote_count + value.hold_count + value.block_count + value.supersede_count,
            "decision counters cover every history entry",
        ),
        _check(
            6,
            "head-projection",
            value.head_address == head.content_address
            and value.gate_address == head.gate_address
            and value.state == head.state
            and value.accepted == head.accepted
            and value.release_ready == head.release_ready,
            head.to_dict(),
            value.summary(),
            "history summary follows its current head",
        ),
        _check(
            7,
            "unique-gates",
            len({item.gate_address for item in entries}) == value.entry_count,
            value.entry_count,
            len({item.gate_address for item in entries}),
            "a gate address is recorded at most once",
        ),
        _check(
            8,
            "public-boundary",
            _public(value.to_dict()),
            True,
            _public(value.to_dict()),
            "history projection contains only public fields",
        ),
    ]
    if supplied_gate is not None:
        checks.append(
            _check(
                9,
                "supplied-head-gate",
                supplied_gate.content_address == value.gate_address
                and verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                    supplied_gate
                ).accepted,
                value.gate_address,
                supplied_gate.content_address,
                "supplied gate matches the historical head and verifies",
            )
        )
    return tuple(checks)


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
    *,
    supplied_gate: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate
    | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryVerification:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
    ):
        raise ValidationError("gate history verification requires a typed history")
    if supplied_gate is not None and not isinstance(
        supplied_gate,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    ):
        raise ValidationError("supplied gate must be typed")
    checks = _history_checks(value, supplied_gate)
    body = {
        "history_address": value.content_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": checks,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryVerification(
        **body, content_address="pending:verification"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_verification(
            provisional
        ),
    )


def _require_verified_history(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
) -> None:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
        value
    ).accepted:
        raise ValidationError("packet review gate history verification failed")


def _entry_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry(
        ordinal=value["ordinal"],
        gate_address=value["gate_address"],
        decision=value["decision"],
        state=value["state"],
        accepted=value["accepted"],
        release_ready=value["release_ready"],
        previous_head_address=value["previous_head_address"],
        detail=value["detail"],
        content_address=value["content_address"],
    )


def _history_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory:
    body = dict(value)
    body["entries"] = tuple(_entry_from_dict(item) for item in body.pop("entries"))
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory(
        **body
    )


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Persist a verified history as an atomic, exact two-file directory."""

    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
        value
    ).accepted:
        raise ValidationError("cannot persist an unverified packet review gate history")
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("packet review gate history destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        document = canonical_bytes(value.to_dict())
        manifest_body = {
            "manifest_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_VERSION,
            "history": value.to_dict(),
            "byte_count": len(document),
            "byte_address": hash_bytes(
                document,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
                + "-bytes",
            ),
        }
        manifest = manifest_body | {
            "manifest_address": content_hash(
                manifest_body,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
                + "-manifest",
            )
        }
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_DOCUMENT
        ).write_bytes(document)
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MANIFEST
        ).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError(
                    "packet review gate history destination is not a regular directory"
                )
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory:
    """Load and fail closed on any non-canonical or mismatched history archive."""

    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("packet review gate history directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MANIFEST,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_DOCUMENT,
    }
    children = tuple(directory.iterdir())
    if (
        any(item.is_symlink() or not item.is_file() for item in children)
        or {item.name for item in children} != expected
    ):
        raise ValidationError("packet review gate history files do not match the published set")
    manifest_path = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MANIFEST
    )
    document_path = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_DOCUMENT
    )
    manifest_raw = manifest_path.read_bytes()
    document_raw = document_path.read_bytes()
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
        document = json.loads(document_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("packet review gate history files are not valid JSON") from exc
    if (
        not isinstance(manifest, dict)
        or not isinstance(document, dict)
        or canonical_bytes(manifest) != manifest_raw
        or canonical_bytes(document) != document_raw
    ):
        raise ValidationError("packet review gate history files must be canonical JSON objects")
    if (
        set(manifest)
        != {"manifest_version", "history", "byte_count", "byte_address", "manifest_address"}
        or manifest.get("manifest_version")
        != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_VERSION
    ):
        raise ValidationError("packet review gate history manifest structure is invalid")
    manifest_body = {key: item for key, item in manifest.items() if key != "manifest_address"}
    if manifest["manifest_address"] != content_hash(
        manifest_body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
        + "-manifest",
    ):
        raise ValidationError("packet review gate history manifest address mismatch")
    if (
        manifest["history"] != document
        or manifest["byte_count"] != len(document_raw)
        or manifest["byte_address"]
        != hash_bytes(
            document_raw,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
            + "-bytes",
        )
    ):
        raise ValidationError("packet review gate history document does not match the manifest")
    try:
        history = _history_from_dict(document)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("packet review gate history document structure is invalid") from exc
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
        history
    ).accepted:
        raise ValidationError("packet review gate history verification failed")
    return history


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
) -> str:
    _require_verified_history(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
) -> str:
    _require_verified_history(value)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "gate_address",
            "decision",
            "state",
            "accepted",
            "release_ready",
            "previous_head_address",
            "detail",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for item in value.entries:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
) -> str:
    _require_verified_history(value)
    lines = [
        "# Catalog Packet Review Gate History",
        "",
        f"- history: `{value.history_id}`",
        f"- state: `{value.state}`",
        f"- entries: `{value.entry_count}`",
        f"- head: `{value.head_address}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Decision | State | Accepted | Ready | Detail |",
        "|---:|---|---|---:|---:|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.decision}` | `{item.state}` | `{str(item.accepted).lower()}` | `{str(item.release_ready).lower()}` | {item.detail} |"
        for item in value.entries
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
    *,
    resource: str = "entries",
    decision: str | None = None,
    state: str | None = None,
    accepted: bool | None = None,
    release_ready: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_DEFAULT_LIMIT,
) -> dict[str, Any]:
    _require_verified_history(value)
    if resource not in {"summary", "entries", "checks"}:
        raise ValidationError("packet review gate history query resource is invalid")
    if decision is not None:
        decision = _decision(decision, "packet review gate history query decision")
    if state is not None:
        state = _state(state, "packet review gate history query state")
    if accepted is not None and not isinstance(accepted, bool):
        raise ValidationError("packet review gate history query accepted filter is invalid")
    if release_ready is not None and not isinstance(release_ready, bool):
        raise ValidationError("packet review gate history query release-ready filter is invalid")
    if text is not None:
        text = _text(text, "packet review gate history query text")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 512
    ):
        raise ValidationError("packet review gate history query bounds are invalid")
    if resource == "summary":
        rows = [value.summary()]
    elif resource == "entries":
        rows = [item.to_dict() for item in value.entries]
    else:
        verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value
        )
        rows = [item.to_dict() for item in verification.checks]
    if resource in {"summary", "entries"}:
        if decision is not None:
            rows = [row for row in rows if row.get("decision") == decision]
        if state is not None:
            rows = [row for row in rows if row.get("state") == state]
        if accepted is not None:
            rows = [row for row in rows if row.get("accepted") == accepted]
        if release_ready is not None:
            rows = [row for row in rows if row.get("release_ready") == release_ready]
    if text is not None:
        rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
    body = {
        "query": {
            "resource": resource,
            "decision": decision,
            "state": state,
            "accepted": accepted,
            "release_ready": release_ready,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "history": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("packet review gate history query must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_QUERY_PREFIX,
        )
        != value["content_address"]
    ):
        raise ValidationError("packet review gate history query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query(
        value
    )
    output = io.StringIO(newline="")
    items = value.get("items", [])
    resource = value.get("query", {}).get("resource")
    fieldnames = (
        (
            "ordinal",
            "gate_address",
            "decision",
            "state",
            "accepted",
            "release_ready",
            "previous_head_address",
            "detail",
            "content_address",
        )
        if resource == "entries"
        else (
            "history_id",
            "version",
            "boundary",
            "gate_address",
            "head_address",
            "state",
            "accepted",
            "release_ready",
            "entry_count",
            "promote_count",
            "hold_count",
            "block_count",
            "supersede_count",
            "content_address",
        )
        if resource == "summary"
        else (
            "ordinal",
            "kind",
            "state",
            "passed",
            "expected",
            "observed",
            "detail",
            "content_address",
        )
    )
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for item in items:
        row = dict(item)
        for key in ("expected", "observed"):
            if key in row:
                row[key] = canonical_json(row[key])
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query(
        value
    )
    resource = value["query"]["resource"]
    lines = [
        "# Catalog Packet Review Gate History Query",
        "",
        f"- resource: `{resource}`",
        f"- total: `{value['total']}`",
        f"- address: `{value['content_address']}`",
        "",
    ]
    if resource == "entries":
        lines.extend(
            ["| # | Decision | State | Accepted | Ready | Detail |", "|---:|---|---|---:|---:|---|"]
        )
        lines.extend(
            f"| {row.get('ordinal', '')} | `{row.get('decision', '')}` | `{row.get('state', '')}` | `{str(row.get('accepted', '')).lower()}` | `{str(row.get('release_ready', '')).lower()}` | {row.get('detail', '')} |"
            for row in value.get("items", [])
            if isinstance(row, Mapping)
        )
    elif resource == "checks":
        lines.extend(["| # | Kind | State | Detail |", "|---:|---|---|---|"])
        lines.extend(
            f"| {row.get('ordinal', '')} | `{row.get('kind', '')}` | `{row.get('state', '')}` | {row.get('detail', '')} |"
            for row in value.get("items", [])
            if isinstance(row, Mapping)
        )
    else:
        lines.extend(["| Field | Value |", "|---|---|"])
        lines.extend(
            f"| {key} | `{item}` |" for key, item in value.get("items", [{}])[0].items()
        ) if value.get("items") else None
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_BOUNDARY,
        "decisions": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryDecision
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryState
        ],
        "resources": ["summary", "entries", "checks"],
        "exact_files": ["manifest.json", "history.json"],
        "max_entries": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES,
        "max_checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_CHECKS,
        "bounded": True,
        "append_only": True,
        "optimistic_head_guard": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_VERSION,
        "operations": [
            "build",
            "append",
            "verify",
            "write",
            "load",
            "query",
            "json",
            "csv",
            "markdown",
        ],
        "append_only": True,
        "optimistic_head_guard": True,
        "atomic_write": True,
        "canonical_json": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "entries", "checks"],
        "filters": ["decision", "state", "accepted", "release_ready", "text", "offset", "limit"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "entries", "checks"],
        "filters": ["decision", "state", "accepted", "release_ready", "text", "offset", "limit"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }
