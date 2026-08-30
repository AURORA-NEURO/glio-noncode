"""Durable, value-free handoffs for filtered runtime-query snapshot-diff results.

The handoff keeps the exact query page and its independent query audit together
with a small source-link summary.  It is intentionally independent of the
source diff directory after construction: every retained relationship is an
address or a bounded public label, never a source value or filesystem path.
"""

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
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff as diff_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query as query_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_audit as query_audit_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = query_audit_model.VERSION + "-snapshot-v1"
BOUNDARY = query_model.BOUNDARY + "_snapshot"
SNAPSHOT_PREFIX = query_model.QUERY_PREFIX + "-snapshot"
MANIFEST_PREFIX = SNAPSHOT_PREFIX + "-manifest"
ARTIFACT_PREFIX = SNAPSHOT_PREFIX + "-artifact"
SUMMARY_PREFIX = SNAPSHOT_PREFIX + "-summary"
DEFAULT_SNAPSHOT_ID = "policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot"
STATES = ("ready", "blocked")
FILES = ("manifest.json", "snapshot.json", "query.json", "audit.json", "summary.json")
ARTIFACT_FILES = FILES[1:]
SNAPSHOT_FIELDS = ("snapshot_id", "version", "boundary", "diff_id", "diff_address", "query_address", "query_audit_address", "left_snapshot_id", "right_snapshot_id", "direction", "state_transition", "diff_verified", "query_audit_accepted", "query_total_count", "query_matched_count", "query_returned_count", "state", "accepted", "content_address")
SUMMARY_FIELDS = ("snapshot_id", "snapshot_address", "diff_id", "diff_address", "query_address", "query_audit_address", "left_snapshot_id", "right_snapshot_id", "direction", "state_transition", "diff_verified", "query_audit_accepted", "query_total_count", "query_matched_count", "query_returned_count", "state", "accepted", "content_address")
ARTIFACT_FIELDS = ("ordinal", "name", "size", "hash", "content_address")
MANIFEST_FIELDS = ("snapshot_id", "version", "boundary", "files", "artifacts", "snapshot_address", "manifest_address")
MAX_SNAPSHOT_BYTES = 128 * 1024 * 1024


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotArtifact:
    """One byte receipt for a persisted diff-query snapshot member."""

    FIELDS = ARTIFACT_FIELDS

    def __init__(self, ordinal: int, name: str, size: int, hash: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff-query snapshot artifact ordinal", len(ARTIFACT_FILES), positive=True)
        self.name = _label(name, "diff-query snapshot artifact name", required=True)
        if self.name not in ARTIFACT_FILES or self.ordinal != ARTIFACT_FILES.index(self.name) + 1:
            raise ValidationError("diff-query snapshot artifact order is not canonical")
        self.size = _count(size, "diff-query snapshot artifact size", MAX_SNAPSHOT_BYTES, positive=True)
        self.hash = _address(hash, "diff-query snapshot artifact hash", ARTIFACT_PREFIX)
        self.content_address = _address(content_address, "diff-query snapshot artifact address", ARTIFACT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("diff-query snapshot artifact crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_artifact(self) != self.content_address:
            raise ValidationError("diff-query snapshot artifact address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "diff-query snapshot artifact")
        _strict(value, set(cls.FIELDS), "diff-query snapshot artifact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_artifact(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotArtifact) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotArtifact):
        raise ValidationError("diff-query snapshot artifact address requires a typed artifact")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARTIFACT_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotManifest:
    """Canonical five-file boundary and byte receipts."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, snapshot_id: str, version: str, boundary: str, files: Sequence[str], artifacts: Sequence[Any], snapshot_address: str, manifest_address: str) -> None:
        self.snapshot_id = _label(snapshot_id, "diff-query snapshot manifest ID", required=True)
        self.version = _text(version, "diff-query snapshot manifest version", 512, required=True)
        self.boundary = _label(boundary, "diff-query snapshot manifest boundary", required=True)
        self.files = tuple(_label(item, "diff-query snapshot manifest file", required=True) for item in _sequence(files, "diff-query snapshot manifest files", len(FILES)))
        if self.files != FILES:
            raise ValidationError("diff-query snapshot manifest files are not canonical")
        self.artifacts = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotArtifact) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotArtifact.from_mapping(item) for item in _sequence(artifacts, "diff-query snapshot manifest artifacts", len(ARTIFACT_FILES)))
        if len(self.artifacts) != len(ARTIFACT_FILES) or tuple(item.name for item in self.artifacts) != ARTIFACT_FILES:
            raise ValidationError("diff-query snapshot manifest artifacts are incomplete")
        self.snapshot_address = _address(snapshot_address, "diff-query snapshot manifest snapshot address", SNAPSHOT_PREFIX)
        self.manifest_address = _address(manifest_address, "diff-query snapshot manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or not _public(self.to_dict()):
            raise ValidationError("diff-query snapshot manifest version or boundary is unsupported")
        if not self.manifest_address.endswith(":pending") and address_manifest(self) != self.manifest_address:
            raise ValidationError("diff-query snapshot manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, "version": self.version, "boundary": self.boundary, "files": self.files, "artifacts": tuple(item.to_dict() for item in self.artifacts), "snapshot_address": self.snapshot_address, "manifest_address": self.manifest_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "diff-query snapshot manifest")
        _strict(value, set(cls.FIELDS), "diff-query snapshot manifest")
        return cls(value["snapshot_id"], value["version"], value["boundary"], value["files"], value["artifacts"], value["snapshot_address"], value["manifest_address"])


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotManifest):
        raise ValidationError("diff-query snapshot manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"manifest_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotSummary:
    """Derived, compact review summary for a diff-query snapshot."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, snapshot_id: str, snapshot_address: str, diff_id: str, diff_address: str, query_address: str, query_audit_address: str, left_snapshot_id: str, right_snapshot_id: str, direction: str, state_transition: str, diff_verified: bool, query_audit_accepted: bool, query_total_count: int, query_matched_count: int, query_returned_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.snapshot_id = _label(snapshot_id, "diff-query snapshot summary ID", required=True)
        self.snapshot_address = _address(snapshot_address, "diff-query snapshot summary address", SNAPSHOT_PREFIX)
        self.diff_id = _label(diff_id, "diff-query snapshot summary diff ID", required=True)
        self.diff_address = _address(diff_address, "diff-query snapshot summary diff address", diff_model.DIFF_PREFIX)
        self.query_address = _address(query_address, "diff-query snapshot summary query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "diff-query snapshot summary query audit address", query_audit_model.AUDIT_PREFIX)
        self.left_snapshot_id = _label(left_snapshot_id, "diff-query snapshot summary left snapshot ID", required=True)
        self.right_snapshot_id = _label(right_snapshot_id, "diff-query snapshot summary right snapshot ID", required=True)
        self.direction = _label(direction, "diff-query snapshot summary direction", required=True)
        if self.direction not in diff_model.DIRECTIONS:
            raise ValidationError("diff-query snapshot summary direction is unsupported")
        self.state_transition = _label(state_transition, "diff-query snapshot summary state transition", required=True)
        self.diff_verified = _bool(diff_verified, "diff-query snapshot summary diff verification")
        self.query_audit_accepted = _bool(query_audit_accepted, "diff-query snapshot summary query audit acceptance")
        self.query_total_count = _count(query_total_count, "diff-query snapshot summary total count", query_model.MAX_TOTAL_COUNT)
        self.query_matched_count = _count(query_matched_count, "diff-query snapshot summary matched count", query_model.MAX_TOTAL_COUNT)
        self.query_returned_count = _count(query_returned_count, "diff-query snapshot summary returned count", query_model.MAX_LIMIT)
        self.state = _label(state, "diff-query snapshot summary state", required=True)
        if self.state not in STATES:
            raise ValidationError("diff-query snapshot summary state is unsupported")
        self.accepted = _bool(accepted, "diff-query snapshot summary acceptance")
        self.content_address = _address(content_address, "diff-query snapshot summary content address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.accepted != (self.diff_verified and self.query_audit_accepted) or self.state != ("ready" if self.accepted else "blocked") or self.query_matched_count > self.query_total_count or self.query_returned_count > self.query_matched_count or not _public(self.to_dict()):
            raise ValidationError("diff-query snapshot summary counters do not replay")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("diff-query snapshot summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "diff-query snapshot summary")
        _strict(value, set(cls.FIELDS), "diff-query snapshot summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotSummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotSummary):
        raise ValidationError("diff-query snapshot summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot:
    """A durable, reloadable query page over one verified snapshot diff."""

    FIELDS = SNAPSHOT_FIELDS

    def __init__(self, snapshot_id: str, version: str, boundary: str, diff_id: str, diff_address: str, query_address: str, query_audit_address: str, left_snapshot_id: str, right_snapshot_id: str, direction: str, state_transition: str, diff_verified: bool, query_audit_accepted: bool, query_total_count: int, query_matched_count: int, query_returned_count: int, state: str, accepted: bool, content_address: str, query: Any = None, query_audit: Any = None, summary: Any = None, manifest: Any = None) -> None:
        self.snapshot_id = _label(snapshot_id, "diff-query snapshot ID", required=True)
        self.version = _text(version, "diff-query snapshot version", 512, required=True)
        self.boundary = _label(boundary, "diff-query snapshot boundary", required=True)
        self.diff_id = _label(diff_id, "diff-query snapshot diff ID", required=True)
        self.diff_address = _address(diff_address, "diff-query snapshot diff address", diff_model.DIFF_PREFIX)
        self.query_address = _address(query_address, "diff-query snapshot query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "diff-query snapshot query audit address", query_audit_model.AUDIT_PREFIX)
        self.left_snapshot_id = _label(left_snapshot_id, "diff-query snapshot left snapshot ID", required=True)
        self.right_snapshot_id = _label(right_snapshot_id, "diff-query snapshot right snapshot ID", required=True)
        self.direction = _label(direction, "diff-query snapshot direction", required=True)
        if self.direction not in diff_model.DIRECTIONS:
            raise ValidationError("diff-query snapshot direction is unsupported")
        self.state_transition = _label(state_transition, "diff-query snapshot state transition", required=True)
        self.diff_verified = _bool(diff_verified, "diff-query snapshot diff verification")
        self.query_audit_accepted = _bool(query_audit_accepted, "diff-query snapshot query audit acceptance")
        self.query_total_count = _count(query_total_count, "diff-query snapshot total count", query_model.MAX_TOTAL_COUNT)
        self.query_matched_count = _count(query_matched_count, "diff-query snapshot matched count", query_model.MAX_TOTAL_COUNT)
        self.query_returned_count = _count(query_returned_count, "diff-query snapshot returned count", query_model.MAX_LIMIT)
        self.state = _label(state, "diff-query snapshot state", required=True)
        if self.state not in STATES:
            raise ValidationError("diff-query snapshot state is unsupported")
        self.accepted = _bool(accepted, "diff-query snapshot acceptance")
        self.content_address = _address(content_address, "diff-query snapshot content address", SNAPSHOT_PREFIX)
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
        if self.version != VERSION or self.boundary != BOUNDARY or self.accepted != (self.diff_verified and self.query_audit_accepted) or self.state != ("ready" if self.accepted else "blocked"):
            raise ValidationError("diff-query snapshot acceptance or version does not replay")
        if self.query is not None and (self.query.diff_id != self.diff_id or self.query.diff_address != self.diff_address or self.query.content_address != self.query_address):
            raise ValidationError("diff-query snapshot query linkage does not replay")
        if self.query_audit is not None and (self.query_audit.query_address != self.query_address or self.query_audit.content_address != self.query_audit_address or self.query_audit.accepted != self.query_audit_accepted):
            raise ValidationError("diff-query snapshot audit linkage does not replay")
        if self.query is not None and (self.query_total_count, self.query_matched_count, self.query_returned_count) != (self.query.total_count, self.query.matched_count, self.query.returned_count):
            raise ValidationError("diff-query snapshot query counts do not replay")
        if self.query is not None:
            source_rows = tuple(self.query.rows)
            if source_rows and any((row.left_snapshot_id, row.right_snapshot_id, row.direction, row.state_transition) != (self.left_snapshot_id, self.right_snapshot_id, self.direction, self.state_transition) for row in source_rows):
                raise ValidationError("diff-query snapshot source metadata does not replay")
        if self.summary is not None and (self.summary.snapshot_address, self.summary.diff_address, self.summary.query_address) != (self.content_address, self.diff_address, self.query_address):
            raise ValidationError("diff-query snapshot summary linkage does not replay")
        if self.manifest is not None and (self.manifest.snapshot_address, self.manifest.snapshot_id) != (self.content_address, self.snapshot_id):
            raise ValidationError("diff-query snapshot manifest linkage does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff-query snapshot crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_snapshot(self) != self.content_address:
            raise ValidationError("diff-query snapshot address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary_document(self) -> dict[str, Any]:
        return (self.summary if self.summary is not None else _build_summary(self)).to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "diff-query snapshot")
        _strict(value, set(cls.FIELDS), "diff-query snapshot")
        return cls(*(value[field] for field in cls.FIELDS))


def address_snapshot(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot):
        raise ValidationError("diff-query snapshot address requires a typed snapshot")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SNAPSHOT_PREFIX)


def _build_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot):
    body = {"snapshot_id": value.snapshot_id, "snapshot_address": value.content_address, "diff_id": value.diff_id, "diff_address": value.diff_address, "query_address": value.query_address, "query_audit_address": value.query_audit_address, "left_snapshot_id": value.left_snapshot_id, "right_snapshot_id": value.right_snapshot_id, "direction": value.direction, "state_transition": value.state_transition, "diff_verified": value.diff_verified, "query_audit_accepted": value.query_audit_accepted, "query_total_count": value.query_total_count, "query_matched_count": value.query_matched_count, "query_returned_count": value.query_returned_count, "state": value.state, "accepted": value.accepted, "content_address": SUMMARY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotSummary(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotSummary(**(body | {"content_address": address_summary(provisional)}))


def _documents(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot) -> dict[str, bytes]:
    if value.query is None or value.query_audit is None:
        raise ValidationError("diff-query snapshot persistence requires query and query audit receipts")
    summary = value.summary.to_dict() if value.summary is not None else _build_summary(value).to_dict()
    return {"snapshot.json": canonical_bytes(value.to_dict()), "query.json": canonical_bytes(value.query.to_dict()), "audit.json": canonical_bytes(value.query_audit.to_dict()), "summary.json": canonical_bytes(summary)}


def _build_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot):
    documents = _documents(value)
    receipts = []
    for ordinal, name in enumerate(ARTIFACT_FILES, 1):
        artifact = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotArtifact(ordinal, name, len(documents[name]), hash_bytes(documents[name], prefix=ARTIFACT_PREFIX), ARTIFACT_PREFIX + ":pending")
        receipts.append(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotArtifact(ordinal, name, artifact.size, artifact.hash, address_artifact(artifact)))
    body = {"snapshot_id": value.snapshot_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": tuple(receipts), "snapshot_address": value.content_address, "manifest_address": MANIFEST_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotManifest(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotManifest(**(body | {"manifest_address": address_manifest(provisional)}))


def build_snapshot(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff, *, snapshot_id: str = DEFAULT_SNAPSHOT_ID, **filters: Any):
    if not isinstance(value, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff):
        raise ValidationError("diff-query snapshot requires a typed snapshot diff")
    value = diff_model.diff_from_mapping(value.to_dict())
    diff_verified = True
    value = diff_model.diff_from_mapping(value.to_dict())
    query = query_model.query_diff(value, **filters)
    query_audit = query_audit_model.audit_query(query)
    body = {"snapshot_id": snapshot_id, "version": VERSION, "boundary": BOUNDARY, "diff_id": value.diff_id, "diff_address": value.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "left_snapshot_id": value.left_snapshot_id, "right_snapshot_id": value.right_snapshot_id, "direction": value.direction, "state_transition": value.state_transition, "diff_verified": diff_verified, "query_audit_accepted": query_audit.accepted, "query_total_count": query.total_count, "query_matched_count": query.matched_count, "query_returned_count": query.returned_count, "state": "ready" if diff_verified and query_audit.accepted else "blocked", "accepted": diff_verified and query_audit.accepted, "content_address": SNAPSHOT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot(**body)
    snapshot = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot(**(body | {"content_address": address_snapshot(provisional)}), query=query, query_audit=query_audit)
    summary = _build_summary(snapshot)
    manifest = _build_manifest(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot(**snapshot.to_dict(), query=query, query_audit=query_audit, summary=summary))
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot(**snapshot.to_dict(), query=query, query_audit=query_audit, summary=summary, manifest=manifest)


def verify_snapshot(value):
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot):
        raise ValidationError("diff-query snapshot verification requires a typed snapshot")
    value._validate()
    if not value.content_address.endswith(":pending") and address_snapshot(value) != value.content_address:
        raise ValidationError("diff-query snapshot address verification failed")
    return value


def snapshot_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot.from_mapping(value)


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
    lines = ["# Runtime Query Snapshot Diff Query Snapshot", "", f"- Snapshot: {mark}{value.snapshot_id}{mark}", f"- Diff: {mark}{value.diff_id}{mark}", f"- Rows: {mark}{value.query_returned_count}{mark} of {mark}{value.query_matched_count}{mark}", f"- Direction: {mark}{value.direction}{mark}", f"- State: {mark}{value.state}{mark}", f"- Accepted: {mark}{value.accepted}{mark}", f"- Address: {mark}{value.content_address}{mark}"]
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
        raise ValidationError("diff-query snapshot destination exists; explicit overwrite is required")
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
        raise ValidationError("diff-query snapshot could not be persisted atomically") from error
    return target


def _read_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = _mapping(json.loads(raw.decode("utf-8")), f"diff-query snapshot member {path.name}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"diff-query snapshot member {path.name} is not valid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"diff-query snapshot member {path.name} is not canonical")
    return value, raw


def load_snapshot(destination: str | Path):
    root = Path(destination)
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("diff-query snapshot source must be a regular directory")
    entries = tuple(root.iterdir())
    if tuple(sorted(item.name for item in entries)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in entries):
        raise ValidationError("diff-query snapshot directory has an unexpected file set")
    raw = {}
    member_bytes = {}
    for filename in FILES:
        raw[filename], member_bytes[filename] = _read_json(root / filename)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotManifest.from_mapping(raw["manifest.json"])
    snapshot = snapshot_from_mapping(raw["snapshot.json"])
    query = query_model.query_from_mapping(raw["query.json"])
    query_audit = query_audit_model.audit_from_mapping(raw["audit.json"])
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotSummary.from_mapping(raw["summary.json"])
    candidate = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot(**snapshot.to_dict(), query=query, query_audit=query_audit, summary=summary, manifest=manifest)
    expected_summary = _build_summary(candidate)
    expected_manifest = _build_manifest(candidate)
    if summary.to_dict() != expected_summary.to_dict() or manifest.to_dict() != expected_manifest.to_dict() or member_bytes["manifest.json"] != canonical_bytes(expected_manifest.to_dict()):
        raise ValidationError("diff-query snapshot manifest or summary does not replay")
    expected_members = {"manifest.json": canonical_bytes(expected_manifest.to_dict()), **_documents(candidate)}
    for filename in FILES:
        if member_bytes[filename] != expected_members[filename]:
            raise ValidationError(f"diff-query snapshot member {filename} does not replay")
    for receipt in manifest.artifacts:
        raw_bytes = expected_members[receipt.name]
        provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotArtifact(receipt.ordinal, receipt.name, len(raw_bytes), receipt.hash, ARTIFACT_PREFIX + ":pending")
        if receipt.size != len(raw_bytes) or receipt.hash != hash_bytes(raw_bytes, prefix=ARTIFACT_PREFIX) or receipt.content_address != address_artifact(provisional):
            raise ValidationError("diff-query snapshot artifact receipt does not replay")
    return verify_snapshot(candidate)


def run_snapshot(value: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiff | str | Path, *, snapshot_id: str = DEFAULT_SNAPSHOT_ID, destination: str | Path | None = None, overwrite: bool = False, **filters: Any):
    if isinstance(value, (str, Path)):
        value = diff_model.load_diff(value)
    snapshot = build_snapshot(value, snapshot_id=snapshot_id, **filters)
    if destination is not None:
        persist_snapshot(snapshot, destination, overwrite=overwrite)
    return snapshot


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff query snapshot manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"snapshot_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": list(ARTIFACT_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "size": {"type": "integer", "minimum": 1}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}, "content_address": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}, "minItems": len(ARTIFACT_FILES), "maxItems": len(ARTIFACT_FILES)}, "snapshot_address": {"type": "string", "pattern": "^" + SNAPSHOT_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff query snapshot summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"snapshot_id": {"type": "string"}, "snapshot_address": {"type": "string", "pattern": "^" + SNAPSHOT_PREFIX + ":"}, "diff_id": {"type": "string"}, "diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "query_audit_address": {"type": "string", "pattern": "^" + query_audit_model.AUDIT_PREFIX + ":"}, "left_snapshot_id": {"type": "string"}, "right_snapshot_id": {"type": "string"}, "direction": {"enum": list(diff_model.DIRECTIONS)}, "state_transition": {"type": "string"}, "diff_verified": {"type": "boolean"}, "query_audit_accepted": {"type": "boolean"}, "query_total_count": {"type": "integer", "minimum": 0}, "query_matched_count": {"type": "integer", "minimum": 0}, "query_returned_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + SUMMARY_PREFIX + ":"}}}


def snapshot_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime query snapshot diff query snapshot", "type": "object", "additionalProperties": False, "required": list(SNAPSHOT_FIELDS), "properties": {"snapshot_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "diff_id": {"type": "string"}, "diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "query_audit_address": {"type": "string", "pattern": "^" + query_audit_model.AUDIT_PREFIX + ":"}, "left_snapshot_id": {"type": "string"}, "right_snapshot_id": {"type": "string"}, "direction": {"enum": list(diff_model.DIRECTIONS)}, "state_transition": {"type": "string"}, "diff_verified": {"type": "boolean"}, "query_audit_accepted": {"type": "boolean"}, "query_total_count": {"type": "integer", "minimum": 0}, "query_matched_count": {"type": "integer", "minimum": 0}, "query_returned_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + SNAPSHOT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "snapshot_prefix": SNAPSHOT_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "artifact_prefix": ARTIFACT_PREFIX, "summary_prefix": SUMMARY_PREFIX, "files": list(FILES), "artifact_files": list(ARTIFACT_FILES), "states": list(STATES), "max_snapshot_bytes": MAX_SNAPSHOT_BYTES, "features": ["durable filtered diff-query handoffs", "query and audit linkage", "source diff address retention", "exact five-file persistence", "canonical JSON reload", "per-file byte receipts", "atomic writes", "fail-closed tamper detection", "JSON CSV and Markdown projections"]}


__all__ = ["ARTIFACT_FIELDS", "ARTIFACT_FILES", "ARTIFACT_PREFIX", "BOUNDARY", "DEFAULT_SNAPSHOT_ID", "FILES", "MANIFEST_FIELDS", "MANIFEST_PREFIX", "MAX_SNAPSHOT_BYTES", "SNAPSHOT_FIELDS", "SNAPSHOT_PREFIX", "STATES", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshot", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotArtifact", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotDiffQuerySnapshotSummary", "address_artifact", "address_manifest", "address_snapshot", "address_summary", "build_snapshot", "capabilities", "load_snapshot", "manifest_document", "manifest_schema", "persist_snapshot", "run_snapshot", "snapshot_csv", "snapshot_from_mapping", "snapshot_json", "snapshot_schema", "summary_document", "summary_schema", "render_snapshot_markdown", "verify_snapshot"]
