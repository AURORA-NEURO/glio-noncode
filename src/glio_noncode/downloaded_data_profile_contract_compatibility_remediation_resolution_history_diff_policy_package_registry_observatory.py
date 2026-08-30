"""Cross-history observatory for value-free policy package registries.

The observatory folds independently verified registry histories into a stable,
path-free view. It keeps content addresses and aggregate counters while
excluding source records, source paths, and private execution metadata.
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
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history as history_model
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
STATES = ("empty", "ready", "review", "blocked", "mixed")
DECISIONS = ("promote", "hold", "block", "mixed")
TRENDS = ("stable", "improved", "regressed", "changed")
TRANSITIONS = history_model.TRANSITIONS
MEMBER_FIELDS = ("ordinal", "history_id", "registry_id", "history_address", "snapshot_count", "latest_registry_address", "latest_state", "latest_decision", "latest_accepted", "latest_release_ready", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "trend", "content_address")
MEMBERS_FIELDS = ("members", "content_address")
TRANSITION_FIELDS = ("ordinal", "member_ordinal", "history_id", "registry_id", "history_address", "snapshot_ordinal", "registry_address", "transition", "state", "decision", "accepted", "release_ready", "content_address")
TRANSITIONS_FIELDS = ("transitions", "content_address")
MANIFEST_FIELDS = ("observatory_id", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("observatory_id", "member_count", "transition_count", "empty_count", "ready_count", "review_count", "blocked_count", "mixed_count", "promote_count", "hold_count", "block_count", "mixed_decision_count", "accepted_member_count", "release_ready_member_count", "total_snapshot_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "latest_history_address", "state", "decision", "accepted", "release_ready", "content_address")
OBSERVATORY_FIELDS = ("observatory_id", "version", "boundary", "member_count", "transition_count", "empty_count", "ready_count", "review_count", "blocked_count", "mixed_count", "promote_count", "hold_count", "block_count", "mixed_decision_count", "accepted_member_count", "release_ready_member_count", "total_snapshot_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "latest_history_address", "state", "decision", "accepted", "release_ready", "members", "transitions", "manifest", "summary", "content_address")
MAX_MEMBERS = history_model.MAX_ENTRIES
MAX_TRANSITIONS = MAX_MEMBERS * history_model.MAX_ENTRIES


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
    if isinstance(value, (list, tuple)):
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
    if not values or all(state == "empty" for state in values):
        return "empty"
    if "blocked" in values:
        return "blocked"
    if "review" in values:
        return "review"
    if len(set(values)) == 1 and values[0] == "ready":
        return "ready"
    return "mixed"


def fold_decision(decisions: Sequence[str]) -> str:
    values = tuple(decisions)
    if not values:
        return "hold"
    if "block" in values:
        return "block"
    if "hold" in values:
        return "hold"
    if len(set(values)) == 1:
        return values[0]
    return "mixed"


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember:
    FIELDS = MEMBER_FIELDS

    def __init__(self, ordinal: int, history_id: str, registry_id: str, history_address: str, snapshot_count: int, latest_registry_address: str, latest_state: str, latest_decision: str, latest_accepted: bool, latest_release_ready: bool, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, trend: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory member ordinal", MAX_MEMBERS, positive=True)
        self.history_id = _label(history_id, "observatory member history ID")
        self.registry_id = _label(registry_id, "observatory member registry ID", required=False)
        self.history_address = _address(history_address, "observatory member history address", history_model.HISTORY_PREFIX)
        self.snapshot_count = _count(snapshot_count, "observatory member snapshot count", history_model.MAX_ENTRIES)
        self.latest_registry_address = _address(latest_registry_address, "observatory member latest registry address", history_model.registry_model.REGISTRY_PREFIX, required=False)
        self.latest_state = _label(latest_state, "observatory member latest state")
        if self.latest_state not in history_model.STATES:
            raise ValidationError("observatory member latest state is unsupported")
        self.latest_decision = _label(latest_decision, "observatory member latest decision")
        if self.latest_decision not in history_model.DECISIONS:
            raise ValidationError("observatory member latest decision is unsupported")
        self.latest_accepted = _bool(latest_accepted, "observatory member latest acceptance")
        self.latest_release_ready = _bool(latest_release_ready, "observatory member latest readiness")
        self.initial_count = _count(initial_count, "observatory member initial count", history_model.MAX_ENTRIES)
        self.improved_count = _count(improved_count, "observatory member improved count", history_model.MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "observatory member regressed count", history_model.MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "observatory member unchanged count", history_model.MAX_ENTRIES)
        self.changed_count = _count(changed_count, "observatory member changed count", history_model.MAX_ENTRIES)
        self.trend = _label(trend, "observatory member trend")
        if self.trend not in TRENDS:
            raise ValidationError("observatory member trend is unsupported")
        self.content_address = _address(content_address, "observatory member content address", MEMBER_PREFIX)
        self._validate()

    def _validate(self) -> None:
        total = self.initial_count + self.improved_count + self.regressed_count + self.unchanged_count + self.changed_count
        if total != self.snapshot_count:
            raise ValidationError("observatory member transition counts are not conserved")
        if self.snapshot_count == 0 and (self.latest_registry_address or self.latest_state != "empty" or self.latest_decision != "hold" or self.latest_accepted or self.latest_release_ready):
            raise ValidationError("empty observatory member has a latest snapshot")
        if self.snapshot_count and not self.latest_registry_address:
            raise ValidationError("non-empty observatory member requires a latest snapshot address")
        if self.trend == "improved" and self.improved_count <= self.regressed_count:
            raise ValidationError("improved member trend does not replay")
        if self.trend == "regressed" and self.regressed_count <= self.improved_count:
            raise ValidationError("regressed member trend does not replay")
        if self.trend == "changed" and (self.changed_count == 0 or self.improved_count != self.regressed_count):
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


def address_member(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember):
        raise ValidationError("observatory member address requires a typed member")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMembers:
    FIELDS = MEMBERS_FIELDS

    def __init__(self, members: Sequence[Any], content_address: str) -> None:
        self.members = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember.from_mapping(item) for item in _sequence(members, "observatory members", MAX_MEMBERS))
        self.content_address = _address(content_address, "observatory members content address", MEMBERS_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.members) != tuple(range(1, len(self.members) + 1)) or len({item.history_id for item in self.members}) != len(self.members) or not _public(self.to_dict()):
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


def address_members(value: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember) for item in typed):
        raise ValidationError("observatory members address requires typed members")
    return content_hash({"members": [item.to_dict() for item in typed]}, prefix=MEMBERS_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition:
    FIELDS = TRANSITION_FIELDS

    def __init__(self, ordinal: int, member_ordinal: int, history_id: str, registry_id: str, history_address: str, snapshot_ordinal: int, registry_address: str, transition: str, state: str, decision: str, accepted: bool, release_ready: bool, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory transition ordinal", MAX_TRANSITIONS, positive=True)
        self.member_ordinal = _count(member_ordinal, "observatory transition member ordinal", MAX_MEMBERS, positive=True)
        self.history_id = _label(history_id, "observatory transition history ID")
        self.registry_id = _label(registry_id, "observatory transition registry ID", required=False)
        self.history_address = _address(history_address, "observatory transition history address", history_model.HISTORY_PREFIX)
        self.snapshot_ordinal = _count(snapshot_ordinal, "observatory transition snapshot ordinal", history_model.MAX_ENTRIES, positive=True)
        self.registry_address = _address(registry_address, "observatory transition registry address", history_model.registry_model.REGISTRY_PREFIX)
        self.transition = _label(transition, "observatory transition kind")
        if self.transition not in TRANSITIONS:
            raise ValidationError("observatory transition kind is unsupported")
        self.state = _label(state, "observatory transition state")
        if self.state not in history_model.STATES:
            raise ValidationError("observatory transition state is unsupported")
        self.decision = _label(decision, "observatory transition decision")
        if self.decision not in history_model.DECISIONS:
            raise ValidationError("observatory transition decision is unsupported")
        self.accepted = _bool(accepted, "observatory transition acceptance")
        self.release_ready = _bool(release_ready, "observatory transition readiness")
        self.content_address = _address(content_address, "observatory transition content address", TRANSITION_PREFIX)
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


def address_transition(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition):
        raise ValidationError("observatory transition address requires a typed transition")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=TRANSITION_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransitions:
    FIELDS = TRANSITIONS_FIELDS

    def __init__(self, transitions: Sequence[Any], content_address: str) -> None:
        self.transitions = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition.from_mapping(item) for item in _sequence(transitions, "observatory transitions", MAX_TRANSITIONS))
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


def address_transitions(value: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition) for item in typed):
        raise ValidationError("observatory transitions address requires typed transitions")
    return content_hash({"transitions": [item.to_dict() for item in typed]}, prefix=TRANSITIONS_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryManifest:
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


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryManifest):
        raise ValidationError("observatory manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, observatory_id: str, member_count: int, transition_count: int, empty_count: int, ready_count: int, review_count: int, blocked_count: int, mixed_count: int, promote_count: int, hold_count: int, block_count: int, mixed_decision_count: int, accepted_member_count: int, release_ready_member_count: int, total_snapshot_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, latest_history_address: str, state: str, decision: str, accepted: bool, release_ready: bool, content_address: str) -> None:
        self.observatory_id = _label(observatory_id, "observatory summary ID")
        self.member_count = _count(member_count, "observatory summary member count", MAX_MEMBERS)
        self.transition_count = _count(transition_count, "observatory summary transition count", MAX_TRANSITIONS)
        for field in ("empty_count", "ready_count", "review_count", "blocked_count", "mixed_count", "promote_count", "hold_count", "block_count", "mixed_decision_count", "accepted_member_count", "release_ready_member_count"):
            setattr(self, field, _count(locals()[field], f"observatory summary {field}", MAX_MEMBERS))
        self.total_snapshot_count = _count(total_snapshot_count, "observatory summary snapshot count", MAX_TRANSITIONS)
        for field in ("initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count"):
            setattr(self, field, _count(locals()[field], f"observatory summary {field}", MAX_TRANSITIONS))
        self.latest_history_address = _address(latest_history_address, "observatory summary latest history address", history_model.HISTORY_PREFIX, required=False)
        self.state = _label(state, "observatory summary state")
        if self.state not in STATES:
            raise ValidationError("observatory summary state is unsupported")
        self.decision = _label(decision, "observatory summary decision")
        if self.decision not in DECISIONS:
            raise ValidationError("observatory summary decision is unsupported")
        self.accepted = _bool(accepted, "observatory summary acceptance")
        self.release_ready = _bool(release_ready, "observatory summary readiness")
        self.content_address = _address(content_address, "observatory summary content address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.empty_count + self.ready_count + self.review_count + self.blocked_count + self.mixed_count != self.member_count:
            raise ValidationError("observatory summary state counts are not conserved")
        if self.promote_count + self.hold_count + self.block_count + self.mixed_decision_count != self.member_count:
            raise ValidationError("observatory summary decision counts are not conserved")
        if self.accepted_member_count > self.member_count or self.release_ready_member_count > self.member_count:
            raise ValidationError("observatory summary readiness counts exceed members")
        if self.total_snapshot_count != self.transition_count or self.initial_count + self.improved_count + self.regressed_count + self.unchanged_count + self.changed_count != self.transition_count:
            raise ValidationError("observatory summary transition counts are not conserved")
        if self.accepted != (bool(self.member_count) and self.accepted_member_count == self.member_count) or self.release_ready != (bool(self.member_count) and self.release_ready_member_count == self.member_count):
            raise ValidationError("observatory summary readiness does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory summary crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("observatory summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory summary")
        _strict(value, set(cls.FIELDS), "observatory summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary):
        raise ValidationError("observatory summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory:
    FIELDS = OBSERVATORY_FIELDS

    def __init__(self, observatory_id: str, version: str, boundary: str, member_count: int, transition_count: int, empty_count: int, ready_count: int, review_count: int, blocked_count: int, mixed_count: int, promote_count: int, hold_count: int, block_count: int, mixed_decision_count: int, accepted_member_count: int, release_ready_member_count: int, total_snapshot_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, latest_history_address: str, state: str, decision: str, accepted: bool, release_ready: bool, members: Sequence[Any], transitions: Sequence[Any], manifest: Any, summary: Any, content_address: str) -> None:
        self.observatory_id = _label(observatory_id, "observatory ID")
        self.version = _text(version, "observatory version", 512)
        self.boundary = _label(boundary, "observatory boundary")
        self.member_count = _count(member_count, "observatory member count", MAX_MEMBERS)
        self.transition_count = _count(transition_count, "observatory transition count", MAX_TRANSITIONS)
        for field in ("empty_count", "ready_count", "review_count", "blocked_count", "mixed_count", "promote_count", "hold_count", "block_count", "mixed_decision_count", "accepted_member_count", "release_ready_member_count"):
            setattr(self, field, _count(locals()[field], f"observatory {field}", MAX_MEMBERS))
        for field in ("total_snapshot_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count"):
            setattr(self, field, _count(locals()[field], f"observatory {field}", MAX_TRANSITIONS))
        self.latest_history_address = _address(latest_history_address, "observatory latest history address", history_model.HISTORY_PREFIX, required=False)
        self.state = _label(state, "observatory state")
        if self.state not in STATES:
            raise ValidationError("observatory state is unsupported")
        self.decision = _label(decision, "observatory decision")
        if self.decision not in DECISIONS:
            raise ValidationError("observatory decision is unsupported")
        self.accepted = _bool(accepted, "observatory acceptance")
        self.release_ready = _bool(release_ready, "observatory readiness")
        self.members = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember.from_mapping(item) for item in _sequence(members, "observatory members", MAX_MEMBERS))
        self.transitions = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition.from_mapping(item) for item in _sequence(transitions, "observatory transitions", MAX_TRANSITIONS))
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary.from_mapping(summary)
        self.content_address = _address(content_address, "observatory content address", OBSERVATORY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("observatory version or boundary is unsupported")
        if len(self.members) != self.member_count or len(self.transitions) != self.transition_count:
            raise ValidationError("observatory counts do not replay")
        if tuple(item.ordinal for item in self.members) != tuple(range(1, self.member_count + 1)) or tuple(item.ordinal for item in self.transitions) != tuple(range(1, self.transition_count + 1)):
            raise ValidationError("observatory ordinals are not contiguous")
        if len({item.history_id for item in self.members}) != self.member_count:
            raise ValidationError("observatory history identities are not unique")
        if self.empty_count + self.ready_count + self.review_count + self.blocked_count + self.mixed_count != self.member_count or self.promote_count + self.hold_count + self.block_count + self.mixed_decision_count != self.member_count:
            raise ValidationError("observatory disposition counts are not conserved")
        if self.accepted_member_count != sum(item.latest_accepted for item in self.members) or self.release_ready_member_count != sum(item.latest_release_ready for item in self.members):
            raise ValidationError("observatory readiness counts do not replay")
        if self.total_snapshot_count != self.transition_count or self.initial_count + self.improved_count + self.regressed_count + self.unchanged_count + self.changed_count != self.transition_count:
            raise ValidationError("observatory transition totals do not replay")
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
        return {"observatory_id": self.observatory_id, "version": self.version, "boundary": self.boundary, "member_count": self.member_count, "transition_count": self.transition_count, "empty_count": self.empty_count, "ready_count": self.ready_count, "review_count": self.review_count, "blocked_count": self.blocked_count, "mixed_count": self.mixed_count, "promote_count": self.promote_count, "hold_count": self.hold_count, "block_count": self.block_count, "mixed_decision_count": self.mixed_decision_count, "accepted_member_count": self.accepted_member_count, "release_ready_member_count": self.release_ready_member_count, "total_snapshot_count": self.total_snapshot_count, "initial_count": self.initial_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "latest_history_address": self.latest_history_address, "state": self.state, "decision": self.decision, "accepted": self.accepted, "release_ready": self.release_ready, "members": [item.to_dict() for item in self.members], "transitions": [item.to_dict() for item in self.transitions], "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"members", "transitions", "manifest", "summary"}}

    def summary(self) -> dict[str, Any]:
        return self.compact()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "observatory")
        _strict(value, set(cls.FIELDS), "observatory")
        return cls(*(value[field] for field in cls.FIELDS))


def address_observatory(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory):
        raise ValidationError("observatory address requires a typed observatory")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATORY_PREFIX)


def _member_from_history(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember:
    body = {"ordinal": ordinal, "history_id": value.history_id, "registry_id": value.registry_id, "history_address": value.content_address, "snapshot_count": value.entry_count, "latest_registry_address": value.latest_registry_address, "latest_state": value.state, "latest_decision": value.decision, "latest_accepted": value.accepted, "latest_release_ready": value.release_ready, "initial_count": value.initial_count, "improved_count": value.improved_count, "regressed_count": value.regressed_count, "unchanged_count": value.unchanged_count, "changed_count": value.changed_count, "trend": trend_from_history(value), "content_address": MEMBER_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember(**(body | {"content_address": address_member(provisional)}))


def _transition_from_entry(member: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember, entry: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition:
    body = {"ordinal": ordinal, "member_ordinal": member.ordinal, "history_id": member.history_id, "registry_id": member.registry_id, "history_address": member.history_address, "snapshot_ordinal": entry.ordinal, "registry_address": entry.registry_address, "transition": entry.transition, "state": entry.state, "decision": entry.decision, "accepted": entry.accepted, "release_ready": entry.release_ready, "content_address": TRANSITION_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition(**(body | {"content_address": address_transition(provisional)}))


def build_observatory(histories: Sequence[history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory], *, observatory_id: str = DEFAULT_OBSERVATORY_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory:
    raw_histories = _sequence(histories, "observatory histories", MAX_MEMBERS)
    if not raw_histories:
        raise ValidationError("observatory requires at least one history")
    typed_histories = tuple(sorted((_verify_history(item) for item in raw_histories), key=lambda item: (item.history_id, item.content_address)))
    if len({item.history_id for item in typed_histories}) != len(typed_histories) or len({item.content_address for item in typed_histories}) != len(typed_histories):
        raise ValidationError("observatory histories must have unique identities and addresses")
    members = tuple(_member_from_history(item, ordinal) for ordinal, item in enumerate(typed_histories, 1))
    transition_items = []
    transition_ordinal = 1
    for member, history in zip(members, typed_histories):
        for entry in history.entries:
            transition_items.append(_transition_from_entry(member, entry, transition_ordinal))
            transition_ordinal += 1
    transitions = tuple(transition_items)
    state_counts = {name + "_count": sum(item.latest_state == name for item in members) for name in STATES}
    decision_counts = {("mixed_decision_count" if name == "mixed" else name + "_count"): sum(item.latest_decision == name for item in members) for name in DECISIONS}
    transition_counts = {name + "_count": sum(item.transition == name for item in transitions) for name in TRANSITIONS}
    state = fold_state(tuple(item.latest_state for item in members))
    decision = fold_decision(tuple(item.latest_decision for item in members))
    summary_body = {"observatory_id": observatory_id, "member_count": len(members), "transition_count": len(transitions), **state_counts, **decision_counts, "accepted_member_count": sum(item.latest_accepted for item in members), "release_ready_member_count": sum(item.latest_release_ready for item in members), "total_snapshot_count": len(transitions), **transition_counts, "latest_history_address": members[-1].history_address if members else "", "state": state, "decision": decision, "accepted": bool(members) and all(item.latest_accepted for item in members), "release_ready": bool(members) and all(item.latest_release_ready for item in members), "content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary(**summary_body)
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    members_artifact = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMembers(members, address_members(members))
    transitions_artifact = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransitions(transitions, address_transitions(transitions))
    manifest_body = {"observatory_id": observatory_id, "files": FILES, "artifact_addresses": (members_artifact.content_address, transitions_artifact.content_address, summary.content_address), "content_address": MANIFEST_PREFIX + ":pending"}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryManifest(**manifest_body)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = {"observatory_id": observatory_id, "version": VERSION, "boundary": BOUNDARY, "member_count": len(members), "transition_count": len(transitions), **state_counts, **decision_counts, "accepted_member_count": summary.accepted_member_count, "release_ready_member_count": summary.release_ready_member_count, "total_snapshot_count": len(transitions), **transition_counts, "latest_history_address": summary.latest_history_address, "state": state, "decision": decision, "accepted": summary.accepted, "release_ready": summary.release_ready, "members": members, "transitions": transitions, "manifest": manifest, "summary": summary, "content_address": OBSERVATORY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory(**(body | {"content_address": address_observatory(provisional)}))


def observatory_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory.from_mapping(value)


def observatory_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory) -> str:
    return canonical_json(observatory_from_mapping(value.to_dict()).to_dict())


def observatory_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory) -> str:
    value = observatory_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=MEMBER_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.members:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_observatory_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory) -> str:
    value = observatory_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry Observatory", "", f"- Observatory: `{value.observatory_id}`", f"- Members: `{value.member_count}`", f"- Snapshots: `{value.transition_count}`", f"- State: `{value.state}`", f"- Decision: `{value.decision}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| # | history | registry | snapshots | latest state | latest decision | trend |", "| ---: | --- | --- | ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.history_id}` | `{item.registry_id}` | `{item.snapshot_count}` | `{item.latest_state}` | `{item.latest_decision}` | `{item.trend}` |" for item in value.members)
    return "\n".join(lines) + "\n"


def members_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMembers) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMembers.from_mapping(value.to_dict()).to_dict())


def transitions_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransitions) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransitions.from_mapping(value.to_dict()).to_dict())


def summary_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary.from_mapping(value.to_dict()).to_dict())


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_observatory(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = observatory_from_mapping(value.to_dict())
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("observatory destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-policy-package-registry-observatory-", dir=str(parent)))
    try:
        members_artifact = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMembers(value.members, address_members(value.members))
        transitions_artifact = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransitions(value.transitions, address_transitions(value.transitions))
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


def load_observatory(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory:
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
    members = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMembers.from_mapping(raw["members.json"])
    transitions = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransitions.from_mapping(raw["transitions.json"])
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryManifest.from_mapping(raw["manifest.json"])
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary.from_mapping(raw["summary.json"])
    if members.to_dict() != {"members": [item.to_dict() for item in observatory.members], "content_address": address_members(observatory.members)} or transitions.to_dict() != {"transitions": [item.to_dict() for item in observatory.transitions], "content_address": address_transitions(observatory.transitions)} or manifest.to_dict() != observatory.manifest.to_dict() or summary.to_dict() != observatory.summary.to_dict():
        raise ValidationError("observatory artifacts do not replay")
    return observatory


def run_observatory(histories: Sequence[history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory], *, observatory_id: str = DEFAULT_OBSERVATORY_ID, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory:
    value = build_observatory(histories, observatory_id=observatory_id)
    if destination is not None:
        persist_observatory(value, destination, overwrite=overwrite)
    return value


def member_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry observatory member", "type": "object", "additionalProperties": False, "required": list(MEMBER_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "history_id": {"type": "string"}, "registry_id": {"type": "string"}, "history_address": {"type": "string"}, "snapshot_count": {"type": "integer", "minimum": 0}, "latest_registry_address": {"type": "string"}, "latest_state": {"enum": list(history_model.STATES)}, "latest_decision": {"enum": list(history_model.DECISIONS)}, "latest_accepted": {"type": "boolean"}, "latest_release_ready": {"type": "boolean"}, "initial_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "trend": {"enum": list(TRENDS)}, "content_address": {"type": "string"}}}


def members_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry observatory members", "type": "object", "additionalProperties": False, "required": list(MEMBERS_FIELDS), "properties": {"members": {"type": "array", "items": member_schema(), "maxItems": MAX_MEMBERS}, "content_address": {"type": "string"}}}


def transition_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry observatory transition", "type": "object", "additionalProperties": False, "required": list(TRANSITION_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "member_ordinal": {"type": "integer", "minimum": 1}, "history_id": {"type": "string"}, "registry_id": {"type": "string"}, "history_address": {"type": "string"}, "snapshot_ordinal": {"type": "integer", "minimum": 1}, "registry_address": {"type": "string"}, "transition": {"enum": list(TRANSITIONS)}, "state": {"enum": list(history_model.STATES)}, "decision": {"enum": list(history_model.DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "content_address": {"type": "string"}}}


def transitions_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry observatory transitions", "type": "object", "additionalProperties": False, "required": list(TRANSITIONS_FIELDS), "properties": {"transitions": {"type": "array", "items": transition_schema(), "maxItems": MAX_TRANSITIONS}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry observatory manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"observatory_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for field in SUMMARY_FIELDS:
        if field in {"observatory_id", "latest_history_address", "content_address"}:
            properties[field] = {"type": "string"}
        elif field in {"accepted", "release_ready"}:
            properties[field] = {"type": "boolean"}
        elif field == "state":
            properties[field] = {"enum": list(STATES)}
        elif field == "decision":
            properties[field] = {"enum": list(DECISIONS)}
        else:
            properties[field] = {"type": "integer", "minimum": 0}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry observatory summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": properties}


def observatory_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for field in OBSERVATORY_FIELDS:
        if field in {"observatory_id", "version", "boundary", "latest_history_address", "content_address"}:
            properties[field] = {"type": "string"}
        elif field in {"accepted", "release_ready"}:
            properties[field] = {"type": "boolean"}
        elif field == "state":
            properties[field] = {"enum": list(STATES)}
        elif field == "decision":
            properties[field] = {"enum": list(DECISIONS)}
        elif field in {"members", "transitions"}:
            properties[field] = {"type": "array"}
        elif field in {"manifest", "summary"}:
            properties[field] = {"type": "object"}
        else:
            properties[field] = {"type": "integer", "minimum": 0}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry observatory", "type": "object", "additionalProperties": False, "required": list(OBSERVATORY_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": list(FILES), "states": list(STATES), "decisions": list(DECISIONS), "trends": list(TRENDS), "transitions": list(TRANSITIONS), "limits": {"max_members": MAX_MEMBERS, "max_transitions": MAX_TRANSITIONS}, "features": ["multi-history registry observation", "member-level latest-state folding", "snapshot transition projection", "exact five-file persistence", "canonical reload verification", "atomic writes", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "DECISIONS", "DEFAULT_OBSERVATORY_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_MEMBERS", "MAX_TRANSITIONS", "MEMBER_FIELDS", "MEMBER_PREFIX", "MEMBERS_FIELDS", "MEMBERS_PREFIX", "OBSERVATORY_FIELDS", "OBSERVATORY_PREFIX", "STATES", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "TRANSITION_FIELDS", "TRANSITION_PREFIX", "TRANSITIONS", "TRANSITIONS_FIELDS", "TRANSITIONS_PREFIX", "TRENDS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMember", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMembers", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatorySummary", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransition", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransitions", "address_manifest", "address_member", "address_members", "address_observatory", "address_summary", "address_transition", "address_transitions", "build_observatory", "capabilities", "fold_decision", "fold_state", "load_observatory", "manifest_schema", "member_schema", "members_json", "members_schema", "observatory_csv", "observatory_from_mapping", "observatory_json", "observatory_schema", "persist_observatory", "render_observatory_markdown", "run_observatory", "summary_json", "summary_schema", "transition_schema", "transitions_json", "transitions_schema", "trend_from_history"]
