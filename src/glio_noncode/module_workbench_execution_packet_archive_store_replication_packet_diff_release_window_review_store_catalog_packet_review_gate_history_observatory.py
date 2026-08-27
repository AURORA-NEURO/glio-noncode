"""Deterministic longitudinal observatory for packet-review gate histories."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_OBSERVATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX
    + "-observation"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_TRANSITION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX
    + "-transition"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX
    + "-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_ROLLUP_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX
    + "-rollup"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERIFICATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX
    + "-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_DOCUMENT = "observatory.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS = 128
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_TRANSITIONS = 127
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_CHECKS = 32

History = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory
HistoryEntry = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryState(
    StrEnum
):
    EMPTY = "empty"
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    MIXED = "mixed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind(
    StrEnum
):
    STABLE = "stable"
    PROMOTED = "promoted"
    RECOVERED = "recovered"
    REGRESSED = "regressed"
    HELD = "held"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"
    CHANGED = "changed"


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


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _delta(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not -maximum <= value <= maximum:
        raise ValidationError(f"{field} is outside its bounded range")
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


def _enum(value: Any, field: str, values: type[StrEnum]) -> str:
    value = _text(value, field, 64)
    if value not in {item.value for item in values}:
        raise ValidationError(f"{field} is invalid")
    return value


def _json_value(value: Any, field: str) -> Any:
    try:
        result = json.loads(canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be canonical JSON data") from exc
    if not _public(result):
        raise ValidationError(f"{field} crosses the public boundary")
    return result


def _history_entry_decision(history: History) -> str:
    if not history.entries:
        raise ValidationError("history must contain a head entry")
    return _text(history.entries[-1].decision, "history head decision", 32)


def _observatory_state(states: Sequence[str]) -> str:
    if not states:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryState.EMPTY.value
    distinct = set(states)
    if len(distinct) == 1:
        return next(iter(distinct))
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryState.MIXED.value


def _classify_transition(
    previous: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation,
    current: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation,
) -> str:
    if (
        previous.state == current.state
        and previous.decision == current.decision
        and previous.release_ready == current.release_ready
        and previous.accepted == current.accepted
    ):
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind.STABLE.value
    if not previous.release_ready and current.release_ready:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind.RECOVERED.value
    if previous.release_ready and not current.release_ready:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind.REGRESSED.value
    if current.decision == "promote":
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind.PROMOTED.value
    if current.decision == "hold":
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind.HELD.value
    if current.decision == "block":
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind.BLOCKED.value
    if current.decision == "supersede":
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind.SUPERSEDED.value
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind.CHANGED.value


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_observation(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_OBSERVATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation:
    """A path-free verified projection of one retained gate history."""

    def __init__(
        self,
        *,
        ordinal: int,
        observation_id: str,
        history_id: str,
        history_address: str,
        history_verification_address: str,
        gate_address: str,
        head_address: str,
        first_entry_address: str,
        decision: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        entry_count: int,
        promote_count: int,
        hold_count: int,
        block_count: int,
        supersede_count: int,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.observation_id = observation_id
        self.history_id = history_id
        self.history_address = history_address
        self.history_verification_address = history_verification_address
        self.gate_address = gate_address
        self.head_address = head_address
        self.first_entry_address = first_entry_address
        self.decision = decision
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.entry_count = entry_count
        self.promote_count = promote_count
        self.hold_count = hold_count
        self.block_count = block_count
        self.supersede_count = supersede_count
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "observatory observation ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS
            - 1,
        )
        _text(self.observation_id, "observatory observation ID", 256)
        _text(self.history_id, "observatory history ID", 256)
        _address(self.history_address, "observatory history address")
        _address(self.history_verification_address, "observatory history verification address")
        _address(self.gate_address, "observatory gate address")
        _address(self.head_address, "observatory head address")
        _address(self.first_entry_address, "observatory first entry address")
        _text(self.decision, "observatory observation decision", 32)
        if self.decision not in {"promote", "hold", "block", "supersede"}:
            raise ValidationError("observatory observation decision is invalid")
        if self.state not in {"ready", "held", "blocked"}:
            raise ValidationError("observatory observation state is invalid")
        _bool(self.accepted, "observatory observation accepted")
        _bool(self.release_ready, "observatory observation release-ready")
        _count(self.entry_count, "observatory observation entry count", 256, positive=True)
        for value, field in (
            (self.promote_count, "promote"),
            (self.hold_count, "hold"),
            (self.block_count, "block"),
            (self.supersede_count, "supersede"),
        ):
            _count(value, f"observatory observation {field} count", self.entry_count)
        if (
            self.promote_count + self.hold_count + self.block_count + self.supersede_count
            != self.entry_count
        ):
            raise ValidationError("observatory observation decision counts are not conserved")
        _text(self.detail, "observatory observation detail")
        _address(self.content_address, "observatory observation content address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory observation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "observation_id": self.observation_id,
            "history_id": self.history_id,
            "history_address": self.history_address,
            "history_verification_address": self.history_verification_address,
            "gate_address": self.gate_address,
            "head_address": self.head_address,
            "first_entry_address": self.first_entry_address,
            "decision": self.decision,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "entry_count": self.entry_count,
            "promote_count": self.promote_count,
            "hold_count": self.hold_count,
            "block_count": self.block_count,
            "supersede_count": self.supersede_count,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_transition(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_TRANSITION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition:
    """A deterministic comparison between adjacent retained histories."""

    def __init__(
        self,
        *,
        ordinal: int,
        previous_observation_id: str,
        current_observation_id: str,
        previous_observation_address: str,
        current_observation_address: str,
        kind: str,
        previous_state: str,
        current_state: str,
        previous_decision: str,
        current_decision: str,
        accepted_changed: bool,
        release_ready_changed: bool,
        entry_count_delta: int,
        promote_count_delta: int,
        hold_count_delta: int,
        block_count_delta: int,
        supersede_count_delta: int,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.previous_observation_id = previous_observation_id
        self.current_observation_id = current_observation_id
        self.previous_observation_address = previous_observation_address
        self.current_observation_address = current_observation_address
        self.kind = kind
        self.previous_state = previous_state
        self.current_state = current_state
        self.previous_decision = previous_decision
        self.current_decision = current_decision
        self.accepted_changed = accepted_changed
        self.release_ready_changed = release_ready_changed
        self.entry_count_delta = entry_count_delta
        self.promote_count_delta = promote_count_delta
        self.hold_count_delta = hold_count_delta
        self.block_count_delta = block_count_delta
        self.supersede_count_delta = supersede_count_delta
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "observatory transition ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_TRANSITIONS
            - 1,
        )
        _text(self.previous_observation_id, "previous observation ID", 256)
        _text(self.current_observation_id, "current observation ID", 256)
        _address(self.previous_observation_address, "previous observation address")
        _address(self.current_observation_address, "current observation address")
        if self.kind not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind
        }:
            raise ValidationError("observatory transition kind is invalid")
        for value, field in (
            (self.previous_state, "previous state"),
            (self.current_state, "current state"),
            (self.previous_decision, "previous decision"),
            (self.current_decision, "current decision"),
        ):
            _text(value, f"observatory {field}", 32)
        _bool(self.accepted_changed, "observatory accepted change")
        _bool(self.release_ready_changed, "observatory release-ready change")
        for value, field in (
            (self.entry_count_delta, "entry count delta"),
            (self.promote_count_delta, "promote count delta"),
            (self.hold_count_delta, "hold count delta"),
            (self.block_count_delta, "block count delta"),
            (self.supersede_count_delta, "supersede count delta"),
        ):
            _delta(
                value,
                f"observatory {field}",
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
            )
        _text(self.detail, "observatory transition detail")
        _address(self.content_address, "observatory transition content address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory transition crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "previous_observation_id": self.previous_observation_id,
            "current_observation_id": self.current_observation_id,
            "previous_observation_address": self.previous_observation_address,
            "current_observation_address": self.current_observation_address,
            "kind": self.kind,
            "previous_state": self.previous_state,
            "current_state": self.current_state,
            "previous_decision": self.previous_decision,
            "current_decision": self.current_decision,
            "accepted_changed": self.accepted_changed,
            "release_ready_changed": self.release_ready_changed,
            "entry_count_delta": self.entry_count_delta,
            "promote_count_delta": self.promote_count_delta,
            "hold_count_delta": self.hold_count_delta,
            "block_count_delta": self.block_count_delta,
            "supersede_count_delta": self.supersede_count_delta,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck:
    """An addressed, reviewable observatory invariant result."""

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
        self.expected = _json_value(expected, "observatory check expected")
        self.observed = _json_value(observed, "observatory check observed")
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "observatory check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "observatory check kind", 128)
        _bool(self.passed, "observatory check passed")
        _text(self.detail, "observatory check detail")
        _address(self.content_address, "observatory check content address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_rollup(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRollup,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_ROLLUP_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRollup:
    """Conserved aggregate counts for an observatory."""

    def __init__(
        self,
        *,
        observation_count: int,
        transition_count: int,
        total_entry_count: int,
        ready_count: int,
        held_count: int,
        blocked_count: int,
        accepted_count: int,
        release_ready_count: int,
        promote_count: int,
        hold_count: int,
        block_count: int,
        supersede_count: int,
        stable_count: int,
        promoted_count: int,
        recovered_count: int,
        regressed_count: int,
        held_transition_count: int,
        blocked_transition_count: int,
        superseded_count: int,
        changed_count: int,
        unique_history_count: int,
        unique_gate_count: int,
        unique_head_count: int,
        content_address: str,
    ) -> None:
        self.observation_count = observation_count
        self.transition_count = transition_count
        self.total_entry_count = total_entry_count
        self.ready_count = ready_count
        self.held_count = held_count
        self.blocked_count = blocked_count
        self.accepted_count = accepted_count
        self.release_ready_count = release_ready_count
        self.promote_count = promote_count
        self.hold_count = hold_count
        self.block_count = block_count
        self.supersede_count = supersede_count
        self.stable_count = stable_count
        self.promoted_count = promoted_count
        self.recovered_count = recovered_count
        self.regressed_count = regressed_count
        self.held_transition_count = held_transition_count
        self.blocked_transition_count = blocked_transition_count
        self.superseded_count = superseded_count
        self.changed_count = changed_count
        self.unique_history_count = unique_history_count
        self.unique_gate_count = unique_gate_count
        self.unique_head_count = unique_head_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.observation_count,
            "observatory rollup observation count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
            positive=True,
        )
        _count(
            self.transition_count,
            "observatory rollup transition count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_TRANSITIONS,
        )
        _count(
            self.total_entry_count,
            "observatory rollup entry count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS
            * 256,
        )
        for value, field in (
            (self.ready_count, "ready"),
            (self.held_count, "held"),
            (self.blocked_count, "blocked"),
            (self.accepted_count, "accepted"),
            (self.release_ready_count, "release-ready"),
            (self.promote_count, "promote"),
            (self.hold_count, "hold"),
            (self.block_count, "block"),
            (self.supersede_count, "supersede"),
            (self.stable_count, "stable"),
            (self.promoted_count, "promoted"),
            (self.recovered_count, "recovered"),
            (self.regressed_count, "regressed"),
            (self.held_transition_count, "held transition"),
            (self.blocked_transition_count, "blocked transition"),
            (self.superseded_count, "superseded"),
            (self.changed_count, "changed"),
        ):
            _count(
                value,
                f"observatory rollup {field} count",
                max(self.observation_count, self.transition_count),
            )
        if self.ready_count + self.held_count + self.blocked_count != self.observation_count:
            raise ValidationError("observatory state rollup is not conserved")
        if (
            self.accepted_count > self.observation_count
            or self.release_ready_count > self.observation_count
        ):
            raise ValidationError("observatory boolean rollup is not bounded")
        if (
            self.promote_count + self.hold_count + self.block_count + self.supersede_count
            != self.observation_count
        ):
            raise ValidationError("observatory decision rollup is not conserved")
        if (
            self.stable_count
            + self.promoted_count
            + self.recovered_count
            + self.regressed_count
            + self.held_transition_count
            + self.blocked_transition_count
            + self.superseded_count
            + self.changed_count
            != self.transition_count
        ):
            raise ValidationError("observatory transition rollup is not conserved")
        _count(
            self.unique_history_count,
            "observatory unique history count",
            self.observation_count,
            positive=True,
        )
        _count(
            self.unique_gate_count,
            "observatory unique gate count",
            self.observation_count,
            positive=True,
        )
        _count(
            self.unique_head_count,
            "observatory unique head count",
            self.observation_count,
            positive=True,
        )
        _address(self.content_address, "observatory rollup content address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory rollup crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_count": self.observation_count,
            "transition_count": self.transition_count,
            "total_entry_count": self.total_entry_count,
            "ready_count": self.ready_count,
            "held_count": self.held_count,
            "blocked_count": self.blocked_count,
            "accepted_count": self.accepted_count,
            "release_ready_count": self.release_ready_count,
            "promote_count": self.promote_count,
            "hold_count": self.hold_count,
            "block_count": self.block_count,
            "supersede_count": self.supersede_count,
            "stable_count": self.stable_count,
            "promoted_count": self.promoted_count,
            "recovered_count": self.recovered_count,
            "regressed_count": self.regressed_count,
            "held_transition_count": self.held_transition_count,
            "blocked_transition_count": self.blocked_transition_count,
            "superseded_count": self.superseded_count,
            "changed_count": self.changed_count,
            "unique_history_count": self.unique_history_count,
            "unique_gate_count": self.unique_gate_count,
            "unique_head_count": self.unique_head_count,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory:
    """A deterministic, path-free view over a bounded ordered history set."""

    def __init__(
        self,
        *,
        observatory_id: str,
        version: str,
        boundary: str,
        observation_count: int,
        transition_count: int,
        state: str,
        accepted: bool,
        release_ready: bool,
        latest_observation_address: str,
        observations: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation,
            ...,
        ],
        transitions: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition,
            ...,
        ],
        rollup: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRollup,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.observatory_id = observatory_id
        self.version = version
        self.boundary = boundary
        self.observation_count = observation_count
        self.transition_count = transition_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.latest_observation_address = latest_observation_address
        self.observations = tuple(observations)
        self.transitions = tuple(transitions)
        self.rollup = rollup
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.observatory_id, "observatory ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERSION
        ):
            raise ValidationError("observatory version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_BOUNDARY
        ):
            raise ValidationError("observatory boundary is invalid")
        _count(
            self.observation_count,
            "observatory observation count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
            positive=True,
        )
        _count(
            self.transition_count,
            "observatory transition count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_TRANSITIONS,
        )
        if (
            self.observation_count != len(self.observations)
            or self.transition_count != len(self.transitions)
            or self.transition_count != self.observation_count - 1
        ):
            raise ValidationError("observatory sequence counts are not conserved")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryState
            if item
            != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryState.EMPTY
        }:
            raise ValidationError("observatory state is invalid")
        _bool(self.accepted, "observatory accepted")
        _bool(self.release_ready, "observatory release-ready")
        _address(self.latest_observation_address, "observatory latest observation address")
        if not isinstance(
            self.rollup,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRollup,
        ):
            raise ValidationError("observatory rollup must be typed")
        if (
            len(self.checks) == 0
            or len(self.checks)
            > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_CHECKS
        ):
            raise ValidationError("observatory checks are outside their bounded range")
        for ordinal, item in enumerate(self.observations):
            if (
                not isinstance(
                    item,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation,
                )
                or item.ordinal != ordinal
            ):
                raise ValidationError("observatory observations are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_observation(
                    item
                )
                != item.content_address
            ):
                raise ValidationError("observatory observation address is invalid")
        for ordinal, item in enumerate(self.transitions):
            if (
                not isinstance(
                    item,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition,
                )
                or item.ordinal != ordinal
            ):
                raise ValidationError("observatory transitions are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_transition(
                    item
                )
                != item.content_address
            ):
                raise ValidationError("observatory transition address is invalid")
        if self.latest_observation_address != self.observations[-1].content_address:
            raise ValidationError("observatory latest observation is not conserved")
        if (
            self.rollup.observation_count != self.observation_count
            or self.rollup.transition_count != self.transition_count
        ):
            raise ValidationError("observatory rollup counts are not conserved")
        if self.state != _observatory_state(tuple(item.state for item in self.observations)):
            raise ValidationError("observatory state projection is not conserved")
        if self.release_ready != self.observations[-1].release_ready:
            raise ValidationError("observatory release-ready projection is not conserved")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("observatory embedded check projection is not conserved")
        _address(self.content_address, "observatory content address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "observatory_id": self.observatory_id,
            "version": self.version,
            "boundary": self.boundary,
            "observation_count": self.observation_count,
            "transition_count": self.transition_count,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "latest_observation_address": self.latest_observation_address,
            "rollup": self.rollup.to_dict(),
            "check_count": len(self.checks),
            "content_address": self.content_address,
        }

    def to_dict(
        self,
        *,
        include_observations: bool = True,
        include_transitions: bool = True,
        include_checks: bool = True,
    ) -> dict[str, Any]:
        body = self.summary()
        if include_observations:
            body["observations"] = [item.to_dict() for item in self.observations]
        if include_transitions:
            body["transitions"] = [item.to_dict() for item in self.transitions]
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def _observation_from_history(
    history: History, ordinal: int, observation_id: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation:
    verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
        history
    )
    if not verification.accepted:
        raise ValidationError("observatory input history verification failed")
    head = history.entries[-1]
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation(
        ordinal=ordinal,
        observation_id=observation_id,
        history_id=history.history_id,
        history_address=history.content_address,
        history_verification_address=verification.content_address,
        gate_address=history.gate_address,
        head_address=history.head_address,
        first_entry_address=history.entries[0].content_address,
        decision=head.decision,
        state=head.state,
        accepted=head.accepted,
        release_ready=head.release_ready,
        entry_count=history.entry_count,
        promote_count=history.promote_count,
        hold_count=history.hold_count,
        block_count=history.block_count,
        supersede_count=history.supersede_count,
        detail="verified retained gate history observation",
        content_address="pending:observation",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation(
        **(
            provisional.to_dict()
            | {
                "content_address": address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_observation(
                    provisional
                )
            }
        )
    )


def _transition_from_observations(
    previous: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation,
    current: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation,
    ordinal: int,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition:
    body = {
        "ordinal": ordinal,
        "previous_observation_id": previous.observation_id,
        "current_observation_id": current.observation_id,
        "previous_observation_address": previous.content_address,
        "current_observation_address": current.content_address,
        "kind": _classify_transition(previous, current),
        "previous_state": previous.state,
        "current_state": current.state,
        "previous_decision": previous.decision,
        "current_decision": current.decision,
        "accepted_changed": previous.accepted != current.accepted,
        "release_ready_changed": previous.release_ready != current.release_ready,
        "entry_count_delta": current.entry_count - previous.entry_count,
        "promote_count_delta": current.promote_count - previous.promote_count,
        "hold_count_delta": current.hold_count - previous.hold_count,
        "block_count_delta": current.block_count - previous.block_count,
        "supersede_count_delta": current.supersede_count - previous.supersede_count,
        "detail": "compared adjacent verified history observations",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition(
        **body, content_address="pending:transition"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition(
        **(
            provisional.to_dict()
            | {
                "content_address": address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_transition(
                    provisional
                )
            }
        )
    )


def _rollup(
    observations: Sequence[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation
    ],
    transitions: Sequence[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition
    ],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRollup:
    body = {
        "observation_count": len(observations),
        "transition_count": len(transitions),
        "total_entry_count": sum(item.entry_count for item in observations),
        "ready_count": sum(item.state == "ready" for item in observations),
        "held_count": sum(item.state == "held" for item in observations),
        "blocked_count": sum(item.state == "blocked" for item in observations),
        "accepted_count": sum(item.accepted for item in observations),
        "release_ready_count": sum(item.release_ready for item in observations),
        "promote_count": sum(item.decision == "promote" for item in observations),
        "hold_count": sum(item.decision == "hold" for item in observations),
        "block_count": sum(item.decision == "block" for item in observations),
        "supersede_count": sum(item.decision == "supersede" for item in observations),
        "stable_count": sum(item.kind == "stable" for item in transitions),
        "promoted_count": sum(item.kind == "promoted" for item in transitions),
        "recovered_count": sum(item.kind == "recovered" for item in transitions),
        "regressed_count": sum(item.kind == "regressed" for item in transitions),
        "held_transition_count": sum(item.kind == "held" for item in transitions),
        "blocked_transition_count": sum(item.kind == "blocked" for item in transitions),
        "superseded_count": sum(item.kind == "superseded" for item in transitions),
        "changed_count": sum(item.kind == "changed" for item in transitions),
        "unique_history_count": len({item.history_address for item in observations}),
        "unique_gate_count": len({item.gate_address for item in observations}),
        "unique_head_count": len({item.head_address for item in observations}),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRollup(
        **body, content_address="pending:rollup"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRollup(
        **(
            provisional.to_dict()
            | {
                "content_address": address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_rollup(
                    provisional
                )
            }
        )
    )


def _check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "passed": bool(passed),
        "expected": _json_value(expected, "check expected"),
        "observed": _json_value(observed, "check observed"),
        "detail": _text(detail, "check detail"),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck(
        **(
            provisional.to_dict()
            | {
                "content_address": address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_check(
                    provisional
                )
            }
        )
    )


def _embedded_checks(
    observations: Sequence[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation
    ],
    transitions: Sequence[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition
    ],
    rollup: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRollup,
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck,
    ...,
]:
    return tuple(
        (
            _check(ordinal, kind, passed, expected, observed, detail)
            for ordinal, (kind, passed, expected, observed, detail) in enumerate(
                (
                    (
                        "observation-count",
                        len(observations) > 0
                        and len(observations)
                        <= MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
                        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
                        len(observations),
                        "observations are present and bounded",
                    ),
                    (
                        "observation-ordinals",
                        tuple(item.ordinal for item in observations)
                        == tuple(range(len(observations))),
                        tuple(range(len(observations))),
                        tuple(item.ordinal for item in observations),
                        "observation ordinals are contiguous",
                    ),
                    (
                        "observation-addresses",
                        all(
                            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_observation(
                                item
                            )
                            == item.content_address
                            for item in observations
                        ),
                        True,
                        tuple(item.content_address for item in observations),
                        "observation addresses are independently recomputed",
                    ),
                    (
                        "transition-count",
                        len(transitions) == max(0, len(observations) - 1),
                        max(0, len(observations) - 1),
                        len(transitions),
                        "one transition exists for every adjacent pair",
                    ),
                    (
                        "transition-addresses",
                        all(
                            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_transition(
                                item
                            )
                            == item.content_address
                            for item in transitions
                        ),
                        True,
                        tuple(item.content_address for item in transitions),
                        "transition addresses are independently recomputed",
                    ),
                    (
                        "transition-endpoints",
                        all(
                            item.previous_observation_address
                            == observations[item.ordinal].content_address
                            and item.current_observation_address
                            == observations[item.ordinal + 1].content_address
                            for item in transitions
                        ),
                        True,
                        tuple(
                            (item.previous_observation_address, item.current_observation_address)
                            for item in transitions
                        ),
                        "transition endpoints follow observation order",
                    ),
                    (
                        "rollup-conservation",
                        rollup.observation_count == len(observations)
                        and rollup.transition_count == len(transitions)
                        and rollup.total_entry_count
                        == sum(item.entry_count for item in observations),
                        rollup.to_dict(),
                        {
                            "observation_count": len(observations),
                            "transition_count": len(transitions),
                            "total_entry_count": sum(item.entry_count for item in observations),
                        },
                        "rollup conserves sequence and entry counts",
                    ),
                    (
                        "transition-classification",
                        all(
                            item.kind
                            == _classify_transition(
                                observations[item.ordinal], observations[item.ordinal + 1]
                            )
                            for item in transitions
                        ),
                        True,
                        tuple(item.kind for item in transitions),
                        "transition classifications are recomputed from endpoints",
                    ),
                    (
                        "public-boundary",
                        _public(
                            {
                                "observations": observations,
                                "transitions": transitions,
                                "rollup": rollup,
                            }
                        ),
                        True,
                        True,
                        "embedded observatory projections contain only public fields",
                    ),
                    (
                        "unique-history-addresses",
                        len({item.history_address for item in observations})
                        == rollup.unique_history_count,
                        rollup.unique_history_count,
                        len({item.history_address for item in observations}),
                        "history address cardinality is conserved",
                    ),
                )
            )
        )
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
    histories: Sequence[History],
    *,
    observatory_id: str = "glio-noncode-review-store-catalog-packet-review-gate-history-observatory",
    observation_ids: Sequence[str] | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory:
    if not isinstance(histories, Sequence) or isinstance(histories, (str, bytes)):
        raise ValidationError("observatory histories must be a bounded sequence")
    if (
        not histories
        or len(histories)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS
    ):
        raise ValidationError("observatory history count is outside its bounded range")
    ids = (
        tuple(observation_ids)
        if observation_ids is not None
        else tuple(f"observation-{index:04d}" for index in range(len(histories)))
    )
    if len(ids) != len(histories) or len(set(ids)) != len(ids):
        raise ValidationError("observatory observation IDs must be unique and conserved")
    observations = tuple(
        _observation_from_history(history, ordinal, _text(observation_id, "observation ID", 256))
        for ordinal, (history, observation_id) in enumerate(zip(histories, ids, strict=True))
    )
    transitions = tuple(
        _transition_from_observations(previous, current, ordinal)
        for ordinal, (previous, current) in enumerate(
            zip(observations, observations[1:], strict=False)
        )
    )
    rollup = _rollup(observations, transitions)
    checks = _embedded_checks(observations, transitions, rollup)
    state = _observatory_state(tuple(item.state for item in observations))
    accepted = all(item.passed for item in checks)
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory(
        observatory_id=_text(observatory_id, "observatory ID", 256),
        version=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERSION,
        boundary=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_BOUNDARY,
        observation_count=len(observations),
        transition_count=len(transitions),
        state=state,
        accepted=accepted,
        release_ready=observations[-1].release_ready,
        latest_observation_address=observations[-1].content_address,
        observations=observations,
        transitions=transitions,
        rollup=rollup,
        checks=checks,
        content_address="pending:observatory",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory(
        observatory_id=provisional.observatory_id,
        version=provisional.version,
        boundary=provisional.boundary,
        observation_count=provisional.observation_count,
        transition_count=provisional.transition_count,
        state=provisional.state,
        accepted=provisional.accepted,
        release_ready=provisional.release_ready,
        latest_observation_address=provisional.latest_observation_address,
        observations=observations,
        transitions=transitions,
        rollup=rollup,
        checks=checks,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_from_directories(
    directories: Iterable[str | Path],
    *,
    observatory_id: str = "glio-noncode-review-store-catalog-packet-review-gate-history-observatory",
    observation_ids: Sequence[str] | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory:
    paths = tuple(Path(item) for item in directories)
    if (
        not paths
        or len(paths)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS
    ):
        raise ValidationError("observatory history directory count is outside its bounded range")
    histories = tuple(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            path
        )
        for path in paths
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
        histories, observatory_id=observatory_id, observation_ids=observation_ids
    )


def _entry_from_mapping(value: Mapping[str, Any]) -> HistoryEntry:
    return HistoryEntry(
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


def history_from_mapping(value: Mapping[str, Any]) -> History:
    if not isinstance(value, Mapping):
        raise ValidationError("observatory history mapping must be an object")
    body = dict(value)
    entries = body.pop("entries", None)
    if not isinstance(entries, list):
        raise ValidationError("observatory history mapping requires entries")
    try:
        history = History(
            **(body | {"entries": tuple(_entry_from_mapping(item) for item in entries)})
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("observatory history mapping is invalid") from exc
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
        history
    ).accepted:
        raise ValidationError("observatory history mapping is not independently verified")
    return history


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_from_mappings(
    histories: Sequence[Mapping[str, Any]],
    *,
    observatory_id: str = "glio-noncode-review-store-catalog-packet-review-gate-history-observatory",
    observation_ids: Sequence[str] | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory:
    if not isinstance(histories, Sequence) or isinstance(histories, (str, bytes)):
        raise ValidationError("observatory histories must be a sequence of objects")
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
        tuple(history_from_mapping(item) for item in histories),
        observatory_id=observatory_id,
        observation_ids=observation_ids,
    )


def _observation_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryObservation(
        **dict(value)
    )


def _transition_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransition(
        **dict(value)
    )


def _check_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck(
        **dict(value)
    )


def _rollup_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRollup:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRollup(
        **dict(value)
    )


def observatory_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory:
    if not isinstance(value, Mapping):
        raise ValidationError("observatory mapping must be an object")
    body = dict(value)
    try:
        observations = tuple(_observation_from_dict(item) for item in body.pop("observations"))
        transitions = tuple(_transition_from_dict(item) for item in body.pop("transitions"))
        checks = tuple(_check_from_dict(item) for item in body.pop("checks"))
        body.pop("check_count", None)
        rollup = _rollup_from_dict(body.pop("rollup"))
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory(
            **(
                body
                | {
                    "observations": observations,
                    "transitions": transitions,
                    "checks": checks,
                    "rollup": rollup,
                }
            )
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("observatory mapping structure is invalid") from exc


def _verification_check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck:
    return _check(ordinal, kind, passed, expected, observed, detail)


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryVerification:
    """Independent verification of observatory projections and conservation."""

    def __init__(
        self,
        *,
        observatory_address: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.observatory_address = observatory_address
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.observatory_address, "observatory verification address")
        _count(
            self.check_count,
            "observatory verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_CHECKS
            + 8,
            positive=True,
        )
        _count(self.passed_count, "observatory verification passed count", self.check_count)
        _count(self.failed_count, "observatory verification failed count", self.check_count)
        if (
            self.check_count != len(self.checks)
            or self.passed_count + self.failed_count != self.check_count
            or self.accepted != (self.failed_count == 0)
        ):
            raise ValidationError("observatory verification counts are not conserved")
        _bool(self.accepted, "observatory verification accepted")
        _address(self.content_address, "observatory verification content address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory verification crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observatory_address": self.observatory_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryVerification:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
    ):
        raise ValidationError("observatory verification requires a typed observatory")
    observations = value.observations
    transitions = value.transitions
    rollup = value.rollup
    checks = [
        _verification_check(
            0,
            "observatory-address",
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value
            )
            == value.content_address,
            value.content_address,
            value.content_address,
            "observatory aggregate address is recomputed",
        ),
        _verification_check(
            1,
            "observation-addresses",
            all(
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_observation(
                    item
                )
                == item.content_address
                for item in observations
            ),
            True,
            tuple(item.content_address for item in observations),
            "observation addresses are recomputed",
        ),
        _verification_check(
            2,
            "transition-addresses",
            all(
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_transition(
                    item
                )
                == item.content_address
                for item in transitions
            ),
            True,
            tuple(item.content_address for item in transitions),
            "transition addresses are recomputed",
        ),
        _verification_check(
            3,
            "check-addresses",
            all(
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_check(
                    item
                )
                == item.content_address
                for item in value.checks
            ),
            True,
            tuple(item.content_address for item in value.checks),
            "embedded check addresses are recomputed",
        ),
        _verification_check(
            4,
            "sequence-continuity",
            tuple(item.ordinal for item in observations) == tuple(range(value.observation_count))
            and tuple(item.ordinal for item in transitions) == tuple(range(value.transition_count)),
            True,
            {
                "observation_ordinals": tuple(item.ordinal for item in observations),
                "transition_ordinals": tuple(item.ordinal for item in transitions),
            },
            "sequence ordinals are contiguous",
        ),
        _verification_check(
            5,
            "endpoint-continuity",
            all(
                item.previous_observation_address == observations[item.ordinal].content_address
                and item.current_observation_address
                == observations[item.ordinal + 1].content_address
                for item in transitions
            ),
            True,
            tuple(
                (item.previous_observation_address, item.current_observation_address)
                for item in transitions
            ),
            "transition endpoints follow the ordered observations",
        ),
        _verification_check(
            6,
            "rollup-address",
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_rollup(
                rollup
            )
            == rollup.content_address,
            rollup.content_address,
            rollup.content_address,
            "rollup address is recomputed",
        ),
        _verification_check(
            7,
            "rollup-conservation",
            rollup.to_dict() == _rollup(observations, transitions).to_dict(),
            _rollup(observations, transitions).to_dict(),
            rollup.to_dict(),
            "rollup is independently rebuilt",
        ),
        _verification_check(
            8,
            "state-projection",
            value.state == _observatory_state(tuple(item.state for item in observations)),
            _observatory_state(tuple(item.state for item in observations)),
            value.state,
            "observatory state follows all observations",
        ),
        _verification_check(
            9,
            "terminal-projection",
            value.latest_observation_address == observations[-1].content_address
            and value.release_ready == observations[-1].release_ready,
            {
                "latest_observation_address": observations[-1].content_address,
                "release_ready": observations[-1].release_ready,
            },
            {
                "latest_observation_address": value.latest_observation_address,
                "release_ready": value.release_ready,
            },
            "terminal release projection follows the latest observation",
        ),
        _verification_check(
            10,
            "public-boundary",
            _public(value.to_dict()),
            True,
            _public(value.to_dict()),
            "observatory projection is identity-free and public",
        ),
        _verification_check(
            11,
            "embedded-acceptance",
            value.accepted == all(item.passed for item in value.checks),
            all(item.passed for item in value.checks),
            value.accepted,
            "embedded check acceptance is conserved",
        ),
    ]
    body = {
        "observatory_address": value.content_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": tuple(checks),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryVerification(
        **body, content_address="pending:verification"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryVerification(
        observatory_address=provisional.observatory_address,
        check_count=provisional.check_count,
        passed_count=provisional.passed_count,
        failed_count=provisional.failed_count,
        accepted=provisional.accepted,
        checks=provisional.checks,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_verification(
            provisional
        ),
    )


def _require_verified(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
) -> None:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
        value
    ).accepted:
        raise ValidationError("observatory verification failed")


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    _require_verified(value)
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("observatory destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        document = canonical_bytes(value.to_dict())
        manifest_body = {
            "manifest_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERSION,
            "observatory": value.to_dict(),
            "byte_count": len(document),
            "byte_address": hash_bytes(
                document,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX
                + "-bytes",
            ),
        }
        manifest = manifest_body | {
            "manifest_address": content_hash(
                manifest_body,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX
                + "-manifest",
            )
        }
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_DOCUMENT
        ).write_bytes(document)
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MANIFEST
        ).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("observatory destination is not a regular directory")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("observatory directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MANIFEST,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_DOCUMENT,
    }
    children = tuple(directory.iterdir())
    if (
        any(item.is_symlink() or not item.is_file() for item in children)
        or {item.name for item in children} != expected
    ):
        raise ValidationError("observatory files do not match the published set")
    manifest_raw = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MANIFEST
    ).read_bytes()
    document_raw = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_DOCUMENT
    ).read_bytes()
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
        document = json.loads(document_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("observatory files are not valid JSON") from exc
    if (
        not isinstance(manifest, dict)
        or not isinstance(document, dict)
        or canonical_bytes(manifest) != manifest_raw
        or canonical_bytes(document) != document_raw
    ):
        raise ValidationError("observatory files must be canonical JSON objects")
    if (
        set(manifest)
        != {"manifest_version", "observatory", "byte_count", "byte_address", "manifest_address"}
        or manifest.get("manifest_version")
        != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERSION
    ):
        raise ValidationError("observatory manifest structure is invalid")
    manifest_body = {key: item for key, item in manifest.items() if key != "manifest_address"}
    if manifest["manifest_address"] != content_hash(
        manifest_body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX
        + "-manifest",
    ):
        raise ValidationError("observatory manifest address mismatch")
    if (
        manifest["observatory"] != document
        or manifest["byte_count"] != len(document_raw)
        or manifest["byte_address"]
        != hash_bytes(
            document_raw,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PREFIX
            + "-bytes",
        )
    ):
        raise ValidationError("observatory document does not match the manifest")
    value = observatory_from_mapping(document)
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
        value
    ).accepted:
        raise ValidationError("observatory verification failed")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
) -> str:
    _require_verified(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
) -> str:
    _require_verified(value)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "observation_id",
            "history_id",
            "history_address",
            "history_verification_address",
            "gate_address",
            "head_address",
            "decision",
            "state",
            "accepted",
            "release_ready",
            "entry_count",
            "promote_count",
            "hold_count",
            "block_count",
            "supersede_count",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for item in value.observations:
        row = item.to_dict()
        row.pop("first_entry_address", None)
        row.pop("detail", None)
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
) -> str:
    _require_verified(value)
    lines = [
        "# Packet-review gate history observatory",
        "",
        f"- State: `{value.state}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Release ready: `{str(value.release_ready).lower()}`",
        f"- Observations: `{value.observation_count}`",
        f"- Transitions: `{value.transition_count}`",
        "",
        "## Rollup",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, item in value.rollup.to_dict().items():
        if key != "content_address":
            lines.append(f"| {key} | `{item}` |")
    lines.extend(
        [
            "",
            "## Observations",
            "",
            "| # | ID | State | Decision | Accepted | Ready | Entries |",
            "|---:|---|---|---|---|---|---:|",
        ]
    )
    lines.extend(
        f"| {item.ordinal} | `{item.observation_id}` | `{item.state}` | `{item.decision}` | `{str(item.accepted).lower()}` | `{str(item.release_ready).lower()}` | {item.entry_count} |"
        for item in value.observations
    )
    lines.extend(
        [
            "",
            "## Transitions",
            "",
            "| # | From | To | Kind | Ready change |",
            "|---:|---|---|---|---|",
        ]
    )
    lines.extend(
        f"| {item.ordinal} | `{item.previous_observation_id}` | `{item.current_observation_id}` | `{item.kind}` | `{str(item.release_ready_changed).lower()}` |"
        for item in value.transitions
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_verification_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryVerification,
) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_verification_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryVerification,
) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "kind",
            "passed",
            "expected",
            "observed",
            "detail",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["expected"] = canonical_json(row["expected"])
        row["observed"] = canonical_json(row["observed"])
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_verification_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryVerification,
) -> str:
    lines = [
        "# Packet-review gate history observatory verification",
        "",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Checks: `{value.check_count}`",
        f"- Passed: `{value.passed_count}`",
        f"- Failed: `{value.failed_count}`",
        "",
        "| # | Kind | Passed | Detail |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.kind}` | `{str(item.passed).lower()}` | {item.detail} |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQuery:
    """Bounded, identity-free observatory query parameters."""

    def __init__(
        self,
        *,
        resource: str = "summary",
        state: str | None = None,
        transition_kind: str | None = None,
        accepted: bool | None = None,
        release_ready: bool | None = None,
        text: str | None = None,
        offset: int = 0,
        limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_DEFAULT_LIMIT,
    ) -> None:
        self.resource = _text(resource, "observatory query resource", 32)
        if self.resource not in {
            "summary",
            "observations",
            "transitions",
            "checks",
            "verification",
        }:
            raise ValidationError("observatory query resource is invalid")
        self.state = None if state is None else _text(state, "observatory query state", 32)
        if self.state is not None and self.state not in {
            "ready",
            "held",
            "blocked",
            "mixed",
            "empty",
        }:
            raise ValidationError("observatory query state is invalid")
        self.transition_kind = (
            None
            if transition_kind is None
            else _text(transition_kind, "observatory transition kind", 32)
        )
        if self.transition_kind is not None and self.transition_kind not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind
        }:
            raise ValidationError("observatory query transition kind is invalid")
        self.accepted = accepted
        self.release_ready = release_ready
        if accepted is not None:
            _bool(accepted, "observatory query accepted")
        if release_ready is not None:
            _bool(release_ready, "observatory query release-ready")
        self.text = None if text is None else _text(text, "observatory query text", 256)
        _count(
            offset,
            "observatory query offset",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
        )
        _count(
            limit,
            "observatory query limit",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_DEFAULT_LIMIT
            * 4,
            positive=True,
        )
        self.offset = offset
        self.limit = limit

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "state": self.state,
            "transition_kind": self.transition_kind,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "text": self.text,
            "offset": self.offset,
            "limit": self.limit,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQueryResult,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_QUERY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQueryResult:
    """An addressed bounded query receipt."""

    def __init__(
        self,
        *,
        observatory_address: str,
        query: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQuery,
        total: int,
        offset: int,
        limit: int,
        items: tuple[Mapping[str, Any], ...],
        content_address: str,
    ) -> None:
        self.observatory_address = observatory_address
        self.query = query
        self.total = total
        self.offset = offset
        self.limit = limit
        self.items = tuple(dict(item) for item in items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.observatory_address, "observatory query observatory address")
        if not isinstance(
            self.query,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQuery,
        ):
            raise ValidationError("observatory query must be typed")
        _count(
            self.total,
            "observatory query total",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS
            + MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_CHECKS,
        )
        _count(
            self.offset,
            "observatory query offset",
            self.total
            if self.total
            else MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
        )
        _count(
            self.limit,
            "observatory query limit",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_DEFAULT_LIMIT
            * 4,
            positive=True,
        )
        if len(self.items) > self.limit or self.offset > self.total:
            raise ValidationError("observatory query page is not bounded")
        if not all(_public(item) for item in self.items):
            raise ValidationError("observatory query items cross the public boundary")
        _address(self.content_address, "observatory query content address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observatory_address": self.observatory_address,
            "query": self.query.to_dict(),
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "items": list(self.items),
            "content_address": self.content_address,
        }


def _matches(
    item: Mapping[str, Any],
    query: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQuery,
) -> bool:
    if query.state is not None and item.get("state", item.get("current_state")) != query.state:
        return False
    if query.transition_kind is not None and item.get("kind") != query.transition_kind:
        return False
    if query.accepted is not None and item.get("accepted") != query.accepted:
        return False
    if query.release_ready is not None and item.get("release_ready") != query.release_ready:
        return False
    if query.text is not None and query.text.casefold() not in canonical_json(item).casefold():
        return False
    return True


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
    query: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQuery
    | None = None,
    **kwargs: Any,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQueryResult:
    _require_verified(value)
    query = (
        query
        or ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQuery(
            **kwargs
        )
    )
    if query.resource == "summary":
        candidates = (value.summary(),)
    elif query.resource == "observations":
        candidates = tuple(item.to_dict() for item in value.observations)
    elif query.resource == "transitions":
        candidates = tuple(item.to_dict() for item in value.transitions)
    elif query.resource == "checks":
        candidates = tuple(item.to_dict() for item in value.checks)
    else:
        candidates = (
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value
            ).summary(),
        )
    filtered = tuple(item for item in candidates if _matches(item, query))
    items = filtered[query.offset : query.offset + query.limit]
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQueryResult(
        observatory_address=value.content_address,
        query=query,
        total=len(filtered),
        offset=query.offset,
        limit=query.limit,
        items=tuple(items),
        content_address="pending:query",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQueryResult(
        observatory_address=provisional.observatory_address,
        query=provisional.query,
        total=provisional.total,
        offset=provisional.offset,
        limit=provisional.limit,
        items=provisional.items,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQueryResult,
) -> bool:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQueryResult,
    ):
        raise ValidationError("observatory query verification requires a typed result")
    return (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query(
            value
        )
        == value.content_address
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query(
        value
    ):
        raise ValidationError("observatory query address verification failed")
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query(
        value
    ):
        raise ValidationError("observatory query address verification failed")
    output = io.StringIO(newline="")
    items = value.items
    fieldnames = tuple(sorted({str(key) for item in items for key in item})) or ("value",)
    writer = csv.DictWriter(
        output, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                key: canonical_json(item[key])
                if isinstance(item.get(key), (dict, list, tuple))
                else item.get(key, "")
                for key in fieldnames
            }
        )
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query(
        value
    ):
        raise ValidationError("observatory query address verification failed")
    lines = [
        "# Packet-review gate history observatory query",
        "",
        f"- Resource: `{value.query.resource}`",
        f"- Total: `{value.total}`",
        f"- Offset: `{value.offset}`",
        f"- Limit: `{value.limit}`",
        "",
    ]
    if value.items:
        keys = tuple(sorted({str(key) for item in value.items for key in item}))
        lines.extend(["| " + " | ".join(keys) + " |", "|" + "|".join("---" for _ in keys) + "|"])
        lines.extend(
            "| " + " | ".join(f"`{item.get(key, '')}`" for key in keys) + " |"
            for item in value.items
        )
    else:
        lines.append("No matching items.")
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_BOUNDARY,
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryState
        ],
        "transition_kinds": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryTransitionKind
        ],
        "resources": ["summary", "observations", "transitions", "checks", "verification"],
        "exact_files": ["manifest.json", "observatory.json"],
        "max_observations": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
        "max_transitions": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_TRANSITIONS,
        "max_checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_CHECKS,
        "bounded": True,
        "deterministic": True,
        "path_free": True,
        "identity_free": True,
        "timestamp_free": True,
        "independent_verification": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERSION,
        "operations": [
            "build",
            "build-from-directories",
            "build-from-mappings",
            "verify",
            "write",
            "load",
            "query",
            "json",
            "csv",
            "markdown",
            "verification-json",
            "verification-csv",
            "verification-markdown",
        ],
        "exports": ["json", "csv", "markdown"],
        "bounded": True,
        "ordered_observations": True,
        "adjacent_transition_classification": True,
        "rollup_conservation": True,
        "canonical_json": True,
        "atomic_write": True,
        "fail_closed": True,
        "independent_verification": True,
        "identity_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "observations", "transitions", "checks", "verification"],
        "filters": [
            "state",
            "transition_kind",
            "accepted",
            "release_ready",
            "text",
            "offset",
            "limit",
        ],
        "bounded": True,
        "addressed_receipts": True,
        "path_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "observations", "transitions", "checks", "verification"],
        "filters": [
            "state",
            "transition_kind",
            "accepted",
            "release_ready",
            "text",
            "offset",
            "limit",
        ],
        "bounded": True,
        "deterministic": True,
        "addressed_receipts": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_verification_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERIFICATION_PREFIX
        + "-v1",
        "resources": ["summary", "checks"],
        "check_fields": ["kind", "passed", "expected", "observed", "detail"],
        "bounded": True,
        "independent": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_verification_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_VERIFICATION_PREFIX
        + "-v1",
        "operations": ["verify", "json", "csv", "markdown"],
        "recomputes": True,
        "recomputes_addresses": True,
        "recomputes_rollups": True,
        "fail_closed": True,
        "identity_free": True,
    }
