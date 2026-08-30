"""Append-only value-free history for policy package registries.

The history records addressed registry snapshots, their aggregate counters, and
deterministic trend transitions. It deliberately keeps source records, paths,
and private execution metadata outside the public boundary.
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
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry as registry_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history"
HISTORY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
ENTRIES_PREFIX = HISTORY_PREFIX + "-entries"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
SUMMARY_PREFIX = HISTORY_PREFIX + "-summary"
DEFAULT_HISTORY_ID = HISTORY_PREFIX
FILES = ("manifest.json", "history.json", "entries.json", "summary.json")
MANIFEST_ARTIFACT_FILES = ("entries.json", "summary.json")
TRANSITIONS = ("initial", "improved", "regressed", "unchanged", "changed")
STATES = registry_model.STATES
DECISIONS = registry_model.DECISIONS
ENTRY_FIELDS = ("ordinal", "registry_id", "registry_address", "entry_count", "accepted_count", "release_ready_count", "promote_count", "hold_count", "block_count", "state", "decision", "accepted", "release_ready", "transition", "previous_registry_address", "content_address")
ENTRIES_FIELDS = ("entries", "content_address")
MANIFEST_FIELDS = ("history_id", "registry_id", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("history_id", "registry_id", "entry_count", "latest_registry_address", "latest_entry_count", "latest_accepted_count", "latest_release_ready_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "state", "decision", "accepted", "release_ready", "content_address")
HISTORY_FIELDS = ("history_id", "registry_id", "version", "boundary", "entry_count", "latest_registry_address", "latest_entry_count", "latest_accepted_count", "latest_release_ready_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "changed_count", "state", "decision", "accepted", "release_ready", "manifest", "summary", "entries", "content_address")
MAX_ENTRIES = registry_model.MAX_ENTRIES


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


def _signed(value: Any, field: str, bound: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or abs(value) > bound:
        raise ValidationError(f"{field} is outside its signed bound")
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


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _quality(value: Any) -> tuple[int, int, int, int, int, int]:
    ranks = {"ready": 0, "empty": 1, "review": 2, "blocked": 3}
    return (ranks[value.state], -value.release_ready_count, -value.accepted_count, value.block_count, value.hold_count, value.entry_count)


def _registry_decision(value: Any) -> str:
    return {"empty": "hold", "ready": "promote", "review": "hold", "blocked": "block"}[value.state]


def _transition(current: Any, previous: Any | None) -> str:
    if previous is None:
        return "initial"
    current_quality = _quality(current)
    previous_quality = _quality(previous)
    if current_quality < previous_quality:
        return "improved"
    if current_quality > previous_quality:
        return "regressed"
    fields = ("entry_count", "accepted_count", "release_ready_count", "promote_count", "hold_count", "block_count", "state", "decision", "accepted", "release_ready")
    return "unchanged" if all(getattr(current, field) == getattr(previous, field) for field in fields) else "changed"


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry:
    """One addressed registry snapshot in append order."""

    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, registry_id: str, registry_address: str, entry_count: int, accepted_count: int, release_ready_count: int, promote_count: int, hold_count: int, block_count: int, state: str, decision: str, accepted: bool, release_ready: bool, transition: str, previous_registry_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry history entry ordinal", MAX_ENTRIES, positive=True)
        self.registry_id = _label(registry_id, "registry history registry ID")
        self.registry_address = _address(registry_address, "registry history registry address", registry_model.REGISTRY_PREFIX)
        self.entry_count = _count(entry_count, "registry history entry count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "registry history accepted count", MAX_ENTRIES)
        self.release_ready_count = _count(release_ready_count, "registry history release-ready count", MAX_ENTRIES)
        self.promote_count = _count(promote_count, "registry history promote count", MAX_ENTRIES)
        self.hold_count = _count(hold_count, "registry history hold count", MAX_ENTRIES)
        self.block_count = _count(block_count, "registry history block count", MAX_ENTRIES)
        self.state = _label(state, "registry history entry state")
        if self.state not in STATES:
            raise ValidationError("registry history entry state is unsupported")
        self.decision = _label(decision, "registry history entry decision")
        if self.decision not in DECISIONS:
            raise ValidationError("registry history entry decision is unsupported")
        self.accepted = _bool(accepted, "registry history entry acceptance")
        self.release_ready = _bool(release_ready, "registry history entry release readiness")
        self.transition = _label(transition, "registry history transition")
        if self.transition not in TRANSITIONS:
            raise ValidationError("registry history transition is unsupported")
        self.previous_registry_address = _address(previous_registry_address, "registry history previous registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.content_address = _address(content_address, "registry history entry address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.ordinal == 1 and (self.transition != "initial" or self.previous_registry_address):
            raise ValidationError("first registry history entry must be initial")
        if self.ordinal > 1 and (self.transition == "initial" or not self.previous_registry_address):
            raise ValidationError("later registry history entries require a previous registry")
        if self.accepted_count > self.entry_count or self.release_ready_count > self.entry_count:
            raise ValidationError("registry history acceptance counts exceed entries")
        if self.promote_count + self.hold_count + self.block_count != self.entry_count:
            raise ValidationError("registry history decision counts are not conserved")
        if self.accepted != (not self.entry_count or self.accepted_count == self.entry_count):
            raise ValidationError("registry history entry acceptance does not replay")
        if self.release_ready != (bool(self.entry_count) and self.release_ready_count == self.entry_count):
            raise ValidationError("registry history entry readiness does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry history entry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("registry history entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry:
        value = _mapping(value, "registry history entry")
        _strict(value, set(cls.FIELDS), "registry history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry):
        raise ValidationError("registry history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def entry_from_registry(value: registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry, ordinal: int, transition: str, previous_registry_address: str) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry:
    if not isinstance(value, registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry):
        raise ValidationError("registry history entries require typed registries")
    body = {"ordinal": ordinal, "registry_id": value.registry_id, "registry_address": value.content_address, "entry_count": value.entry_count, "accepted_count": value.accepted_count, "release_ready_count": value.release_ready_count, "promote_count": value.promote_count, "hold_count": value.hold_count, "block_count": value.block_count, "state": value.state, "decision": _registry_decision(value), "accepted": value.accepted, "release_ready": value.release_ready, "transition": transition, "previous_registry_address": previous_registry_address, "content_address": ENTRY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry(**(body | {"content_address": address_entry(provisional)}))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries:
    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry.from_mapping(item) for item in _sequence(entries, "registry history entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "registry history entries address", ENTRIES_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("registry history entries cross the public boundary")
        if not self.content_address.endswith(":pending") and address_entries(self.entries) != self.content_address:
            raise ValidationError("registry history entries address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries:
        value = _mapping(value, "registry history entries")
        _strict(value, set(cls.FIELDS), "registry history entries")
        return cls(value["entries"], value["content_address"])


def address_entries(value: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry) for item in typed):
        raise ValidationError("registry history entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, history_id: str, registry_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.history_id = _label(history_id, "registry history manifest history ID")
        self.registry_id = _label(registry_id, "registry history manifest registry ID", required=False)
        self.files = tuple(_label(item, "registry history manifest file") for item in _sequence(files, "registry history manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "registry history manifest artifact address") for item in _sequence(artifact_addresses, "registry history manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "registry history manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("registry history manifest does not close the public file boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("registry history manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest:
        value = _mapping(value, "registry history manifest")
        _strict(value, set(cls.FIELDS), "registry history manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest):
        raise ValidationError("registry history manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, history_id: str, registry_id: str, entry_count: int, latest_registry_address: str, latest_entry_count: int, latest_accepted_count: int, latest_release_ready_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, state: str, decision: str, accepted: bool, release_ready: bool, content_address: str) -> None:
        self.history_id = _label(history_id, "registry history summary history ID")
        self.registry_id = _label(registry_id, "registry history summary registry ID", required=False)
        self.entry_count = _count(entry_count, "registry history summary entry count", MAX_ENTRIES)
        self.latest_registry_address = _address(latest_registry_address, "registry history summary latest registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.latest_entry_count = _count(latest_entry_count, "registry history summary latest entry count", MAX_ENTRIES)
        self.latest_accepted_count = _count(latest_accepted_count, "registry history summary latest accepted count", MAX_ENTRIES)
        self.latest_release_ready_count = _count(latest_release_ready_count, "registry history summary latest release-ready count", MAX_ENTRIES)
        self.initial_count = _count(initial_count, "registry history summary initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "registry history summary improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "registry history summary regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "registry history summary unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "registry history summary changed count", MAX_ENTRIES)
        self.state = _label(state, "registry history summary state")
        if self.state not in STATES:
            raise ValidationError("registry history summary state is unsupported")
        self.decision = _label(decision, "registry history summary decision")
        if self.decision not in DECISIONS:
            raise ValidationError("registry history summary decision is unsupported")
        self.accepted = _bool(accepted, "registry history summary acceptance")
        self.release_ready = _bool(release_ready, "registry history summary release readiness")
        self.content_address = _address(content_address, "registry history summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.initial_count + self.improved_count + self.regressed_count + self.unchanged_count + self.changed_count != self.entry_count:
            raise ValidationError("registry history summary transition counts are not conserved")
        if self.latest_accepted_count > self.latest_entry_count or self.latest_release_ready_count > self.latest_entry_count:
            raise ValidationError("registry history summary latest counts exceed entries")
        if not _public(self.to_dict()):
            raise ValidationError("registry history summary crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("registry history summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary:
        value = _mapping(value, "registry history summary")
        _strict(value, set(cls.FIELDS), "registry history summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary):
        raise ValidationError("registry history summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory:
    FIELDS = HISTORY_FIELDS

    def __init__(self, history_id: str, registry_id: str, version: str, boundary: str, entry_count: int, latest_registry_address: str, latest_entry_count: int, latest_accepted_count: int, latest_release_ready_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, state: str, decision: str, accepted: bool, release_ready: bool, manifest: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest | Mapping[str, Any], summary: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary | Mapping[str, Any], entries: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.history_id = _label(history_id, "registry history ID")
        self.registry_id = _label(registry_id, "registry history registry ID", required=False)
        self.version = _text(version, "registry history version", 512)
        self.boundary = _text(boundary, "registry history boundary", 512)
        self.entries = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry.from_mapping(item) for item in _sequence(entries, "registry history entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "registry history entry count", MAX_ENTRIES)
        self.latest_registry_address = _address(latest_registry_address, "registry history latest registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.latest_entry_count = _count(latest_entry_count, "registry history latest entry count", MAX_ENTRIES)
        self.latest_accepted_count = _count(latest_accepted_count, "registry history latest accepted count", MAX_ENTRIES)
        self.latest_release_ready_count = _count(latest_release_ready_count, "registry history latest release-ready count", MAX_ENTRIES)
        self.initial_count = _count(initial_count, "registry history initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "registry history improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "registry history regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "registry history unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "registry history changed count", MAX_ENTRIES)
        self.state = _label(state, "registry history state")
        if self.state not in STATES:
            raise ValidationError("registry history state is unsupported")
        self.decision = _label(decision, "registry history decision")
        if self.decision not in DECISIONS:
            raise ValidationError("registry history decision is unsupported")
        self.accepted = _bool(accepted, "registry history acceptance")
        self.release_ready = _bool(release_ready, "registry history release readiness")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary.from_mapping(summary)
        self.content_address = _address(content_address, "registry history address", HISTORY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("registry history version or boundary is not current")
        if len(self.entries) != self.entry_count or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("registry history entry order is not conserved")
        if len({item.registry_address for item in self.entries}) != len(self.entries):
            raise ValidationError("registry history registry addresses must be unique")
        if self.registry_id != (self.entries[0].registry_id if self.entries else ""):
            raise ValidationError("registry history registry identity does not replay")
        for index, item in enumerate(self.entries):
            if index and item.previous_registry_address != self.entries[index - 1].registry_address:
                raise ValidationError("registry history ancestry does not link to the previous snapshot")
            if item.transition != _transition(item, self.entries[index - 1] if index else None):
                raise ValidationError("registry history transition does not replay")
        if self.entry_count:
            latest = self.entries[-1]
            expected_latest = (latest.registry_address, latest.entry_count, latest.accepted_count, latest.release_ready_count)
        else:
            expected_latest = ("", 0, 0, 0)
        if (self.latest_registry_address, self.latest_entry_count, self.latest_accepted_count, self.latest_release_ready_count) != expected_latest:
            raise ValidationError("registry history latest snapshot does not replay")
        transitions = tuple(sum(item.transition == transition for item in self.entries) for transition in TRANSITIONS)
        if transitions != (self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count):
            raise ValidationError("registry history transition counts do not replay")
        latest = self.entries[-1] if self.entries else None
        expected_state = latest.state if latest else "empty"
        expected_decision = latest.decision if latest else "hold"
        expected_acceptance = latest.accepted if latest else False
        expected_readiness = latest.release_ready if latest else False
        if (self.state, self.decision, self.accepted, self.release_ready) != (expected_state, expected_decision, expected_acceptance, expected_readiness):
            raise ValidationError("registry history disposition does not replay")
        if (self.manifest.history_id, self.manifest.registry_id, self.manifest.files, tuple(self.manifest.artifact_addresses)) != (self.history_id, self.registry_id, FILES, (address_entries(self.entries), self.summary.content_address)):
            raise ValidationError("registry history manifest does not replay")
        summary_values = (self.summary.history_id, self.summary.registry_id, self.summary.entry_count, self.summary.latest_registry_address, self.summary.latest_entry_count, self.summary.latest_accepted_count, self.summary.latest_release_ready_count, self.summary.initial_count, self.summary.improved_count, self.summary.regressed_count, self.summary.unchanged_count, self.summary.changed_count, self.summary.state, self.summary.decision, self.summary.accepted, self.summary.release_ready)
        expected_summary = (self.history_id, self.registry_id, self.entry_count, self.latest_registry_address, self.latest_entry_count, self.latest_accepted_count, self.latest_release_ready_count, self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count, self.state, self.decision, self.accepted, self.release_ready)
        if summary_values != expected_summary:
            raise ValidationError("registry history summary does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry history crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_history(self) != self.content_address:
            raise ValidationError("registry history address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "entry_count": self.entry_count, "latest_registry_address": self.latest_registry_address, "latest_entry_count": self.latest_entry_count, "latest_accepted_count": self.latest_accepted_count, "latest_release_ready_count": self.latest_release_ready_count, "initial_count": self.initial_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "state": self.state, "decision": self.decision, "accepted": self.accepted, "release_ready": self.release_ready, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "summary", "entries"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory:
        value = _mapping(value, "registry history")
        _strict(value, set(cls.FIELDS), "registry history")
        return cls(*(value[field] for field in cls.FIELDS))


def address_history(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
        raise ValidationError("registry history address requires a typed history")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def build_history(registries: Sequence[registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry], *, history_id: str = DEFAULT_HISTORY_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory:
    registries = _sequence(registries, "registry history registries", MAX_ENTRIES)
    if any(not isinstance(item, registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry) for item in registries):
        raise ValidationError("registry history requires typed registries")
    typed = tuple(registries)
    registry_ids = {item.registry_id for item in typed}
    if len(registry_ids) > 1:
        raise ValidationError("registry history cannot mix registry identities")
    registry_id = next(iter(registry_ids), "")
    if len({item.content_address for item in typed}) != len(typed):
        raise ValidationError("registry history cannot repeat a registry address")
    entries = []
    previous = None
    for ordinal, value in enumerate(typed, 1):
        provisional = type("RegistrySnapshot", (), {"state": value.state, "release_ready_count": value.release_ready_count, "accepted_count": value.accepted_count, "block_count": value.block_count, "hold_count": value.hold_count, "entry_count": value.entry_count, "promote_count": value.promote_count, "decision": _registry_decision(value), "accepted": value.accepted, "release_ready": value.release_ready})()
        transition = _transition(provisional, previous)
        entries.append(entry_from_registry(value, ordinal, transition, previous.registry_address if previous else ""))
        previous = entries[-1]
    counts = {transition + "_count": sum(item.transition == transition for item in entries) for transition in TRANSITIONS}
    latest = entries[-1] if entries else None
    state = latest.state if latest else "empty"
    decision = latest.decision if latest else "hold"
    accepted = latest.accepted if latest else False
    release_ready = latest.release_ready if latest else False
    summary_body = {"history_id": history_id, "registry_id": registry_id, "entry_count": len(entries), "latest_registry_address": latest.registry_address if latest else "", "latest_entry_count": latest.entry_count if latest else 0, "latest_accepted_count": latest.accepted_count if latest else 0, "latest_release_ready_count": latest.release_ready_count if latest else 0, **counts, "state": state, "decision": decision, "accepted": accepted, "release_ready": release_ready, "content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary(**summary_body)
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    entries_address = address_entries(entries)
    manifest_body = {"history_id": history_id, "registry_id": registry_id, "files": FILES, "artifact_addresses": (entries_address, summary.content_address), "content_address": MANIFEST_PREFIX + ":pending"}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest(**manifest_body)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = {"history_id": history_id, "registry_id": registry_id, "version": VERSION, "boundary": BOUNDARY, "entry_count": len(entries), "latest_registry_address": latest.registry_address if latest else "", "latest_entry_count": latest.entry_count if latest else 0, "latest_accepted_count": latest.accepted_count if latest else 0, "latest_release_ready_count": latest.release_ready_count if latest else 0, **counts, "state": state, "decision": decision, "accepted": accepted, "release_ready": release_ready, "manifest": manifest, "summary": summary, "entries": entries, "content_address": HISTORY_PREFIX + ":pending"}
    provisional_history = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory(**(body | {"content_address": address_history(provisional_history)}))


def history_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory.from_mapping(value)


def history_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory) -> str:
    return canonical_json(history_from_mapping(value.to_dict()).to_dict())


def history_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory) -> str:
    value = history_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ENTRY_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in ENTRY_FIELDS) for item in value.entries)
    return output.getvalue()


def render_history_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory) -> str:
    value = history_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry History", "", f"- History: `{value.history_id}`", f"- Registry: `{value.registry_id}`", f"- Snapshots: `{value.entry_count}`", f"- State: `{value.state}`", f"- Decision: `{value.decision}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| # | registry snapshot | entries | accepted | ready | transition | state |", "| ---: | --- | ---: | ---: | ---: | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.registry_address}` | `{item.entry_count}` | `{item.accepted_count}` | `{item.release_ready_count}` | `{item.transition}` | `{item.state}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def entries_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries.from_mapping(value.to_dict()).to_dict())


def summary_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary.from_mapping(value.to_dict()).to_dict())


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_history(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
        raise ValidationError("registry history persistence requires a typed history")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("registry history destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-policy-package-registry-history-", dir=str(parent)))
    try:
        entries = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries(value.entries, address_entries(value.entries))
        documents = {"manifest.json": value.manifest.to_dict(), "history.json": value.to_dict(), "entries.json": entries.to_dict(), "summary.json": value.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("registry history destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("registry history artifact is not valid JSON") from error
    return _mapping(value, "registry history artifact")


def _read_canonical(path: Path, value: Mapping[str, Any]) -> None:
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValidationError("registry history artifact cannot be read") from error
    if actual != canonical_json(value):
        raise ValidationError("registry history artifact is not canonical")


def load_history(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("registry history destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("registry history directory does not contain the exact file set")
    raw = {name: _read_json(destination / name) for name in FILES}
    for name, value in raw.items():
        _read_canonical(destination / name, value)
    history = history_from_mapping(raw["history.json"])
    entries = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries.from_mapping(raw["entries.json"])
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest.from_mapping(raw["manifest.json"])
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary.from_mapping(raw["summary.json"])
    if entries.to_dict() != {"entries": [item.to_dict() for item in history.entries], "content_address": address_entries(history.entries)} or manifest.to_dict() != history.manifest.to_dict() or summary.to_dict() != history.summary.to_dict():
        raise ValidationError("registry history artifacts do not replay")
    return history


def run_history(registries: Sequence[registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry], *, history_id: str = DEFAULT_HISTORY_ID, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory:
    value = build_history(registries, history_id=history_id)
    if destination is not None:
        persist_history(value, destination, overwrite=overwrite)
    return value


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "registry_id": {"type": "string"}, "registry_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "release_ready_count": {"type": "integer", "minimum": 0}, "promote_count": {"type": "integer", "minimum": 0}, "hold_count": {"type": "integer", "minimum": 0}, "block_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "transition": {"enum": list(TRANSITIONS)}, "previous_registry_address": {"type": "string"}, "content_address": {"type": "string"}}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history entries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "latest_registry_address": {"type": "string"}, "latest_entry_count": {"type": "integer", "minimum": 0}, "latest_accepted_count": {"type": "integer", "minimum": 0}, "latest_release_ready_count": {"type": "integer", "minimum": 0}, "initial_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "content_address": {"type": "string"}}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry history", "type": "object", "additionalProperties": False, "required": list(HISTORY_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "entry_count": {"type": "integer", "minimum": 0}, "latest_registry_address": {"type": "string"}, "latest_entry_count": {"type": "integer", "minimum": 0}, "latest_accepted_count": {"type": "integer", "minimum": 0}, "latest_release_ready_count": {"type": "integer", "minimum": 0}, "initial_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "manifest": {"type": "object"}, "summary": {"type": "object"}, "entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": list(FILES), "transitions": list(TRANSITIONS), "states": list(STATES), "decisions": list(DECISIONS), "limits": {"max_entries": MAX_ENTRIES}, "features": ["append-only registry snapshots", "deterministic transition folding", "ancestry-linked receipts", "exact four-file persistence", "canonical reload verification", "atomic writes", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "DECISIONS", "DEFAULT_HISTORY_ID", "ENTRIES_FIELDS", "ENTRIES_PREFIX", "ENTRY_FIELDS", "ENTRY_PREFIX", "FILES", "HISTORY_FIELDS", "HISTORY_PREFIX", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ENTRIES", "STATES", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "TRANSITIONS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary", "address_entries", "address_entry", "address_history", "address_manifest", "address_summary", "build_history", "capabilities", "entries_json", "entries_schema", "entry_from_registry", "entry_schema", "history_csv", "history_from_mapping", "history_json", "history_schema", "load_history", "manifest_schema", "persist_history", "render_history_markdown", "run_history", "summary_json", "summary_schema"]
