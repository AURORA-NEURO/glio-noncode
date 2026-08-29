"""Deterministic diffs between verified observatory archive registries.

This boundary compares two independently persisted registry snapshots without
opening, merging, or rewriting their source archives.  The comparison is
entry-keyed and path-free: additions, removals, unchanged receipts, changed
receipts, aggregate registry changes, state transitions, and readiness
transitions are all represented as public content-addressed records.

The implementation deliberately consumes only typed
``ObservatoryArchiveRegistry`` values.  Directory helpers load the exact
five-file registry package first, so a caller cannot accidentally compare an
unverified JSON mapping or a private filesystem path.  Diff output is a
portable explanation of two verified snapshots; it is not a new evidence
source and does not copy private metadata from either input.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-diff-v1"
BOUNDARY = registry_model.BOUNDARY + "_diff"
DIFF_PREFIX = registry_model.REGISTRY_PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"
DIFF_QUERY_PREFIX = DIFF_PREFIX + "-query"
DEFAULT_DIFF_ID = registry_model.DEFAULT_REGISTRY_ID + "-diff"
MAX_DIFF_ITEMS = registry_model.MAX_ENTRIES * 2
MAX_QUERY_ITEMS = min(4096, MAX_DIFF_ITEMS * 8)
MAX_TEXT = 1024

# These are the public fields that explain an entry change.  The order is part
# of the contract: changed_fields is emitted in this order, independent of
# input ordering or dictionary insertion order.
ENTRY_FIELDS = (
    "entry_id",
    "archive_id",
    "archive_address",
    "observatory_id",
    "observatory_address",
    "verification_address",
    "archive_size",
    "state",
    "accepted",
    "release_ready",
    "member_count",
    "observatory_entry_count",
    "finding_count",
    "check_count",
    "content_address",
)

# content_address is intentionally excluded.  It is the address of the
# projection, not an independent source field; baseline_address and
# candidate_address already carry the two aggregate identities.
REGISTRY_FIELDS = (
    "registry_id",
    "version",
    "boundary",
    "entry_count",
    "state",
    "accepted",
    "release_ready",
    "metrics",
    "verification_address",
)


class RegistryDiffAction(StrEnum):
    """Membership action for one registry entry key."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class RegistryDiffState(StrEnum):
    """Aggregate direction of a registry comparison."""

    UNCHANGED = "unchanged"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    MIXED = "mixed"


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return registry_model._public(value)


def _action(value: Any, field: str = "registry diff action") -> str:
    value = _text(value, field, 32)
    if value not in tuple(item.value for item in RegistryDiffAction):
        raise ValidationError(f"{field} is not supported")
    return value


def _diff_state(value: Any) -> str:
    value = _text(value, "registry diff state", 32)
    if value not in tuple(item.value for item in RegistryDiffState):
        raise ValidationError("registry diff state is not supported")
    return value


def _entry(value: Any, field: str) -> registry_model.RegistryEntry:
    if value is not None and not isinstance(value, registry_model.RegistryEntry):
        raise ValidationError(f"{field} must be a typed registry entry or null")
    return value


def _validate_metrics(value: Any, field: str) -> dict[str, Any]:
    mapping = dict(_mapping(value, field))
    try:
        typed = registry_model.RegistryMetrics(mapping)
    except ValidationError as error:
        raise ValidationError(f"{field} is invalid") from error
    if not _public(mapping):
        raise ValidationError(f"{field} crosses the public boundary")
    return typed.to_dict()


def _entry_values(value: registry_model.RegistryEntry) -> dict[str, Any]:
    return value.to_dict()


def _changed_entry_fields(baseline: registry_model.RegistryEntry, candidate: registry_model.RegistryEntry) -> tuple[str, ...]:
    before = _entry_values(baseline)
    after = _entry_values(candidate)
    return tuple(field for field in ENTRY_FIELDS if before[field] != after[field])


def _registry_values(
    registry_id: str,
    version: str,
    boundary: str,
    metrics: Mapping[str, Any],
    state: str,
    accepted: bool,
    release_ready: bool,
    verification_address: str,
) -> dict[str, Any]:
    return {
        "registry_id": registry_id,
        "version": version,
        "boundary": boundary,
        "entry_count": metrics["entry_count"],
        "state": state,
        "accepted": accepted,
        "release_ready": release_ready,
        "metrics": dict(metrics),
        "verification_address": verification_address,
    }


def _quality_vector(state: str, accepted: bool, release_ready: bool) -> tuple[int, int, int]:
    # The state score is only an ordering for explaining a transition; the
    # source registry remains authoritative for the actual state semantics.
    state_score = {
        registry_model.RegistryState.BLOCKED.value: -2,
        registry_model.RegistryState.EMPTY.value: 0,
        registry_model.RegistryState.HELD.value: 1,
        registry_model.RegistryState.MIXED.value: 2,
        registry_model.RegistryState.READY.value: 3,
    }[state]
    return (int(accepted), int(release_ready), state_score)


