"""Deterministic registry for persisted comparison-query snapshot handoffs.

The registry is deliberately value-free. It admits already verified query
snapshots, retains their public identities and receipts, and folds their state
without reopening the source archive or copying source record values.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot as snapshot_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = snapshot_model.VERSION + "-registry-v1"
BOUNDARY = snapshot_model.BOUNDARY + "_registry"
REGISTRY_PREFIX = snapshot_model.SNAPSHOT_PREFIX + "-registry"
ENTRY_PREFIX = REGISTRY_PREFIX + "-entry"
ENTRIES_PREFIX = REGISTRY_PREFIX + "-entries"
ARTIFACT_PREFIX = REGISTRY_PREFIX + "-artifact"
MANIFEST_PREFIX = REGISTRY_PREFIX + "-manifest"
SUMMARY_PREFIX = REGISTRY_PREFIX + "-summary"
DEFAULT_REGISTRY_ID = REGISTRY_PREFIX
FILES = ("manifest.json", "registry.json", "entries.json", "summary.json")
MANIFEST_ARTIFACT_FILES = ("entries.json", "summary.json")
STATES = ("empty", "ready", "blocked", "mixed")
MAX_ENTRIES = 128
MAX_TOTAL_ROWS = 1_000_000
MAX_REGISTRY_BYTES = 128 * 1024 * 1024
ENTRY_FIELDS = (
    "ordinal",
    "snapshot_id",
    "snapshot_address",
    "diff_id",
    "diff_address",
    "query_address",
    "query_audit_address",
    "resources",
    "change_filter",
    "source_resource_filter",
    "key_filter",
    "identity_filter",
    "field_filter",
    "direction_filter",
    "state_transition_filter",
    "address_filter",
    "text_filter",
    "offset",
    "limit",
    "query_total_count",
    "query_matched_count",
    "query_returned_count",
    "state",
    "accepted",
    "content_address",
)
ENTRIES_FIELDS = ("entries", "content_address")
ARTIFACT_FIELDS = ("name", "size", "digest", "content_address")
MANIFEST_FIELDS = ("registry_id", "version", "boundary", "files", "artifacts", "content_address")
SUMMARY_FIELDS = (
    "registry_id",
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
    "latest_snapshot_id",
    "latest_snapshot_address",
    "state",
    "accepted",
    "content_address",
)
REGISTRY_FIELDS = (
    "registry_id",
    "version",
    "boundary",
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
    "latest_snapshot_id",
    "latest_snapshot_address",
    "state",
    "accepted",
    "entries",
    "manifest",
    "summary",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (required and not value)
        or any(ord(char) < 32 and char not in "\n\t" for char in value)
    ):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (
        value.strip() != value
        or any(char.isspace() for char in value)
        or "/" in value
        or "\\" in value
        or '"' in value
    ):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and (
        "/" in value
        or "\\" in value
        or '"' in value
        or ":" not in value
        or (prefix is not None and not value.startswith(prefix + ":"))
    ):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _filter(value: Any, field: str, maximum: int = 1024) -> str:
    return _text(value, field, maximum, required=False)


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
        return all(
            isinstance(key, str)
            and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS
            and _public(child)
            for key, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_public(child) for child in value)
    return True


def _verify_snapshot(value: Any):
    if not isinstance(
        value,
        snapshot_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot,
    ):
        raise ValidationError("snapshot registry requires typed comparison-query snapshots")
    snapshot_model.verify_snapshot(value)
    return value


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntry:
    FIELDS = ENTRY_FIELDS

    def __init__(
        self,
        ordinal: int,
        snapshot_id: str,
        snapshot_address: str,
        diff_id: str,
        diff_address: str,
        query_address: str,
        query_audit_address: str,
        resources: Sequence[str],
        change_filter: str,
        source_resource_filter: str,
        key_filter: str,
        identity_filter: str,
        field_filter: str,
        direction_filter: str,
        state_transition_filter: str,
        address_filter: str,
        text_filter: str,
        offset: int,
        limit: int,
        query_total_count: int,
        query_matched_count: int,
        query_returned_count: int,
        state: str,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.ordinal = _count(ordinal, "registry entry ordinal", MAX_ENTRIES, positive=True)
        self.snapshot_id = _label(snapshot_id, "registry entry snapshot ID")
        self.snapshot_address = _address(snapshot_address, "registry entry snapshot address", snapshot_model.SNAPSHOT_PREFIX)
        self.diff_id = _label(diff_id, "registry entry diff ID")
        self.diff_address = _address(diff_address, "registry entry diff address")
        self.query_address = _address(query_address, "registry entry query address")
        self.query_audit_address = _address(query_audit_address, "registry entry query audit address")
        self.resources = tuple(_label(item, "registry entry resource") for item in _sequence(resources, "registry entry resources", 64))
        if not self.resources:
            raise ValidationError("registry entry resources must not be empty")
        self.change_filter = _filter(change_filter, "registry entry change filter")
        self.source_resource_filter = _filter(source_resource_filter, "registry entry source resource filter")
        self.key_filter = _filter(key_filter, "registry entry key filter")
        self.identity_filter = _filter(identity_filter, "registry entry identity filter")
        self.field_filter = _filter(field_filter, "registry entry field filter")
        self.direction_filter = _filter(direction_filter, "registry entry direction filter")
        self.state_transition_filter = _filter(state_transition_filter, "registry entry state transition filter")
        self.address_filter = _filter(address_filter, "registry entry address filter")
        self.text_filter = _filter(text_filter, "registry entry text filter")
        self.offset = _count(offset, "registry entry offset", MAX_TOTAL_ROWS)
        self.limit = _count(limit, "registry entry limit", MAX_TOTAL_ROWS, positive=True)
        self.query_total_count = _count(query_total_count, "registry entry total query count", MAX_TOTAL_ROWS)
        self.query_matched_count = _count(query_matched_count, "registry entry matched query count", MAX_TOTAL_ROWS)
        self.query_returned_count = _count(query_returned_count, "registry entry returned query count", MAX_TOTAL_ROWS)
        self.state = _label(state, "registry entry state")
        if self.state not in snapshot_model.STATES:
            raise ValidationError("registry entry state is unsupported")
        self.accepted = _bool(accepted, "registry entry acceptance")
        self.content_address = _address(content_address, "registry entry content address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.query_matched_count > self.query_total_count:
            raise ValidationError("registry entry query counts are not conserved")
        if self.query_returned_count > self.query_matched_count or self.query_returned_count > self.limit:
            raise ValidationError("registry entry returned count is outside the query bound")
        if self.state == "ready" and not self.accepted:
            raise ValidationError("ready registry entry must be accepted")
        if not _public(self.to_dict()):
            raise ValidationError("registry entry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("registry entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry entry")
        _strict(value, set(cls.FIELDS), "registry entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(
    value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntry,
) -> str:
    if not isinstance(
        value,
        DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntry,
    ):
        raise ValidationError("registry entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntries:
    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[Any], content_address: str) -> None:
        self.entries = tuple(
            item
            if isinstance(
                item,
                DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntry,
            )
            else self._entry_from_mapping(item)
            for item in _sequence(entries, "registry entries", MAX_ENTRIES)
        )
        self.content_address = _address(content_address, "registry entries content address", ENTRIES_PREFIX)
        self._validate()

    @staticmethod
    def _entry_from_mapping(value: Mapping[str, Any]):
        return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntry.from_mapping(value)

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("registry entries are not consecutively ordered")
        if len({item.snapshot_id for item in self.entries}) != len(self.entries) or len({item.snapshot_address for item in self.entries}) != len(self.entries):
            raise ValidationError("registry entries contain duplicate snapshot identities")
        if not _public(self.to_dict()):
            raise ValidationError("registry entries cross the public boundary")
        if not self.content_address.endswith(":pending") and address_entries(self.entries) != self.content_address:
            raise ValidationError("registry entries address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry entries")
        _strict(value, set(cls.FIELDS), "registry entries")
        return cls(value["entries"], value["content_address"])


def address_entries(
    value: Sequence[
        DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntry
    ],
) -> str:
    typed = tuple(value)
    if any(
        not isinstance(
            item,
            DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntry,
        )
        for item in typed
    ):
        raise ValidationError("registry entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryArtifact:
    FIELDS = ARTIFACT_FIELDS

    def __init__(self, name: str, size: int, digest: str, content_address: str) -> None:
        self.name = _label(name, "registry artifact name")
        if self.name not in MANIFEST_ARTIFACT_FILES:
            raise ValidationError("registry artifact name is not permitted")
        self.size = _count(size, "registry artifact size", MAX_REGISTRY_BYTES)
        self.digest = _text(digest, "registry artifact digest", 128)
        if len(self.digest) != 64 or any(char not in "0123456789abcdef" for char in self.digest):
            raise ValidationError("registry artifact digest is not a lowercase SHA-256")
        self.content_address = _address(content_address, "registry artifact content address", ARTIFACT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("registry artifact crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_artifact(self) != self.content_address:
            raise ValidationError("registry artifact address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry artifact")
        _strict(value, set(cls.FIELDS), "registry artifact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_artifact(
    value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryArtifact,
) -> str:
    if not isinstance(
        value,
        DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryArtifact,
    ):
        raise ValidationError("registry artifact address requires a typed artifact")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARTIFACT_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, files: Sequence[str], artifacts: Sequence[Any], content_address: str) -> None:
        self.registry_id = _label(registry_id, "registry manifest ID")
        self.version = _text(version, "registry manifest version", 4096)
        self.boundary = _text(boundary, "registry manifest boundary", 4096)
        self.files = tuple(_label(item, "registry manifest file") for item in _sequence(files, "registry manifest files", len(FILES)))
        self.artifacts = tuple(
            item
            if isinstance(
                item,
                DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryArtifact,
            )
            else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryArtifact.from_mapping(item)
            for item in _sequence(artifacts, "registry manifest artifacts", len(MANIFEST_ARTIFACT_FILES))
        )
        self.content_address = _address(content_address, "registry manifest content address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES:
            raise ValidationError("registry manifest file order is not canonical")
        if tuple(item.name for item in self.artifacts) != MANIFEST_ARTIFACT_FILES:
            raise ValidationError("registry manifest artifact order is not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("registry manifest crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("registry manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "files": self.files, "artifacts": [item.to_dict() for item in self.artifacts], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry manifest")
        _strict(value, set(cls.FIELDS), "registry manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(
    value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryManifest,
) -> str:
    if not isinstance(
        value,
        DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryManifest,
    ):
        raise ValidationError("registry manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistrySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, registry_id: str, entry_count: int, ready_count: int, blocked_count: int, accepted_count: int, rejected_count: int, total_query_rows: int, matched_query_rows: int, returned_query_rows: int, distinct_diff_count: int, distinct_query_count: int, latest_snapshot_id: str, latest_snapshot_address: str, state: str, accepted: bool, content_address: str) -> None:
        self.registry_id = _label(registry_id, "registry summary ID")
        self.entry_count = _count(entry_count, "registry summary entry count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "registry summary ready count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "registry summary blocked count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "registry summary accepted count", MAX_ENTRIES)
        self.rejected_count = _count(rejected_count, "registry summary rejected count", MAX_ENTRIES)
        self.total_query_rows = _count(total_query_rows, "registry summary total query rows", MAX_TOTAL_ROWS)
        self.matched_query_rows = _count(matched_query_rows, "registry summary matched query rows", MAX_TOTAL_ROWS)
        self.returned_query_rows = _count(returned_query_rows, "registry summary returned query rows", MAX_TOTAL_ROWS)
        self.distinct_diff_count = _count(distinct_diff_count, "registry summary distinct diff count", MAX_ENTRIES)
        self.distinct_query_count = _count(distinct_query_count, "registry summary distinct query count", MAX_ENTRIES)
        self.latest_snapshot_id = _label(latest_snapshot_id, "registry summary latest snapshot ID", required=False)
        self.latest_snapshot_address = _address(latest_snapshot_address, "registry summary latest snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=False)
        self.state = _label(state, "registry summary state")
        if self.state not in STATES:
            raise ValidationError("registry summary state is unsupported")
        self.accepted = _bool(accepted, "registry summary acceptance")
        self.content_address = _address(content_address, "registry summary content address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.ready_count + self.blocked_count != self.entry_count or self.accepted_count + self.rejected_count != self.entry_count:
            raise ValidationError("registry summary counts are not conserved")
        if self.matched_query_rows > self.total_query_rows or self.returned_query_rows > self.matched_query_rows:
            raise ValidationError("registry summary query counts are not conserved")
        expected_state = "empty" if not self.entry_count else "ready" if not self.blocked_count else "blocked" if not self.ready_count else "mixed"
        if self.state != expected_state or self.accepted != bool(self.entry_count and not self.rejected_count):
            raise ValidationError("registry summary state or acceptance does not replay")
        if bool(self.entry_count) != bool(self.latest_snapshot_id) or bool(self.entry_count) != bool(self.latest_snapshot_address):
            raise ValidationError("registry summary latest snapshot linkage is invalid")
        if not _public(self.to_dict()):
            raise ValidationError("registry summary crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("registry summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry summary")
        _strict(value, set(cls.FIELDS), "registry summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(
    value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistrySummary,
) -> str:
    if not isinstance(
        value,
        DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistrySummary,
    ):
        raise ValidationError("registry summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry:
    FIELDS = REGISTRY_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, entry_count: int, ready_count: int, blocked_count: int, accepted_count: int, rejected_count: int, total_query_rows: int, matched_query_rows: int, returned_query_rows: int, distinct_diff_count: int, distinct_query_count: int, latest_snapshot_id: str, latest_snapshot_address: str, state: str, accepted: bool, entries: Any, manifest: Any, summary: Any, content_address: str) -> None:
        self.registry_id = _label(registry_id, "registry ID")
        self.version = _text(version, "registry version", 4096)
        self.boundary = _text(boundary, "registry boundary", 4096)
        self.entry_count = _count(entry_count, "registry entry count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "registry ready count", MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "registry blocked count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "registry accepted count", MAX_ENTRIES)
        self.rejected_count = _count(rejected_count, "registry rejected count", MAX_ENTRIES)
        self.total_query_rows = _count(total_query_rows, "registry total query rows", MAX_TOTAL_ROWS)
        self.matched_query_rows = _count(matched_query_rows, "registry matched query rows", MAX_TOTAL_ROWS)
        self.returned_query_rows = _count(returned_query_rows, "registry returned query rows", MAX_TOTAL_ROWS)
        self.distinct_diff_count = _count(distinct_diff_count, "registry distinct diff count", MAX_ENTRIES)
        self.distinct_query_count = _count(distinct_query_count, "registry distinct query count", MAX_ENTRIES)
        self.latest_snapshot_id = _label(latest_snapshot_id, "registry latest snapshot ID", required=False)
        self.latest_snapshot_address = _address(latest_snapshot_address, "registry latest snapshot address", snapshot_model.SNAPSHOT_PREFIX, required=False)
        self.state = _label(state, "registry state")
        if self.state not in STATES:
            raise ValidationError("registry state is unsupported")
        self.accepted = _bool(accepted, "registry acceptance")
        self.entries = entries if isinstance(entries, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntries) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntries.from_mapping(entries)
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistrySummary) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistrySummary.from_mapping(summary)
        self.content_address = _address(content_address, "registry content address", REGISTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("registry version or boundary is unsupported")
        if self.entries.content_address.endswith(":pending") or self.summary.content_address.endswith(":pending") or self.manifest.content_address.endswith(":pending"):
            raise ValidationError("registry nested artifacts must be addressed")
        if self.entry_count != len(self.entries.entries) or self.entry_count != self.summary.entry_count:
            raise ValidationError("registry entry count does not replay")
        if any(getattr(self, field) != getattr(self.summary, field) for field in SUMMARY_FIELDS if field != "registry_id" and field != "content_address"):
            raise ValidationError("registry summary does not match registry")
        if self.summary.registry_id != self.registry_id or self.manifest.registry_id != self.registry_id or self.manifest.version != self.version or self.manifest.boundary != self.boundary:
            raise ValidationError("registry nested identity does not match")
        if not _public(self.to_dict()):
            raise ValidationError("registry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_registry(self) != self.content_address:
            raise ValidationError("registry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "version": self.version,
            "boundary": self.boundary,
            "entry_count": self.entry_count,
            "ready_count": self.ready_count,
            "blocked_count": self.blocked_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "total_query_rows": self.total_query_rows,
            "matched_query_rows": self.matched_query_rows,
            "returned_query_rows": self.returned_query_rows,
            "distinct_diff_count": self.distinct_diff_count,
            "distinct_query_count": self.distinct_query_count,
            "latest_snapshot_id": self.latest_snapshot_id,
            "latest_snapshot_address": self.latest_snapshot_address,
            "state": self.state,
            "accepted": self.accepted,
            "entries": self.entries.to_dict(),
            "manifest": self.manifest.to_dict(),
            "summary": self.summary.to_dict(),
            "content_address": self.content_address,
        }

    def summary_projection(self) -> dict[str, Any]:
        return self.summary.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "registry")
        _strict(value, set(cls.FIELDS), "registry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_registry(
    value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry,
) -> str:
    if not isinstance(
        value,
        DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry,
    ):
        raise ValidationError("registry address requires a typed registry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REGISTRY_PREFIX)


def _entry_for_snapshot(snapshot: Any, ordinal: int):
    snapshot = _verify_snapshot(snapshot)
    source = snapshot.to_dict()
    body = {field: source[field] for field in ENTRY_FIELDS if field not in {"ordinal", "content_address", "snapshot_address"}}
    body["snapshot_address"] = snapshot_model.address_snapshot(snapshot)
    body["ordinal"] = ordinal
    body["content_address"] = ENTRY_PREFIX + ":pending"
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntry(**body)
    body["content_address"] = address_entry(provisional)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntry(**body)


def _summary_for_entries(registry_id: str, entries: Sequence[Any]):
    typed = tuple(entries)
    ready = sum(item.state == "ready" for item in typed)
    blocked = sum(item.state == "blocked" for item in typed)
    accepted = sum(item.accepted for item in typed)
    body = {
        "registry_id": registry_id,
        "entry_count": len(typed),
        "ready_count": ready,
        "blocked_count": blocked,
        "accepted_count": accepted,
        "rejected_count": len(typed) - accepted,
        "total_query_rows": sum(item.query_total_count for item in typed),
        "matched_query_rows": sum(item.query_matched_count for item in typed),
        "returned_query_rows": sum(item.query_returned_count for item in typed),
        "distinct_diff_count": len({item.diff_id for item in typed}),
        "distinct_query_count": len({item.query_address for item in typed}),
        "latest_snapshot_id": typed[-1].snapshot_id if typed else "",
        "latest_snapshot_address": typed[-1].snapshot_address if typed else "",
        "state": "empty" if not typed else "ready" if not blocked else "blocked" if not ready else "mixed",
        "accepted": bool(typed and accepted == len(typed)),
        "content_address": SUMMARY_PREFIX + ":pending",
    }
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistrySummary(**body)
    body["content_address"] = address_summary(provisional)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistrySummary(**body)


def _artifact(name: str, payload: bytes):
    body = {"name": name, "size": len(payload), "digest": hashlib.sha256(payload).hexdigest(), "content_address": ARTIFACT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryArtifact(**body)
    body["content_address"] = address_artifact(provisional)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryArtifact(**body)


def _manifest(registry_id: str, entries: Any, summary: Any):
    entries_payload = canonical_json(entries.to_dict()).encode("utf-8")
    summary_payload = canonical_json(summary.to_dict()).encode("utf-8")
    body = {
        "registry_id": registry_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "files": FILES,
        "artifacts": (_artifact("entries.json", entries_payload), _artifact("summary.json", summary_payload)),
        "content_address": MANIFEST_PREFIX + ":pending",
    }
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryManifest(**body)
    body["content_address"] = address_manifest(provisional)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryManifest(**body)


def build_registry(
    snapshots: Sequence[Any],
    *,
    registry_id: str = DEFAULT_REGISTRY_ID,
) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry:
    registry_id = _label(registry_id, "registry ID")
    values = _sequence(snapshots, "registry snapshots", MAX_ENTRIES)
    typed = tuple(_verify_snapshot(item) if not isinstance(item, Mapping) else snapshot_model.snapshot_from_mapping(item) for item in values)
    if len({item.snapshot_id for item in typed}) != len(typed) or len({item.content_address for item in typed}) != len(typed):
        raise ValidationError("registry snapshot IDs and addresses must be unique")
    ordered = tuple(sorted(typed, key=lambda item: (item.snapshot_id, item.content_address)))
    entries = tuple(_entry_for_snapshot(item, ordinal) for ordinal, item in enumerate(ordered, 1))
    entries_body = {"entries": entries, "content_address": ENTRIES_PREFIX + ":pending"}
    entries_body["content_address"] = address_entries(entries)
    entries_value = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntries(**entries_body)
    summary_value = _summary_for_entries(registry_id, entries_value.entries)
    manifest_value = _manifest(registry_id, entries_value, summary_value)
    body = {
        "registry_id": registry_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "entry_count": summary_value.entry_count,
        "ready_count": summary_value.ready_count,
        "blocked_count": summary_value.blocked_count,
        "accepted_count": summary_value.accepted_count,
        "rejected_count": summary_value.rejected_count,
        "total_query_rows": summary_value.total_query_rows,
        "matched_query_rows": summary_value.matched_query_rows,
        "returned_query_rows": summary_value.returned_query_rows,
        "distinct_diff_count": summary_value.distinct_diff_count,
        "distinct_query_count": summary_value.distinct_query_count,
        "latest_snapshot_id": summary_value.latest_snapshot_id,
        "latest_snapshot_address": summary_value.latest_snapshot_address,
        "state": summary_value.state,
        "accepted": summary_value.accepted,
        "entries": entries_value,
        "manifest": manifest_value,
        "summary": summary_value,
        "content_address": REGISTRY_PREFIX + ":pending",
    }
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry(**body)
    body["content_address"] = address_registry(provisional)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry(**body)


def registry_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry.from_mapping(value)


def verify_registry(value):
    if not isinstance(
        value,
        DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry,
    ):
        raise ValidationError("registry verification requires a typed registry")
    value._validate()
    if not value.content_address.endswith(":pending") and address_registry(value) != value.content_address:
        raise ValidationError("registry address verification failed")
    return value


def registry_json(value) -> str:
    return canonical_json(registry_from_mapping(verify_registry(value).to_dict()).to_dict())


def entries_document(value) -> dict[str, Any]:
    return verify_registry(value).entries.to_dict()


def summary_document(value) -> dict[str, Any]:
    return verify_registry(value).summary.to_dict()


def manifest_document(value) -> dict[str, Any]:
    return verify_registry(value).manifest.to_dict()


def entries_json(value) -> str:
    return canonical_json(entries_document(value))


def summary_json(value) -> str:
    return canonical_json(summary_document(value))


def manifest_json(value) -> str:
    return canonical_json(manifest_document(value))


def registry_csv(value) -> str:
    value = verify_registry(value)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=ENTRY_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.entries.entries:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_registry_markdown(value) -> str:
    value = verify_registry(value)
    lines = [
        "# Comparison Query Snapshot Registry",
        "",
        f"- Registry: `{value.registry_id}`",
        f"- State: `{value.state}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Entries: `{value.entry_count}`",
        f"- Ready / blocked: `{value.ready_count}` / `{value.blocked_count}`",
        f"- Address: `{value.content_address}`",
        "",
        "| # | snapshot | diff | state | accepted | returned rows | address |",
        "| ---: | --- | --- | :---: | :---: | ---: | --- |",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.snapshot_id}` | `{item.diff_id}` | `{item.state}` | `{str(item.accepted).lower()}` | {item.query_returned_count} | `{item.snapshot_address}` |"
        for item in value.entries.entries
    )
    return "\n".join(lines) + "\n"


def _documents(value) -> dict[str, bytes]:
    value = verify_registry(value)
    return {
        "registry.json": registry_json(value).encode("utf-8"),
        "entries.json": entries_json(value).encode("utf-8"),
        "summary.json": summary_json(value).encode("utf-8"),
        "manifest.json": manifest_json(value).encode("utf-8"),
    }


def persist_registry(value, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_registry(value)
    destination = Path(destination)
    if destination.exists() and destination.is_symlink():
        raise ValidationError("registry destination may not be a symlink")
    if destination.exists() and not overwrite:
        raise ValidationError("registry destination already exists")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=str(parent)))
    backup: Path | None = None
    try:
        documents = _documents(value)
        for name in FILES:
            (temporary / name).write_bytes(documents[name])
        if destination.exists():
            if not destination.is_dir():
                raise ValidationError("registry destination must be a directory")
            backup = parent / f".{destination.name}-old-{next(tempfile._get_candidate_names())}"
            os.replace(destination, backup)
        os.replace(temporary, destination)
        temporary = Path()
        if backup is not None:
            shutil.rmtree(backup)
        return destination
    except Exception:
        if temporary and temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        if backup is not None and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise


def _read_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise ValidationError("registry artifact must be a regular file")
    raw = path.read_bytes()
    if len(raw) > MAX_REGISTRY_BYTES:
        raise ValidationError("registry artifact exceeds the size bound")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("registry artifact is not canonical JSON") from exc
    if not isinstance(parsed, Mapping) or canonical_json(parsed).encode("utf-8") != raw:
        raise ValidationError("registry artifact is not canonical JSON")
    return parsed, raw


def load_registry(destination: str | Path):
    destination = Path(destination)
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("registry destination must be a regular directory")
    names = tuple(sorted(item.name for item in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("registry directory has an unexpected member set")
    documents = {name: _read_json(destination / name) for name in FILES}
    registry_value = registry_from_mapping(documents["registry.json"][0])
    if canonical_json(registry_value.entries.to_dict()).encode("utf-8") != documents["entries.json"][1] or canonical_json(registry_value.summary.to_dict()).encode("utf-8") != documents["summary.json"][1] or canonical_json(registry_value.manifest.to_dict()).encode("utf-8") != documents["manifest.json"][1]:
        raise ValidationError("registry documents are cross-linked inconsistently")
    if registry_json(registry_value).encode("utf-8") != documents["registry.json"][1]:
        raise ValidationError("registry JSON address does not replay")
    for artifact in registry_value.manifest.artifacts:
        raw = documents[artifact.name][1]
        if len(raw) != artifact.size or hashlib.sha256(raw).hexdigest() != artifact.digest or address_artifact(artifact) != artifact.content_address:
            raise ValidationError("registry artifact byte receipt does not replay")
    if address_manifest(registry_value.manifest) != registry_value.manifest.content_address or address_registry(registry_value) != registry_value.content_address:
        raise ValidationError("registry manifest or registry address does not replay")
    return verify_registry(registry_value)


def run_registry(value: Sequence[Any] | str | Path | Mapping[str, Any], *, registry_id: str = DEFAULT_REGISTRY_ID, destination: str | Path | None = None, overwrite: bool = False):
    if isinstance(value, (str, Path)):
        source = Path(value)
        if source.is_dir() and tuple(sorted(item.name for item in source.iterdir())) == tuple(sorted(FILES)):
            result = load_registry(source)
        else:
            values = []
            paths = [source] if source.is_file() else sorted(source.glob("*.json")) if source.is_dir() else []
            if not paths:
                raise ValidationError("registry input must contain snapshot JSON documents")
            for path in paths:
                raw = json.loads(path.read_text(encoding="utf-8"))
                values.append(raw.get("snapshot", raw))
            result = build_registry(values, registry_id=registry_id)
    elif isinstance(value, Mapping):
        result = build_registry((value.get("snapshot", value),), registry_id=registry_id)
    else:
        result = build_registry(value, registry_id=registry_id)
    if destination is not None:
        persist_registry(result, destination, overwrite=overwrite)
    return result


def registry_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data comparison query snapshot registry",
        "type": "object",
        "additionalProperties": False,
        "required": list(REGISTRY_FIELDS),
        "properties": {
            "registry_id": {"type": "string"},
            "version": {"const": VERSION},
            "boundary": {"const": BOUNDARY},
            "entry_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "ready_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "blocked_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "accepted_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "rejected_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES},
            "total_query_rows": {"type": "integer", "minimum": 0},
            "matched_query_rows": {"type": "integer", "minimum": 0},
            "returned_query_rows": {"type": "integer", "minimum": 0},
            "distinct_diff_count": {"type": "integer", "minimum": 0},
            "distinct_query_count": {"type": "integer", "minimum": 0},
            "latest_snapshot_id": {"type": "string"},
            "latest_snapshot_address": {"type": "string"},
            "state": {"enum": list(STATES)},
            "accepted": {"type": "boolean"},
            "entries": {"$ref": "#/$defs/entries"},
            "manifest": {"$ref": "#/$defs/manifest"},
            "summary": {"$ref": "#/$defs/summary"},
            "content_address": {"type": "string"},
        },
        "$defs": {"entries": entries_schema(), "manifest": manifest_schema(), "summary": summary_schema()},
    }


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot registry entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": "array" if field == "resources" else "integer" if field in {"ordinal", "offset", "limit", "query_total_count", "query_matched_count", "query_returned_count"} else "boolean" if field == "accepted" else "string"} for field in ENTRY_FIELDS}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot registry entries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "maxItems": MAX_ENTRIES, "items": entry_schema()}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot registry manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"registry_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot registry summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") or field.endswith("rows") else "boolean" if field == "accepted" else "string"} for field in SUMMARY_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "value_free": True, "files": list(FILES), "max_entries": MAX_ENTRIES, "features": ["deterministic snapshot admission", "duplicate identity rejection", "ready blocked mixed state folding", "query count and identity conservation", "exact-byte manifest receipts", "atomic persistence", "strict canonical reload", "JSON CSV and Markdown projections"]}


__all__ = [
    "ARTIFACT_FIELDS",
    "ARTIFACT_PREFIX",
    "BOUNDARY",
    "DEFAULT_REGISTRY_ID",
    "ENTRY_FIELDS",
    "ENTRY_PREFIX",
    "ENTRIES_FIELDS",
    "ENTRIES_PREFIX",
    "FILES",
    "MANIFEST_ARTIFACT_FILES",
    "MANIFEST_FIELDS",
    "MANIFEST_PREFIX",
    "MAX_ENTRIES",
    "MAX_REGISTRY_BYTES",
    "REGISTRY_FIELDS",
    "REGISTRY_PREFIX",
    "STATES",
    "SUMMARY_FIELDS",
    "SUMMARY_PREFIX",
    "VERSION",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistry",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryArtifact",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntry",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryEntries",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistryManifest",
    "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotRegistrySummary",
    "address_artifact",
    "address_entry",
    "address_entries",
    "address_manifest",
    "address_registry",
    "address_summary",
    "build_registry",
    "capabilities",
    "entries_document",
    "entries_json",
    "entries_schema",
    "entry_schema",
    "load_registry",
    "manifest_document",
    "manifest_json",
    "manifest_schema",
    "persist_registry",
    "registry_csv",
    "registry_from_mapping",
    "registry_json",
    "registry_schema",
    "render_registry_markdown",
    "run_registry",
    "summary_document",
    "summary_json",
    "summary_schema",
    "verify_registry",
]
