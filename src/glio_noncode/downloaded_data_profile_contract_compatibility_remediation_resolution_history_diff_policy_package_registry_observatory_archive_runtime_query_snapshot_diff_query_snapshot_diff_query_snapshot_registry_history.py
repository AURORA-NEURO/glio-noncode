"""Longitudinal, value-free history for comparison-query snapshot registries.

The history boundary records registry revisions and their public receipts. It
does not reopen source archives or retain source values. Every transition is
derived from bounded registry summaries, and the latest disposition is always
replayed from the final history entry.
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
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

RegistryType = registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry

VERSION = registry_model.VERSION + "-history-v1"
BOUNDARY = registry_model.BOUNDARY + "_history"
HISTORY_PREFIX = registry_model.REGISTRY_PREFIX + "-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
ENTRIES_PREFIX = HISTORY_PREFIX + "-entries"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
SUMMARY_PREFIX = HISTORY_PREFIX + "-summary"
DEFAULT_HISTORY_ID = HISTORY_PREFIX
FILES = ("manifest.json", "history.json", "entries.json", "summary.json")
MANIFEST_ARTIFACT_FILES = ("entries.json", "summary.json")
TRANSITIONS = ("initial", "improved", "regressed", "unchanged", "changed")
STATES = registry_model.STATES
MAX_ENTRIES = registry_model.MAX_ENTRIES
MAX_TOTAL_ROWS = registry_model.MAX_TOTAL_ROWS
MAX_HISTORY_BYTES = 128 * 1024 * 1024
ENTRY_FIELDS = (
    "ordinal",
    "registry_id",
    "registry_address",
    "entry_count",
    "ready_count",
    "blocked_count",
    "accepted_count",
    "rejected_count",
    "total_query_rows",
    "matched_query_rows",
    "returned_query_rows",
    "distinct_diff_count",
    "distinct_query_count",
    "state",
    "accepted",
    "transition",
    "previous_registry_address",
    "content_address",
)
ENTRIES_FIELDS = ("entries", "content_address")
MANIFEST_FIELDS = ("history_id", "registry_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = (
    "history_id",
    "registry_id",
    "entry_count",
    "latest_registry_address",
    "latest_entry_count",
    "latest_ready_count",
    "latest_blocked_count",
    "latest_accepted_count",
    "latest_rejected_count",
    "latest_total_query_rows",
    "latest_matched_query_rows",
    "latest_returned_query_rows",
    "initial_count",
    "improved_count",
    "regressed_count",
    "unchanged_count",
    "changed_count",
    "state",
    "accepted",
    "content_address",
)
HISTORY_FIELDS = (
    "history_id",
    "registry_id",
    "version",
    "boundary",
    "entry_count",
    "latest_registry_address",
    "latest_entry_count",
    "latest_ready_count",
    "latest_blocked_count",
    "latest_accepted_count",
    "latest_rejected_count",
    "latest_total_query_rows",
    "latest_matched_query_rows",
    "latest_returned_query_rows",
    "initial_count",
    "improved_count",
    "regressed_count",
    "unchanged_count",
    "changed_count",
    "state",
    "accepted",
    "manifest",
    "summary",
    "entries",
    "content_address",
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


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _registry_summary(value: RegistryType) -> dict[str, Any]:
    if not isinstance(value, RegistryType):
        raise ValidationError("registry history requires typed registries")
    return {
        "registry_id": value.registry_id,
        "registry_address": value.content_address,
        "entry_count": value.entry_count,
        "ready_count": value.ready_count,
        "blocked_count": value.blocked_count,
        "accepted_count": value.accepted_count,
        "rejected_count": value.rejected_count,
        "total_query_rows": value.total_query_rows,
        "matched_query_rows": value.matched_query_rows,
        "returned_query_rows": value.returned_query_rows,
        "distinct_diff_count": value.distinct_diff_count,
        "distinct_query_count": value.distinct_query_count,
        "state": value.state,
        "accepted": value.accepted,
    }


def _quality(value: Mapping[str, Any]) -> tuple[int, int, int, int, int, int, int, int]:
    return (
        int(value["accepted"]),
        int(value["state"] == "ready"),
        int(value["ready_count"]),
        -int(value["blocked_count"]),
        -int(value["rejected_count"]),
        int(value["returned_query_rows"]),
        int(value["matched_query_rows"]),
        -int(value["entry_count"]),
    )


def _transition(current: Mapping[str, Any], previous: Mapping[str, Any] | None) -> str:
    if previous is None:
        return "initial"
    comparable = tuple(current[key] for key in ("entry_count", "ready_count", "blocked_count", "accepted_count", "rejected_count", "total_query_rows", "matched_query_rows", "returned_query_rows", "distinct_diff_count", "distinct_query_count", "state", "accepted"))
    prior = tuple(previous[key] for key in ("entry_count", "ready_count", "blocked_count", "accepted_count", "rejected_count", "total_query_rows", "matched_query_rows", "returned_query_rows", "distinct_diff_count", "distinct_query_count", "state", "accepted"))
    if comparable == prior:
        return "unchanged"
    if _quality(current) > _quality(previous):
        return "improved"
    if _quality(current) < _quality(previous):
        return "regressed"
    return "changed"


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry:
    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, registry_id: str, registry_address: str, entry_count: int, ready_count: int, blocked_count: int, accepted_count: int, rejected_count: int, total_query_rows: int, matched_query_rows: int, returned_query_rows: int, distinct_diff_count: int, distinct_query_count: int, state: str, accepted: bool, transition: str, previous_registry_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history entry ordinal", MAX_ENTRIES, positive=True)
        self.registry_id = _label(registry_id, "history entry registry ID")
        self.registry_address = _address(registry_address, "history entry registry address", registry_model.REGISTRY_PREFIX)
        self.entry_count = _count(entry_count, "history entry entry count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "history entry ready count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "history entry blocked count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "history entry accepted count", MAX_ENTRIES)
        self.rejected_count = _count(rejected_count, "history entry rejected count", MAX_ENTRIES)
        self.total_query_rows = _count(total_query_rows, "history entry total query rows", MAX_TOTAL_ROWS)
        self.matched_query_rows = _count(matched_query_rows, "history entry matched query rows", MAX_TOTAL_ROWS)
        self.returned_query_rows = _count(returned_query_rows, "history entry returned query rows", MAX_TOTAL_ROWS)
        self.distinct_diff_count = _count(distinct_diff_count, "history entry distinct diff count", MAX_ENTRIES)
        self.distinct_query_count = _count(distinct_query_count, "history entry distinct query count", MAX_ENTRIES)
        self.state = _label(state, "history entry state")
        if self.state not in STATES:
            raise ValidationError("history entry state is unsupported")
        self.accepted = _bool(accepted, "history entry acceptance")
        self.transition = _label(transition, "history entry transition")
        if self.transition not in TRANSITIONS:
            raise ValidationError("history entry transition is unsupported")
        self.previous_registry_address = _address(previous_registry_address, "history entry previous registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.content_address = _address(content_address, "history entry content address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.ready_count + self.blocked_count != self.entry_count or self.accepted_count + self.rejected_count != self.entry_count:
            raise ValidationError("history entry counts are not conserved")
        if self.matched_query_rows > self.total_query_rows or self.returned_query_rows > self.matched_query_rows:
            raise ValidationError("history entry query counts are not conserved")
        if self.state == "ready" and not self.accepted:
            raise ValidationError("ready history entry must be accepted")
        if self.transition == "initial" and self.previous_registry_address:
            raise ValidationError("initial history entry cannot have a predecessor")
        if self.transition != "initial" and not self.previous_registry_address:
            raise ValidationError("non-initial history entry requires a predecessor")
        if not _public(self.to_dict()):
            raise ValidationError("history entry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("history entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history entry")
        _strict(value, set(cls.FIELDS), "history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry):
        raise ValidationError("history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries:
    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry.from_mapping(item) for item in _sequence(entries, "history entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "history entries address", ENTRIES_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("history entries must be ordinal and contiguous")
        if len({item.registry_address for item in self.entries}) != len(self.entries):
            raise ValidationError("history registry addresses must be unique")
        if not _public(self.to_dict()):
            raise ValidationError("history entries cross the public boundary")
        if not self.content_address.endswith(":pending") and address_entries(self.entries) != self.content_address:
            raise ValidationError("history entries address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history entries")
        _strict(value, set(cls.FIELDS), "history entries")
        return cls(value["entries"], value["content_address"])


def address_entries(value: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry]) -> str:
    return content_hash({"entries": [item.to_dict() for item in value]}, prefix=ENTRIES_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, history_id: str, registry_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.history_id = _label(history_id, "history manifest ID")
        self.registry_id = _label(registry_id, "history manifest registry ID", required=False)
        self.version = _text(version, "history manifest version", 4096)
        self.boundary = _text(boundary, "history manifest boundary", 4096)
        self.files = tuple(_label(item, "history manifest file") for item in _sequence(files, "history manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "history manifest artifact address") for item in _sequence(artifact_addresses, "history manifest artifacts", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "history manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES):
            raise ValidationError("history manifest does not name the exact package")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history manifest version or boundary is unsupported")
        if not _public(self.to_dict()):
            raise ValidationError("history manifest crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("history manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history manifest")
        _strict(value, set(cls.FIELDS), "history manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest):
        raise ValidationError("history manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, history_id: str, registry_id: str, entry_count: int, latest_registry_address: str, latest_entry_count: int, latest_ready_count: int, latest_blocked_count: int, latest_accepted_count: int, latest_rejected_count: int, latest_total_query_rows: int, latest_matched_query_rows: int, latest_returned_query_rows: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.history_id = _label(history_id, "history summary ID")
        self.registry_id = _label(registry_id, "history summary registry ID", required=False)
        self.entry_count = _count(entry_count, "history summary entry count", MAX_ENTRIES)
        self.latest_registry_address = _address(latest_registry_address, "history summary latest registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.latest_entry_count = _count(latest_entry_count, "history summary latest entry count", MAX_ENTRIES)
        self.latest_ready_count = _count(latest_ready_count, "history summary latest ready count", MAX_ENTRIES)
        self.latest_blocked_count = _count(latest_blocked_count, "history summary latest blocked count", MAX_ENTRIES)
        self.latest_accepted_count = _count(latest_accepted_count, "history summary latest accepted count", MAX_ENTRIES)
        self.latest_rejected_count = _count(latest_rejected_count, "history summary latest rejected count", MAX_ENTRIES)
        self.latest_total_query_rows = _count(latest_total_query_rows, "history summary latest total query rows", MAX_TOTAL_ROWS)
        self.latest_matched_query_rows = _count(latest_matched_query_rows, "history summary latest matched query rows", MAX_TOTAL_ROWS)
        self.latest_returned_query_rows = _count(latest_returned_query_rows, "history summary latest returned query rows", MAX_TOTAL_ROWS)
        self.initial_count = _count(initial_count, "history summary initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "history summary improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "history summary regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "history summary unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "history summary changed count", MAX_ENTRIES)
        self.state = _label(state, "history summary state")
        if self.state not in STATES:
            raise ValidationError("history summary state is unsupported")
        self.accepted = _bool(accepted, "history summary acceptance")
        self.content_address = _address(content_address, "history summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.initial_count + self.improved_count + self.regressed_count + self.unchanged_count + self.changed_count != self.entry_count:
            raise ValidationError("history summary transition counts are not conserved")
        if self.latest_ready_count + self.latest_blocked_count != self.latest_entry_count or self.latest_accepted_count + self.latest_rejected_count != self.latest_entry_count:
            raise ValidationError("history summary latest counts are not conserved")
        if self.latest_matched_query_rows > self.latest_total_query_rows or self.latest_returned_query_rows > self.latest_matched_query_rows:
            raise ValidationError("history summary latest query counts are not conserved")
        if bool(self.entry_count) != bool(self.latest_registry_address):
            raise ValidationError("history summary latest linkage is invalid")
        if not _public(self.to_dict()):
            raise ValidationError("history summary crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("history summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history summary")
        _strict(value, set(cls.FIELDS), "history summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary):
        raise ValidationError("history summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory:
    FIELDS = HISTORY_FIELDS

    def __init__(self, history_id: str, registry_id: str, version: str, boundary: str, entry_count: int, latest_registry_address: str, latest_entry_count: int, latest_ready_count: int, latest_blocked_count: int, latest_accepted_count: int, latest_rejected_count: int, latest_total_query_rows: int, latest_matched_query_rows: int, latest_returned_query_rows: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, state: str, accepted: bool, manifest: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest | Mapping[str, Any], summary: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary | Mapping[str, Any], entries: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries | Mapping[str, Any], content_address: str) -> None:
        self.history_id = _label(history_id, "history ID")
        self.registry_id = _label(registry_id, "history registry ID", required=False)
        self.version = _text(version, "history version", 4096)
        self.boundary = _text(boundary, "history boundary", 4096)
        self.entry_count = _count(entry_count, "history entry count", MAX_ENTRIES)
        self.latest_registry_address = _address(latest_registry_address, "history latest registry address", registry_model.REGISTRY_PREFIX, required=False)
        self.latest_entry_count = _count(latest_entry_count, "history latest entry count", MAX_ENTRIES)
        self.latest_ready_count = _count(latest_ready_count, "history latest ready count", MAX_ENTRIES)
        self.latest_blocked_count = _count(latest_blocked_count, "history latest blocked count", MAX_ENTRIES)
        self.latest_accepted_count = _count(latest_accepted_count, "history latest accepted count", MAX_ENTRIES)
        self.latest_rejected_count = _count(latest_rejected_count, "history latest rejected count", MAX_ENTRIES)
        self.latest_total_query_rows = _count(latest_total_query_rows, "history latest total query rows", MAX_TOTAL_ROWS)
        self.latest_matched_query_rows = _count(latest_matched_query_rows, "history latest matched query rows", MAX_TOTAL_ROWS)
        self.latest_returned_query_rows = _count(latest_returned_query_rows, "history latest returned query rows", MAX_TOTAL_ROWS)
        self.initial_count = _count(initial_count, "history initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "history improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "history regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "history unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "history changed count", MAX_ENTRIES)
        self.state = _label(state, "history state")
        if self.state not in STATES:
            raise ValidationError("history state is unsupported")
        self.accepted = _bool(accepted, "history acceptance")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary.from_mapping(summary)
        self.entries = entries if isinstance(entries, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries.from_mapping(entries)
        self.content_address = _address(content_address, "history address", HISTORY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history version or boundary is unsupported")
        if self.entry_count != len(self.entries.entries) or self.entry_count != self.summary.entry_count:
            raise ValidationError("history entry count does not replay")
        if self.registry_id != (self.entries.entries[0].registry_id if self.entries.entries else ""):
            raise ValidationError("history registry identity does not replay")
        for index, entry in enumerate(self.entries.entries):
            if index == 0:
                if entry.transition != "initial" or entry.previous_registry_address:
                    raise ValidationError("history first transition does not replay")
            elif entry.previous_registry_address != self.entries.entries[index - 1].registry_address:
                raise ValidationError("history predecessor linkage does not replay")
            expected = _transition(entry.to_dict(), self.entries.entries[index - 1].to_dict() if index else None)
            if entry.transition != expected:
                raise ValidationError("history transition does not replay")
        transitions = tuple(sum(entry.transition == transition for entry in self.entries.entries) for transition in TRANSITIONS)
        if transitions != (self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count):
            raise ValidationError("history transition counts do not replay")
        latest = self.entries.entries[-1] if self.entries.entries else None
        expected_latest = (latest.registry_address, latest.entry_count, latest.ready_count, latest.blocked_count, latest.accepted_count, latest.rejected_count, latest.total_query_rows, latest.matched_query_rows, latest.returned_query_rows) if latest else ("", 0, 0, 0, 0, 0, 0, 0, 0)
        actual_latest = (self.latest_registry_address, self.latest_entry_count, self.latest_ready_count, self.latest_blocked_count, self.latest_accepted_count, self.latest_rejected_count, self.latest_total_query_rows, self.latest_matched_query_rows, self.latest_returned_query_rows)
        if actual_latest != expected_latest:
            raise ValidationError("history latest registry projection does not replay")
        expected_disposition = (latest.state, latest.accepted) if latest else ("empty", False)
        if (self.state, self.accepted) != expected_disposition:
            raise ValidationError("history disposition does not replay")
        summary_values = tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS if field not in {"content_address"})
        expected_summary = tuple(getattr(self, field) for field in SUMMARY_FIELDS if field not in {"content_address"})
        if summary_values != expected_summary:
            raise ValidationError("history summary does not replay")
        if (self.manifest.history_id, self.manifest.registry_id, self.manifest.version, self.manifest.boundary, self.manifest.files, tuple(self.manifest.artifact_addresses)) != (self.history_id, self.registry_id, self.version, self.boundary, FILES, (self.entries.content_address, self.summary.content_address)):
            raise ValidationError("history manifest does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_history(self) != self.content_address:
            raise ValidationError("history address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id,
            "registry_id": self.registry_id,
            "version": self.version,
            "boundary": self.boundary,
            "entry_count": self.entry_count,
            "latest_registry_address": self.latest_registry_address,
            "latest_entry_count": self.latest_entry_count,
            "latest_ready_count": self.latest_ready_count,
            "latest_blocked_count": self.latest_blocked_count,
            "latest_accepted_count": self.latest_accepted_count,
            "latest_rejected_count": self.latest_rejected_count,
            "latest_total_query_rows": self.latest_total_query_rows,
            "latest_matched_query_rows": self.latest_matched_query_rows,
            "latest_returned_query_rows": self.latest_returned_query_rows,
            "initial_count": self.initial_count,
            "improved_count": self.improved_count,
            "regressed_count": self.regressed_count,
            "unchanged_count": self.unchanged_count,
            "changed_count": self.changed_count,
            "state": self.state,
            "accepted": self.accepted,
            "manifest": self.manifest.to_dict(),
            "summary": self.summary.to_dict(),
            "entries": self.entries.to_dict(),
            "content_address": self.content_address,
        }

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in HISTORY_FIELDS if field not in {"manifest", "summary", "entries"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history")
        _strict(value, set(cls.FIELDS), "history")
        return cls(*(value[field] for field in cls.FIELDS))


def address_history(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
        raise ValidationError("history address requires a typed history")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def _entry(value: RegistryType, ordinal: int, previous: Mapping[str, Any] | None):
    summary = _registry_summary(value)
    body = {
        "ordinal": ordinal,
        "registry_id": summary["registry_id"],
        "registry_address": summary["registry_address"],
        "entry_count": summary["entry_count"],
        "ready_count": summary["ready_count"],
        "blocked_count": summary["blocked_count"],
        "accepted_count": summary["accepted_count"],
        "rejected_count": summary["rejected_count"],
        "total_query_rows": summary["total_query_rows"],
        "matched_query_rows": summary["matched_query_rows"],
        "returned_query_rows": summary["returned_query_rows"],
        "distinct_diff_count": summary["distinct_diff_count"],
        "distinct_query_count": summary["distinct_query_count"],
        "state": summary["state"],
        "accepted": summary["accepted"],
        "transition": _transition(summary, previous),
        "previous_registry_address": previous["registry_address"] if previous else "",
        "content_address": ENTRY_PREFIX + ":pending",
    }
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntry(**(body | {"content_address": address_entry(provisional)}))


def build_history(registries: Sequence[RegistryType], *, history_id: str = DEFAULT_HISTORY_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory:
    history_id = _label(history_id, "history ID")
    values = _sequence(registries, "history registries", MAX_ENTRIES)
    if any(not isinstance(value, RegistryType) for value in values):
        raise ValidationError("history requires typed registries")
    typed = tuple(values)
    identities = {value.registry_id for value in typed}
    if len(identities) > 1:
        raise ValidationError("history cannot mix registry identities")
    registry_id = next(iter(identities), "")
    addresses = {value.content_address for value in typed}
    if len(addresses) != len(typed):
        raise ValidationError("history cannot repeat registry addresses")
    entries_list = []
    previous = None
    for ordinal, value in enumerate(typed, 1):
        entry = _entry(value, ordinal, previous)
        entries_list.append(entry)
        previous = entry.to_dict()
    entries = tuple(entries_list)
    entries_address = address_entries(entries)
    entries_value = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries(entries, entries_address)
    latest = entries[-1] if entries else None
    transitions = {transition + "_count": sum(entry.transition == transition for entry in entries) for transition in TRANSITIONS}
    latest_values = {
        "latest_registry_address": latest.registry_address if latest else "",
        "latest_entry_count": latest.entry_count if latest else 0,
        "latest_ready_count": latest.ready_count if latest else 0,
        "latest_blocked_count": latest.blocked_count if latest else 0,
        "latest_accepted_count": latest.accepted_count if latest else 0,
        "latest_rejected_count": latest.rejected_count if latest else 0,
        "latest_total_query_rows": latest.total_query_rows if latest else 0,
        "latest_matched_query_rows": latest.matched_query_rows if latest else 0,
        "latest_returned_query_rows": latest.returned_query_rows if latest else 0,
    }
    state = latest.state if latest else "empty"
    accepted = latest.accepted if latest else False
    summary_body = {"history_id": history_id, "registry_id": registry_id, "entry_count": len(entries), **latest_values, **transitions, "state": state, "accepted": accepted, "content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary(**summary_body)
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistorySummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    manifest_body = {"history_id": history_id, "registry_id": registry_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifact_addresses": (entries_value.content_address, summary.content_address), "content_address": MANIFEST_PREFIX + ":pending"}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest(**manifest_body)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = {"history_id": history_id, "registry_id": registry_id, "version": VERSION, "boundary": BOUNDARY, "entry_count": len(entries), **latest_values, **transitions, "state": state, "accepted": accepted, "manifest": manifest, "summary": summary, "entries": entries_value, "content_address": HISTORY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory(**(body | {"content_address": address_history(provisional)}))


def history_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory.from_mapping(value)


def verify_history(value):
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
        raise ValidationError("history verification requires a typed history")
    value._validate()
    if not value.content_address.endswith(":pending") and address_history(value) != value.content_address:
        raise ValidationError("history address verification failed")
    return value


def history_json(value) -> str:
    return canonical_json(history_from_mapping(verify_history(value).to_dict()).to_dict())


def entries_json(value) -> str:
    typed = verify_history(value).entries
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries(typed.entries, address_entries(typed.entries)).to_dict())


def summary_json(value) -> str:
    return canonical_json(verify_history(value).summary.to_dict())


def manifest_json(value) -> str:
    return canonical_json(verify_history(value).manifest.to_dict())


def history_csv(value) -> str:
    typed = verify_history(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ENTRY_FIELDS)
    for entry in typed.entries.entries:
        body = entry.to_dict()
        writer.writerow(json.dumps(body[field], ensure_ascii=False, sort_keys=True) if isinstance(body[field], (tuple, list, dict)) else body[field] for field in ENTRY_FIELDS)
    return output.getvalue()


def render_history_markdown(value) -> str:
    typed = verify_history(value)
    lines = ["# Downloaded Data Comparison-Query Snapshot Registry History", "", f"- History: `{typed.history_id}`", f"- Registry: `{typed.registry_id}`", f"- State: `{typed.state}`", f"- Accepted: `{typed.accepted}`", f"- Entries: `{typed.entry_count}`", f"- Initial: `{typed.initial_count}`", f"- Improved: `{typed.improved_count}`", f"- Regressed: `{typed.regressed_count}`", f"- Unchanged: `{typed.unchanged_count}`", f"- Changed: `{typed.changed_count}`", f"- Address: `{typed.content_address}`", "", "| # | registry address | state | accepted | transition |", "| ---: | --- | --- | ---: | --- |"]
    lines.extend(f"| {entry.ordinal} | `{entry.registry_address}` | `{entry.state}` | `{entry.accepted}` | `{entry.transition}` |" for entry in typed.entries.entries)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_history(value, destination: str | Path, *, overwrite: bool = False) -> Path:
    typed = verify_history(value)
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("history destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".comparison-query-snapshot-registry-history-", dir=str(parent)))
    try:
        entries = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryEntries(typed.entries.entries, address_entries(typed.entries.entries))
        documents = {"manifest.json": typed.manifest.to_dict(), "history.json": typed.to_dict(), "entries.json": entries.to_dict(), "summary.json": typed.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("history destination could not be written") from error
    return destination


def _read_json(path: Path) -> tuple[Mapping[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
        value = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("history artifact is not valid JSON") from error
    mapping = _mapping(value, "history artifact")
    if canonical_json(mapping) != text:
        raise ValidationError("history artifact is not canonical JSON")
    return mapping, text


def load_history(destination: str | Path):
    destination = Path(destination)
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("history destination must be a regular directory")
    names = tuple(sorted(item.name for item in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("history directory must contain the exact package files")
    paths = {name: destination / name for name in FILES}
    if any(not path.is_file() or path.is_symlink() for path in paths.values()):
        raise ValidationError("history package files must be regular files")
    if sum(path.stat().st_size for path in paths.values()) > MAX_HISTORY_BYTES:
        raise ValidationError("history package exceeds its byte bound")
    documents = {name: _read_json(path)[0] for name, path in paths.items()}
    value = history_from_mapping(documents["history.json"])
    if any(canonical_json(documents[name]) != canonical_json(expected) for name, expected in (("manifest.json", value.manifest.to_dict()), ("summary.json", value.summary.to_dict()), ("entries.json", value.entries.to_dict()))):
        raise ValidationError("history external documents do not replay the nested contract")
    verify_history(value)
    return value


def run_history(value: Sequence[RegistryType], *, history_id: str = DEFAULT_HISTORY_ID, destination: str | Path | None = None, overwrite: bool = False):
    typed = build_history(value, history_id=history_id)
    if destination is not None:
        persist_history(typed, destination, overwrite=overwrite)
    return typed


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": "string"} for field in ENTRY_FIELDS if field not in {"ordinal", "entry_count", "ready_count", "blocked_count", "accepted_count", "rejected_count", "total_query_rows", "matched_query_rows", "returned_query_rows", "distinct_diff_count", "distinct_query_count", "accepted"}} | {field: {"type": "integer", "minimum": 0} for field in {"ordinal", "entry_count", "ready_count", "blocked_count", "accepted_count", "rejected_count", "total_query_rows", "matched_query_rows", "returned_query_rows", "distinct_diff_count", "distinct_query_count"}} | {"accepted": {"type": "boolean"}}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history entries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "maxItems": MAX_ENTRIES, "items": entry_schema()}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES), "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    string_fields = ("history_id", "registry_id", "latest_registry_address", "state", "content_address")
    count_fields = tuple(field for field in SUMMARY_FIELDS if field not in string_fields + ("accepted",))
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "string"} for field in string_fields} | {field: {"type": "integer", "minimum": 0} for field in count_fields} | {"accepted": {"type": "boolean"}}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history", "type": "object", "additionalProperties": False, "required": list(HISTORY_FIELDS), "properties": {"history_id": {"type": "string"}, "registry_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "entry_count": {"type": "integer", "minimum": 0}, "latest_registry_address": {"type": "string"}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "manifest": manifest_schema(), "summary": summary_schema(), "entries": entries_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "files": list(FILES), "transitions": list(TRANSITIONS), "states": list(STATES), "max_entries": MAX_ENTRIES, "max_total_rows": MAX_TOTAL_ROWS, "max_history_bytes": MAX_HISTORY_BYTES, "value_free": True, "operations": ["build", "verify", "persist", "load", "json", "csv", "markdown", "schema"]}