def _aggregate_diff_state(
    baseline_state: str,
    candidate_state: str,
    baseline_accepted: bool,
    candidate_accepted: bool,
    baseline_release_ready: bool,
    candidate_release_ready: bool,
    changed: bool,
) -> str:
    if not changed:
        return RegistryDiffState.UNCHANGED.value
    before = _quality_vector(baseline_state, baseline_accepted, baseline_release_ready)
    after = _quality_vector(candidate_state, candidate_accepted, candidate_release_ready)
    if after > before:
        return RegistryDiffState.IMPROVED.value
    if after < before:
        return RegistryDiffState.REGRESSED.value
    return RegistryDiffState.MIXED.value


class RegistryDiffItem:
    """One deterministic entry-level transition between two registries."""

    def __init__(
        self,
        ordinal: int,
        entry_id: str,
        action: str,
        baseline: registry_model.RegistryEntry | None,
        candidate: registry_model.RegistryEntry | None,
        changed_fields: Sequence[str],
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.entry_id = entry_id
        self.action = action
        self.baseline = baseline
        self.candidate = candidate
        self.changed_fields = tuple(changed_fields)
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "registry diff item ordinal", MAX_DIFF_ITEMS, positive=True)
        _text(self.entry_id, "registry diff item entry ID")
        _action(self.action)
        baseline = _entry(self.baseline, "registry diff item baseline")
        candidate = _entry(self.candidate, "registry diff item candidate")
        if self.action == RegistryDiffAction.ADDED.value and (baseline is not None or candidate is None):
            raise ValidationError("added registry diff item has invalid sides")
        if self.action == RegistryDiffAction.REMOVED.value and (baseline is None or candidate is not None):
            raise ValidationError("removed registry diff item has invalid sides")
        if self.action in {RegistryDiffAction.CHANGED.value, RegistryDiffAction.UNCHANGED.value} and (baseline is None or candidate is None):
            raise ValidationError("shared registry diff item has invalid sides")
        for value, field in ((baseline, "baseline"), (candidate, "candidate")):
            if value is not None and value.entry_id != self.entry_id:
                raise ValidationError(f"registry diff item {field} key does not match entry ID")
        if isinstance(self.changed_fields, (str, bytes)) or not isinstance(self.changed_fields, Sequence):
            raise ValidationError("registry diff item changed fields must be a sequence")
        changed_fields = tuple(self.changed_fields)
        if tuple(field for field in ENTRY_FIELDS if field in changed_fields) != changed_fields or len(set(changed_fields)) != len(changed_fields):
            raise ValidationError("registry diff item changed fields are not canonically ordered")
        if any(field not in ENTRY_FIELDS for field in changed_fields):
            raise ValidationError("registry diff item contains an unsupported changed field")
        if baseline is not None and candidate is not None:
            expected = _changed_entry_fields(baseline, candidate)
            if changed_fields != expected:
                raise ValidationError("registry diff item changed fields are not derived from entries")
            if self.action == RegistryDiffAction.UNCHANGED.value and expected:
                raise ValidationError("unchanged registry diff item contains changes")
            if self.action == RegistryDiffAction.CHANGED.value and not expected:
                raise ValidationError("changed registry diff item has no changed fields")
        elif changed_fields != tuple(ENTRY_FIELDS):
            raise ValidationError("added or removed registry diff item must expose all entry fields")
        _text(self.detail, "registry diff item detail", MAX_TEXT)
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry diff item content address")
        else:
            _address(self.content_address, "registry diff item content address", DIFF_ITEM_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_diff_item(self) != self.content_address):
            raise ValidationError("registry diff item address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "entry_id": self.entry_id,
            "action": self.action,
            "baseline": None if self.baseline is None else self.baseline.to_dict(),
            "candidate": None if self.candidate is None else self.candidate.to_dict(),
            "changed_fields": tuple(self.changed_fields),
            "detail": self.detail,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "entry_id": self.entry_id,
            "action": self.action,
            "baseline_address": None if self.baseline is None else self.baseline.content_address,
            "candidate_address": None if self.candidate is None else self.candidate.content_address,
            "baseline_state": None if self.baseline is None else self.baseline.state,
            "candidate_state": None if self.candidate is None else self.candidate.state,
            "baseline_release_ready": None if self.baseline is None else self.baseline.release_ready,
            "candidate_release_ready": None if self.candidate is None else self.candidate.release_ready,
            "changed_fields": tuple(self.changed_fields),
            "detail": self.detail,
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryDiffItem:
        value = _mapping(value, "registry diff item")
        _strict(value, {"ordinal", "entry_id", "action", "baseline", "candidate", "changed_fields", "detail", "content_address"}, "registry diff item")
        baseline = None if value["baseline"] is None else registry_model.RegistryEntry.from_mapping(_mapping(value["baseline"], "registry diff baseline"))
        candidate = None if value["candidate"] is None else registry_model.RegistryEntry.from_mapping(_mapping(value["candidate"], "registry diff candidate"))
        return cls(value["ordinal"], value["entry_id"], value["action"], baseline, candidate, _sequence(value["changed_fields"], "registry diff changed fields", len(ENTRY_FIELDS)), value["detail"], value["content_address"])


def address_diff_item(value: RegistryDiffItem) -> str:
    if not isinstance(value, RegistryDiffItem):
        raise ValidationError("registry diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


class RegistryDiff:
    """Content-addressed comparison of two verified registry projections."""

    def __init__(
        self,
        diff_id: str,
        version: str,
        boundary: str,
        baseline_address: str,
        candidate_address: str,
        baseline_registry_id: str,
        candidate_registry_id: str,
        baseline_state: str,
        candidate_state: str,
        baseline_accepted: bool,
        candidate_accepted: bool,
        baseline_release_ready: bool,
        candidate_release_ready: bool,
        baseline_metrics: Mapping[str, Any],
        candidate_metrics: Mapping[str, Any],
        baseline_verification_address: str,
        candidate_verification_address: str,
        registry_changed_fields: Sequence[str],
        item_count: int,
        added_count: int,
        removed_count: int,
        changed_count: int,
        unchanged_count: int,
        state: str,
        items: Sequence[RegistryDiffItem],
        content_address: str,
    ) -> None:
        self.diff_id = diff_id
        self.version = version
        self.boundary = boundary
        self.baseline_address = baseline_address
        self.candidate_address = candidate_address
        self.baseline_registry_id = baseline_registry_id
        self.candidate_registry_id = candidate_registry_id
        self.baseline_state = baseline_state
        self.candidate_state = candidate_state
        self.baseline_accepted = baseline_accepted
        self.candidate_accepted = candidate_accepted
        self.baseline_release_ready = baseline_release_ready
        self.candidate_release_ready = candidate_release_ready
        self.baseline_metrics = dict(baseline_metrics)
        self.candidate_metrics = dict(candidate_metrics)
        self.baseline_verification_address = baseline_verification_address
        self.candidate_verification_address = candidate_verification_address
        self.registry_changed_fields = tuple(registry_changed_fields)
        self.item_count = item_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.changed_count = changed_count
        self.unchanged_count = unchanged_count
        self.state = state
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "registry diff ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("registry diff contract version or boundary is invalid")
        _address(self.baseline_address, "registry diff baseline address", registry_model.REGISTRY_PREFIX)
        _address(self.candidate_address, "registry diff candidate address", registry_model.REGISTRY_PREFIX)
        _text(self.baseline_registry_id, "registry diff baseline registry ID")
        _text(self.candidate_registry_id, "registry diff candidate registry ID")
        registry_model._state(self.baseline_state, "registry diff baseline state")
        registry_model._state(self.candidate_state, "registry diff candidate state")
        _bool(self.baseline_accepted, "registry diff baseline accepted")
        _bool(self.candidate_accepted, "registry diff candidate accepted")
        _bool(self.baseline_release_ready, "registry diff baseline release-ready")
        _bool(self.candidate_release_ready, "registry diff candidate release-ready")
        baseline_metrics = _validate_metrics(self.baseline_metrics, "registry diff baseline metrics")
        candidate_metrics = _validate_metrics(self.candidate_metrics, "registry diff candidate metrics")
        if baseline_metrics != self.baseline_metrics or candidate_metrics != self.candidate_metrics:
            raise ValidationError("registry diff metrics are not canonical")
        _address(self.baseline_verification_address, "registry diff baseline verification address", registry_model.REGISTRY_VERIFICATION_PREFIX)
        _address(self.candidate_verification_address, "registry diff candidate verification address", registry_model.REGISTRY_VERIFICATION_PREFIX)
        if isinstance(self.registry_changed_fields, (str, bytes)) or not isinstance(self.registry_changed_fields, Sequence):
            raise ValidationError("registry diff changed registry fields must be a sequence")
        registry_changed_fields = tuple(self.registry_changed_fields)
        if tuple(field for field in REGISTRY_FIELDS if field in registry_changed_fields) != registry_changed_fields or len(set(registry_changed_fields)) != len(registry_changed_fields):
            raise ValidationError("registry diff changed registry fields are not canonically ordered")
        if any(field not in REGISTRY_FIELDS for field in registry_changed_fields):
            raise ValidationError("registry diff contains an unsupported registry field")
        baseline_values = _registry_values(self.baseline_registry_id, registry_model.VERSION, registry_model.BOUNDARY, self.baseline_metrics, self.baseline_state, self.baseline_accepted, self.baseline_release_ready, self.baseline_verification_address)
        candidate_values = _registry_values(self.candidate_registry_id, registry_model.VERSION, registry_model.BOUNDARY, self.candidate_metrics, self.candidate_state, self.candidate_accepted, self.candidate_release_ready, self.candidate_verification_address)
        expected_registry_changes = tuple(field for field in REGISTRY_FIELDS if baseline_values[field] != candidate_values[field])
        if registry_changed_fields != expected_registry_changes:
            raise ValidationError("registry diff changed registry fields are not derived from snapshots")
        _count(self.item_count, "registry diff item count", MAX_DIFF_ITEMS)
        for value, field in ((self.added_count, "registry diff added count"), (self.removed_count, "registry diff removed count"), (self.changed_count, "registry diff changed count"), (self.unchanged_count, "registry diff unchanged count")):
            _count(value, field, MAX_DIFF_ITEMS)
        if self.item_count != len(self.items) or self.added_count + self.removed_count + self.changed_count + self.unchanged_count != self.item_count:
            raise ValidationError("registry diff item counts are not conserved")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, self.item_count + 1)):
            raise ValidationError("registry diff item ordinals are not contiguous")
        if tuple(item.entry_id for item in self.items) != tuple(sorted(item.entry_id for item in self.items)):
            raise ValidationError("registry diff items are not canonically ordered")
        if len({item.entry_id for item in self.items}) != self.item_count or len({item.content_address for item in self.items}) != self.item_count:
            raise ValidationError("registry diff item identities are not unique")
        counts = {action.value: 0 for action in RegistryDiffAction}
        for item in self.items:
            if not isinstance(item, RegistryDiffItem):
                raise ValidationError("registry diff items must be typed")
            counts[item.action] += 1
        if (self.added_count, self.removed_count, self.changed_count, self.unchanged_count) != (counts["added"], counts["removed"], counts["changed"], counts["unchanged"]):
            raise ValidationError("registry diff action counts are not derived from items")
        expected_state = _aggregate_diff_state(self.baseline_state, self.candidate_state, self.baseline_accepted, self.candidate_accepted, self.baseline_release_ready, self.candidate_release_ready, any(item.action != RegistryDiffAction.UNCHANGED.value for item in self.items) or bool(self.registry_changed_fields))
        if self.state != expected_state:
            raise ValidationError("registry diff aggregate state is not derived")
        _diff_state(self.state)
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry diff content address")
        else:
            _address(self.content_address, "registry diff content address", DIFF_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_diff(self) != self.content_address):
            raise ValidationError("registry diff address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "version": self.version,
            "boundary": self.boundary,
            "baseline_address": self.baseline_address,
            "candidate_address": self.candidate_address,
            "baseline_registry_id": self.baseline_registry_id,
            "candidate_registry_id": self.candidate_registry_id,
            "baseline_state": self.baseline_state,
            "candidate_state": self.candidate_state,
            "baseline_accepted": self.baseline_accepted,
            "candidate_accepted": self.candidate_accepted,
            "baseline_release_ready": self.baseline_release_ready,
            "candidate_release_ready": self.candidate_release_ready,
            "baseline_metrics": self.baseline_metrics,
            "candidate_metrics": self.candidate_metrics,
            "baseline_verification_address": self.baseline_verification_address,
            "candidate_verification_address": self.candidate_verification_address,
            "registry_changed_fields": tuple(self.registry_changed_fields),
            "item_count": self.item_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "changed_count": self.changed_count,
            "unchanged_count": self.unchanged_count,
            "state": self.state,
            "items": tuple(item.to_dict() for item in self.items),
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "baseline_address": self.baseline_address,
            "candidate_address": self.candidate_address,
            "baseline_registry_id": self.baseline_registry_id,
            "candidate_registry_id": self.candidate_registry_id,
            "baseline_state": self.baseline_state,
            "candidate_state": self.candidate_state,
            "baseline_accepted": self.baseline_accepted,
            "candidate_accepted": self.candidate_accepted,
            "baseline_release_ready": self.baseline_release_ready,
            "candidate_release_ready": self.candidate_release_ready,
            "baseline_verification_address": self.baseline_verification_address,
            "candidate_verification_address": self.candidate_verification_address,
            "registry_changed_fields": tuple(self.registry_changed_fields),
            "item_count": self.item_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "changed_count": self.changed_count,
            "unchanged_count": self.unchanged_count,
            "state": self.state,
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryDiff:
        value = _mapping(value, "registry diff")
        allowed = {"diff_id", "version", "boundary", "baseline_address", "candidate_address", "baseline_registry_id", "candidate_registry_id", "baseline_state", "candidate_state", "baseline_accepted", "candidate_accepted", "baseline_release_ready", "candidate_release_ready", "baseline_metrics", "candidate_metrics", "baseline_verification_address", "candidate_verification_address", "registry_changed_fields", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "state", "items", "content_address"}
        _strict(value, allowed, "registry diff")
        items = tuple(RegistryDiffItem.from_mapping(item) for item in _sequence(value["items"], "registry diff items", MAX_DIFF_ITEMS))
        return cls(value["diff_id"], value["version"], value["boundary"], value["baseline_address"], value["candidate_address"], value["baseline_registry_id"], value["candidate_registry_id"], value["baseline_state"], value["candidate_state"], value["baseline_accepted"], value["candidate_accepted"], value["baseline_release_ready"], value["candidate_release_ready"], _mapping(value["baseline_metrics"], "registry diff baseline metrics"), _mapping(value["candidate_metrics"], "registry diff candidate metrics"), value["baseline_verification_address"], value["candidate_verification_address"], _sequence(value["registry_changed_fields"], "registry diff changed registry fields", len(REGISTRY_FIELDS)), value["item_count"], value["added_count"], value["removed_count"], value["changed_count"], value["unchanged_count"], value["state"], items, value["content_address"])


def address_diff(value: RegistryDiff) -> str:
    if not isinstance(value, RegistryDiff):
        raise ValidationError("registry diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _build_item(
    ordinal: int,
    entry_id: str,
    action: str,
    baseline: registry_model.RegistryEntry | None,
    candidate: registry_model.RegistryEntry | None,
) -> RegistryDiffItem:
    if action == RegistryDiffAction.ADDED.value:
        changed_fields = ENTRY_FIELDS
        detail = f"entry {entry_id} added to candidate registry"
    elif action == RegistryDiffAction.REMOVED.value:
        changed_fields = ENTRY_FIELDS
        detail = f"entry {entry_id} removed from candidate registry"
    elif action == RegistryDiffAction.UNCHANGED.value:
        changed_fields = ()
        detail = f"entry {entry_id} is unchanged"
    else:
        assert baseline is not None and candidate is not None
        changed_fields = _changed_entry_fields(baseline, candidate)
        detail = f"entry {entry_id} changed fields: {', '.join(changed_fields)}"
    provisional = RegistryDiffItem(ordinal, entry_id, action, baseline, candidate, changed_fields, detail, "pending:diff-item")
    return RegistryDiffItem(ordinal, entry_id, action, baseline, candidate, changed_fields, detail, address_diff_item(provisional))


def build_diff(
    baseline: registry_model.ObservatoryArchiveRegistry,
    candidate: registry_model.ObservatoryArchiveRegistry,
    *,
    diff_id: str | None = None,
) -> RegistryDiff:
    """Compare two verified registry snapshots by their stable entry IDs."""

    registry_model.verify_registry(baseline)
    registry_model.verify_registry(candidate)
    selected_id = DEFAULT_DIFF_ID if diff_id is None else _text(diff_id, "registry diff ID")
    before = {entry.entry_id: entry for entry in baseline.entries}
    after = {entry.entry_id: entry for entry in candidate.entries}
    items: list[RegistryDiffItem] = []
    for ordinal, entry_id in enumerate(sorted(set(before) | set(after)), start=1):
        baseline_entry = before.get(entry_id)
        candidate_entry = after.get(entry_id)
        if baseline_entry is None:
            action = RegistryDiffAction.ADDED.value
        elif candidate_entry is None:
            action = RegistryDiffAction.REMOVED.value
        elif _entry_values(baseline_entry) == _entry_values(candidate_entry):
            action = RegistryDiffAction.UNCHANGED.value
        else:
            action = RegistryDiffAction.CHANGED.value
        items.append(_build_item(ordinal, entry_id, action, baseline_entry, candidate_entry))
    baseline_values = _registry_values(baseline.registry_id, baseline.version, baseline.boundary, baseline.metrics.to_dict(), baseline.state, baseline.accepted, baseline.release_ready, baseline.verification_address)
    candidate_values = _registry_values(candidate.registry_id, candidate.version, candidate.boundary, candidate.metrics.to_dict(), candidate.state, candidate.accepted, candidate.release_ready, candidate.verification_address)
    registry_changed_fields = tuple(field for field in REGISTRY_FIELDS if baseline_values[field] != candidate_values[field])
    counts = {action.value: sum(item.action == action.value for item in items) for action in RegistryDiffAction}
    state = _aggregate_diff_state(baseline.state, candidate.state, baseline.accepted, candidate.accepted, baseline.release_ready, candidate.release_ready, any(item.action != RegistryDiffAction.UNCHANGED.value for item in items) or bool(registry_changed_fields))
    body = {
        "diff_id": selected_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "baseline_address": baseline.content_address,
        "candidate_address": candidate.content_address,
        "baseline_registry_id": baseline.registry_id,
        "candidate_registry_id": candidate.registry_id,
        "baseline_state": baseline.state,
        "candidate_state": candidate.state,
        "baseline_accepted": baseline.accepted,
        "candidate_accepted": candidate.accepted,
        "baseline_release_ready": baseline.release_ready,
        "candidate_release_ready": candidate.release_ready,
        "baseline_metrics": baseline.metrics.to_dict(),
        "candidate_metrics": candidate.metrics.to_dict(),
        "baseline_verification_address": baseline.verification_address,
        "candidate_verification_address": candidate.verification_address,
        "registry_changed_fields": registry_changed_fields,
        "item_count": len(items),
        "added_count": counts["added"],
        "removed_count": counts["removed"],
        "changed_count": counts["changed"],
        "unchanged_count": counts["unchanged"],
        "state": state,
        "items": tuple(items),
    }
    provisional = RegistryDiff(**body, content_address="pending:diff")
    return RegistryDiff(**body, content_address=address_diff(provisional))


def build_diff_from_directories(
    baseline_source: str | Path,
    candidate_source: str | Path,
    *,
    diff_id: str | None = None,
) -> RegistryDiff:
    """Load two exact registry packages and compare their verified values."""

    baseline = registry_model.load_registry(baseline_source)
    candidate = registry_model.load_registry(candidate_source)
    return build_diff(baseline, candidate, diff_id=diff_id)


def verify_diff(value: RegistryDiff) -> RegistryDiff:
    if not isinstance(value, RegistryDiff):
        raise ValidationError("registry diff verification requires a typed diff")
    value._validate()
    return value


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryDiff:
    return RegistryDiff.from_mapping(value)


class RegistryDiffQuery:
    """Bounded query over diff items and aggregate transitions."""

    RESOURCES = (
        "summary",
        "items",
        "added",
        "removed",
        "changed",
        "unchanged",
        "state-transitions",
        "readiness-transitions",
        "registry-changes",
    )

    def __init__(self, resource: str = "summary", action: str | None = None, text: str | None = None, offset: int = 0, limit: int = registry_model.DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "registry diff query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("registry diff query resource is not supported")
        self.action = None if action is None else _action(action, "registry diff query action")
        self.text = None if text is None else _text(text, "registry diff query text", MAX_TEXT)
        self.offset = _count(offset, "registry diff query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "registry diff query limit", MAX_QUERY_ITEMS, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "action": self.action, "text": self.text, "offset": self.offset, "limit": self.limit}


class RegistryDiffQueryResult:
    """Content-addressed bounded result window for a registry diff query."""

    def __init__(self, diff_address: str, query: RegistryDiffQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.diff_address = diff_address
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.diff_address, "registry diff query diff address", DIFF_PREFIX)
        if not isinstance(self.query, RegistryDiffQuery):
            raise ValidationError("registry diff query result query must be typed")
        _count(self.total_count, "registry diff query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "registry diff query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("registry diff query result window is invalid")
        if any(not isinstance(record, Mapping) or not _public(record) for record in self.records):
            raise ValidationError("registry diff query result contains a private record")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry diff query content address")
        else:
            _address(self.content_address, "registry diff query content address", DIFF_QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("registry diff query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryDiffQueryResult:
        value = _mapping(value, "registry diff query result")
        _strict(value, {"diff_address", "query", "total_count", "returned_count", "records", "content_address"}, "registry diff query result")
        query_mapping = _mapping(value["query"], "registry diff query")
        _strict(query_mapping, {"resource", "action", "text", "offset", "limit"}, "registry diff query")
        query = RegistryDiffQuery(**query_mapping)
        records = tuple(_mapping(record, "registry diff query record") for record in _sequence(value["records"], "registry diff query records", MAX_QUERY_ITEMS))
        result = cls(value["diff_address"], query, value["total_count"], records, value["content_address"])
        if result.returned_count != value["returned_count"]:
            raise ValidationError("registry diff query returned count is not conserved")
        return result


def address_query(value: RegistryDiffQueryResult) -> str:
    if not isinstance(value, RegistryDiffQueryResult):
        raise ValidationError("registry diff query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_QUERY_PREFIX)


def _item_record_matches(item: RegistryDiffItem, query: RegistryDiffQuery) -> bool:
    if query.action is not None and item.action != query.action:
        return False
    return query.text is None or query.text.lower() in canonical_json(item.to_dict()).lower()


def _registry_change_record(value: RegistryDiff) -> dict[str, Any]:
    return {
        "baseline_registry_id": value.baseline_registry_id,
        "candidate_registry_id": value.candidate_registry_id,
        "baseline_address": value.baseline_address,
        "candidate_address": value.candidate_address,
        "changed_fields": tuple(value.registry_changed_fields),
        "baseline_metrics": value.baseline_metrics,
        "candidate_metrics": value.candidate_metrics,
        "content_address": value.content_address,
    }


def query_diff(value: RegistryDiff, query: RegistryDiffQuery | None = None, *, resource: str = "summary", action: str | None = None, text: str | None = None, offset: int = 0, limit: int = registry_model.DEFAULT_LIMIT) -> RegistryDiffQueryResult:
    verify_diff(value)
    if query is not None and any(argument != default for argument, default in ((resource, "summary"), (action, None), (text, None), (offset, 0), (limit, registry_model.DEFAULT_LIMIT))):
        raise ValidationError("registry diff query accepts either a query object or keyword filters")
    selected = query or RegistryDiffQuery(resource=resource, action=action, text=text, offset=offset, limit=limit)
    if selected.resource == "summary":
        records = (value.summary(),)
        if selected.text is not None and selected.text.lower() not in canonical_json(records[0]).lower():
            records = ()
    elif selected.resource == "registry-changes":
        records = (_registry_change_record(value),) if value.registry_changed_fields else ()
        if selected.text is not None and records and selected.text.lower() not in canonical_json(records[0]).lower():
            records = ()
    else:
        items = tuple(item for item in value.items if _item_record_matches(item, selected))
        if selected.resource != "items":
            if selected.resource in {action.value for action in RegistryDiffAction}:
                items = tuple(item for item in items if item.action == selected.resource)
            elif selected.resource == "state-transitions":
                items = tuple(item for item in items if item.baseline is not None and item.candidate is not None and item.baseline.state != item.candidate.state)
            elif selected.resource == "readiness-transitions":
                items = tuple(item for item in items if item.baseline is not None and item.candidate is not None and item.baseline.release_ready != item.candidate.release_ready)
        records = tuple(item.summary() for item in items)
    total_count = len(records)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryDiffQueryResult(value.content_address, selected, total_count, window, "pending:query")
    return RegistryDiffQueryResult(value.content_address, selected, total_count, window, address_query(provisional))


def verify_query(value: RegistryDiffQueryResult) -> RegistryDiffQueryResult:
    if not isinstance(value, RegistryDiffQueryResult):
        raise ValidationError("registry diff query verification requires a typed result")
    value._validate()
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryDiffQueryResult:
    return RegistryDiffQueryResult.from_mapping(value)


def _csv_text(records: Sequence[Mapping[str, Any]]) -> str:
    output = io.StringIO()
    rows = list(records)
    fieldnames = sorted({str(key) for record in rows for key in record}) or ["content_address"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for record in rows:
        writer.writerow({key: canonical_json(record[key]) if isinstance(record.get(key), (dict, list, tuple)) else record.get(key, "") for key in fieldnames})
    return output.getvalue()


def diff_json(value: RegistryDiff) -> str:
    verify_diff(value)
    return canonical_json(value.to_dict())


def diff_csv(value: RegistryDiff) -> str:
    verify_diff(value)
    return _csv_text(tuple(item.summary() for item in value.items))


def diff_query_json(value: RegistryDiffQueryResult) -> str:
    verify_query(value)
    return canonical_json(value.to_dict())


def diff_query_csv(value: RegistryDiffQueryResult) -> str:
    verify_query(value)
    return _csv_text(value.records)


def render_markdown(value: RegistryDiff) -> str:
    verify_diff(value)
    lines = [
        "# Assurance History Observatory Archive Registry Diff",
        "",
        f"- Diff: `{value.diff_id}`",
        f"- Baseline: `{value.baseline_address}`",
        f"- Candidate: `{value.candidate_address}`",
        f"- State: `{value.state}`",
        f"- Entries: `{value.item_count}`",
        f"- Added / removed / changed / unchanged: `{value.added_count}` / `{value.removed_count}` / `{value.changed_count}` / `{value.unchanged_count}`",
        f"- Registry changed fields: `{', '.join(value.registry_changed_fields) or 'none'}`",
        f"- Content address: `{value.content_address}`",
        "",
    ]
    if value.items:
        lines.extend(("| Ordinal | Entry | Action | Changed fields | Detail |", "| ---: | --- | --- | --- | --- |"))
        lines.extend(f"| {item.ordinal} | `{item.entry_id}` | `{item.action}` | `{', '.join(item.changed_fields) or 'none'}` | {item.detail} |" for item in value.items)
        lines.append("")
    return "\n".join(lines)


def render_query_markdown(value: RegistryDiffQueryResult) -> str:
    verify_query(value)
    lines = [
        "# Assurance History Observatory Archive Registry Diff Query",
        "",
        f"- Resource: `{value.query.resource}`",
        f"- Returned: `{value.returned_count}` of `{value.total_count}`",
        f"- Content address: `{value.content_address}`",
        "",
    ]
    if value.records:
        keys = sorted({str(key) for record in value.records for key in record})
        lines.extend(("| " + " | ".join(keys) + " |", "| " + " | ".join("---" for _ in keys) + " |"))
        lines.extend("| " + " | ".join(str(record.get(key, "")) for key in keys) + " |" for record in value.records)
    return "\n".join(lines) + "\n"


def diff_item_schema() -> dict[str, Any]:
    fields = {
        "ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_DIFF_ITEMS},
        "entry_id": {"type": "string", "minLength": 1, "maxLength": 512},
        "action": {"type": "string", "enum": [item.value for item in RegistryDiffAction]},
        "baseline": {"anyOf": [registry_model.entry_schema(), {"type": "null"}]},
        "candidate": {"anyOf": [registry_model.entry_schema(), {"type": "null"}]},
        "changed_fields": {"type": "array", "items": {"type": "string", "enum": list(ENTRY_FIELDS)}, "maxItems": len(ENTRY_FIELDS)},
        "detail": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT},
        "content_address": {"type": "string"},
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Archive Registry Diff Item", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def diff_schema() -> dict[str, Any]:
    fields = {
        "diff_id": {"type": "string", "minLength": 1, "maxLength": 512},
        "version": {"type": "string", "const": VERSION},
        "boundary": {"type": "string", "const": BOUNDARY},
        "baseline_address": {"type": "string"},
        "candidate_address": {"type": "string"},
        "baseline_registry_id": {"type": "string"},
        "candidate_registry_id": {"type": "string"},
        "baseline_state": {"type": "string", "enum": [item.value for item in registry_model.RegistryState]},
        "candidate_state": {"type": "string", "enum": [item.value for item in registry_model.RegistryState]},
        "baseline_accepted": {"type": "boolean"},
        "candidate_accepted": {"type": "boolean"},
        "baseline_release_ready": {"type": "boolean"},
        "candidate_release_ready": {"type": "boolean"},
        "baseline_metrics": registry_model.metrics_schema(),
        "candidate_metrics": registry_model.metrics_schema(),
        "baseline_verification_address": {"type": "string"},
        "candidate_verification_address": {"type": "string"},
        "registry_changed_fields": {"type": "array", "items": {"type": "string", "enum": list(REGISTRY_FIELDS)}, "maxItems": len(REGISTRY_FIELDS)},
        "item_count": {"type": "integer", "minimum": 0, "maximum": MAX_DIFF_ITEMS},
        "added_count": {"type": "integer", "minimum": 0, "maximum": MAX_DIFF_ITEMS},
        "removed_count": {"type": "integer", "minimum": 0, "maximum": MAX_DIFF_ITEMS},
        "changed_count": {"type": "integer", "minimum": 0, "maximum": MAX_DIFF_ITEMS},
        "unchanged_count": {"type": "integer", "minimum": 0, "maximum": MAX_DIFF_ITEMS},
        "state": {"type": "string", "enum": [item.value for item in RegistryDiffState]},
        "items": {"type": "array", "maxItems": MAX_DIFF_ITEMS, "items": diff_item_schema()},
        "content_address": {"type": "string"},
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Archive Registry Diff", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_schema() -> dict[str, Any]:
    fields = {
        "resource": {"type": "string", "enum": list(RegistryDiffQuery.RESOURCES)},
        "action": {"anyOf": [{"type": "string", "enum": [item.value for item in RegistryDiffAction]}, {"type": "null"}]},
        "text": {"anyOf": [{"type": "string", "maxLength": MAX_TEXT}, {"type": "null"}]},
        "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS},
        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS},
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Archive Registry Diff Query", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    fields = {
        "diff_address": {"type": "string"},
        "query": query_schema(),
        "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS},
        "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS},
        "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object"}},
        "content_address": {"type": "string"},
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Archive Registry Diff Query Result", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {
        "version": VERSION,
        "boundary": BOUNDARY,
        "limits": {"max_diff_items": MAX_DIFF_ITEMS, "max_query_items": MAX_QUERY_ITEMS, "max_changed_entry_fields": len(ENTRY_FIELDS), "max_changed_registry_fields": len(REGISTRY_FIELDS)},
        "actions": tuple(item.value for item in RegistryDiffAction),
        "states": tuple(item.value for item in RegistryDiffState),
        "resources": RegistryDiffQuery.RESOURCES,
        "entry_fields": ENTRY_FIELDS,
        "registry_fields": REGISTRY_FIELDS,
        "features": (
            "typed verified registry inputs",
            "stable entry-key membership comparison",
            "field-level change explanations",
            "aggregate registry transition detection",
            "state and readiness transition queries",
            "deterministic content-addressed items and queries",
            "bounded JSON CSV and Markdown projections",
            "path-free public diff output",
        ),
        "schemas": ("diff-item", "diff", "query", "query-result"),
    }


__all__ = [
    "BOUNDARY",
    "DEFAULT_DIFF_ID",
    "DIFF_ITEM_PREFIX",
    "DIFF_PREFIX",
    "DIFF_QUERY_PREFIX",
    "ENTRY_FIELDS",
    "MAX_DIFF_ITEMS",
    "MAX_QUERY_ITEMS",
    "REGISTRY_FIELDS",
    "RegistryDiff",
    "RegistryDiffAction",
    "RegistryDiffItem",
    "RegistryDiffQuery",
    "RegistryDiffQueryResult",
    "RegistryDiffState",
    "VERSION",
    "address_diff",
    "address_diff_item",
    "address_query",
    "build_diff",
    "build_diff_from_directories",
    "capabilities",
    "diff_csv",
    "diff_from_mapping",
    "diff_item_schema",
    "diff_json",
    "diff_query_csv",
    "diff_query_json",
    "diff_schema",
    "query_diff",
    "query_result_from_mapping",
    "query_result_schema",
    "query_schema",
    "render_markdown",
    "render_query_markdown",
    "verify_diff",
    "verify_query",
]
