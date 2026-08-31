"""Cross-history observatory for comparison-query snapshot registry histories.

This public contract folds independently verified history streams into a
deterministic, value-free overview. It retains bounded receipt metrics and
content addresses only; source archives, source paths, and source values never
cross this boundary.
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = history_model.VERSION + "-observatory-v1"
BOUNDARY = history_model.BOUNDARY + "_observatory"
OBSERVATORY_PREFIX = history_model.HISTORY_PREFIX + "-observatory"
MEMBER_PREFIX = OBSERVATORY_PREFIX + "-member"
MEMBERS_PREFIX = OBSERVATORY_PREFIX + "-members"
TRANSITION_PREFIX = OBSERVATORY_PREFIX + "-transition"
TRANSITIONS_PREFIX = OBSERVATORY_PREFIX + "-transitions"
MANIFEST_PREFIX = OBSERVATORY_PREFIX + "-manifest"
SUMMARY_PREFIX = OBSERVATORY_PREFIX + "-summary"
DEFAULT_OBSERVATORY_ID = OBSERVATORY_PREFIX
FILES = ("manifest.json", "observatory.json", "members.json", "transitions.json", "summary.json")
MANIFEST_ARTIFACT_FILES = ("members.json", "transitions.json", "summary.json")
STATES = history_model.STATES
TRANSITIONS = history_model.TRANSITIONS
TRENDS = ("stable", "improved", "regressed", "changed")
MAX_MEMBERS = history_model.MAX_ENTRIES
MAX_TRANSITIONS = MAX_MEMBERS * history_model.MAX_ENTRIES
MAX_TOTAL_ROWS = history_model.MAX_TOTAL_ROWS

MEMBER_FIELDS = (
    "ordinal", "history_id", "registry_id", "history_address", "snapshot_count",
    "latest_registry_address", "latest_entry_count", "latest_ready_count",
    "latest_blocked_count", "latest_accepted_count", "latest_rejected_count",
    "latest_total_query_rows", "latest_matched_query_rows",
    "latest_returned_query_rows", "latest_state", "latest_accepted",
    "initial_count", "improved_count", "regressed_count", "unchanged_count",
    "changed_count", "trend", "content_address",
)
MEMBERS_FIELDS = ("members", "content_address")
TRANSITION_FIELDS = (
    "ordinal", "member_ordinal", "history_id", "registry_id", "history_address",
    "snapshot_ordinal", "registry_address", "entry_count", "ready_count",
    "blocked_count", "accepted_count", "rejected_count", "total_query_rows",
    "matched_query_rows", "returned_query_rows", "state", "accepted",
    "transition", "previous_registry_address", "content_address",
)
TRANSITIONS_FIELDS = ("transitions", "content_address")
MANIFEST_FIELDS = ("observatory_id", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = (
    "observatory_id", "member_count", "transition_count", "empty_count",
    "ready_count", "blocked_count", "mixed_count", "accepted_member_count",
    "total_snapshot_count", "total_query_rows", "matched_query_rows",
    "returned_query_rows", "initial_count", "improved_count", "regressed_count",
    "unchanged_count", "changed_count", "latest_history_address", "state",
    "accepted", "content_address",
)
OBSERVATORY_FIELDS = (
    "observatory_id", "version", "boundary", "member_count", "transition_count",
    "empty_count", "ready_count", "blocked_count", "mixed_count",
    "accepted_member_count", "total_snapshot_count", "total_query_rows",
    "matched_query_rows", "returned_query_rows", "initial_count", "improved_count",
    "regressed_count", "unchanged_count", "changed_count",
    "latest_history_address", "state", "accepted", "members", "transitions",
    "manifest", "summary", "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _verify_history(value: Any) -> history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory:
    if not isinstance(value, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
        raise ValidationError("observatory requires typed registry histories")
    if not value.content_address.endswith(":pending") and history_model.address_history(value) != value.content_address:
        raise ValidationError("observatory history address does not replay")
    return value


def trend_from_history(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory) -> str:
    value = _verify_history(value)
    if value.regressed_count > value.improved_count:
        return "regressed"
    if value.improved_count > value.regressed_count:
        return "improved"
    if value.changed_count:
        return "changed"
    return "stable"


def fold_state(states: Sequence[str]) -> str:
    values = tuple(states)
    if not values or all(item == "empty" for item in values):
        return "empty"
    if "blocked" in values:
        return "blocked"
    if len(set(values)) == 1 and values[0] == "ready":
        return "ready"
    return "mixed"


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember:
    FIELDS = MEMBER_FIELDS

    def __init__(self, ordinal: int, history_id: str, registry_id: str, history_address: str, snapshot_count: int, latest_registry_address: str, latest_entry_count: int, latest_ready_count: int, latest_blocked_count: int, latest_accepted_count: int, latest_rejected_count: int, latest_total_query_rows: int, latest_matched_query_rows: int, latest_returned_query_rows: int, latest_state: str, latest_accepted: bool, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, trend: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory member ordinal", MAX_MEMBERS, positive=True)
        self.history_id = _label(history_id, "observatory member history ID")
        self.registry_id = _label(registry_id, "observatory member registry ID", required=False)
        self.history_address = _address(history_address, "observatory member history address", history_model.HISTORY_PREFIX)
        self.snapshot_count = _count(snapshot_count, "observatory member snapshot count", history_model.MAX_ENTRIES)
        self.latest_registry_address = _address(latest_registry_address, "observatory member latest registry address", history_model.registry_model.REGISTRY_PREFIX, required=False)
        self.latest_entry_count = _count(latest_entry_count, "observatory member latest entry count", history_model.MAX_ENTRIES)
        self.latest_ready_count = _count(latest_ready_count, "observatory member latest ready count", history_model.MAX_ENTRIES)
        self.latest_blocked_count = _count(latest_blocked_count, "observatory member latest blocked count", history_model.MAX_ENTRIES)
        self.latest_accepted_count = _count(latest_accepted_count, "observatory member latest accepted count", history_model.MAX_ENTRIES)
        self.latest_rejected_count = _count(latest_rejected_count, "observatory member latest rejected count", history_model.MAX_ENTRIES)
        for field in ("latest_total_query_rows", "latest_matched_query_rows", "latest_returned_query_rows"):
            setattr(self, field, _count(locals()[field], f"observatory member {field}", MAX_TOTAL_ROWS))
        self.latest_state = _label(latest_state, "observatory member latest state")
        if self.latest_state not in STATES:
            raise ValidationError("observatory member latest state is unsupported")
        self.latest_accepted = _bool(latest_accepted, "observatory member latest acceptance")
        for field in ("initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count"):
            setattr(self, field, _count(locals()[field], f"observatory member {field}", history_model.MAX_ENTRIES))
        self.trend = _label(trend, "observatory member trend")
        if self.trend not in TRENDS:
            raise ValidationError("observatory member trend is unsupported")
        self.content_address = _address(content_address, "observatory member content address", MEMBER_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.initial_count + self.improved_count + self.regressed_count + self.unchanged_count + self.changed_count != self.snapshot_count:
            raise ValidationError("observatory member transition counts are not conserved")
        if self.latest_accepted_count + self.latest_rejected_count > self.latest_entry_count:
            raise ValidationError("observatory member latest acceptance counts exceed entries")
        if self.latest_ready_count + self.latest_blocked_count > self.latest_entry_count:
            raise ValidationError("observatory member latest state counts exceed entries")
        if self.snapshot_count == 0 and (self.latest_registry_address or self.latest_entry_count or self.latest_state != "empty" or self.latest_accepted):
            raise ValidationError("empty observatory member has a latest snapshot")
        if self.snapshot_count and not self.latest_registry_address:
            raise ValidationError("non-empty observatory member requires a latest snapshot")
        if self.trend == "improved" and self.improved_count <= self.regressed_count:
            raise ValidationError("improved member trend does not replay")
        if self.trend == "regressed" and self.regressed_count <= self.improved_count:
            raise ValidationError("regressed member trend does not replay")
        if self.trend == "changed" and (not self.changed_count or self.improved_count != self.regressed_count):
            raise ValidationError("changed member trend does not replay")
        if self.trend == "stable" and (self.changed_count or self.improved_count != self.regressed_count):
            raise ValidationError("stable member trend does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory member crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_member(self) != self.content_address:
            raise ValidationError("observatory member address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory member")
        _strict(value, set(cls.FIELDS), "observatory member")
        return cls(*(value[field] for field in cls.FIELDS))


def address_member(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember):
        raise ValidationError("observatory member address requires a typed member")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMembers:
    FIELDS = MEMBERS_FIELDS

    def __init__(self, members: Sequence[Any], content_address: str) -> None:
        self.members = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember.from_mapping(item) for item in _sequence(members, "observatory members", MAX_MEMBERS))
        self.content_address = _address(content_address, "observatory members content address", MEMBERS_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.members) != tuple(range(1, len(self.members) + 1)) or len({item.history_id for item in self.members}) != len(self.members) or len({item.history_address for item in self.members}) != len(self.members) or not _public(self.to_dict()):
            raise ValidationError("observatory members are not ordered, unique, or public")
        if not self.content_address.endswith(":pending") and address_members(self.members) != self.content_address:
            raise ValidationError("observatory members address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"members": [item.to_dict() for item in self.members], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory members")
        _strict(value, set(cls.FIELDS), "observatory members")
        return cls(value["members"], value["content_address"])


def address_members(value: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember) for item in typed):
        raise ValidationError("observatory members address requires typed members")
    return content_hash({"members": [item.to_dict() for item in typed]}, prefix=MEMBERS_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition:
    FIELDS = TRANSITION_FIELDS

    def __init__(self, ordinal: int, member_ordinal: int, history_id: str, registry_id: str, history_address: str, snapshot_ordinal: int, registry_address: str, entry_count: int, ready_count: int, blocked_count: int, accepted_count: int, rejected_count: int, total_query_rows: int, matched_query_rows: int, returned_query_rows: int, state: str, accepted: bool, transition: str, previous_registry_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory transition ordinal", MAX_TRANSITIONS, positive=True)
        self.member_ordinal = _count(member_ordinal, "observatory transition member ordinal", MAX_MEMBERS, positive=True)
        self.history_id = _label(history_id, "observatory transition history ID")
        self.registry_id = _label(registry_id, "observatory transition registry ID", required=False)
        self.history_address = _address(history_address, "observatory transition history address", history_model.HISTORY_PREFIX)
        self.snapshot_ordinal = _count(snapshot_ordinal, "observatory transition snapshot ordinal", history_model.MAX_ENTRIES, positive=True)
        self.registry_address = _address(registry_address, "observatory transition registry address", history_model.registry_model.REGISTRY_PREFIX)
        for field in ("entry_count", "ready_count", "blocked_count", "accepted_count", "rejected_count"):
            setattr(self, field, _count(locals()[field], f"observatory transition {field}", history_model.MAX_ENTRIES))
        for field in ("total_query_rows", "matched_query_rows", "returned_query_rows"):
            setattr(self, field, _count(locals()[field], f"observatory transition {field}", MAX_TOTAL_ROWS))
        self.state = _label(state, "observatory transition state")
        if self.state not in STATES:
            raise ValidationError("observatory transition state is unsupported")
        self.accepted = _bool(accepted, "observatory transition acceptance")
        self.transition = _label(transition, "observatory transition kind")
        if self.transition not in TRANSITIONS:
            raise ValidationError("observatory transition kind is unsupported")
        self.previous_registry_address = _address(previous_registry_address, "observatory transition previous registry address", history_model.registry_model.REGISTRY_PREFIX, required=False)
        self.content_address = _address(content_address, "observatory transition content address", TRANSITION_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.accepted_count + self.rejected_count > self.entry_count or self.ready_count + self.blocked_count > self.entry_count:
            raise ValidationError("observatory transition counts exceed entries")
        if self.snapshot_ordinal == 1 and (self.transition != "initial" or self.previous_registry_address):
            raise ValidationError("initial transition does not have initial linkage")
        if self.snapshot_ordinal > 1 and not self.previous_registry_address:
            raise ValidationError("non-initial transition requires previous linkage")
        if not _public(self.to_dict()):
            raise ValidationError("observatory transition crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_transition(self) != self.content_address:
            raise ValidationError("observatory transition address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory transition")
        _strict(value, set(cls.FIELDS), "observatory transition")
        return cls(*(value[field] for field in cls.FIELDS))


def address_transition(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition):
        raise ValidationError("observatory transition address requires a typed transition")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=TRANSITION_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransitions:
    FIELDS = TRANSITIONS_FIELDS

    def __init__(self, transitions: Sequence[Any], content_address: str) -> None:
        self.transitions = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition.from_mapping(item) for item in _sequence(transitions, "observatory transitions", MAX_TRANSITIONS))
        self.content_address = _address(content_address, "observatory transitions content address", TRANSITIONS_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.transitions) != tuple(range(1, len(self.transitions) + 1)) or not _public(self.to_dict()):
            raise ValidationError("observatory transitions are not ordered or public")
        if not self.content_address.endswith(":pending") and address_transitions(self.transitions) != self.content_address:
            raise ValidationError("observatory transitions address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"transitions": [item.to_dict() for item in self.transitions], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory transitions")
        _strict(value, set(cls.FIELDS), "observatory transitions")
        return cls(value["transitions"], value["content_address"])


def address_transitions(value: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition) for item in typed):
        raise ValidationError("observatory transitions address requires typed transitions")
    return content_hash({"transitions": [item.to_dict() for item in typed]}, prefix=TRANSITIONS_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, observatory_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.observatory_id = _label(observatory_id, "observatory manifest ID")
        self.files = tuple(_label(item, "observatory manifest file") for item in _sequence(files, "observatory manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "observatory manifest artifact address") for item in _sequence(artifact_addresses, "observatory manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "observatory manifest content address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("observatory manifest does not close the public file boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("observatory manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory manifest")
        _strict(value, set(cls.FIELDS), "observatory manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryManifest):
        raise ValidationError("observatory manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatorySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, observatory_id: str, member_count: int, transition_count: int, empty_count: int, ready_count: int, blocked_count: int, mixed_count: int, accepted_member_count: int, total_snapshot_count: int, total_query_rows: int, matched_query_rows: int, returned_query_rows: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, latest_history_address: str, state: str, accepted: bool, content_address: str) -> None:
        self.observatory_id = _label(observatory_id, "observatory summary ID")
        for field in ("member_count", "empty_count", "ready_count", "blocked_count", "mixed_count", "accepted_member_count"):
            setattr(self, field, _count(locals()[field], f"observatory summary {field}", MAX_MEMBERS))
        self.transition_count = _count(transition_count, "observatory summary transition count", MAX_TRANSITIONS)
        self.total_snapshot_count = _count(total_snapshot_count, "observatory summary snapshot count", MAX_TRANSITIONS)
        for field in ("total_query_rows", "matched_query_rows", "returned_query_rows"):
            setattr(self, field, _count(locals()[field], f"observatory summary {field}", MAX_TOTAL_ROWS))
        for field in ("initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count"):
            setattr(self, field, _count(locals()[field], f"observatory summary {field}", MAX_TRANSITIONS))
        self.latest_history_address = _address(latest_history_address, "observatory summary latest history address", history_model.HISTORY_PREFIX, required=False)
        self.state = _label(state, "observatory summary state")
        if self.state not in STATES:
            raise ValidationError("observatory summary state is unsupported")
        self.accepted = _bool(accepted, "observatory summary acceptance")
        self.content_address = _address(content_address, "observatory summary content address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.empty_count + self.ready_count + self.blocked_count + self.mixed_count != self.member_count:
            raise ValidationError("observatory summary state counts are not conserved")
        if self.accepted_member_count > self.member_count:
            raise ValidationError("observatory summary acceptance count exceeds members")
        if self.total_snapshot_count != self.transition_count or self.initial_count + self.improved_count + self.regressed_count + self.unchanged_count + self.changed_count != self.transition_count:
            raise ValidationError("observatory summary transition counts are not conserved")
        if self.accepted != (bool(self.member_count) and self.accepted_member_count == self.member_count):
            raise ValidationError("observatory summary acceptance does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory summary crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("observatory summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory summary")
        _strict(value, set(cls.FIELDS), "observatory summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatorySummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatorySummary):
        raise ValidationError("observatory summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatory:
    FIELDS = OBSERVATORY_FIELDS

    def __init__(self, observatory_id: str, version: str, boundary: str, member_count: int, transition_count: int, empty_count: int, ready_count: int, blocked_count: int, mixed_count: int, accepted_member_count: int, total_snapshot_count: int, total_query_rows: int, matched_query_rows: int, returned_query_rows: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, latest_history_address: str, state: str, accepted: bool, members: Sequence[Any], transitions: Sequence[Any], manifest: Any, summary: Any, content_address: str) -> None:
        self.observatory_id = _label(observatory_id, "observatory ID")
        self.version = _text(version, "observatory version", 512)
        self.boundary = _label(boundary, "observatory boundary")
        for field in ("member_count", "empty_count", "ready_count", "blocked_count", "mixed_count", "accepted_member_count"):
            setattr(self, field, _count(locals()[field], f"observatory {field}", MAX_MEMBERS))
        for field in ("transition_count", "total_snapshot_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count"):
            setattr(self, field, _count(locals()[field], f"observatory {field}", MAX_TRANSITIONS))
        for field in ("total_query_rows", "matched_query_rows", "returned_query_rows"):
            setattr(self, field, _count(locals()[field], f"observatory {field}", MAX_TOTAL_ROWS))
        self.latest_history_address = _address(latest_history_address, "observatory latest history address", history_model.HISTORY_PREFIX, required=False)
        self.state = _label(state, "observatory state")
        if self.state not in STATES:
            raise ValidationError("observatory state is unsupported")
        self.accepted = _bool(accepted, "observatory acceptance")
        self.members = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember.from_mapping(item) for item in _sequence(members, "observatory members", MAX_MEMBERS))
        self.transitions = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition.from_mapping(item) for item in _sequence(transitions, "observatory transitions", MAX_TRANSITIONS))
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatorySummary) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatorySummary.from_mapping(summary)
        self.content_address = _address(content_address, "observatory content address", OBSERVATORY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("observatory version or boundary is unsupported")
        if len(self.members) != self.member_count or len(self.transitions) != self.transition_count:
            raise ValidationError("observatory counts do not replay")
        if tuple(item.ordinal for item in self.members) != tuple(range(1, self.member_count + 1)) or tuple(item.ordinal for item in self.transitions) != tuple(range(1, self.transition_count + 1)):
            raise ValidationError("observatory ordinals are not contiguous")
        if len({item.history_id for item in self.members}) != self.member_count or len({item.history_address for item in self.members}) != self.member_count:
            raise ValidationError("observatory history identities are not unique")
        if self.empty_count + self.ready_count + self.blocked_count + self.mixed_count != self.member_count:
            raise ValidationError("observatory state counts are not conserved")
        if self.accepted_member_count != sum(item.latest_accepted for item in self.members):
            raise ValidationError("observatory acceptance count does not replay")
        if self.total_snapshot_count != self.transition_count or self.initial_count + self.improved_count + self.regressed_count + self.unchanged_count + self.changed_count != self.transition_count:
            raise ValidationError("observatory transition totals do not replay")
        if (self.total_query_rows, self.matched_query_rows, self.returned_query_rows) != tuple(sum(getattr(item, field) for item in self.transitions) for field in ("total_query_rows", "matched_query_rows", "returned_query_rows")):
            raise ValidationError("observatory query totals do not replay")
        if self.latest_history_address != (self.members[-1].history_address if self.members else ""):
            raise ValidationError("observatory latest history pointer does not replay")
        if self.manifest.observatory_id != self.observatory_id or self.summary.observatory_id != self.observatory_id or self.manifest.files != FILES:
            raise ValidationError("observatory nested identities do not replay")
        if self.manifest.artifact_addresses != (address_members(self.members), address_transitions(self.transitions), self.summary.content_address):
            raise ValidationError("observatory manifest linkage does not replay")
        for field in SUMMARY_FIELDS:
            if field != "content_address" and getattr(self.summary, field) != getattr(self, field):
                raise ValidationError("observatory summary linkage does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_observatory(self) != self.content_address:
            raise ValidationError("observatory address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"observatory_id": self.observatory_id, "version": self.version, "boundary": self.boundary, "member_count": self.member_count, "transition_count": self.transition_count, "empty_count": self.empty_count, "ready_count": self.ready_count, "blocked_count": self.blocked_count, "mixed_count": self.mixed_count, "accepted_member_count": self.accepted_member_count, "total_snapshot_count": self.total_snapshot_count, "total_query_rows": self.total_query_rows, "matched_query_rows": self.matched_query_rows, "returned_query_rows": self.returned_query_rows, "initial_count": self.initial_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "latest_history_address": self.latest_history_address, "state": self.state, "accepted": self.accepted, "members": [item.to_dict() for item in self.members], "transitions": [item.to_dict() for item in self.transitions], "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"members", "transitions", "manifest", "summary"}}

    def summary_view(self) -> dict[str, Any]:
        return self.compact()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory")
        _strict(value, set(cls.FIELDS), "observatory")
        return cls(*(value[field] for field in cls.FIELDS))


def address_observatory(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatory) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatory):
        raise ValidationError("observatory address requires a typed observatory")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATORY_PREFIX)


def _member_from_history(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, ordinal: int):
    value = _verify_history(value)
    body = {"ordinal": ordinal, "history_id": value.history_id, "registry_id": value.registry_id, "history_address": value.content_address, "snapshot_count": value.entry_count, "latest_registry_address": value.latest_registry_address, "latest_entry_count": value.latest_entry_count, "latest_ready_count": value.latest_ready_count, "latest_blocked_count": value.latest_blocked_count, "latest_accepted_count": value.latest_accepted_count, "latest_rejected_count": value.latest_rejected_count, "latest_total_query_rows": value.latest_total_query_rows, "latest_matched_query_rows": value.latest_matched_query_rows, "latest_returned_query_rows": value.latest_returned_query_rows, "latest_state": value.state, "latest_accepted": value.accepted, "initial_count": value.initial_count, "improved_count": value.improved_count, "regressed_count": value.regressed_count, "unchanged_count": value.unchanged_count, "changed_count": value.changed_count, "trend": trend_from_history(value), "content_address": MEMBER_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember(**(body | {"content_address": address_member(provisional)}))


def _transition_from_entry(member: Any, entry: Any, ordinal: int):
    body = {"ordinal": ordinal, "member_ordinal": member.ordinal, "history_id": member.history_id, "registry_id": member.registry_id, "history_address": member.history_address, "snapshot_ordinal": entry.ordinal, "registry_address": entry.registry_address, "entry_count": entry.entry_count, "ready_count": entry.ready_count, "blocked_count": entry.blocked_count, "accepted_count": entry.accepted_count, "rejected_count": entry.rejected_count, "total_query_rows": entry.total_query_rows, "matched_query_rows": entry.matched_query_rows, "returned_query_rows": entry.returned_query_rows, "state": entry.state, "accepted": entry.accepted, "transition": entry.transition, "previous_registry_address": entry.previous_registry_address, "content_address": TRANSITION_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition(**(body | {"content_address": address_transition(provisional)}))


def build_observatory(histories: Sequence[Any], *, observatory_id: str = DEFAULT_OBSERVATORY_ID):
    raw_histories = _sequence(histories, "observatory histories", MAX_MEMBERS)
    if not raw_histories:
        raise ValidationError("observatory requires at least one history")
    typed_histories = tuple(sorted((_verify_history(item) for item in raw_histories), key=lambda item: (item.history_id, item.content_address)))
    if len({item.history_id for item in typed_histories}) != len(typed_histories) or len({item.content_address for item in typed_histories}) != len(typed_histories):
        raise ValidationError("observatory histories must have unique identities and addresses")
    members = tuple(_member_from_history(item, ordinal) for ordinal, item in enumerate(typed_histories, 1))
    transitions: list[Any] = []
    for member, history in zip(members, typed_histories):
        transitions.extend(_transition_from_entry(member, entry, len(transitions) + 1) for entry in history.entries.entries)
    transitions = tuple(transitions)
    state_counts = {name + "_count": sum(item.latest_state == name for item in members) for name in STATES}
    transition_counts = {name + "_count": sum(item.transition == name for item in transitions) for name in TRANSITIONS}
    totals = {field: sum(getattr(item, field) for item in transitions) for field in ("total_query_rows", "matched_query_rows", "returned_query_rows")}
    summary_body = {"observatory_id": observatory_id, "member_count": len(members), "transition_count": len(transitions), **state_counts, "accepted_member_count": sum(item.latest_accepted for item in members), "total_snapshot_count": len(transitions), **totals, **transition_counts, "latest_history_address": members[-1].history_address if members else "", "state": fold_state(tuple(item.latest_state for item in members)), "accepted": bool(members) and all(item.latest_accepted for item in members), "content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatorySummary(**summary_body)
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatorySummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    members_artifact = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMembers(members, address_members(members))
    transitions_artifact = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransitions(transitions, address_transitions(transitions))
    manifest_body = {"observatory_id": observatory_id, "files": FILES, "artifact_addresses": (members_artifact.content_address, transitions_artifact.content_address, summary.content_address), "content_address": MANIFEST_PREFIX + ":pending"}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryManifest(**manifest_body)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = {"observatory_id": observatory_id, "version": VERSION, "boundary": BOUNDARY, "member_count": len(members), "transition_count": len(transitions), **state_counts, "accepted_member_count": summary.accepted_member_count, "total_snapshot_count": len(transitions), **totals, **transition_counts, "latest_history_address": summary.latest_history_address, "state": summary.state, "accepted": summary.accepted, "members": members, "transitions": transitions, "manifest": manifest, "summary": summary, "content_address": OBSERVATORY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatory(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatory(**(body | {"content_address": address_observatory(provisional)}))


def observatory_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatory.from_mapping(value)


def observatory_json(value: Any) -> str:
    return canonical_json(observatory_from_mapping(value.to_dict()).to_dict())


def observatory_csv(value: Any) -> str:
    value = observatory_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=MEMBER_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.members:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_observatory_markdown(value: Any) -> str:
    value = observatory_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Comparison Query Snapshot Registry History Observatory", "", f"Observatory: {value.observatory_id}", f"Members: {value.member_count}", f"Snapshots: {value.transition_count}", f"State: {value.state}", f"Accepted: {value.accepted}", f"Address: {value.content_address}", "", "| # | history | registry | snapshots | latest state | trend |", "| ---: | --- | --- | ---: | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.history_id} | {item.registry_id} | {item.snapshot_count} | {item.latest_state} | {item.trend} |" for item in value.members)
    return "\n".join(lines) + "\n"


def members_json(value: Any) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMembers.from_mapping(value.to_dict()).to_dict())


def transitions_json(value: Any) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransitions.from_mapping(value.to_dict()).to_dict())


def summary_json(value: Any) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatorySummary.from_mapping(value.to_dict()).to_dict())


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_observatory(value: Any, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = observatory_from_mapping(value.to_dict())
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("observatory destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-comparison-history-observatory-", dir=str(parent)))
    try:
        members_artifact = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMembers(value.members, address_members(value.members))
        transitions_artifact = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransitions(value.transitions, address_transitions(value.transitions))
        documents = {"manifest.json": value.manifest.to_dict(), "observatory.json": value.to_dict(), "members.json": members_artifact.to_dict(), "transitions.json": transitions_artifact.to_dict(), "summary.json": value.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("observatory destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("observatory artifact is not valid JSON") from error
    return _mapping(value, "observatory artifact")


def _read_canonical(path: Path, value: Mapping[str, Any]) -> None:
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValidationError("observatory artifact cannot be read") from error
    if actual != canonical_json(value):
        raise ValidationError("observatory artifact is not canonical")


def load_observatory(destination: str | Path):
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("observatory destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("observatory directory does not contain the exact file set")
    raw = {name: _read_json(destination / name) for name in FILES}
    for name, value in raw.items():
        _read_canonical(destination / name, value)
    observatory = observatory_from_mapping(raw["observatory.json"])
    members = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMembers.from_mapping(raw["members.json"])
    transitions = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransitions.from_mapping(raw["transitions.json"])
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryManifest.from_mapping(raw["manifest.json"])
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatorySummary.from_mapping(raw["summary.json"])
    if members.to_dict() != {"members": [item.to_dict() for item in observatory.members], "content_address": address_members(observatory.members)} or transitions.to_dict() != {"transitions": [item.to_dict() for item in observatory.transitions], "content_address": address_transitions(observatory.transitions)} or manifest.to_dict() != observatory.manifest.to_dict() or summary.to_dict() != observatory.summary.to_dict():
        raise ValidationError("observatory artifacts do not replay")
    return observatory


def run_observatory(histories: Sequence[Any], *, observatory_id: str = DEFAULT_OBSERVATORY_ID, destination: str | Path | None = None, overwrite: bool = False):
    value = build_observatory(histories, observatory_id=observatory_id)
    if destination is not None:
        persist_observatory(value, destination, overwrite=overwrite)
    return value


def member_schema() -> dict[str, Any]:
    integer_fields = {"ordinal", "snapshot_count", "latest_entry_count", "latest_ready_count", "latest_blocked_count", "latest_accepted_count", "latest_rejected_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count"}
    properties = {field: {"type": "integer", "minimum": 0} if field in integer_fields else {"type": "boolean"} if field == "latest_accepted" else {"enum": list(STATES)} if field == "latest_state" else {"enum": list(TRENDS)} if field == "trend" else {"type": "string"} for field in MEMBER_FIELDS}
    properties["ordinal"]["minimum"] = 1
    for field in ("latest_total_query_rows", "latest_matched_query_rows", "latest_returned_query_rows"):
        properties[field] = {"type": "integer", "minimum": 0}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history observatory member", "type": "object", "additionalProperties": False, "required": list(MEMBER_FIELDS), "properties": properties}


def members_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history observatory members", "type": "object", "additionalProperties": False, "required": list(MEMBERS_FIELDS), "properties": {"members": {"type": "array", "maxItems": MAX_MEMBERS, "items": member_schema()}, "content_address": {"type": "string"}}}


def transition_schema() -> dict[str, Any]:
    integer_fields = {"ordinal", "member_ordinal", "snapshot_ordinal", "entry_count", "ready_count", "blocked_count", "accepted_count", "rejected_count", "total_query_rows", "matched_query_rows", "returned_query_rows"}
    properties = {field: {"type": "integer", "minimum": 0} if field in integer_fields else {"type": "boolean"} if field == "accepted" else {"enum": list(STATES)} if field == "state" else {"enum": list(TRANSITIONS)} if field == "transition" else {"type": "string"} for field in TRANSITION_FIELDS}
    properties["ordinal"]["minimum"] = 1
    properties["member_ordinal"]["minimum"] = 1
    properties["snapshot_ordinal"]["minimum"] = 1
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history observatory transition", "type": "object", "additionalProperties": False, "required": list(TRANSITION_FIELDS), "properties": properties}


def transitions_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history observatory transitions", "type": "object", "additionalProperties": False, "required": list(TRANSITIONS_FIELDS), "properties": {"transitions": {"type": "array", "maxItems": MAX_TRANSITIONS, "items": transition_schema()}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history observatory manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"observatory_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES), "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for field in SUMMARY_FIELDS:
        if field in {"observatory_id", "latest_history_address", "content_address"}:
            properties[field] = {"type": "string"}
        elif field == "accepted":
            properties[field] = {"type": "boolean"}
        elif field == "state":
            properties[field] = {"enum": list(STATES)}
        else:
            properties[field] = {"type": "integer", "minimum": 0}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history observatory summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": properties}


def observatory_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for field in OBSERVATORY_FIELDS:
        if field in {"observatory_id", "version", "boundary", "latest_history_address", "content_address"}:
            properties[field] = {"type": "string"}
        elif field == "accepted":
            properties[field] = {"type": "boolean"}
        elif field == "state":
            properties[field] = {"enum": list(STATES)}
        elif field in {"members", "transitions"}:
            properties[field] = {"type": "array"}
        elif field in {"manifest", "summary"}:
            properties[field] = {"type": "object"}
        else:
            properties[field] = {"type": "integer", "minimum": 0}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history observatory", "type": "object", "additionalProperties": False, "required": list(OBSERVATORY_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": list(FILES), "states": list(STATES), "transitions": list(TRANSITIONS), "trends": list(TRENDS), "limits": {"max_members": MAX_MEMBERS, "max_transitions": MAX_TRANSITIONS, "max_total_rows": MAX_TOTAL_ROWS}, "features": ["multi-history aggregation", "member latest-metric projection", "snapshot transition flattening", "query-row total folding", "exact five-file persistence", "canonical reload verification", "atomic writes", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "DEFAULT_OBSERVATORY_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_MEMBERS", "MAX_TOTAL_ROWS", "MAX_TRANSITIONS", "MEMBER_FIELDS", "MEMBER_PREFIX", "MEMBERS_FIELDS", "MEMBERS_PREFIX", "OBSERVATORY_FIELDS", "OBSERVATORY_PREFIX", "STATES", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "TRANSITION_FIELDS", "TRANSITION_PREFIX", "TRANSITIONS", "TRANSITIONS_FIELDS", "TRANSITIONS_PREFIX", "TRENDS", "TRANSITIONS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatory", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMember", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryMembers", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatorySummary", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransition", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryHistoryObservatoryTransitions", "address_manifest", "address_member", "address_members", "address_observatory", "address_summary", "address_transition", "address_transitions", "build_observatory", "capabilities", "fold_state", "load_observatory", "manifest_schema", "member_schema", "members_json", "members_schema", "observatory_csv", "observatory_from_mapping", "observatory_json", "observatory_schema", "persist_observatory", "render_observatory_markdown", "run_observatory", "summary_json", "summary_schema", "transition_schema", "transitions_json", "transitions_schema", "trend_from_history"]
