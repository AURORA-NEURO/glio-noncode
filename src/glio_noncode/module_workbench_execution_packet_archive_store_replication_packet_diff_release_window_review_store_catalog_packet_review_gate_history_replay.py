"""Deterministic replay and release reporting for packet-review gate history."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_CHECKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history,
)
from .serialization import canonical_json, content_hash

_History = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistory
_Entry = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryEntry

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_PREFIX
    + "-replay"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_EVENT_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_PREFIX
    + "-event"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_PREFIX
    + "-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_REPORT_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_PREFIX
    + "-report"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_DEFAULT_LIMIT = 50


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayState(
    StrEnum
):
    START = "start"
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayEvent:
    """One replayed transition with both sides of the state boundary."""

    def __init__(
        self,
        *,
        ordinal: int,
        gate_address: str,
        head_address: str,
        decision: str,
        before_state: str,
        after_state: str,
        accepted: bool,
        release_ready: bool,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.gate_address = gate_address
        self.head_address = head_address
        self.decision = decision
        self.before_state = before_state
        self.after_state = after_state
        self.accepted = accepted
        self.release_ready = release_ready
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or not 0
            <= self.ordinal
            < MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES
        ):
            raise ValidationError("replay event ordinal is outside its bounded range")
        for value, field in (
            (self.gate_address, "replay event gate address"),
            (self.head_address, "replay event head address"),
            (self.content_address, "replay event content address"),
        ):
            if not isinstance(value, str) or ":" not in value or len(value) > 512:
                raise ValidationError(f"{field} must be addressed")
        if self.decision not in {"promote", "hold", "block", "supersede"}:
            raise ValidationError("replay event decision is invalid")
        if self.before_state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayState
        }:
            raise ValidationError("replay event before-state is invalid")
        if self.after_state not in {"ready", "held", "blocked"}:
            raise ValidationError("replay event after-state is invalid")
        if not isinstance(self.accepted, bool) or not isinstance(self.release_ready, bool):
            raise ValidationError("replay event flags must be boolean")
        if self.before_state == "start" and self.ordinal != 0:
            raise ValidationError("only the first replay event may begin at start")
        if self.ordinal == 0 and self.before_state != "start":
            raise ValidationError("first replay event must begin at start")
        if not _public(self.to_dict()):
            raise ValidationError("replay event crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "gate_address": self.gate_address,
            "head_address": self.head_address,
            "decision": self.decision,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_event(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayEvent,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_EVENT_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayCheck:
    """An addressed replay invariant and its observed values."""

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
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or not 0
            <= self.ordinal
            < MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_CHECKS
        ):
            raise ValidationError("replay check ordinal is outside its bounded range")
        if not isinstance(self.kind, str) or not self.kind or len(self.kind) > 256:
            raise ValidationError("replay check kind is invalid")
        if (
            not isinstance(self.passed, bool)
            or not isinstance(self.detail, str)
            or not self.detail
            or len(self.detail) > 4096
        ):
            raise ValidationError("replay check fields are invalid")
        if not isinstance(self.content_address, str) or ":" not in self.content_address:
            raise ValidationError("replay check must be addressed")
        if not _public(self.to_dict()):
            raise ValidationError("replay check crosses the public boundary")

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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport:
    """The release-facing result of replaying every historical decision."""

    def __init__(
        self,
        *,
        history_address: str,
        boundary: str,
        version: str,
        event_count: int,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        final_state: str,
        final_accepted: bool,
        final_release_ready: bool,
        events: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayEvent,
            ...,
        ],
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.history_address = history_address
        self.boundary = boundary
        self.version = version
        self.event_count = event_count
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.final_state = final_state
        self.final_accepted = final_accepted
        self.final_release_ready = final_release_ready
        self.events = tuple(events)
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.history_address, "replay history address")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_BOUNDARY
            or self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_VERSION
        ):
            raise ValidationError("replay report identity is invalid")
        _count(
            self.event_count,
            "replay event count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES,
        )
        _count(
            self.check_count,
            "replay check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_CHECKS,
        )
        if (
            self.event_count != len(self.events)
            or self.event_count == 0
            or self.check_count != len(self.checks)
            or self.check_count == 0
        ):
            raise ValidationError("replay report collections are not conserved")
        if (self.passed_count, self.failed_count) != (
            sum(item.passed for item in self.checks),
            sum(not item.passed for item in self.checks),
        ):
            raise ValidationError("replay report check counts are not conserved")
        _count(self.passed_count, "replay passed count", self.check_count)
        _count(self.failed_count, "replay failed count", self.check_count)
        _bool(self.accepted, "replay accepted")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("replay acceptance is not conserved")
        if (
            self.final_state not in {"ready", "held", "blocked"}
            or not isinstance(self.final_accepted, bool)
            or not isinstance(self.final_release_ready, bool)
        ):
            raise ValidationError("replay terminal projection is invalid")
        for ordinal, event in enumerate(self.events):
            if (
                event.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_event(
                    event
                )
                != event.content_address
            ):
                raise ValidationError("replay event address is invalid")
        for ordinal, check in enumerate(self.checks):
            if (
                check.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("replay check address is invalid")
        _address(self.content_address, "replay report content address")
        if not _public(self.to_dict()):
            raise ValidationError("replay report crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "history_address": self.history_address,
            "boundary": self.boundary,
            "version": self.version,
            "event_count": self.event_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "final_state": self.final_state,
            "final_accepted": self.final_accepted,
            "final_release_ready": self.final_release_ready,
            "content_address": self.content_address,
        }

    def to_dict(
        self, *, include_events: bool = True, include_checks: bool = True
    ) -> dict[str, Any]:
        body = self.summary()
        if include_events:
            body["events"] = [item.to_dict() for item in self.events]
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_report(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_REPORT_PREFIX,
    )


def _address(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or ":" not in value or len(value) > 512:
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
        return all(
            str(key).casefold() not in {"agent", "language", "model", "user"}
            and not str(key).casefold().endswith(("_agent", "_language", "_model", "_user"))
            and _public(item)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list)):
        return all(_public(item) for item in value)
    return True


def _closed(entry: _Entry) -> bool:
    if entry.decision == "promote":
        return entry.state == "ready" and entry.accepted and entry.release_ready
    if entry.decision in {"hold", "supersede"}:
        return entry.state == "held" and entry.accepted and not entry.release_ready
    return (
        entry.decision == "block"
        and entry.state == "blocked"
        and not entry.accepted
        and not entry.release_ready
    )


def _event(
    ordinal: int, entry: _Entry, before_state: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayEvent:
    body = {
        "ordinal": ordinal,
        "gate_address": entry.gate_address,
        "head_address": entry.content_address,
        "decision": entry.decision,
        "before_state": before_state,
        "after_state": entry.state,
        "accepted": entry.accepted,
        "release_ready": entry.release_ready,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayEvent(
        **body, content_address="pending:event"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayEvent(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_event(
            provisional
        ),
    )


def _check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayCheck:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "passed": passed,
        "expected": _json_value(expected),
        "observed": _json_value(observed),
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_check(
            provisional
        ),
    )


def _json_value(value: Any) -> Any:
    import json

    return json.loads(canonical_json(value))


def replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
    value: _History,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport:
    if not isinstance(value, _History):
        raise ValidationError("history replay requires a typed history")
    entries = value.entries
    events = tuple(
        _event(ordinal, entry, "start" if ordinal == 0 else entries[ordinal - 1].state)
        for ordinal, entry in enumerate(entries)
    )
    history_receipt = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
        value
    )
    terminal = entries[-1]
    checks = (
        _check(
            0,
            "history-verification",
            history_receipt.accepted,
            True,
            history_receipt.accepted,
            "source history structural verification is replayable",
        ),
        _check(
            1,
            "event-conservation",
            len(events) == value.entry_count,
            value.entry_count,
            len(events),
            "one replay event exists for every historical entry",
        ),
        _check(
            2,
            "event-addresses",
            all(
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_event(
                    item
                )
                == item.content_address
                for item in events
            ),
            True,
            tuple(item.content_address for item in events),
            "replay event addresses are independently recomputed",
        ),
        _check(
            3,
            "transition-chain",
            all(
                item.before_state == ("start" if ordinal == 0 else events[ordinal - 1].after_state)
                for ordinal, item in enumerate(events)
            ),
            "previous after-state",
            tuple(item.before_state for item in events),
            "replay states form a contiguous sequence",
        ),
        _check(
            4,
            "head-chain",
            all(item.head_address == entries[item.ordinal].content_address for item in events),
            True,
            tuple(item.head_address for item in events),
            "each event points to its source history entry",
        ),
        _check(
            5,
            "decision-state",
            all(_closed(entry) for entry in entries),
            True,
            tuple(
                (entry.decision, entry.state, entry.accepted, entry.release_ready)
                for entry in entries
            ),
            "every replayed decision has a closed state projection",
        ),
        _check(
            6,
            "terminal-projection",
            (value.state, value.accepted, value.release_ready)
            == (terminal.state, terminal.accepted, terminal.release_ready),
            (terminal.state, terminal.accepted, terminal.release_ready),
            (value.state, value.accepted, value.release_ready),
            "replay terminal state matches the historical head",
        ),
        _check(
            7,
            "public-boundary",
            _public({"history": value.summary(), "events": [item.to_dict() for item in events]}),
            True,
            True,
            "replay report contains only public fields",
        ),
    )
    body = {
        "history_address": value.content_address,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_BOUNDARY,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_VERSION,
        "event_count": len(events),
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "final_state": terminal.state,
        "final_accepted": terminal.accepted,
        "final_release_ready": terminal.release_ready,
        "events": events,
        "checks": checks,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport(
        **body, content_address="pending:report"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_report(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport,
    ):
        raise ValidationError("replay verification requires a typed replay report")
    if not all(
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_event(
            item
        )
        == item.content_address
        for item in value.events
    ):
        raise ValidationError("replay event verification failed")
    if not all(
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_check(
            item
        )
        == item.content_address
        for item in value.checks
    ):
        raise ValidationError("replay check verification failed")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_report(
            value
        )
        != value.content_address
    ):
        raise ValidationError("replay report address mismatch")
    if not value.accepted:
        raise ValidationError("replay report is not accepted")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
        value
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "gate_address",
            "head_address",
            "decision",
            "before_state",
            "after_state",
            "accepted",
            "release_ready",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for item in value.events:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
        value
    )
    lines = [
        "# Catalog Packet Review Gate History Replay",
        "",
        f"- history: `{value.history_address}`",
        f"- events: `{value.event_count}`",
        f"- final-state: `{value.final_state}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Decision | Before | After | Accepted | Ready |",
        "|---:|---|---|---|---:|---:|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.decision}` | `{item.before_state}` | `{item.after_state}` | `{str(item.accepted).lower()}` | `{str(item.release_ready).lower()}` |"
        for item in value.events
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_BOUNDARY,
        "source_boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_BOUNDARY,
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayState
        ],
        "max_events": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_ENTRIES,
        "max_checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_MAX_CHECKS,
        "bounded": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_VERSION,
        "operations": ["replay", "verify", "json", "csv", "markdown"],
        "state_reconstruction": True,
        "terminal_projection": True,
        "canonical_json": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_PREFIX
        + "-query-v1",
        "resources": ["summary", "events", "checks"],
        "filters": [
            "decision",
            "before_state",
            "after_state",
            "accepted",
            "release_ready",
            "text",
            "offset",
            "limit",
        ],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_PREFIX
        + "-query-v1",
        "resources": ["summary", "events", "checks"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayReport,
    *,
    resource: str = "events",
    decision: str | None = None,
    before_state: str | None = None,
    after_state: str | None = None,
    accepted: bool | None = None,
    release_ready: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay(
        value
    )
    if resource not in {"summary", "events", "checks"}:
        raise ValidationError("replay query resource is invalid")
    if decision is not None and decision not in {"promote", "hold", "block", "supersede"}:
        raise ValidationError("replay query decision is invalid")
    if before_state is not None and before_state not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryReplayState
    }:
        raise ValidationError("replay query before-state is invalid")
    if after_state is not None and after_state not in {"ready", "held", "blocked"}:
        raise ValidationError("replay query after-state is invalid")
    if (
        accepted is not None
        and not isinstance(accepted, bool)
        or release_ready is not None
        and not isinstance(release_ready, bool)
    ):
        raise ValidationError("replay query boolean filter is invalid")
    if text is not None and (not isinstance(text, str) or not text or len(text) > 4096):
        raise ValidationError("replay query text is invalid")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 512
    ):
        raise ValidationError("replay query bounds are invalid")
    if resource == "summary":
        rows = [value.summary()]
    elif resource == "events":
        rows = [item.to_dict() for item in value.events]
    else:
        rows = [item.to_dict() for item in value.checks]
    if resource in {"summary", "events"}:
        if decision is not None:
            rows = [row for row in rows if row.get("decision") == decision]
        if before_state is not None:
            rows = [row for row in rows if row.get("before_state") == before_state]
        if after_state is not None:
            rows = [row for row in rows if row.get("after_state") == after_state]
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
            "before_state": before_state,
            "after_state": after_state,
            "accepted": accepted,
            "release_ready": release_ready,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "replay": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_PREFIX
            + "-query",
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("replay query must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_REPLAY_PREFIX
        + "-query",
    )
    if expected != value["content_address"]:
        raise ValidationError("replay query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query(
        value
    )
    resource = value.get("query", {}).get("resource")
    fields = (
        (
            "ordinal",
            "gate_address",
            "head_address",
            "decision",
            "before_state",
            "after_state",
            "accepted",
            "release_ready",
            "content_address",
        )
        if resource == "events"
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
        if resource == "checks"
        else tuple(value.get("items", [{}])[0].keys())
        if value.get("items")
        else ("history_address", "content_address")
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.get("items", []):
        row = dict(item)
        for key in ("expected", "observed"):
            if key in row:
                row[key] = canonical_json(row[key])
        writer.writerow({key: row.get(key, "") for key in fields})
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_replay_query(
        value
    )
    resource = value["query"]["resource"]
    lines = [
        "# Catalog Packet Review Gate History Replay Query",
        "",
        f"- resource: `{resource}`",
        f"- total: `{value['total']}`",
        f"- address: `{value['content_address']}`",
        "",
    ]
    if resource == "events":
        lines.extend(["| # | Decision | Before | After |", "|---:|---|---|---|"])
        lines.extend(
            f"| {row.get('ordinal', '')} | `{row.get('decision', '')}` | `{row.get('before_state', '')}` | `{row.get('after_state', '')}` |"
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
        if value.get("items"):
            lines.extend(f"| {key} | `{item}` |" for key, item in value["items"][0].items())
    return "\n".join(lines) + "\n"


__all__ = [
    name
    for name in globals()
    if (
        name.startswith("ModuleWorkbenchExecutionPacketArchiveStoreReplication")
        or name.startswith("MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION")
        or name.startswith("address_module_workbench_execution_packet_archive_store_replication")
        or name.startswith("replay_module_workbench_execution_packet_archive_store_replication")
        or name.startswith("verify_module_workbench_execution_packet_archive_store_replication")
        or name.startswith("query_module_workbench_execution_packet_archive_store_replication")
        or name.startswith("render_module_workbench_execution_packet_archive_store_replication")
        or name.startswith("module_workbench_execution_packet_archive_store_replication")
    )
    and not name.endswith("_History")
]
