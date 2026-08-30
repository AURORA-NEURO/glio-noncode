"""Durable handoffs for bounded queries over persisted comparison results."""

from __future__ import annotations

# ruff: noqa: E501, I001

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
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query as query_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_audit as query_audit_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = query_model.VERSION + "-snapshot-v1"
BOUNDARY = query_model.BOUNDARY + "_snapshot"
SNAPSHOT_PREFIX = query_model.QUERY_PREFIX + "-snapshot"
MANIFEST_PREFIX = SNAPSHOT_PREFIX + "-manifest"
ARTIFACT_PREFIX = SNAPSHOT_PREFIX + "-artifact"
SUMMARY_PREFIX = SNAPSHOT_PREFIX + "-summary"
DEFAULT_SNAPSHOT_ID = "policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot"
STATES = ("ready", "blocked")
FILES = ("manifest.json", "snapshot.json", "query.json", "audit.json", "summary.json")
ARTIFACT_FILES = FILES[1:]
MAX_SNAPSHOT_BYTES = 128 * 1024 * 1024

SNAPSHOT_FIELDS = (
    "snapshot_id", "version", "boundary", "diff_id", "diff_address", "query_address", "query_audit_address",
    "resources", "change_filter", "source_resource_filter", "key_filter", "identity_filter", "field_filter",
    "direction_filter", "state_transition_filter", "address_filter", "text_filter", "offset", "limit",
    "query_total_count", "query_matched_count", "query_returned_count", "state", "accepted", "content_address",
)
SUMMARY_FIELDS = (
    "snapshot_id", "snapshot_address", "diff_id", "diff_address", "query_address", "query_audit_address",
    "resources", "change_filter", "source_resource_filter", "key_filter", "identity_filter", "field_filter",
    "direction_filter", "state_transition_filter", "address_filter", "text_filter", "offset", "limit",
    "query_total_count", "query_matched_count", "query_returned_count", "state", "accepted", "content_address",
)
ARTIFACT_FIELDS = ("ordinal", "name", "size", "hash", "content_address")
MANIFEST_FIELDS = ("snapshot_id", "version", "boundary", "files", "artifacts", "snapshot_address", "manifest_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = False) -> str:
    value = _text(value, field, 4096, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
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
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _resources(value: Any, field: str) -> tuple[str, ...]:
    selected = _sequence(value, field, len(query_model.RESOURCES))
    if not selected or len(set(selected)) != len(selected) or any(item not in query_model.RESOURCES for item in selected):
        raise ValidationError(f"{field} are invalid")
    return tuple(item for item in query_model.RESOURCES if item in selected)


def _direction(value: Any, field: str) -> str:
    value = _label(value, field)
    if value and value not in query_model.diff_model.DIRECTIONS:
        raise ValidationError(f"{field} is unsupported")
    return value


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotArtifact:
    """One exact-byte receipt in a comparison-query snapshot."""

    FIELDS = ARTIFACT_FIELDS

    def __init__(self, ordinal: int, name: str, size: int, hash: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "comparison-query snapshot artifact ordinal", len(ARTIFACT_FILES), positive=True)
        self.name = _label(name, "comparison-query snapshot artifact name", required=True)
        if self.name not in ARTIFACT_FILES:
            raise ValidationError("comparison-query snapshot artifact name is unsupported")
        self.size = _count(size, "comparison-query snapshot artifact size", MAX_SNAPSHOT_BYTES, positive=True)
        self.hash = _address(hash, "comparison-query snapshot artifact hash", ARTIFACT_PREFIX, required=True)
        self.content_address = _address(content_address, "comparison-query snapshot artifact address", ARTIFACT_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("comparison-query snapshot artifact crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_artifact(self) != self.content_address:
            raise ValidationError("comparison-query snapshot artifact address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison-query snapshot artifact")
        _strict(value, set(cls.FIELDS), "comparison-query snapshot artifact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_artifact(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotArtifact) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotArtifact):
        raise ValidationError("comparison-query snapshot artifact address requires a typed artifact")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARTIFACT_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotManifest:
    """The fixed manifest for one comparison-query snapshot."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, snapshot_id: str, version: str, boundary: str, files: Sequence[str], artifacts: Sequence[Any], snapshot_address: str, manifest_address: str) -> None:
        self.snapshot_id = _label(snapshot_id, "comparison-query snapshot manifest ID", required=True)
        self.version = _text(version, "comparison-query snapshot manifest version", 512, required=True)
        self.boundary = _label(boundary, "comparison-query snapshot manifest boundary", required=True)
        self.files = tuple(_label(item, "comparison-query snapshot manifest file", required=True) for item in _sequence(files, "comparison-query snapshot manifest files", len(FILES)))
        if self.files != FILES:
            raise ValidationError("comparison-query snapshot manifest file set is not canonical")
        self.artifacts = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotArtifact) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotArtifact.from_mapping(item) for item in _sequence(artifacts, "comparison-query snapshot manifest artifacts", len(ARTIFACT_FILES)))
        if tuple(item.ordinal for item in self.artifacts) != tuple(range(1, len(ARTIFACT_FILES) + 1)) or tuple(item.name for item in self.artifacts) != ARTIFACT_FILES:
            raise ValidationError("comparison-query snapshot manifest artifacts are not canonical")
        self.snapshot_address = _address(snapshot_address, "comparison-query snapshot manifest snapshot address", SNAPSHOT_PREFIX, required=True)
        self.manifest_address = _address(manifest_address, "comparison-query snapshot manifest address", MANIFEST_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("comparison-query snapshot manifest crosses the public boundary")
        if not self.manifest_address.endswith(":pending") and address_manifest(self) != self.manifest_address:
            raise ValidationError("comparison-query snapshot manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "artifacts" else [item.to_dict() for item in self.artifacts] for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison-query snapshot manifest")
        _strict(value, set(cls.FIELDS), "comparison-query snapshot manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotManifest):
        raise ValidationError("comparison-query snapshot manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"manifest_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotSummary:
    """A compact value-free summary of one comparison-query handoff."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, snapshot_id: str, snapshot_address: str, diff_id: str, diff_address: str, query_address: str, query_audit_address: str, resources: Sequence[str], change_filter: str, source_resource_filter: str, key_filter: str, identity_filter: str, field_filter: str, direction_filter: str, state_transition_filter: str, address_filter: str, text_filter: str, offset: int, limit: int, query_total_count: int, query_matched_count: int, query_returned_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.snapshot_id = _label(snapshot_id, "comparison-query snapshot summary ID", required=True)
        self.snapshot_address = _address(snapshot_address, "comparison-query snapshot summary snapshot address", SNAPSHOT_PREFIX, required=True)
        self.diff_id = _label(diff_id, "comparison-query snapshot summary diff ID", required=True)
        self.diff_address = _address(diff_address, "comparison-query snapshot summary diff address", query_model.diff_model.DIFF_PREFIX, required=True)
        self.query_address = _address(query_address, "comparison-query snapshot summary query address", query_model.QUERY_PREFIX, required=True)
        self.query_audit_address = _address(query_audit_address, "comparison-query snapshot summary query audit address", query_audit_model.AUDIT_PREFIX, required=True)
        self.resources = _resources(resources, "comparison-query snapshot summary resources")
        self.change_filter = _label(change_filter, "comparison-query snapshot summary change filter")
        self.source_resource_filter = _label(source_resource_filter, "comparison-query snapshot summary source resource filter")
        if self.source_resource_filter and self.source_resource_filter not in query_model.diff_model.snapshot_model.query_model.RESOURCES:
            raise ValidationError("comparison-query snapshot summary source resource filter is unsupported")
        self.key_filter = _text(key_filter, "comparison-query snapshot summary key filter", 2048, required=False)
        self.identity_filter = _text(identity_filter, "comparison-query snapshot summary identity filter", 1024, required=False)
        self.field_filter = _label(field_filter, "comparison-query snapshot summary field filter")
        if self.field_filter and self.field_filter not in query_model.diff_model.SEMANTIC_ROW_FIELDS:
            raise ValidationError("comparison-query snapshot summary field filter is unsupported")
        self.direction_filter = _direction(direction_filter, "comparison-query snapshot summary direction filter")
        self.state_transition_filter = _label(state_transition_filter, "comparison-query snapshot summary transition filter")
        self.address_filter = _address(address_filter, "comparison-query snapshot summary address filter")
        self.text_filter = _text(text_filter, "comparison-query snapshot summary text filter", 1024, required=False)
        self.offset = _count(offset, "comparison-query snapshot summary offset", query_model.MAX_TOTAL_COUNT)
        self.limit = _count(limit, "comparison-query snapshot summary limit", query_model.MAX_LIMIT, positive=True)
        self.query_total_count = _count(query_total_count, "comparison-query snapshot summary total count", query_model.MAX_TOTAL_COUNT)
        self.query_matched_count = _count(query_matched_count, "comparison-query snapshot summary matched count", query_model.MAX_TOTAL_COUNT)
        self.query_returned_count = _count(query_returned_count, "comparison-query snapshot summary returned count", query_model.MAX_LIMIT)
        self.state = _label(state, "comparison-query snapshot summary state", required=True)
        if self.state not in STATES:
            raise ValidationError("comparison-query snapshot summary state is unsupported")
        self.accepted = _bool(accepted, "comparison-query snapshot summary acceptance")
        self.content_address = _address(content_address, "comparison-query snapshot summary content address", SUMMARY_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.query_matched_count > self.query_total_count or self.query_returned_count > self.query_matched_count or self.query_returned_count > self.limit or self.accepted != (self.state == "ready") or not _public(self.to_dict()):
            raise ValidationError("comparison-query snapshot summary counters do not replay")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("comparison-query snapshot summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison-query snapshot summary")
        _strict(value, set(cls.FIELDS), "comparison-query snapshot summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotSummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotSummary):
        raise ValidationError("comparison-query snapshot summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot:
    """A five-file, atomic, reloadable handoff for one comparison query."""

    FIELDS = SNAPSHOT_FIELDS

    def __init__(self, snapshot_id: str, version: str, boundary: str, diff_id: str, diff_address: str, query_address: str, query_audit_address: str, resources: Sequence[str], change_filter: str, source_resource_filter: str, key_filter: str, identity_filter: str, field_filter: str, direction_filter: str, state_transition_filter: str, address_filter: str, text_filter: str, offset: int, limit: int, query_total_count: int, query_matched_count: int, query_returned_count: int, state: str, accepted: bool, content_address: str, query: Any = None, query_audit: Any = None, summary: Any = None, manifest: Any = None) -> None:
        self.snapshot_id = _label(snapshot_id, "comparison-query snapshot ID", required=True)
        self.version = _text(version, "comparison-query snapshot version", 512, required=True)
        self.boundary = _label(boundary, "comparison-query snapshot boundary", required=True)
        self.diff_id = _label(diff_id, "comparison-query snapshot diff ID", required=True)
        self.diff_address = _address(diff_address, "comparison-query snapshot diff address", query_model.diff_model.DIFF_PREFIX, required=True)
        self.query_address = _address(query_address, "comparison-query snapshot query address", query_model.QUERY_PREFIX, required=True)
        self.query_audit_address = _address(query_audit_address, "comparison-query snapshot query audit address", query_audit_model.AUDIT_PREFIX, required=True)
        self.resources = _resources(resources, "comparison-query snapshot resources")
        self.change_filter = _label(change_filter, "comparison-query snapshot change filter")
        if self.change_filter and self.change_filter not in query_model.diff_model.CHANGES:
            raise ValidationError("comparison-query snapshot change filter is unsupported")
        self.source_resource_filter = _label(source_resource_filter, "comparison-query snapshot source resource filter")
        if self.source_resource_filter and self.source_resource_filter not in query_model.diff_model.snapshot_model.query_model.RESOURCES:
            raise ValidationError("comparison-query snapshot source resource filter is unsupported")
        self.key_filter = _text(key_filter, "comparison-query snapshot key filter", 2048, required=False)
        self.identity_filter = _text(identity_filter, "comparison-query snapshot identity filter", 1024, required=False)
        self.field_filter = _label(field_filter, "comparison-query snapshot field filter")
        if self.field_filter and self.field_filter not in query_model.diff_model.SEMANTIC_ROW_FIELDS:
            raise ValidationError("comparison-query snapshot field filter is unsupported")
        self.direction_filter = _direction(direction_filter, "comparison-query snapshot direction filter")
        self.state_transition_filter = _label(state_transition_filter, "comparison-query snapshot state transition filter")
        self.address_filter = _address(address_filter, "comparison-query snapshot address filter")
        self.text_filter = _text(text_filter, "comparison-query snapshot text filter", 1024, required=False)
        self.offset = _count(offset, "comparison-query snapshot offset", query_model.MAX_TOTAL_COUNT)
        self.limit = _count(limit, "comparison-query snapshot limit", query_model.MAX_LIMIT, positive=True)
        self.query_total_count = _count(query_total_count, "comparison-query snapshot total count", query_model.MAX_TOTAL_COUNT)
        self.query_matched_count = _count(query_matched_count, "comparison-query snapshot matched count", query_model.MAX_TOTAL_COUNT)
        self.query_returned_count = _count(query_returned_count, "comparison-query snapshot returned count", query_model.MAX_LIMIT)
        self.state = _label(state, "comparison-query snapshot state", required=True)
        if self.state not in STATES:
            raise ValidationError("comparison-query snapshot state is unsupported")
        self.accepted = _bool(accepted, "comparison-query snapshot acceptance")
        self.content_address = _address(content_address, "comparison-query snapshot address", SNAPSHOT_PREFIX, required=True)
        self._query = query
        self._query_audit = query_audit
        self._summary = summary
        self._manifest = manifest
        self._validate()

    @property
    def query(self):
        return self._query

    @property
    def query_audit(self):
        return self._query_audit

    @property
    def summary(self):
        return self._summary

    @property
    def manifest(self):
        return self._manifest

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.accepted != (self.state == "ready"):
            raise ValidationError("comparison-query snapshot version or acceptance does not replay")
        if self.query is not None:
            if not isinstance(self.query, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery):
                raise ValidationError("comparison-query snapshot query linkage is not typed")
            if (self.query.diff_id, self.query.diff_address, self.query.content_address, self.query.resources, self.query.change_filter, self.query.source_resource_filter, self.query.key_filter, self.query.identity_filter, self.query.field_filter, self.query.direction_filter, self.query.state_transition_filter, self.query.address_filter, self.query.text_filter, self.query.offset, self.query.limit, self.query.total_count, self.query.matched_count, self.query.returned_count) != (self.diff_id, self.diff_address, self.query_address, self.resources, self.change_filter, self.source_resource_filter, self.key_filter, self.identity_filter, self.field_filter, self.direction_filter, self.state_transition_filter, self.address_filter, self.text_filter, self.offset, self.limit, self.query_total_count, self.query_matched_count, self.query_returned_count):
                raise ValidationError("comparison-query snapshot query metadata does not replay")
        if self.query_audit is not None:
            if not isinstance(self.query_audit, query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQueryAudit):
                raise ValidationError("comparison-query snapshot audit linkage is not typed")
            if (self.query_audit.query_address, self.query_audit.content_address, self.query_audit.accepted) != (self.query_address, self.query_audit_address, self.accepted):
                raise ValidationError("comparison-query snapshot audit linkage does not replay")
        if self.summary is not None and (self.summary.snapshot_address, self.summary.snapshot_id, self.summary.query_address) != (self.content_address, self.snapshot_id, self.query_address):
            raise ValidationError("comparison-query snapshot summary linkage does not replay")
        if self.manifest is not None and (self.manifest.snapshot_address, self.manifest.snapshot_id) != (self.content_address, self.snapshot_id):
            raise ValidationError("comparison-query snapshot manifest linkage does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("comparison-query snapshot crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_snapshot(self) != self.content_address:
            raise ValidationError("comparison-query snapshot address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary_document(self) -> dict[str, Any]:
        return (self.summary if self.summary is not None else _build_summary(self)).to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "comparison-query snapshot")
        _strict(value, set(cls.FIELDS), "comparison-query snapshot")
        return cls(*(value[field] for field in cls.FIELDS))


def address_snapshot(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot):
        raise ValidationError("comparison-query snapshot address requires a typed snapshot")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SNAPSHOT_PREFIX)


def _build_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot):
    body = {field: getattr(value, field) for field in SUMMARY_FIELDS if field not in {"snapshot_address", "content_address"}}
    body.update({"snapshot_address": value.content_address, "content_address": SUMMARY_PREFIX + ":pending"})
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotSummary(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotSummary(**(body | {"content_address": address_summary(provisional)}))


def _documents(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot) -> dict[str, bytes]:
    if value.query is None or value.query_audit is None:
        raise ValidationError("comparison-query snapshot persistence requires query and query audit receipts")
    summary = value.summary.to_dict() if value.summary is not None else _build_summary(value).to_dict()
    return {"snapshot.json": canonical_bytes(value.to_dict()), "query.json": canonical_bytes(value.query.to_dict()), "audit.json": canonical_bytes(value.query_audit.to_dict()), "summary.json": canonical_bytes(summary)}


def _build_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot):
    documents = _documents(value)
    receipts = []
    for ordinal, name in enumerate(ARTIFACT_FILES, 1):
        provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotArtifact(ordinal, name, len(documents[name]), hash_bytes(documents[name], prefix=ARTIFACT_PREFIX), ARTIFACT_PREFIX + ":pending")
        receipts.append(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotArtifact(ordinal, name, provisional.size, provisional.hash, address_artifact(provisional)))
    body = {"snapshot_id": value.snapshot_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": tuple(receipts), "snapshot_address": value.content_address, "manifest_address": MANIFEST_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotManifest(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotManifest(**(body | {"manifest_address": address_manifest(provisional)}))


def build_snapshot(value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery | Mapping[str, Any], *, snapshot_id: str = DEFAULT_SNAPSHOT_ID):
    if isinstance(value, Mapping):
        value = query_model.query_from_mapping(value)
    if not isinstance(value, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery):
        raise ValidationError("comparison-query snapshot requires a typed comparison query")
    value = query_model.verify_query(query_model.query_from_mapping(value.to_dict()))
    query_audit = query_audit_model.audit_query(value)
    body = {"snapshot_id": snapshot_id, "version": VERSION, "boundary": BOUNDARY, "diff_id": value.diff_id, "diff_address": value.diff_address, "query_address": value.content_address, "query_audit_address": query_audit.content_address, "resources": value.resources, "change_filter": value.change_filter, "source_resource_filter": value.source_resource_filter, "key_filter": value.key_filter, "identity_filter": value.identity_filter, "field_filter": value.field_filter, "direction_filter": value.direction_filter, "state_transition_filter": value.state_transition_filter, "address_filter": value.address_filter, "text_filter": value.text_filter, "offset": value.offset, "limit": value.limit, "query_total_count": value.total_count, "query_matched_count": value.matched_count, "query_returned_count": value.returned_count, "state": "ready" if query_audit.accepted else "blocked", "accepted": query_audit.accepted, "content_address": SNAPSHOT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot(**body)
    snapshot = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot(**(body | {"content_address": address_snapshot(provisional)}), query=value, query_audit=query_audit)
    summary = _build_summary(snapshot)
    manifest = _build_manifest(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot(**snapshot.to_dict(), query=value, query_audit=query_audit, summary=summary))
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot(**snapshot.to_dict(), query=value, query_audit=query_audit, summary=summary, manifest=manifest)


def verify_snapshot(value):
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot):
        raise ValidationError("comparison-query snapshot verification requires a typed snapshot")
    value._validate()
    if not value.content_address.endswith(":pending") and address_snapshot(value) != value.content_address:
        raise ValidationError("comparison-query snapshot address verification failed")
    return value


def snapshot_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot.from_mapping(value)


def snapshot_json(value) -> str:
    return canonical_json(snapshot_from_mapping(verify_snapshot(value).to_dict()).to_dict())


def snapshot_csv(value) -> str:
    value = verify_snapshot(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=SNAPSHOT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(value.to_dict())
    return stream.getvalue()


def render_snapshot_markdown(value) -> str:
    value = verify_snapshot(value)
    mark = chr(96)
    lines = ["# Comparison Query Snapshot", "", f"- Snapshot: {mark}{value.snapshot_id}{mark}", f"- Diff: {mark}{value.diff_id}{mark}", f"- Resources: {mark}{', '.join(value.resources)}{mark}", f"- Rows: {mark}{value.query_returned_count}{mark} of {mark}{value.query_matched_count}{mark}", f"- State: {mark}{value.state}{mark}", f"- Accepted: {mark}{value.accepted}{mark}", f"- Address: {mark}{value.content_address}{mark}"]
    return "\n".join(lines) + "\n"


def manifest_document(value) -> dict[str, Any]:
    return _build_manifest(verify_snapshot(value)).to_dict()


def summary_document(value) -> dict[str, Any]:
    return _build_summary(verify_snapshot(value)).to_dict()


def persist_snapshot(value, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_snapshot(value)
    documents = _documents(value)
    manifest = _build_manifest(value)
    members = {"manifest.json": canonical_bytes(manifest.to_dict()), **documents}
    target = Path(destination)
    if target.exists() and (target.is_symlink() or not target.is_dir() or not overwrite):
        raise ValidationError("comparison-query snapshot destination exists; explicit overwrite is required")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
    try:
        for filename in FILES:
            (temporary / filename).write_bytes(members[filename])
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("comparison-query snapshot could not be persisted atomically") from error
    return target


def _read_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        if path.stat().st_size > MAX_SNAPSHOT_BYTES:
            raise ValidationError(f"comparison-query snapshot member {path.name} exceeds its bound")
        raw = path.read_bytes()
        value = _mapping(json.loads(raw.decode("utf-8")), f"comparison-query snapshot member {path.name}")
    except ValidationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"comparison-query snapshot member {path.name} is not valid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"comparison-query snapshot member {path.name} is not canonical")
    return value, raw


def load_snapshot(destination: str | Path):
    root = Path(destination)
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("comparison-query snapshot source must be a regular directory")
    entries = tuple(root.iterdir())
    if tuple(sorted(item.name for item in entries)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in entries):
        raise ValidationError("comparison-query snapshot directory has an unexpected file set")
    raw = {}
    member_bytes = {}
    for filename in FILES:
        raw[filename], member_bytes[filename] = _read_json(root / filename)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotManifest.from_mapping(raw["manifest.json"])
    snapshot = snapshot_from_mapping(raw["snapshot.json"])
    query = query_model.query_from_mapping(raw["query.json"])
    query_audit = query_audit_model.audit_from_mapping(raw["audit.json"])
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotSummary.from_mapping(raw["summary.json"])
    expected_audit = query_audit_model.audit_query(query)
    if query_audit.to_dict() != expected_audit.to_dict():
        raise ValidationError("comparison-query snapshot audit does not replay independently")
    candidate = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot(**snapshot.to_dict(), query=query, query_audit=query_audit, summary=summary, manifest=manifest)
    expected_summary = _build_summary(candidate)
    expected_manifest = _build_manifest(candidate)
    if summary.to_dict() != expected_summary.to_dict() or manifest.to_dict() != expected_manifest.to_dict() or member_bytes["manifest.json"] != canonical_bytes(expected_manifest.to_dict()):
        raise ValidationError("comparison-query snapshot manifest or summary does not replay")
    expected_members = {"manifest.json": canonical_bytes(expected_manifest.to_dict()), **_documents(candidate)}
    for filename in FILES:
        if member_bytes[filename] != expected_members[filename]:
            raise ValidationError(f"comparison-query snapshot member {filename} does not replay")
    for receipt in manifest.artifacts:
        raw_bytes = expected_members[receipt.name]
        provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotArtifact(receipt.ordinal, receipt.name, len(raw_bytes), receipt.hash, ARTIFACT_PREFIX + ":pending")
        if receipt.size != len(raw_bytes) or receipt.hash != hash_bytes(raw_bytes, prefix=ARTIFACT_PREFIX) or receipt.content_address != address_artifact(provisional):
            raise ValidationError("comparison-query snapshot artifact receipt does not replay")
    return verify_snapshot(candidate)


def _query_from_input(value: str | Path | Mapping[str, Any] | query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery):
    if isinstance(value, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery):
        return value
    if isinstance(value, Mapping):
        return query_model.query_from_mapping(value.get("query", value)) if isinstance(value.get("query", value), Mapping) else query_model.query_from_mapping(value)
    path = Path(value)
    if path.is_dir():
        query_path = path / "query.json"
        if not query_path.is_file():
            raise ValidationError("comparison-query snapshot query input directory has no query.json")
        path = query_path
    raw, _ = _read_json(path)
    return query_model.query_from_mapping(raw.get("query", raw) if isinstance(raw.get("query", raw), Mapping) else raw)


def run_snapshot(value: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuery | Mapping[str, Any] | str | Path, *, snapshot_id: str = DEFAULT_SNAPSHOT_ID, destination: str | Path | None = None, overwrite: bool = False):
    snapshot = build_snapshot(_query_from_input(value), snapshot_id=snapshot_id)
    if destination is not None:
        persist_snapshot(snapshot, destination, overwrite=overwrite)
    return snapshot


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"snapshot_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": list(ARTIFACT_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": len(ARTIFACT_FILES)}, "name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "size": {"type": "integer", "minimum": 1, "maximum": MAX_SNAPSHOT_BYTES}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}, "content_address": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}, "minItems": len(ARTIFACT_FILES), "maxItems": len(ARTIFACT_FILES)}, "snapshot_address": {"type": "string", "pattern": "^" + SNAPSHOT_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"snapshot_id": {"type": "string"}, "snapshot_address": {"type": "string", "pattern": "^" + SNAPSHOT_PREFIX + ":"}, "diff_id": {"type": "string"}, "diff_address": {"type": "string", "pattern": "^" + query_model.diff_model.DIFF_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "query_audit_address": {"type": "string", "pattern": "^" + query_audit_model.AUDIT_PREFIX + ":"}, "resources": {"type": "array", "items": {"type": "string", "enum": list(query_model.RESOURCES)}, "minItems": 1, "maxItems": len(query_model.RESOURCES)}, "change_filter": {"type": "string", "enum": ["", *query_model.diff_model.CHANGES]}, "source_resource_filter": {"type": "string", "enum": ["", *query_model.diff_model.snapshot_model.query_model.RESOURCES]}, "key_filter": {"type": "string"}, "identity_filter": {"type": "string"}, "field_filter": {"type": "string", "enum": ["", *query_model.diff_model.SEMANTIC_ROW_FIELDS]}, "direction_filter": {"type": "string", "enum": ["", *query_model.diff_model.DIRECTIONS]}, "state_transition_filter": {"type": "string"}, "address_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": query_model.MAX_LIMIT}, "query_total_count": {"type": "integer", "minimum": 0}, "query_matched_count": {"type": "integer", "minimum": 0}, "query_returned_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + SUMMARY_PREFIX + ":"}}}


def snapshot_schema() -> dict[str, Any]:
    schema = summary_schema()
    properties = dict(schema["properties"])
    properties.update({"version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "content_address": {"type": "string", "pattern": "^" + SNAPSHOT_PREFIX + ":"}})
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison query snapshot", "type": "object", "additionalProperties": False, "required": list(SNAPSHOT_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "snapshot_prefix": SNAPSHOT_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "artifact_prefix": ARTIFACT_PREFIX, "summary_prefix": SUMMARY_PREFIX, "files": list(FILES), "artifact_files": list(ARTIFACT_FILES), "states": list(STATES), "max_snapshot_bytes": MAX_SNAPSHOT_BYTES, "features": ["durable filtered comparison-query handoffs", "source comparison identity retention", "query and audit persistence", "exact five-file persistence", "canonical JSON reload", "per-file byte receipts", "atomic writes", "independent audit replay", "fail-closed tamper detection", "JSON CSV and Markdown projections"]}


__all__ = ["ARTIFACT_FIELDS", "ARTIFACT_FILES", "ARTIFACT_PREFIX", "BOUNDARY", "DEFAULT_SNAPSHOT_ID", "FILES", "MANIFEST_FIELDS", "MANIFEST_PREFIX", "MAX_SNAPSHOT_BYTES", "SNAPSHOT_FIELDS", "SNAPSHOT_PREFIX", "STATES", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshot", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotArtifact", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotDiffQuerySnapshotSummary", "address_artifact", "address_manifest", "address_snapshot", "address_summary", "build_snapshot", "capabilities", "load_snapshot", "manifest_document", "manifest_schema", "persist_snapshot", "run_snapshot", "snapshot_csv", "snapshot_from_mapping", "snapshot_json", "snapshot_schema", "summary_document", "summary_schema", "render_snapshot_markdown", "verify_snapshot"]
