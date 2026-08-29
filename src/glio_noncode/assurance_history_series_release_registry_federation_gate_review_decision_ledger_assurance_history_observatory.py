"""Aggregate verified decision-ledger assurance histories for review.

The assurance-history boundary records one append-only timeline.  This module
adds the next transport boundary: an observatory can contain several
independently verified histories and compare their current review posture
without merging their source records.  A member remains source-scoped and
retains its history address, terminal snapshot, transition counters, and
readiness state.  Aggregate counters are recomputed from those members.

The boundary is intentionally fail-closed.  It does not infer scientific
validity, create missing evidence, or make an old package current by
conversion.  It verifies typed histories, closes the aggregate state, and
persists only bounded path-free public records.  No timestamp, private
identity, execution-language attribute, credential, agent attribute, or
filesystem path is part of the contract.

Observatory packages contain exactly ``manifest.json``, ``observatory.json``,
``members.json``, ``verification.json``, and ``metrics.json``.  Observatory
diff packages contain exactly ``manifest.json`` and ``diff.json``.  Every JSON
artifact is canonical UTF-8 and every manifest receipt is content addressed.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import (
    assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history as history_model,
)
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

AssuranceHistory = history_model.AssuranceHistory
HistoryTransition = history_model.HistoryTransition

VERSION = history_model.VERSION + "-observatory-v1"
BOUNDARY = history_model.BOUNDARY + "_observatory"
OBSERVATORY_PREFIX = history_model.HISTORY_PREFIX + "-observatory"
MEMBER_PREFIX = OBSERVATORY_PREFIX + "-member"
CHECK_PREFIX = OBSERVATORY_PREFIX + "-check"
VERIFICATION_PREFIX = OBSERVATORY_PREFIX + "-verification"
DIFF_PREFIX = OBSERVATORY_PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"
QUERY_PREFIX = OBSERVATORY_PREFIX + "-query"
DIFF_QUERY_PREFIX = DIFF_PREFIX + "-query"
VERIFICATION_QUERY_PREFIX = VERIFICATION_PREFIX + "-query"
MANIFEST_PREFIX = OBSERVATORY_PREFIX + "-manifest"
DIFF_MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"

MANIFEST_NAME = "manifest.json"
OBSERVATORY_NAME = "observatory.json"
MEMBERS_NAME = "members.json"
VERIFICATION_NAME = "verification.json"
METRICS_NAME = "metrics.json"
FILES = (MANIFEST_NAME, OBSERVATORY_NAME, MEMBERS_NAME, VERIFICATION_NAME, METRICS_NAME)
DIFF_NAME = "diff.json"
DIFF_FILES = (MANIFEST_NAME, DIFF_NAME)

DEFAULT_OBSERVATORY_ID = "glio-noncode-release-registry-federation-gate-review-decision-ledger-assurance-history-observatory"
DEFAULT_DIFF_ID = DEFAULT_OBSERVATORY_ID + "-diff"
MAX_MEMBERS = 512
MAX_CHECKS = 64
MAX_QUERY_ITEMS = 4096
MAX_TEXT = 4096
DEFAULT_LIMIT = 50
EMPTY_ADDRESS = "none:assurance-history-observatory"
MAX_MEMBER_FINDINGS = history_model.MAX_ENTRIES * history_model.assurance_model.MAX_FINDINGS
MAX_MEMBER_CHECKS = history_model.MAX_ENTRIES * history_model.assurance_model.MAX_CHECKS

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "assistant",
        "author",
        "email",
        "generated_by",
        "language",
        "model",
        "private",
        "secret",
        "token",
        "user",
    }
)


class ObservatoryState(StrEnum):
    EMPTY = "empty"
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    MIXED = "mixed"


class ObservatoryGateState(StrEnum):
    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"


class ObservatoryCheckSeverity(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class ObservatoryDiffAction(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class ObservatoryDiffDirection(StrEnum):
    UNCHANGED = "unchanged"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    MIXED = "mixed"


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _optional_text(value: Any, field: str, maximum: int = MAX_TEXT) -> str | None:
    return None if value is None else _text(value, field, maximum)


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 1024)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _optional_address(value: Any, field: str) -> str | None:
    return None if value is None else _address(value, field)


def _count(value: Any, field: str, maximum: int = MAX_QUERY_ITEMS, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int = MAX_QUERY_ITEMS) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} has unknown fields: {','.join(sorted(str(item) for item in unknown))}")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        if any(str(key).lower() in _FORBIDDEN_KEYS for key in value):
            return False
        return all(_public(key) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return "c:\\" not in lowered and "/users/" not in lowered and "\\users\\" not in lowered
    return True


def _enum(value: Any, enum_type: type[StrEnum], field: str) -> str:
    value = _text(value, field, 128)
    if value not in {item.value for item in enum_type}:
        raise ValidationError(f"{field} is not supported")
    return value


def _state(value: Any, field: str = "observatory state") -> str:
    return _enum(value, ObservatoryState, field)


def _gate_state(value: Any, field: str = "verification gate state") -> str:
    return _enum(value, ObservatoryGateState, field)


def _severity(value: Any, field: str = "check severity") -> str:
    return _enum(value, ObservatoryCheckSeverity, field)


def _action(value: Any, field: str = "diff action") -> str:
    return _enum(value, ObservatoryDiffAction, field)


def _direction(value: Any, field: str = "diff direction") -> str:
    return _enum(value, ObservatoryDiffDirection, field)


def _transition(value: Any, field: str = "latest transition") -> str | None:
    return None if value is None else _enum(value, HistoryTransition, field)


def _count_map(values: Sequence[str], source: Sequence[Any]) -> dict[str, int]:
    return {key: sum(item == key for item in source) for key in values}


def _member_state(member: ObservatoryMember) -> str:
    if member.entry_count == 0:
        return ObservatoryState.EMPTY.value
    if member.state == history_model.assurance_model.GateState.BLOCK.value:
        return ObservatoryState.BLOCKED.value
    if member.state == history_model.assurance_model.GateState.HOLD.value:
        return ObservatoryState.HELD.value
    if member.release_ready and member.accepted:
        return ObservatoryState.READY.value
    return ObservatoryState.MIXED.value


def _aggregate_state(members: Sequence[ObservatoryMember]) -> str:
    if not members:
        return ObservatoryState.EMPTY.value
    states = tuple(_member_state(item) for item in members)
    if ObservatoryState.BLOCKED.value in states:
        return ObservatoryState.BLOCKED.value
    if ObservatoryState.HELD.value in states:
        return ObservatoryState.HELD.value
    if all(state == ObservatoryState.READY.value for state in states):
        return ObservatoryState.READY.value
    if all(state == ObservatoryState.EMPTY.value for state in states):
        return ObservatoryState.EMPTY.value
    return ObservatoryState.MIXED.value


def _quality_vector(member: ObservatoryMember) -> tuple[int, ...]:
    state_score = {
        ObservatoryState.EMPTY.value: 0,
        ObservatoryState.BLOCKED.value: 1,
        ObservatoryState.HELD.value: 2,
        ObservatoryState.MIXED.value: 2,
        ObservatoryState.READY.value: 3,
    }
    return (
        int(member.release_ready),
        int(member.accepted),
        state_score[_member_state(member)],
        -member.blocker_finding_count,
        -member.blocker_check_count,
        -member.regressed_count,
        member.improved_count,
        member.entry_count,
    )


class ObservatoryMember:
    """One source-scoped verified assurance history in an observatory."""

    def __init__(
        self,
        member_id: str,
        history_id: str,
        history_address: str,
        head_address: str,
        entry_count: int,
        latest_snapshot_id: str | None,
        latest_transition: str | None,
        state: str,
        accepted: bool,
        release_ready: bool,
        initial_count: int,
        stable_count: int,
        improved_count: int,
        regressed_count: int,
        changed_count: int,
        promote_count: int,
        hold_count: int,
        block_count: int,
        finding_count: int,
        passed_finding_count: int,
        warning_finding_count: int,
        blocker_finding_count: int,
        check_count: int,
        passed_check_count: int,
        warning_check_count: int,
        blocker_check_count: int,
        content_address: str,
    ) -> None:
        self.member_id = member_id
        self.history_id = history_id
        self.history_address = history_address
        self.head_address = head_address
        self.entry_count = entry_count
        self.latest_snapshot_id = latest_snapshot_id
        self.latest_transition = latest_transition
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.initial_count = initial_count
        self.stable_count = stable_count
        self.improved_count = improved_count
        self.regressed_count = regressed_count
        self.changed_count = changed_count
        self.promote_count = promote_count
        self.hold_count = hold_count
        self.block_count = block_count
        self.finding_count = finding_count
        self.passed_finding_count = passed_finding_count
        self.warning_finding_count = warning_finding_count
        self.blocker_finding_count = blocker_finding_count
        self.check_count = check_count
        self.passed_check_count = passed_check_count
        self.warning_check_count = warning_check_count
        self.blocker_check_count = blocker_check_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.member_id, "observatory member ID", 512)
        _text(self.history_id, "observatory member history ID", 512)
        _address(self.history_address, "observatory member history address")
        _address(self.head_address, "observatory member head address")
        _count(self.entry_count, "observatory member entry count", history_model.MAX_ENTRIES)
        _optional_text(self.latest_snapshot_id, "observatory member latest snapshot ID", 512)
        _transition(self.latest_transition)
        if self.state != ObservatoryState.EMPTY.value:
            _enum(self.state, history_model.assurance_model.GateState, "observatory member gate state")
        _bool(self.accepted, "observatory member accepted")
        _bool(self.release_ready, "observatory member release-ready")
        counters = (
            (self.initial_count, "initial count"),
            (self.stable_count, "stable count"),
            (self.improved_count, "improved count"),
            (self.regressed_count, "regressed count"),
            (self.changed_count, "changed count"),
        )
        states = ((self.promote_count, "promote count"), (self.hold_count, "hold count"), (self.block_count, "block count"))
        quality = (
            (self.finding_count, "finding count", MAX_MEMBER_FINDINGS),
            (self.passed_finding_count, "passed finding count", MAX_MEMBER_FINDINGS),
            (self.warning_finding_count, "warning finding count", MAX_MEMBER_FINDINGS),
            (self.blocker_finding_count, "blocker finding count", MAX_MEMBER_FINDINGS),
            (self.check_count, "check count", MAX_MEMBER_CHECKS),
            (self.passed_check_count, "passed check count", MAX_MEMBER_CHECKS),
            (self.warning_check_count, "warning check count", MAX_MEMBER_CHECKS),
            (self.blocker_check_count, "blocker check count", MAX_MEMBER_CHECKS),
        )
        for value, field in counters + states:
            _count(value, field, history_model.MAX_ENTRIES)
        for value, field, maximum in quality:
            _count(value, field, maximum)
        if sum(value for value, _ in counters) != self.entry_count or sum(value for value, _ in states) != self.entry_count:
            raise ValidationError("observatory member counters are not conserved")
        if self.passed_finding_count + self.warning_finding_count + self.blocker_finding_count != self.finding_count:
            raise ValidationError("observatory member finding counts are not conserved")
        if self.passed_check_count + self.warning_check_count + self.blocker_check_count != self.check_count:
            raise ValidationError("observatory member check counts are not conserved")
        if self.entry_count == 0:
            if self.state != ObservatoryState.EMPTY.value:
                raise ValidationError("empty observatory member state is invalid")
            if self.latest_snapshot_id is not None or self.latest_transition is not None or self.accepted or self.release_ready:
                raise ValidationError("empty observatory member has a terminal record")
            if self.head_address != history_model.INITIAL_HEAD:
                raise ValidationError("empty observatory member head is invalid")
        else:
            if self.state == ObservatoryState.EMPTY.value:
                raise ValidationError("non-empty observatory member state is invalid")
            if self.latest_snapshot_id is None or self.latest_transition is None:
                raise ValidationError("non-empty observatory member lacks a terminal record")
        if not _public(self.to_dict()):
            raise ValidationError("observatory member crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_member(self) != self.content_address:
            raise ValidationError("observatory member address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "history_id": self.history_id,
            "history_address": self.history_address,
            "head_address": self.head_address,
            "entry_count": self.entry_count,
            "latest_snapshot_id": self.latest_snapshot_id,
            "latest_transition": self.latest_transition,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "initial_count": self.initial_count,
            "stable_count": self.stable_count,
            "improved_count": self.improved_count,
            "regressed_count": self.regressed_count,
            "changed_count": self.changed_count,
            "promote_count": self.promote_count,
            "hold_count": self.hold_count,
            "block_count": self.block_count,
            "finding_count": self.finding_count,
            "passed_finding_count": self.passed_finding_count,
            "warning_finding_count": self.warning_finding_count,
            "blocker_finding_count": self.blocker_finding_count,
            "check_count": self.check_count,
            "passed_check_count": self.passed_check_count,
            "warning_check_count": self.warning_check_count,
            "blocker_check_count": self.blocker_check_count,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("member_id", "history_id", "entry_count", "latest_snapshot_id", "latest_transition", "state", "accepted", "release_ready", "content_address")}


def address_member(value: ObservatoryMember) -> str:
    if not isinstance(value, ObservatoryMember):
        raise ValidationError("observatory member address requires a typed member")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


def _member_from_history(history: AssuranceHistory, member_id: str) -> ObservatoryMember:
    history_model.verify_history(history)
    latest = history.entries[-1] if history.entries else None
    body = {
        "member_id": _text(member_id, "observatory member ID", 512),
        "history_id": history.history_id,
        "history_address": history.content_address,
        "head_address": history.head_address,
        "entry_count": history.entry_count,
        "latest_snapshot_id": None if latest is None else latest.snapshot_id,
        "latest_transition": None if latest is None else latest.transition,
        "state": history.state,
        "accepted": history.accepted,
        "release_ready": history.release_ready,
        "initial_count": history.initial_count,
        "stable_count": history.stable_count,
        "improved_count": history.improved_count,
        "regressed_count": history.regressed_count,
        "changed_count": history.changed_count,
        "promote_count": history.promote_count,
        "hold_count": history.hold_count,
        "block_count": history.block_count,
        "finding_count": sum(entry.finding_count for entry in history.entries),
        "passed_finding_count": sum(entry.passed_finding_count for entry in history.entries),
        "warning_finding_count": sum(entry.warning_finding_count for entry in history.entries),
        "blocker_finding_count": sum(entry.blocker_finding_count for entry in history.entries),
        "check_count": sum(entry.check_count for entry in history.entries),
        "passed_check_count": sum(entry.passed_check_count for entry in history.entries),
        "warning_check_count": sum(entry.warning_check_count for entry in history.entries),
        "blocker_check_count": sum(entry.blocker_check_count for entry in history.entries),
    }
    provisional = ObservatoryMember(**body, content_address="pending:member")
    return ObservatoryMember(**body, content_address=address_member(provisional))


class AssuranceHistoryObservatory:
    """Deterministic aggregate of independently verified assurance histories."""

    def __init__(
        self,
        observatory_id: str,
        version: str,
        boundary: str,
        member_count: int,
        entry_count: int,
        state: str,
        accepted: bool,
        release_ready: bool,
        empty_member_count: int,
        ready_member_count: int,
        held_member_count: int,
        blocked_member_count: int,
        mixed_member_count: int,
        initial_count: int,
        stable_count: int,
        improved_count: int,
        regressed_count: int,
        changed_count: int,
        promote_count: int,
        hold_count: int,
        block_count: int,
        finding_count: int,
        passed_finding_count: int,
        warning_finding_count: int,
        blocker_finding_count: int,
        check_count: int,
        passed_check_count: int,
        warning_check_count: int,
        blocker_check_count: int,
        members: Sequence[ObservatoryMember],
        content_address: str,
    ) -> None:
        self.observatory_id = observatory_id
        self.version = version
        self.boundary = boundary
        self.member_count = member_count
        self.entry_count = entry_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.empty_member_count = empty_member_count
        self.ready_member_count = ready_member_count
        self.held_member_count = held_member_count
        self.blocked_member_count = blocked_member_count
        self.mixed_member_count = mixed_member_count
        self.initial_count = initial_count
        self.stable_count = stable_count
        self.improved_count = improved_count
        self.regressed_count = regressed_count
        self.changed_count = changed_count
        self.promote_count = promote_count
        self.hold_count = hold_count
        self.block_count = block_count
        self.finding_count = finding_count
        self.passed_finding_count = passed_finding_count
        self.warning_finding_count = warning_finding_count
        self.blocker_finding_count = blocker_finding_count
        self.check_count = check_count
        self.passed_check_count = passed_check_count
        self.warning_check_count = warning_check_count
        self.blocker_check_count = blocker_check_count
        self.members = tuple(members)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.observatory_id, "observatory ID", 512)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("assurance history observatory contract is invalid")
        _count(self.member_count, "observatory member count", MAX_MEMBERS)
        _count(self.entry_count, "observatory entry count", MAX_MEMBERS * history_model.MAX_ENTRIES)
        _state(self.state)
        _bool(self.accepted, "observatory accepted")
        _bool(self.release_ready, "observatory release-ready")
        member_states = ((self.empty_member_count, ObservatoryState.EMPTY.value), (self.ready_member_count, ObservatoryState.READY.value), (self.held_member_count, ObservatoryState.HELD.value), (self.blocked_member_count, ObservatoryState.BLOCKED.value), (self.mixed_member_count, ObservatoryState.MIXED.value))
        for count, label in member_states:
            _count(count, f"{label} member count", MAX_MEMBERS)
        if sum(count for count, _ in member_states) != self.member_count:
            raise ValidationError("observatory member state counts are not conserved")
        transition_counts = ((self.initial_count, "initial count"), (self.stable_count, "stable count"), (self.improved_count, "improved count"), (self.regressed_count, "regressed count"), (self.changed_count, "changed count"))
        gate_counts = ((self.promote_count, "promote count"), (self.hold_count, "hold count"), (self.block_count, "block count"))
        for count, label in transition_counts + gate_counts:
            _count(count, label, MAX_MEMBERS * history_model.MAX_ENTRIES)
        if sum(count for count, _ in transition_counts) != self.entry_count or sum(count for count, _ in gate_counts) != self.entry_count:
            raise ValidationError("observatory history counters are not conserved")
        quality = ((self.finding_count, "finding count"), (self.passed_finding_count, "passed finding count"), (self.warning_finding_count, "warning finding count"), (self.blocker_finding_count, "blocker finding count"), (self.check_count, "check count"), (self.passed_check_count, "passed check count"), (self.warning_check_count, "warning check count"), (self.blocker_check_count, "blocker check count"))
        for count, label in quality:
            _count(count, label, MAX_MEMBERS * max(history_model.assurance_model.MAX_FINDINGS, history_model.assurance_model.MAX_CHECKS) * history_model.MAX_ENTRIES)
        if self.passed_finding_count + self.warning_finding_count + self.blocker_finding_count != self.finding_count:
            raise ValidationError("observatory finding counts are not conserved")
        if self.passed_check_count + self.warning_check_count + self.blocker_check_count != self.check_count:
            raise ValidationError("observatory check counts are not conserved")
        if self.member_count != len(self.members):
            raise ValidationError("observatory member count is not conserved")
        if tuple(item.member_id for item in self.members) != tuple(sorted(item.member_id for item in self.members)):
            raise ValidationError("observatory members must be sorted by member ID")
        if len({item.member_id for item in self.members}) != self.member_count or len({item.content_address for item in self.members}) != self.member_count or len({item.history_address for item in self.members}) != self.member_count:
            raise ValidationError("observatory member identities are not unique")
        if self.entry_count != sum(item.entry_count for item in self.members):
            raise ValidationError("observatory entry count is not conserved")
        for field in ("initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "promote_count", "hold_count", "block_count", "finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count", "check_count", "passed_check_count", "warning_check_count", "blocker_check_count"):
            if getattr(self, field) != sum(getattr(item, field) for item in self.members):
                raise ValidationError(f"observatory {field} is not conserved")
        expected_state = _aggregate_state(self.members)
        if self.state != expected_state:
            raise ValidationError("observatory state does not match members")
        expected_accepted = bool(self.members) and all(item.accepted for item in self.members)
        expected_ready = bool(self.members) and self.state == ObservatoryState.READY.value and all(item.release_ready for item in self.members)
        if self.accepted != expected_accepted or self.release_ready != expected_ready:
            raise ValidationError("observatory terminal projection does not match members")
        if not _public(self.to_dict()):
            raise ValidationError("observatory crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_observatory(self) != self.content_address:
            raise ValidationError("observatory address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observatory_id": self.observatory_id,
            "version": self.version,
            "boundary": self.boundary,
            "member_count": self.member_count,
            "entry_count": self.entry_count,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "empty_member_count": self.empty_member_count,
            "ready_member_count": self.ready_member_count,
            "held_member_count": self.held_member_count,
            "blocked_member_count": self.blocked_member_count,
            "mixed_member_count": self.mixed_member_count,
            "initial_count": self.initial_count,
            "stable_count": self.stable_count,
            "improved_count": self.improved_count,
            "regressed_count": self.regressed_count,
            "changed_count": self.changed_count,
            "promote_count": self.promote_count,
            "hold_count": self.hold_count,
            "block_count": self.block_count,
            "finding_count": self.finding_count,
            "passed_finding_count": self.passed_finding_count,
            "warning_finding_count": self.warning_finding_count,
            "blocker_finding_count": self.blocker_finding_count,
            "check_count": self.check_count,
            "passed_check_count": self.passed_check_count,
            "warning_check_count": self.warning_check_count,
            "blocker_check_count": self.blocker_check_count,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return self.to_dict()


def address_observatory(value: AssuranceHistoryObservatory) -> str:
    if not isinstance(value, AssuranceHistoryObservatory):
        raise ValidationError("observatory address requires a typed observatory")
    body = value.to_dict() | {"members": tuple(member.to_dict() for member in value.members), "content_address": None}
    return content_hash(body, prefix=OBSERVATORY_PREFIX)


def _build_observatory_body(observatory_id: str, members: Sequence[ObservatoryMember]) -> dict[str, Any]:
    members = tuple(members)
    state_counts = _count_map(tuple(item.value for item in ObservatoryState), tuple(_member_state(member) for member in members))
    totals = {field: sum(getattr(member, field) for member in members) for field in ("entry_count", "initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "promote_count", "hold_count", "block_count", "finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count", "check_count", "passed_check_count", "warning_check_count", "blocker_check_count")}
    return {
        "observatory_id": _text(observatory_id, "observatory ID", 512),
        "version": VERSION,
        "boundary": BOUNDARY,
        "member_count": len(members),
        "entry_count": totals["entry_count"],
        "state": _aggregate_state(members),
        "accepted": bool(members) and all(item.accepted for item in members),
        "release_ready": bool(members) and _aggregate_state(members) == ObservatoryState.READY.value and all(item.release_ready for item in members),
        "empty_member_count": state_counts[ObservatoryState.EMPTY.value],
        "ready_member_count": state_counts[ObservatoryState.READY.value],
        "held_member_count": state_counts[ObservatoryState.HELD.value],
        "blocked_member_count": state_counts[ObservatoryState.BLOCKED.value],
        "mixed_member_count": state_counts[ObservatoryState.MIXED.value],
        **{key: totals[key] for key in ("initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "promote_count", "hold_count", "block_count", "finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count", "check_count", "passed_check_count", "warning_check_count", "blocker_check_count")},
        "members": tuple(members),
    }


def _finish_observatory(observatory_id: str, members: Sequence[ObservatoryMember]) -> AssuranceHistoryObservatory:
    members = tuple(sorted(members, key=lambda item: item.member_id))
    body = _build_observatory_body(observatory_id, members)
    provisional = AssuranceHistoryObservatory(**body, content_address="pending:observatory")
    body["content_address"] = address_observatory(provisional)
    return AssuranceHistoryObservatory(**body)


def build_observatory(histories: Sequence[AssuranceHistory] = (), *, observatory_id: str = DEFAULT_OBSERVATORY_ID, member_ids: Sequence[str] = ()) -> AssuranceHistoryObservatory:
    histories = _sequence(histories, "observatory histories", MAX_MEMBERS)
    member_ids = _sequence(member_ids, "observatory member IDs", MAX_MEMBERS)
    if member_ids and len(member_ids) != len(histories):
        raise ValidationError("observatory member ID count must equal history count")
    members: list[ObservatoryMember] = []
    for index, history in enumerate(histories):
        if not isinstance(history, AssuranceHistory):
            raise ValidationError("observatory requires typed assurance histories")
        member_id = history.history_id if not member_ids else member_ids[index]
        members.append(_member_from_history(history, member_id))
    return _finish_observatory(observatory_id, members)


def build_observatory_from_directories(directories: Sequence[str | Path], *, observatory_id: str = DEFAULT_OBSERVATORY_ID, member_ids: Sequence[str] = ()) -> AssuranceHistoryObservatory:
    directories = _sequence(directories, "observatory history directories", MAX_MEMBERS)
    histories = tuple(history_model.load_history(directory) for directory in directories)
    return build_observatory(histories, observatory_id=observatory_id, member_ids=member_ids)


def verify_observatory(value: AssuranceHistoryObservatory) -> AssuranceHistoryObservatory:
    if not isinstance(value, AssuranceHistoryObservatory):
        raise ValidationError("observatory verification requires a typed observatory")
    for member in value.members:
        if address_member(member) != member.content_address:
            raise ValidationError("observatory member address verification failed")
    if address_observatory(value) != value.content_address:
        raise ValidationError("observatory address verification failed")
    return value


def verify_observatory_against_histories(value: AssuranceHistoryObservatory, histories: Sequence[AssuranceHistory]) -> AssuranceHistoryObservatory:
    verify_observatory(value)
    histories = _sequence(histories, "observatory verification histories", MAX_MEMBERS)
    expected_ids = tuple(member.member_id for member in value.members)
    expected = build_observatory(histories, observatory_id=value.observatory_id, member_ids=expected_ids)
    if expected.to_dict() != value.to_dict():
        raise ValidationError("observatory does not match independently recomputed histories")
    return value


def member_from_mapping(value: Mapping[str, Any]) -> ObservatoryMember:
    value = _mapping(value, "observatory member")
    allowed = {"member_id", "history_id", "history_address", "head_address", "entry_count", "latest_snapshot_id", "latest_transition", "state", "accepted", "release_ready", "initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "promote_count", "hold_count", "block_count", "finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count", "check_count", "passed_check_count", "warning_check_count", "blocker_check_count", "content_address"}
    _strict(value, allowed, "observatory member")
    return ObservatoryMember(**dict(value))


def observatory_from_mapping(value: Mapping[str, Any]) -> AssuranceHistoryObservatory:
    value = _mapping(value, "observatory")
    allowed = {"observatory_id", "version", "boundary", "member_count", "entry_count", "state", "accepted", "release_ready", "empty_member_count", "ready_member_count", "held_member_count", "blocked_member_count", "mixed_member_count", "initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "promote_count", "hold_count", "block_count", "finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count", "check_count", "passed_check_count", "warning_check_count", "blocker_check_count", "members", "content_address"}
    _strict(value, allowed, "observatory")
    members = tuple(member_from_mapping(item) for item in _sequence(value.get("members"), "observatory members", MAX_MEMBERS))
    return AssuranceHistoryObservatory(**(dict(value) | {"members": members}))


class ObservatoryCheck:
    """One independently recomputed observatory assurance check."""

    def __init__(self, check_id: str, severity: str, passed: bool, detail: str, expected: str, observed: str, content_address: str) -> None:
        self.check_id = check_id
        self.severity = severity
        self.passed = passed
        self.detail = detail
        self.expected = expected
        self.observed = observed
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.check_id, "observatory check ID", 512)
        _severity(self.severity)
        _bool(self.passed, "observatory check passed")
        _text(self.detail, "observatory check detail", MAX_TEXT)
        _text(self.expected, "observatory check expected", MAX_TEXT)
        _text(self.observed, "observatory check observed", MAX_TEXT)
        _address(self.content_address, "observatory check address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory check crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("observatory check address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "severity": self.severity, "passed": self.passed, "detail": self.detail, "expected": self.expected, "observed": self.observed, "content_address": self.content_address}


def address_check(value: ObservatoryCheck) -> str:
    if not isinstance(value, ObservatoryCheck):
        raise ValidationError("observatory check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def _make_check(check_id: str, severity: str, passed: bool, detail: str, expected: Any, observed: Any) -> ObservatoryCheck:
    body = {"check_id": check_id, "severity": severity, "passed": passed, "detail": detail, "expected": canonical_json(expected), "observed": canonical_json(observed)}
    provisional = ObservatoryCheck(**body, content_address="pending:check")
    return ObservatoryCheck(**body, content_address=address_check(provisional))


class ObservatoryVerification:
    """Independent structural and readiness verification for an observatory."""

    def __init__(self, verification_id: str, observatory_id: str, observatory_address: str, version: str, boundary: str, check_count: int, passed_count: int, warning_count: int, blocker_count: int, state: str, release_ready: bool, checks: Sequence[ObservatoryCheck], content_address: str) -> None:
        self.verification_id = verification_id
        self.observatory_id = observatory_id
        self.observatory_address = observatory_address
        self.version = version
        self.boundary = boundary
        self.check_count = check_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.release_ready = release_ready
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.verification_id, "observatory verification ID", 512)
        _text(self.observatory_id, "verified observatory ID", 512)
        _address(self.observatory_address, "verified observatory address")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("observatory verification contract is invalid")
        _count(self.check_count, "verification check count", MAX_CHECKS)
        _count(self.passed_count, "verification passed count", MAX_CHECKS)
        _count(self.warning_count, "verification warning count", MAX_CHECKS)
        _count(self.blocker_count, "verification blocker count", MAX_CHECKS)
        _gate_state(self.state)
        _bool(self.release_ready, "verification release-ready")
        actual_passed = sum(check.passed for check in self.checks)
        actual_warning = sum(not check.passed and check.severity == ObservatoryCheckSeverity.OPTIONAL.value for check in self.checks)
        actual_blocker = sum(not check.passed and check.severity == ObservatoryCheckSeverity.REQUIRED.value for check in self.checks)
        if self.check_count != len(self.checks) or self.passed_count + self.warning_count + self.blocker_count != self.check_count or (self.passed_count, self.warning_count, self.blocker_count) != (actual_passed, actual_warning, actual_blocker):
            raise ValidationError("verification check counts are not conserved")
        if len({check.check_id for check in self.checks}) != self.check_count or len({check.content_address for check in self.checks}) != self.check_count:
            raise ValidationError("verification check identities are not unique")
        if not _public(self.to_dict()):
            raise ValidationError("observatory verification crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_verification(self) != self.content_address:
            raise ValidationError("observatory verification address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"verification_id": self.verification_id, "observatory_id": self.observatory_id, "observatory_address": self.observatory_address, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "warning_count": self.warning_count, "blocker_count": self.blocker_count, "state": self.state, "release_ready": self.release_ready, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("verification_id", "observatory_id", "observatory_address", "check_count", "passed_count", "warning_count", "blocker_count", "state", "release_ready", "content_address")}


def address_verification(value: ObservatoryVerification) -> str:
    if not isinstance(value, ObservatoryVerification):
        raise ValidationError("observatory verification address requires a typed verification")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=VERIFICATION_PREFIX)


def check_from_mapping(value: Mapping[str, Any]) -> ObservatoryCheck:
    value = _mapping(value, "observatory check")
    _strict(value, {"check_id", "severity", "passed", "detail", "expected", "observed", "content_address"}, "observatory check")
    return ObservatoryCheck(**dict(value))


def verification_from_mapping(value: Mapping[str, Any]) -> ObservatoryVerification:
    value = _mapping(value, "observatory verification")
    _strict(value, {"verification_id", "observatory_id", "observatory_address", "version", "boundary", "check_count", "passed_count", "warning_count", "blocker_count", "state", "release_ready", "checks", "content_address"}, "observatory verification")
    checks = tuple(check_from_mapping(item) for item in _sequence(value.get("checks"), "observatory checks", MAX_CHECKS))
    return ObservatoryVerification(**(dict(value) | {"checks": checks}))


class VerificationQuery:
    """Bounded query over an observatory verification and its checks."""

    RESOURCES = ("summary", "checks", "failed", "required", "optional")

    def __init__(self, resource: str = "summary", severity: str | None = None, passed: bool | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "verification query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("verification query resource is not supported")
        self.severity = None if severity is None else _severity(severity, "verification query severity")
        self.passed = None if passed is None else _bool(passed, "verification query passed")
        self.text = _optional_text(text, "verification query text", 512)
        self.offset = _count(offset, "verification query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "verification query limit", MAX_QUERY_ITEMS, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "severity": self.severity, "passed": self.passed, "text": self.text, "offset": self.offset, "limit": self.limit}


class VerificationQueryResult:
    """Addressed window of observatory verification checks."""

    def __init__(self, verification_address: str, query: VerificationQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.verification_address = verification_address
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.verification_address, "verification query address")
        _count(self.total_count, "verification query total count", MAX_CHECKS)
        _count(self.returned_count, "verification query returned count", MAX_CHECKS)
        if self.returned_count > self.query.limit or self.returned_count > self.total_count:
            raise ValidationError("verification query window is invalid")
        _address(self.content_address, "verification query result address")
        if not _public(self.to_dict()):
            raise ValidationError("verification query crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_verification_query(self) != self.content_address:
            raise ValidationError("verification query address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"verification_address": self.verification_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}


def address_verification_query(value: VerificationQueryResult) -> str:
    if not isinstance(value, VerificationQueryResult):
        raise ValidationError("verification query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=VERIFICATION_QUERY_PREFIX)


def _matches_verification_check(check: ObservatoryCheck, query: VerificationQuery) -> bool:
    if query.severity is not None and check.severity != query.severity:
        return False
    if query.passed is not None and check.passed != query.passed:
        return False
    if query.resource == "failed" and check.passed:
        return False
    if query.resource == "required" and check.severity != ObservatoryCheckSeverity.REQUIRED.value:
        return False
    if query.resource == "optional" and check.severity != ObservatoryCheckSeverity.OPTIONAL.value:
        return False
    return not query.text or query.text.lower() in canonical_json(check.to_dict()).lower()


def query_verification(value: ObservatoryVerification, query: VerificationQuery | None = None, **kwargs: Any) -> VerificationQueryResult:
    if not isinstance(value, ObservatoryVerification):
        raise ValidationError("verification query requires a typed verification")
    query = VerificationQuery(**kwargs) if query is None else query
    if not isinstance(query, VerificationQuery):
        raise ValidationError("verification query requires a typed query")
    if query.resource == "summary":
        records = (value.summary(),)
        total = 1
    else:
        matching = tuple(check.to_dict() for check in value.checks if _matches_verification_check(check, query))
        total = len(matching)
        records = matching[query.offset : query.offset + query.limit]
    body = {"verification_address": value.content_address, "query": query, "total_count": total, "records": records}
    provisional = VerificationQueryResult(**body, content_address="pending:verification-query")
    return VerificationQueryResult(**body, content_address=address_verification_query(provisional))


def _gate_for(value: AssuranceHistoryObservatory) -> tuple[str, bool]:
    if value.state == ObservatoryState.BLOCKED.value:
        return ObservatoryGateState.BLOCK.value, False
    if value.state == ObservatoryState.READY.value and value.release_ready:
        return ObservatoryGateState.PROMOTE.value, True
    return ObservatoryGateState.HOLD.value, False


def build_verification(value: AssuranceHistoryObservatory, *, verification_id: str | None = None) -> ObservatoryVerification:
    verify_observatory(value)
    checks = (
        _make_check("member-identities", ObservatoryCheckSeverity.REQUIRED.value, len({item.member_id for item in value.members}) == value.member_count, "member IDs and history addresses are unique", str(value.member_count), str(len({item.member_id for item in value.members}))),
        _make_check("member-addresses", ObservatoryCheckSeverity.REQUIRED.value, all(address_member(item) == item.content_address for item in value.members), "every member content address is recomputed", "addressed", "addressed" if all(address_member(item) == item.content_address for item in value.members) else "mismatch"),
        _make_check("counter-conservation", ObservatoryCheckSeverity.REQUIRED.value, value.entry_count == sum(item.entry_count for item in value.members), "aggregate entry and quality counters are conserved", str(value.entry_count), str(sum(item.entry_count for item in value.members))),
        _make_check("state-projection", ObservatoryCheckSeverity.REQUIRED.value, value.state == _aggregate_state(value.members), "aggregate state is recomputed from member terminal states", _aggregate_state(value.members), value.state),
        _make_check("readiness-projection", ObservatoryCheckSeverity.REQUIRED.value, value.release_ready == (bool(value.members) and value.state == ObservatoryState.READY.value and all(item.release_ready for item in value.members)), "release readiness is conjunctive across members", "conjunctive", "conjunctive"),
        _make_check("history-addresses", ObservatoryCheckSeverity.REQUIRED.value, len({item.history_address for item in value.members}) == value.member_count, "source history addresses remain distinct", str(value.member_count), str(len({item.history_address for item in value.members}))),
        _make_check("public-boundary", ObservatoryCheckSeverity.REQUIRED.value, _public(value.to_dict()), "the aggregate contains only public path-free fields", "public", "public" if _public(value.to_dict()) else "private"),
        _make_check("content-address", ObservatoryCheckSeverity.REQUIRED.value, address_observatory(value) == value.content_address, "the observatory address is reproducible", value.content_address, address_observatory(value)),
    )
    passed = sum(check.passed for check in checks)
    warning = sum(not check.passed and check.severity == ObservatoryCheckSeverity.OPTIONAL.value for check in checks)
    blocker = sum(not check.passed and check.severity == ObservatoryCheckSeverity.REQUIRED.value for check in checks)
    state, release_ready = _gate_for(value)
    if blocker:
        state, release_ready = ObservatoryGateState.BLOCK.value, False
    body = {"verification_id": DEFAULT_OBSERVATORY_ID + "-verification" if verification_id is None else _text(verification_id, "verification ID", 512), "observatory_id": value.observatory_id, "observatory_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "check_count": len(checks), "passed_count": passed, "warning_count": warning, "blocker_count": blocker, "state": state, "release_ready": release_ready, "checks": checks}
    provisional = ObservatoryVerification(**body, content_address="pending:verification")
    return ObservatoryVerification(**body, content_address=address_verification(provisional))


class ObservatoryPackage:
    """In-memory package view used by persistence and operator tooling."""

    def __init__(self, observatory: AssuranceHistoryObservatory, verification: ObservatoryVerification, metrics: Mapping[str, Any]) -> None:
        self.observatory = observatory
        self.verification = verification
        self.metrics = dict(metrics)
        self._validate()

    def _validate(self) -> None:
        verify_observatory(self.observatory)
        if not isinstance(self.verification, ObservatoryVerification):
            raise ValidationError("observatory package verification must be typed")
        if self.verification.observatory_address != self.observatory.content_address or self.verification.observatory_id != self.observatory.observatory_id:
            raise ValidationError("observatory package linkage is invalid")
        if dict(self.metrics) != metrics_document(self.observatory):
            raise ValidationError("observatory package metrics are not recomputed")
        if not _public(self.metrics):
            raise ValidationError("observatory package metrics cross the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"observatory": self.observatory.to_dict(), "verification": self.verification.to_dict(), "metrics": self.metrics}


def metrics_document(value: AssuranceHistoryObservatory) -> dict[str, Any]:
    verify_observatory(value)
    return {
        "observatory_id": value.observatory_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "member_count": value.member_count,
        "entry_count": value.entry_count,
        "state": value.state,
        "member_state_counts": {state.value: sum(_member_state(item) == state.value for item in value.members) for state in ObservatoryState},
        "transition_counts": {transition.value: getattr(value, f"{transition.value}_count") for transition in HistoryTransition},
        "gate_state_counts": {state.value: getattr(value, f"{state.value}_count") for state in history_model.assurance_model.GateState},
        "quality_totals": {field: getattr(value, field) for field in ("finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count", "check_count", "passed_check_count", "warning_check_count", "blocker_check_count")},
        "accepted_member_count": sum(item.accepted for item in value.members),
        "release_ready_member_count": sum(item.release_ready for item in value.members),
        "content_address": value.content_address,
    }


def package_from_values(value: AssuranceHistoryObservatory, verification: ObservatoryVerification | None = None) -> ObservatoryPackage:
    return ObservatoryPackage(value, build_verification(value) if verification is None else verification, metrics_document(value))


class ObservatoryDiffItem:
    """One member-level change between two observatories."""

    def __init__(self, ordinal: int, key: str, action: str, direction: str, baseline: ObservatoryMember | None, candidate: ObservatoryMember | None, detail: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.key = key
        self.action = action
        self.direction = direction
        self.baseline = baseline
        self.candidate = candidate
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "observatory diff ordinal", MAX_MEMBERS * 2)
        _text(self.key, "observatory diff key", 512)
        _action(self.action)
        _direction(self.direction)
        if self.baseline is None and self.candidate is None:
            raise ValidationError("observatory diff item requires a side")
        if self.action == ObservatoryDiffAction.ADDED.value and (self.baseline is not None or self.candidate is None):
            raise ValidationError("added observatory diff item has invalid sides")
        if self.action == ObservatoryDiffAction.REMOVED.value and (self.baseline is None or self.candidate is not None):
            raise ValidationError("removed observatory diff item has invalid sides")
        if self.action in {ObservatoryDiffAction.UNCHANGED.value, ObservatoryDiffAction.CHANGED.value} and (self.baseline is None or self.candidate is None):
            raise ValidationError("shared observatory diff item has invalid sides")
        _text(self.detail, "observatory diff detail", MAX_TEXT)
        _address(self.content_address, "observatory diff item address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff item crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_diff_item(self) != self.content_address:
            raise ValidationError("observatory diff item address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "key": self.key, "action": self.action, "direction": self.direction, "baseline": None if self.baseline is None else self.baseline.to_dict(), "candidate": None if self.candidate is None else self.candidate.to_dict(), "detail": self.detail, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "key": self.key, "action": self.action, "direction": self.direction, "baseline_state": None if self.baseline is None else _member_state(self.baseline), "candidate_state": None if self.candidate is None else _member_state(self.candidate), "detail": self.detail, "content_address": self.content_address}


def address_diff_item(value: ObservatoryDiffItem) -> str:
    if not isinstance(value, ObservatoryDiffItem):
        raise ValidationError("observatory diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


def _diff_direction(action: str, baseline: ObservatoryMember | None, candidate: ObservatoryMember | None) -> str:
    if action == ObservatoryDiffAction.UNCHANGED.value:
        return ObservatoryDiffDirection.UNCHANGED.value
    if action == ObservatoryDiffAction.ADDED.value:
        return ObservatoryDiffDirection.IMPROVED.value if candidate is not None and _quality_vector(candidate) > (0,) else ObservatoryDiffDirection.REGRESSED.value
    if action == ObservatoryDiffAction.REMOVED.value:
        return ObservatoryDiffDirection.REGRESSED.value
    assert baseline is not None and candidate is not None
    before, after = _quality_vector(baseline), _quality_vector(candidate)
    if after > before:
        return ObservatoryDiffDirection.IMPROVED.value
    if after < before:
        return ObservatoryDiffDirection.REGRESSED.value
    return ObservatoryDiffDirection.MIXED.value


def _diff_detail(action: str, baseline: ObservatoryMember | None, candidate: ObservatoryMember | None) -> str:
    if action == ObservatoryDiffAction.ADDED.value:
        return "member added to candidate observatory"
    if action == ObservatoryDiffAction.REMOVED.value:
        return "member removed from candidate observatory"
    if action == ObservatoryDiffAction.UNCHANGED.value:
        return "member projection unchanged"
    assert baseline is not None and candidate is not None
    return f"member terminal state changed from {_member_state(baseline)} to {_member_state(candidate)}"


def _make_diff_item(ordinal: int, key: str, action: str, baseline: ObservatoryMember | None, candidate: ObservatoryMember | None) -> ObservatoryDiffItem:
    body = {"ordinal": ordinal, "key": key, "action": action, "direction": _diff_direction(action, baseline, candidate), "baseline": baseline, "candidate": candidate, "detail": _diff_detail(action, baseline, candidate)}
    provisional = ObservatoryDiffItem(**body, content_address="pending:diff-item")
    return ObservatoryDiffItem(**body, content_address=address_diff_item(provisional))


class ObservatoryDiff:
    """Addressed member-level comparison between two observatories."""

    def __init__(self, diff_id: str, version: str, boundary: str, baseline_address: str, candidate_address: str, item_count: int, added_count: int, removed_count: int, unchanged_count: int, changed_count: int, improved_count: int, regressed_count: int, mixed_count: int, state: str, release_ready: bool, items: Sequence[ObservatoryDiffItem], content_address: str) -> None:
        self.diff_id = diff_id
        self.version = version
        self.boundary = boundary
        self.baseline_address = baseline_address
        self.candidate_address = candidate_address
        self.item_count = item_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.improved_count = improved_count
        self.regressed_count = regressed_count
        self.mixed_count = mixed_count
        self.state = state
        self.release_ready = release_ready
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "observatory diff ID", 512)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("observatory diff contract is invalid")
        _address(self.baseline_address, "observatory diff baseline address")
        _address(self.candidate_address, "observatory diff candidate address")
        _count(self.item_count, "observatory diff item count", MAX_MEMBERS * 2)
        for count, field in ((self.added_count, "added count"), (self.removed_count, "removed count"), (self.unchanged_count, "unchanged count"), (self.changed_count, "changed count"), (self.improved_count, "improved count"), (self.regressed_count, "regressed count"), (self.mixed_count, "mixed count")):
            _count(count, field, MAX_MEMBERS * 2)
        _direction(self.state, "observatory diff state")
        _bool(self.release_ready, "observatory diff release-ready")
        if self.item_count != len(self.items) or self.added_count + self.removed_count + self.unchanged_count + self.changed_count != self.item_count or self.improved_count + self.regressed_count + self.mixed_count + self.unchanged_count != self.item_count:
            raise ValidationError("observatory diff counts are not conserved")
        if len({item.key for item in self.items}) != self.item_count or len({item.content_address for item in self.items}) != self.item_count:
            raise ValidationError("observatory diff item identities are not unique")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_diff(self) != self.content_address:
            raise ValidationError("observatory diff address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "mixed_count": self.mixed_count, "state": self.state, "release_ready": self.release_ready, "items": tuple(item.to_dict() for item in self.items), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("diff_id", "baseline_address", "candidate_address", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "mixed_count", "state", "release_ready", "content_address")}


def address_diff(value: ObservatoryDiff) -> str:
    if not isinstance(value, ObservatoryDiff):
        raise ValidationError("observatory diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def build_diff(baseline: AssuranceHistoryObservatory, candidate: AssuranceHistoryObservatory, *, diff_id: str = DEFAULT_DIFF_ID) -> ObservatoryDiff:
    verify_observatory(baseline)
    verify_observatory(candidate)
    before = {item.member_id: item for item in baseline.members}
    after = {item.member_id: item for item in candidate.members}
    items: list[ObservatoryDiffItem] = []
    for ordinal, key in enumerate(sorted(set(before) | set(after))):
        left, right = before.get(key), after.get(key)
        if left is None:
            action = ObservatoryDiffAction.ADDED.value
        elif right is None:
            action = ObservatoryDiffAction.REMOVED.value
        elif left.to_dict() == right.to_dict():
            action = ObservatoryDiffAction.UNCHANGED.value
        else:
            action = ObservatoryDiffAction.CHANGED.value
        items.append(_make_diff_item(ordinal, key, action, left, right))
    action_counts = {action.value: sum(item.action == action.value for item in items) for action in ObservatoryDiffAction}
    direction_counts = {direction.value: sum(item.direction == direction.value for item in items) for direction in ObservatoryDiffDirection}
    if direction_counts[ObservatoryDiffDirection.MIXED.value] and (direction_counts[ObservatoryDiffDirection.IMPROVED.value] or direction_counts[ObservatoryDiffDirection.REGRESSED.value]):
        state = ObservatoryDiffDirection.MIXED.value
    elif direction_counts[ObservatoryDiffDirection.REGRESSED.value]:
        state = ObservatoryDiffDirection.REGRESSED.value
    elif direction_counts[ObservatoryDiffDirection.IMPROVED.value]:
        state = ObservatoryDiffDirection.IMPROVED.value
    else:
        state = ObservatoryDiffDirection.UNCHANGED.value
    body = {"diff_id": _text(diff_id, "observatory diff ID", 512), "version": VERSION, "boundary": BOUNDARY, "baseline_address": baseline.content_address, "candidate_address": candidate.content_address, "item_count": len(items), "added_count": action_counts[ObservatoryDiffAction.ADDED.value], "removed_count": action_counts[ObservatoryDiffAction.REMOVED.value], "unchanged_count": action_counts[ObservatoryDiffAction.UNCHANGED.value], "changed_count": action_counts[ObservatoryDiffAction.CHANGED.value], "improved_count": direction_counts[ObservatoryDiffDirection.IMPROVED.value], "regressed_count": direction_counts[ObservatoryDiffDirection.REGRESSED.value], "mixed_count": direction_counts[ObservatoryDiffDirection.MIXED.value], "state": state, "release_ready": candidate.release_ready, "items": tuple(items)}
    provisional = ObservatoryDiff(**body, content_address="pending:diff")
    return ObservatoryDiff(**body, content_address=address_diff(provisional))


def verify_diff(value: ObservatoryDiff) -> ObservatoryDiff:
    if not isinstance(value, ObservatoryDiff):
        raise ValidationError("observatory diff verification requires a typed diff")
    for item in value.items:
        if address_diff_item(item) != item.content_address:
            raise ValidationError("observatory diff item address verification failed")
    if address_diff(value) != value.content_address:
        raise ValidationError("observatory diff address verification failed")
    return value


def verify_diff_against_observatories(value: ObservatoryDiff, baseline: AssuranceHistoryObservatory, candidate: AssuranceHistoryObservatory) -> ObservatoryDiff:
    verify_diff(value)
    expected = build_diff(baseline, candidate, diff_id=value.diff_id)
    if expected.to_dict() != value.to_dict():
        raise ValidationError("observatory diff does not match independently recomputed observatories")
    return value


def diff_item_from_mapping(value: Mapping[str, Any]) -> ObservatoryDiffItem:
    value = _mapping(value, "observatory diff item")
    _strict(value, {"ordinal", "key", "action", "direction", "baseline", "candidate", "detail", "content_address"}, "observatory diff item")
    baseline = None if value.get("baseline") is None else member_from_mapping(_mapping(value.get("baseline"), "observatory diff baseline"))
    candidate = None if value.get("candidate") is None else member_from_mapping(_mapping(value.get("candidate"), "observatory diff candidate"))
    return ObservatoryDiffItem(**(dict(value) | {"baseline": baseline, "candidate": candidate}))


def diff_from_mapping(value: Mapping[str, Any]) -> ObservatoryDiff:
    value = _mapping(value, "observatory diff")
    _strict(value, {"diff_id", "version", "boundary", "baseline_address", "candidate_address", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "mixed_count", "state", "release_ready", "items", "content_address"}, "observatory diff")
    items = tuple(diff_item_from_mapping(item) for item in _sequence(value.get("items"), "observatory diff items", MAX_MEMBERS * 2))
    return ObservatoryDiff(**(dict(value) | {"items": items}))


class ObservatoryQuery:
    RESOURCES = ("summary", "members", "empty", "ready", "held", "blocked", "mixed", "accepted", "rejected")

    def __init__(self, resource: str = "summary", state: str | None = None, latest_transition: str | None = None, accepted: bool | None = None, release_ready: bool | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "observatory query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("observatory query resource is not supported")
        self.state = None if state is None else _state(state, "observatory query state")
        self.latest_transition = _transition(latest_transition, "observatory query latest transition")
        self.accepted = None if accepted is None else _bool(accepted, "observatory query accepted")
        self.release_ready = None if release_ready is None else _bool(release_ready, "observatory query release-ready")
        self.text = _optional_text(text, "observatory query text", 512)
        self.offset = _count(offset, "observatory query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "observatory query limit", MAX_QUERY_ITEMS, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "state": self.state, "latest_transition": self.latest_transition, "accepted": self.accepted, "release_ready": self.release_ready, "text": self.text, "offset": self.offset, "limit": self.limit}


class ObservatoryQueryResult:
    def __init__(self, observatory_address: str, query: ObservatoryQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.observatory_address = observatory_address
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.observatory_address, "observatory query address")
        _count(self.total_count, "observatory query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "observatory query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.query.limit or self.returned_count > self.total_count:
            raise ValidationError("observatory query window is invalid")
        _address(self.content_address, "observatory query result address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory query crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_query(self) != self.content_address:
            raise ValidationError("observatory query address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"observatory_address": self.observatory_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}


def address_query(value: ObservatoryQueryResult) -> str:
    if not isinstance(value, ObservatoryQueryResult):
        raise ValidationError("observatory query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _matches_member(member: ObservatoryMember, query: ObservatoryQuery) -> bool:
    state = _member_state(member)
    if query.state is not None and state != query.state:
        return False
    if query.latest_transition is not None and member.latest_transition != query.latest_transition:
        return False
    if query.accepted is not None and member.accepted != query.accepted:
        return False
    if query.release_ready is not None and member.release_ready != query.release_ready:
        return False
    if query.resource == "empty" and state != ObservatoryState.EMPTY.value:
        return False
    if query.resource == "ready" and state != ObservatoryState.READY.value:
        return False
    if query.resource == "held" and state != ObservatoryState.HELD.value:
        return False
    if query.resource == "blocked" and state != ObservatoryState.BLOCKED.value:
        return False
    if query.resource == "mixed" and state != ObservatoryState.MIXED.value:
        return False
    if query.resource == "accepted" and not member.accepted:
        return False
    if query.resource == "rejected" and member.accepted:
        return False
    if query.text:
        haystack = canonical_json(member.to_dict()).lower()
        if query.text.lower() not in haystack:
            return False
    return True


def query_observatory(value: AssuranceHistoryObservatory, query: ObservatoryQuery | None = None, **kwargs: Any) -> ObservatoryQueryResult:
    verify_observatory(value)
    query = ObservatoryQuery(**kwargs) if query is None else query
    if not isinstance(query, ObservatoryQuery):
        raise ValidationError("observatory query requires a typed query")
    if query.resource == "summary":
        records = (value.summary(),)
    else:
        matching = tuple(member.summary() for member in value.members if _matches_member(member, query))
        total = len(matching)
        window = matching[query.offset : query.offset + query.limit]
        body = {"observatory_address": value.content_address, "query": query, "total_count": total, "records": window}
        provisional = ObservatoryQueryResult(**body, content_address="pending:query")
        return ObservatoryQueryResult(**body, content_address=address_query(provisional))
    body = {"observatory_address": value.content_address, "query": query, "total_count": 1, "records": records}
    provisional = ObservatoryQueryResult(**body, content_address="pending:query")
    return ObservatoryQueryResult(**body, content_address=address_query(provisional))


class ObservatoryDiffQuery:
    RESOURCES = ("summary", "items", "added", "removed", "unchanged", "changed", "improved", "regressed", "mixed")

    def __init__(self, resource: str = "summary", action: str | None = None, direction: str | None = None, state: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "observatory diff query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("observatory diff query resource is not supported")
        self.action = None if action is None else _action(action, "observatory diff query action")
        self.direction = None if direction is None else _direction(direction, "observatory diff query direction")
        self.state = None if state is None else _state(state, "observatory diff query state")
        self.text = _optional_text(text, "observatory diff query text", 512)
        self.offset = _count(offset, "observatory diff query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "observatory diff query limit", MAX_QUERY_ITEMS, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "action": self.action, "direction": self.direction, "state": self.state, "text": self.text, "offset": self.offset, "limit": self.limit}


class ObservatoryDiffQueryResult:
    def __init__(self, diff_address: str, query: ObservatoryDiffQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.diff_address = diff_address
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.diff_address, "observatory diff query address")
        _count(self.total_count, "observatory diff query total count", MAX_MEMBERS * 2)
        _count(self.returned_count, "observatory diff query returned count", MAX_MEMBERS * 2)
        if self.returned_count > self.query.limit or self.returned_count > self.total_count:
            raise ValidationError("observatory diff query window is invalid")
        _address(self.content_address, "observatory diff query result address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff query crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_diff_query(self) != self.content_address:
            raise ValidationError("observatory diff query address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}


def address_diff_query(value: ObservatoryDiffQueryResult) -> str:
    if not isinstance(value, ObservatoryDiffQueryResult):
        raise ValidationError("observatory diff query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_QUERY_PREFIX)


def _matches_diff_item(item: ObservatoryDiffItem, query: ObservatoryDiffQuery) -> bool:
    if query.action is not None and item.action != query.action:
        return False
    if query.direction is not None and item.direction != query.direction:
        return False
    if query.resource in {"added", "removed", "unchanged", "changed"} and item.action != query.resource:
        return False
    if query.resource in {"improved", "regressed", "mixed"} and item.direction != query.resource:
        return False
    if query.state is not None:
        states = {_member_state(item.baseline) if item.baseline is not None else None, _member_state(item.candidate) if item.candidate is not None else None}
        if query.state not in states:
            return False
    if query.text and query.text.lower() not in canonical_json(item.to_dict()).lower():
        return False
    return True


def query_diff(value: ObservatoryDiff, query: ObservatoryDiffQuery | None = None, **kwargs: Any) -> ObservatoryDiffQueryResult:
    verify_diff(value)
    query = ObservatoryDiffQuery(**kwargs) if query is None else query
    if not isinstance(query, ObservatoryDiffQuery):
        raise ValidationError("observatory diff query requires a typed query")
    if query.resource == "summary":
        records = (value.summary(),)
        total = 1
    else:
        matching = tuple(item.summary() for item in value.items if _matches_diff_item(item, query))
        total = len(matching)
        records = matching[query.offset : query.offset + query.limit]
    body = {"diff_address": value.content_address, "query": query, "total_count": total, "records": records}
    provisional = ObservatoryDiffQueryResult(**body, content_address="pending:diff-query")
    return ObservatoryDiffQueryResult(**body, content_address=address_diff_query(provisional))


def observatory_json(value: AssuranceHistoryObservatory) -> str:
    verify_observatory(value)
    return canonical_json(value.to_dict())


def member_json(value: ObservatoryMember) -> str:
    return canonical_json(value.to_dict())


def verification_json(value: ObservatoryVerification) -> str:
    if not isinstance(value, ObservatoryVerification):
        raise ValidationError("verification JSON requires a typed verification")
    return canonical_json(value.to_dict())


def verification_query_json(value: VerificationQueryResult) -> str:
    if not isinstance(value, VerificationQueryResult):
        raise ValidationError("verification query JSON requires a typed result")
    return canonical_json(value.to_dict())


def metrics_json(value: AssuranceHistoryObservatory) -> str:
    return canonical_json(metrics_document(value))


def diff_json(value: ObservatoryDiff) -> str:
    verify_diff(value)
    return canonical_json(value.to_dict())


def query_json(value: ObservatoryQueryResult) -> str:
    if not isinstance(value, ObservatoryQueryResult):
        raise ValidationError("observatory query JSON requires a typed result")
    return canonical_json(value.to_dict())


def diff_query_json(value: ObservatoryDiffQueryResult) -> str:
    if not isinstance(value, ObservatoryDiffQueryResult):
        raise ValidationError("observatory diff query JSON requires a typed result")
    return canonical_json(value.to_dict())


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: canonical_json(row.get(field)) if isinstance(row.get(field), (dict, list, tuple)) else row.get(field) for field in fields})
    return stream.getvalue()


def observatory_csv(value: AssuranceHistoryObservatory) -> str:
    return _csv_text((value.summary(),), tuple(value.summary()))


def members_csv(value: AssuranceHistoryObservatory) -> str:
    return _csv_text(tuple(member.summary() for member in value.members), ("member_id", "history_id", "entry_count", "latest_snapshot_id", "latest_transition", "state", "accepted", "release_ready", "content_address"))


def verification_csv(value: ObservatoryVerification) -> str:
    return _csv_text((value.summary(),), tuple(value.summary()))


def checks_csv(value: ObservatoryVerification) -> str:
    return _csv_text(tuple(check.to_dict() for check in value.checks), ("check_id", "severity", "passed", "detail", "expected", "observed", "content_address"))


def verification_query_csv(value: VerificationQueryResult) -> str:
    if not isinstance(value, VerificationQueryResult):
        raise ValidationError("verification query CSV requires a typed result")
    fields = tuple(value.records[0]) if value.records else ("verification_address", "query", "total_count", "returned_count", "content_address")
    return _csv_text(value.records, fields)


def diff_csv(value: ObservatoryDiff) -> str:
    return _csv_text((item.summary() for item in value.items), ("ordinal", "key", "action", "direction", "baseline_state", "candidate_state", "detail", "content_address"))


def query_csv(value: ObservatoryQueryResult) -> str:
    fields = tuple(value.records[0]) if value.records else ("observatory_address", "query", "total_count", "returned_count", "content_address")
    return _csv_text(value.records, fields)


def diff_query_csv(value: ObservatoryDiffQueryResult) -> str:
    fields = tuple(value.records[0]) if value.records else ("diff_address", "query", "total_count", "returned_count", "content_address")
    return _csv_text(value.records, fields)


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", "", "| Field | Value |", "| --- | --- |"]
    lines.extend(f"| {key} | {canonical_json(value)} |" for key, value in summary.items())
    if rows:
        fields = tuple(rows[0])
        lines.extend(("", "## Records", "", "| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"))
        lines.extend("| " + " | ".join(canonical_json(row.get(field)) for field in fields) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def render_observatory_markdown(value: AssuranceHistoryObservatory) -> str:
    return _markdown("Assurance history observatory", value.summary(), tuple(member.summary() for member in value.members))


def render_member_markdown(value: ObservatoryMember) -> str:
    return _markdown("Assurance history observatory member", value.summary(), ())


def render_verification_markdown(value: ObservatoryVerification) -> str:
    return _markdown("Assurance history observatory verification", value.summary(), tuple(check.to_dict() for check in value.checks))


def render_verification_query_markdown(value: VerificationQueryResult) -> str:
    if not isinstance(value, VerificationQueryResult):
        raise ValidationError("verification query Markdown requires a typed result")
    return _markdown("Assurance history observatory verification query", {key: item for key, item in value.to_dict().items() if key != "records"}, value.records)


def render_diff_markdown(value: ObservatoryDiff) -> str:
    return _markdown("Assurance history observatory diff", value.summary(), tuple(item.summary() for item in value.items))


def render_query_markdown(value: ObservatoryQueryResult) -> str:
    return _markdown("Assurance history observatory query", {key: item for key, item in value.to_dict().items() if key != "records"}, value.records)


def render_diff_query_markdown(value: ObservatoryDiffQueryResult) -> str:
    return _markdown("Assurance history observatory diff query", {key: item for key, item in value.to_dict().items() if key != "records"}, value.records)


def _string_schema(maximum: int = MAX_TEXT) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": maximum}


def _address_schema() -> dict[str, Any]:
    return {"type": "string", "pattern": r"^[^:]+:.+$", "maxLength": 1024}


def _nullable(schema: Mapping[str, Any]) -> dict[str, Any]:
    return {"anyOf": [dict(schema), {"type": "null"}]}


def _integer_schema(maximum: int) -> dict[str, Any]:
    return {"type": "integer", "minimum": 0, "maximum": maximum}


def _enum_schema(enum_type: type[StrEnum]) -> dict[str, Any]:
    return {"type": "string", "enum": [item.value for item in enum_type]}


def member_schema() -> dict[str, Any]:
    fields = {"member_id": _string_schema(512), "history_id": _string_schema(512), "history_address": _address_schema(), "head_address": _address_schema(), "entry_count": _integer_schema(history_model.MAX_ENTRIES), "latest_snapshot_id": _nullable(_string_schema(512)), "latest_transition": _nullable(_enum_schema(HistoryTransition)), "state": {"type": "string", "enum": [item.value for item in history_model.assurance_model.GateState] + [ObservatoryState.EMPTY.value]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, **{field: _integer_schema(history_model.MAX_ENTRIES) for field in ("initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "promote_count", "hold_count", "block_count")}, **{field: _integer_schema(MAX_MEMBER_FINDINGS) for field in ("finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count")}, **{field: _integer_schema(MAX_MEMBER_CHECKS) for field in ("check_count", "passed_check_count", "warning_check_count", "blocker_check_count")}, "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def observatory_schema() -> dict[str, Any]:
    fields = {"observatory_id": _string_schema(512), "version": _string_schema(128), "boundary": _string_schema(256), "member_count": _integer_schema(MAX_MEMBERS), "entry_count": _integer_schema(MAX_MEMBERS * history_model.MAX_ENTRIES), "state": _enum_schema(ObservatoryState), "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, **{field: _integer_schema(MAX_MEMBERS) for field in ("empty_member_count", "ready_member_count", "held_member_count", "blocked_member_count", "mixed_member_count")}, **{field: _integer_schema(MAX_MEMBERS * history_model.MAX_ENTRIES) for field in ("initial_count", "stable_count", "improved_count", "regressed_count", "changed_count", "promote_count", "hold_count", "block_count")}, **{field: _integer_schema(MAX_MEMBERS * max(history_model.assurance_model.MAX_FINDINGS, history_model.assurance_model.MAX_CHECKS) * history_model.MAX_ENTRIES) for field in ("finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count", "check_count", "passed_check_count", "warning_check_count", "blocker_check_count")}, "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def check_schema() -> dict[str, Any]:
    fields = {"check_id": _string_schema(512), "severity": _enum_schema(ObservatoryCheckSeverity), "passed": {"type": "boolean"}, "detail": _string_schema(MAX_TEXT), "expected": _string_schema(MAX_TEXT), "observed": _string_schema(MAX_TEXT), "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def verification_schema() -> dict[str, Any]:
    fields = {"verification_id": _string_schema(512), "observatory_id": _string_schema(512), "observatory_address": _address_schema(), "version": _string_schema(128), "boundary": _string_schema(256), "check_count": _integer_schema(MAX_CHECKS), "passed_count": _integer_schema(MAX_CHECKS), "warning_count": _integer_schema(MAX_CHECKS), "blocker_count": _integer_schema(MAX_CHECKS), "state": _enum_schema(ObservatoryGateState), "release_ready": {"type": "boolean"}, "checks": {"type": "array", "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def verification_query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(VerificationQuery.RESOURCES)}, "severity": {"anyOf": [_enum_schema(ObservatoryCheckSeverity), {"type": "null"}]}, "passed": {"anyOf": [{"type": "boolean"}, {"type": "null"}]}, "text": _nullable(_string_schema(512)), "offset": _integer_schema(MAX_QUERY_ITEMS), "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}}
    query = {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}
    summary_fields = {key: verification_schema()["properties"][key] for key in ("verification_id", "observatory_id", "observatory_address", "check_count", "passed_count", "warning_count", "blocker_count", "state", "release_ready", "content_address")}
    summary = {"type": "object", "additionalProperties": False, "required": list(summary_fields), "properties": summary_fields}
    result_fields = {"verification_address": _address_schema(), "query": query, "total_count": _integer_schema(MAX_CHECKS), "returned_count": _integer_schema(MAX_CHECKS), "records": {"type": "array", "maxItems": MAX_CHECKS, "items": {"anyOf": [summary, check_schema()]}}, "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(result_fields), "properties": result_fields}


def metrics_schema() -> dict[str, Any]:
    fields = {"observatory_id": _string_schema(512), "version": _string_schema(128), "boundary": _string_schema(256), "member_count": _integer_schema(MAX_MEMBERS), "entry_count": _integer_schema(MAX_MEMBERS * history_model.MAX_ENTRIES), "state": _enum_schema(ObservatoryState), "member_state_counts": {"type": "object", "additionalProperties": False, "properties": {state.value: _integer_schema(MAX_MEMBERS) for state in ObservatoryState}}, "transition_counts": {"type": "object", "additionalProperties": False, "properties": {transition.value: _integer_schema(MAX_MEMBERS * history_model.MAX_ENTRIES) for transition in HistoryTransition}}, "gate_state_counts": {"type": "object", "additionalProperties": False, "properties": {state.value: _integer_schema(MAX_MEMBERS * history_model.MAX_ENTRIES) for state in history_model.assurance_model.GateState}}, "quality_totals": {"type": "object", "additionalProperties": False, "properties": {field: _integer_schema(MAX_MEMBERS * max(history_model.assurance_model.MAX_FINDINGS, history_model.assurance_model.MAX_CHECKS) * history_model.MAX_ENTRIES) for field in ("finding_count", "passed_finding_count", "warning_finding_count", "blocker_finding_count", "check_count", "passed_check_count", "warning_check_count", "blocker_check_count")}}, "accepted_member_count": _integer_schema(MAX_MEMBERS), "release_ready_member_count": _integer_schema(MAX_MEMBERS), "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def diff_item_schema() -> dict[str, Any]:
    fields = {"ordinal": _integer_schema(MAX_MEMBERS * 2), "key": _string_schema(512), "action": _enum_schema(ObservatoryDiffAction), "direction": _enum_schema(ObservatoryDiffDirection), "baseline": _nullable(member_schema()), "candidate": _nullable(member_schema()), "detail": _string_schema(MAX_TEXT), "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def diff_schema() -> dict[str, Any]:
    fields = {"diff_id": _string_schema(512), "version": _string_schema(128), "boundary": _string_schema(256), "baseline_address": _address_schema(), "candidate_address": _address_schema(), "item_count": _integer_schema(MAX_MEMBERS * 2), "added_count": _integer_schema(MAX_MEMBERS * 2), "removed_count": _integer_schema(MAX_MEMBERS * 2), "unchanged_count": _integer_schema(MAX_MEMBERS * 2), "changed_count": _integer_schema(MAX_MEMBERS * 2), "improved_count": _integer_schema(MAX_MEMBERS * 2), "regressed_count": _integer_schema(MAX_MEMBERS * 2), "mixed_count": _integer_schema(MAX_MEMBERS * 2), "state": _enum_schema(ObservatoryDiffDirection), "release_ready": {"type": "boolean"}, "items": {"type": "array", "maxItems": MAX_MEMBERS * 2, "items": diff_item_schema()}, "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(ObservatoryQuery.RESOURCES)}, "state": _nullable(_enum_schema(ObservatoryState)), "latest_transition": _nullable(_enum_schema(HistoryTransition)), "accepted": {"anyOf": [{"type": "boolean"}, {"type": "null"}]}, "release_ready": {"anyOf": [{"type": "boolean"}, {"type": "null"}]}, "text": _nullable(_string_schema(512)), "offset": _integer_schema(MAX_QUERY_ITEMS), "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def diff_query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(ObservatoryDiffQuery.RESOURCES)}, "action": {"anyOf": [_enum_schema(ObservatoryDiffAction), {"type": "null"}]}, "direction": {"anyOf": [_enum_schema(ObservatoryDiffDirection), {"type": "null"}]}, "state": {"anyOf": [_enum_schema(ObservatoryState), {"type": "null"}]}, "text": _nullable(_string_schema(512)), "offset": _integer_schema(MAX_QUERY_ITEMS), "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def package_schema() -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": ["observatory", "verification", "metrics"], "properties": {"observatory": observatory_schema(), "verification": verification_schema(), "metrics": metrics_schema()}}


def capabilities() -> dict[str, Any]:
    return {
        "version": VERSION,
        "boundary": BOUNDARY,
        "package_files": FILES,
        "diff_package_files": DIFF_FILES,
        "limits": {"max_members": MAX_MEMBERS, "max_checks": MAX_CHECKS, "max_query_items": MAX_QUERY_ITEMS},
        "features": (
            "source-scoped verified history members",
            "conserved cross-history counters",
            "ready-held-blocked-mixed aggregate state",
            "independent eight-check verification",
            "exact package and diff persistence",
            "canonical-byte and manifest receipts",
            "member-level improved-regressed diffs",
            "bounded state and readiness queries",
            "deterministic JSON CSV and Markdown projections",
        ),
        "resources": {"observatory": ObservatoryQuery.RESOURCES, "verification": VerificationQuery.RESOURCES, "diff": ObservatoryDiffQuery.RESOURCES},
        "schemas": ("member", "observatory", "check", "verification", "verification-query", "metrics", "package", "diff-item", "diff", "query", "diff-query"),
    }


def _artifact(name: str, raw: bytes) -> dict[str, Any]:
    return {"name": name, "size": len(raw), "hash": hash_bytes(raw, prefix=MANIFEST_PREFIX + "-artifact")}


def _manifest_body(package: ObservatoryPackage, artifacts: Mapping[str, bytes]) -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "observatory_id": package.observatory.observatory_id, "observatory_address": package.observatory.content_address, "verification_address": package.verification.content_address, "artifact_count": len(artifacts), "files": tuple(artifacts), "artifacts": tuple(_artifact(name, artifacts[name]) for name in artifacts)}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value) | {"manifest_address": None}, prefix=MANIFEST_PREFIX)


def _diff_manifest_body(value: ObservatoryDiff, raw: bytes) -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_id": value.diff_id, "baseline_address": value.baseline_address, "candidate_address": value.candidate_address, "artifact_count": 1, "files": (DIFF_NAME,), "artifact": _artifact(DIFF_NAME, raw)}


def _diff_manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value) | {"manifest_address": None}, prefix=DIFF_MANIFEST_PREFIX)


def _write_exact(destination: Path, files: Mapping[str, bytes], *, overwrite: bool, prefix: str) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("destination already exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_dir():
            raise ValidationError("destination must be a regular directory")
        if any(item.is_symlink() for item in destination.iterdir()) or {item.name for item in destination.iterdir()} != set(files):
            raise ValidationError("existing destination is not an exact compatible package")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=prefix, dir=str(destination.parent)))
    try:
        for name, raw in files.items():
            (temporary / name).write_bytes(raw)
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def write_observatory(value: AssuranceHistoryObservatory, directory: str | Path, *, verification: ObservatoryVerification | None = None, overwrite: bool = False) -> Path:
    package = package_from_values(value, verification)
    observatory_raw = canonical_bytes(value.to_dict())
    members_raw = canonical_bytes({"version": VERSION, "boundary": BOUNDARY, "observatory_id": value.observatory_id, "member_count": value.member_count, "members": tuple(item.to_dict() for item in value.members)})
    verification_raw = canonical_bytes(package.verification.to_dict())
    metrics_raw = canonical_bytes(package.metrics)
    artifacts = {OBSERVATORY_NAME: observatory_raw, MEMBERS_NAME: members_raw, VERIFICATION_NAME: verification_raw, METRICS_NAME: metrics_raw}
    manifest = _manifest_body(package, artifacts)
    manifest["manifest_address"] = _manifest_address(manifest)
    return _write_exact(Path(directory), {**artifacts, MANIFEST_NAME: canonical_bytes(manifest)}, overwrite=overwrite, prefix=".gnd-history-observatory-")


def write_diff(value: ObservatoryDiff, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_diff(value)
    raw = canonical_bytes(value.to_dict())
    manifest = _diff_manifest_body(value, raw)
    manifest["manifest_address"] = _diff_manifest_address(manifest)
    return _write_exact(Path(directory), {DIFF_NAME: raw, MANIFEST_NAME: canonical_bytes(manifest)}, overwrite=overwrite, prefix=".gnd-history-observatory-diff-")


def _read_json(path: Path, field: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"{field} must be a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{field} is invalid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"{field} is not canonical JSON")
    return dict(_mapping(value, field))


def _verify_directory(source: Path, files: Sequence[str], field: str) -> Mapping[str, Any]:
    if source.is_symlink() or not source.is_dir():
        raise ValidationError(f"{field} directory must be a regular directory")
    if any(item.is_symlink() for item in source.iterdir()) or {item.name for item in source.iterdir()} != set(files):
        raise ValidationError(f"{field} file set is invalid")
    return _read_json(source / MANIFEST_NAME, f"{field} manifest")


def _verify_artifact(manifest: Mapping[str, Any], source: Path, name: str, field: str) -> bytes:
    artifacts = _sequence(manifest.get("artifacts"), f"{field} artifacts", 4)
    matches = [item for item in artifacts if _mapping(item, f"{field} artifact").get("name") == name]
    if len(matches) != 1:
        raise ValidationError(f"{field} is missing exactly one {name} artifact")
    path = source / name
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"{field} {name} must be a regular file")
    raw = path.read_bytes()
    if dict(_mapping(matches[0], f"{field} artifact")) != _artifact(name, raw):
        raise ValidationError(f"{field} {name} bytes are not addressed")
    return raw


def _load_package(directory: str | Path) -> ObservatoryPackage:
    source = Path(directory)
    manifest = _verify_directory(source, FILES, "assurance history observatory")
    allowed = {"version", "boundary", "observatory_id", "observatory_address", "verification_address", "artifact_count", "files", "artifacts", "manifest_address"}
    _strict(manifest, allowed, "assurance history observatory manifest")
    if manifest.get("version") != VERSION or manifest.get("boundary") != BOUNDARY or manifest.get("artifact_count") != 4 or tuple(manifest.get("files", ())) != (OBSERVATORY_NAME, MEMBERS_NAME, VERIFICATION_NAME, METRICS_NAME) or manifest.get("manifest_address") != _manifest_address(dict(manifest) | {"manifest_address": None}):
        raise ValidationError("assurance history observatory manifest contract is invalid")
    raw_by_name = {name: _verify_artifact(manifest, source, name, "assurance history observatory") for name in (OBSERVATORY_NAME, MEMBERS_NAME, VERIFICATION_NAME, METRICS_NAME)}
    summary = _read_json(source / OBSERVATORY_NAME, "assurance history observatory summary")
    members_document = _read_json(source / MEMBERS_NAME, "assurance history observatory members")
    verification_document = _read_json(source / VERIFICATION_NAME, "assurance history observatory verification")
    metrics = _read_json(source / METRICS_NAME, "assurance history observatory metrics")
    _strict(members_document, {"version", "boundary", "observatory_id", "member_count", "members"}, "assurance history observatory members")
    if members_document.get("version") != VERSION or members_document.get("boundary") != BOUNDARY or members_document.get("observatory_id") != summary.get("observatory_id") or members_document.get("member_count") != summary.get("member_count"):
        raise ValidationError("assurance history observatory members linkage is invalid")
    value = observatory_from_mapping(dict(summary) | {"members": members_document.get("members")})
    verification = verification_from_mapping(verification_document)
    expected_verification = build_verification(value, verification_id=verification.verification_id)
    if expected_verification.to_dict() != verification.to_dict():
        raise ValidationError("assurance history observatory verification is not independently reproducible")
    if metrics != metrics_document(value):
        raise ValidationError("assurance history observatory metrics are not reproducible")
    if manifest.get("observatory_id") != value.observatory_id or manifest.get("observatory_address") != value.content_address or manifest.get("verification_address") != verification.content_address:
        raise ValidationError("assurance history observatory manifest linkage is invalid")
    if canonical_bytes(summary) != raw_by_name[OBSERVATORY_NAME] or canonical_bytes(members_document) != raw_by_name[MEMBERS_NAME] or canonical_bytes(verification_document) != raw_by_name[VERIFICATION_NAME] or canonical_bytes(metrics) != raw_by_name[METRICS_NAME]:
        raise ValidationError("assurance history observatory artifact bytes are not canonical")
    return ObservatoryPackage(value, verification, metrics)


def load_observatory(directory: str | Path) -> AssuranceHistoryObservatory:
    return _load_package(directory).observatory


def load_package(directory: str | Path) -> ObservatoryPackage:
    return _load_package(directory)


def load_verification(directory: str | Path) -> ObservatoryVerification:
    return _load_package(directory).verification


def verify_observatory_directory(directory: str | Path) -> ObservatoryVerification:
    return _load_package(directory).verification


def _load_diff(directory: str | Path) -> ObservatoryDiff:
    source = Path(directory)
    manifest = _verify_directory(source, DIFF_FILES, "assurance history observatory diff")
    allowed = {"version", "boundary", "diff_id", "baseline_address", "candidate_address", "artifact_count", "files", "artifact", "manifest_address"}
    _strict(manifest, allowed, "assurance history observatory diff manifest")
    if manifest.get("version") != VERSION or manifest.get("boundary") != BOUNDARY or manifest.get("artifact_count") != 1 or tuple(manifest.get("files", ())) != (DIFF_NAME,) or manifest.get("manifest_address") != _diff_manifest_address(dict(manifest) | {"manifest_address": None}):
        raise ValidationError("assurance history observatory diff manifest contract is invalid")
    artifact = _mapping(manifest.get("artifact"), "assurance history observatory diff artifact")
    raw = (source / DIFF_NAME).read_bytes()
    if source.joinpath(DIFF_NAME).is_symlink() or not source.joinpath(DIFF_NAME).is_file() or dict(artifact) != _artifact(DIFF_NAME, raw):
        raise ValidationError("assurance history observatory diff artifact is not addressed")
    value = diff_from_mapping(_read_json(source / DIFF_NAME, "assurance history observatory diff"))
    if manifest.get("diff_id") != value.diff_id or manifest.get("baseline_address") != value.baseline_address or manifest.get("candidate_address") != value.candidate_address:
        raise ValidationError("assurance history observatory diff manifest linkage is invalid")
    return verify_diff(value)


def load_diff(directory: str | Path) -> ObservatoryDiff:
    return _load_diff(directory)


def verify_diff_directory(directory: str | Path) -> ObservatoryDiff:
    return _load_diff(directory)


__all__ = [
    "BOUNDARY",
    "DEFAULT_DIFF_ID",
    "DEFAULT_LIMIT",
    "DEFAULT_OBSERVATORY_ID",
    "DIFF_FILES",
    "DIFF_NAME",
    "FILES",
    "MANIFEST_NAME",
    "MEMBERS_NAME",
    "METRICS_NAME",
    "MAX_CHECKS",
    "MAX_MEMBERS",
    "MAX_QUERY_ITEMS",
    "OBSERVATORY_NAME",
    "ObservatoryCheck",
    "ObservatoryCheckSeverity",
    "ObservatoryDiff",
    "ObservatoryDiffAction",
    "ObservatoryDiffDirection",
    "ObservatoryDiffItem",
    "ObservatoryDiffQuery",
    "ObservatoryDiffQueryResult",
    "ObservatoryGateState",
    "ObservatoryMember",
    "ObservatoryPackage",
    "ObservatoryQuery",
    "ObservatoryQueryResult",
    "ObservatoryState",
    "ObservatoryVerification",
    "VerificationQuery",
    "VerificationQueryResult",
    "AssuranceHistoryObservatory",
    "address_check",
    "address_diff",
    "address_diff_item",
    "address_diff_query",
    "address_member",
    "address_observatory",
    "address_query",
    "address_verification",
    "address_verification_query",
    "build_diff",
    "build_observatory",
    "build_observatory_from_directories",
    "build_verification",
    "capabilities",
    "check_from_mapping",
    "check_schema",
    "checks_csv",
    "diff_csv",
    "diff_from_mapping",
    "diff_item_from_mapping",
    "diff_item_schema",
    "diff_json",
    "diff_query_csv",
    "diff_query_json",
    "diff_query_schema",
    "diff_schema",
    "load_diff",
    "load_observatory",
    "load_package",
    "load_verification",
    "member_from_mapping",
    "member_json",
    "member_schema",
    "members_csv",
    "metrics_document",
    "metrics_json",
    "metrics_schema",
    "observatory_csv",
    "observatory_from_mapping",
    "observatory_json",
    "observatory_schema",
    "package_from_values",
    "package_schema",
    "query_csv",
    "query_diff",
    "query_json",
    "query_observatory",
    "query_verification",
    "query_schema",
    "render_diff_markdown",
    "render_diff_query_markdown",
    "render_member_markdown",
    "render_observatory_markdown",
    "render_query_markdown",
    "render_verification_markdown",
    "render_verification_query_markdown",
    "verification_csv",
    "verification_from_mapping",
    "verification_json",
    "verification_query_csv",
    "verification_query_json",
    "verification_query_schema",
    "verification_schema",
    "verify_diff",
    "verify_diff_against_observatories",
    "verify_diff_directory",
    "verify_observatory",
    "verify_observatory_against_histories",
    "verify_observatory_directory",
    "write_diff",
    "write_observatory",
]
