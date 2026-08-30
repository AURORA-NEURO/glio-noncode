"""Persisted, auditable snapshots of archive-runtime query results."""

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
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime as runtime_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query as query_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_audit as query_audit_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = query_audit_model.VERSION + "-snapshot-v1"
BOUNDARY = query_model.BOUNDARY + "_snapshot"
SNAPSHOT_PREFIX = runtime_model.RUNTIME_PREFIX + "-query-snapshot"
MANIFEST_PREFIX = SNAPSHOT_PREFIX + "-manifest"
ARTIFACT_PREFIX = SNAPSHOT_PREFIX + "-artifact"
SUMMARY_PREFIX = SNAPSHOT_PREFIX + "-summary"
DEFAULT_SNAPSHOT_ID = "policy-package-registry-observatory-archive-runtime-query-snapshot"
STATES = ("ready", "blocked")
FILES = ("manifest.json", "snapshot.json", "query.json", "audit.json", "summary.json")
ARTIFACT_FILES = FILES[1:]
SNAPSHOT_FIELDS = ("snapshot_id", "version", "boundary", "runtime_id", "runtime_address", "query_address", "query_audit_address", "runtime_accepted", "query_audit_accepted", "query_total_count", "query_matched_count", "query_returned_count", "state", "accepted", "content_address")
SUMMARY_FIELDS = ("snapshot_id", "snapshot_address", "runtime_id", "runtime_address", "query_address", "query_audit_address", "runtime_accepted", "query_audit_accepted", "query_total_count", "query_matched_count", "query_returned_count", "state", "accepted", "content_address")
ARTIFACT_FIELDS = ("ordinal", "name", "size", "hash", "content_address")
MANIFEST_FIELDS = ("snapshot_id", "version", "boundary", "files", "artifacts", "snapshot_address", "manifest_address")
MAX_SNAPSHOT_BYTES = runtime_model.MAX_RUNTIME_BYTES


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 256, required=required)
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


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotArtifact:
    """One byte receipt for a persisted snapshot member."""

    FIELDS = ARTIFACT_FIELDS

    def __init__(self, ordinal: int, name: str, size: int, hash: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "snapshot artifact ordinal", len(ARTIFACT_FILES), positive=True)
        self.name = _label(name, "snapshot artifact name", required=True)
        if self.name not in ARTIFACT_FILES or self.ordinal != ARTIFACT_FILES.index(self.name) + 1:
            raise ValidationError("snapshot artifact order is not canonical")
        self.size = _count(size, "snapshot artifact size", MAX_SNAPSHOT_BYTES, positive=True)
        self.hash = _address(hash, "snapshot artifact hash", ARTIFACT_PREFIX)
        self.content_address = _address(content_address, "snapshot artifact address", ARTIFACT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("snapshot artifact crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_artifact(self) != self.content_address:
            raise ValidationError("snapshot artifact address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot artifact")
        _strict(value, set(cls.FIELDS), "snapshot artifact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_artifact(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotArtifact) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotArtifact):
        raise ValidationError("snapshot artifact address requires a typed artifact")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARTIFACT_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotManifest:
    """Exact file vocabulary and receipts for a query snapshot."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, snapshot_id: str, version: str, boundary: str, files: Sequence[str], artifacts: Sequence[Any], snapshot_address: str, manifest_address: str) -> None:
        self.snapshot_id = _label(snapshot_id, "snapshot manifest ID", required=True)
        self.version = _text(version, "snapshot manifest version")
        self.boundary = _label(boundary, "snapshot manifest boundary", required=True)
        self.files = tuple(_label(item, "snapshot manifest file", required=True) for item in _sequence(files, "snapshot manifest files", len(FILES)))
        if self.files != FILES:
            raise ValidationError("snapshot manifest files are not canonical")
        self.artifacts = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotArtifact) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotArtifact.from_mapping(item) for item in _sequence(artifacts, "snapshot manifest artifacts", len(ARTIFACT_FILES)))
        if len(self.artifacts) != len(ARTIFACT_FILES) or tuple(item.name for item in self.artifacts) != ARTIFACT_FILES:
            raise ValidationError("snapshot manifest artifacts are incomplete")
        self.snapshot_address = _address(snapshot_address, "snapshot manifest snapshot address", SNAPSHOT_PREFIX)
        self.manifest_address = _address(manifest_address, "snapshot manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or not _public(self.to_dict()):
            raise ValidationError("snapshot manifest version or boundary is unsupported")
        if not self.manifest_address.endswith(":pending") and address_manifest(self) != self.manifest_address:
            raise ValidationError("snapshot manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, "version": self.version, "boundary": self.boundary, "files": self.files, "artifacts": tuple(item.to_dict() for item in self.artifacts), "snapshot_address": self.snapshot_address, "manifest_address": self.manifest_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot manifest")
        _strict(value, set(cls.FIELDS), "snapshot manifest")
        return cls(value["snapshot_id"], value["version"], value["boundary"], value["files"], value["artifacts"], value["snapshot_address"], value["manifest_address"])


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotManifest):
        raise ValidationError("snapshot manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"manifest_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotSummary:
    """Derived summary for review interfaces."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, snapshot_id: str, snapshot_address: str, runtime_id: str, runtime_address: str, query_address: str, query_audit_address: str, runtime_accepted: bool, query_audit_accepted: bool, query_total_count: int, query_matched_count: int, query_returned_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.snapshot_id = _label(snapshot_id, "snapshot summary ID", required=True)
        self.snapshot_address = _address(snapshot_address, "snapshot summary address", SNAPSHOT_PREFIX)
        self.runtime_id = _label(runtime_id, "snapshot summary runtime ID", required=True)
        self.runtime_address = _address(runtime_address, "snapshot summary runtime address", runtime_model.RUNTIME_PREFIX)
        self.query_address = _address(query_address, "snapshot summary query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "snapshot summary query audit address", query_audit_model.AUDIT_PREFIX)
        self.runtime_accepted = _bool(runtime_accepted, "snapshot summary runtime acceptance")
        self.query_audit_accepted = _bool(query_audit_accepted, "snapshot summary query audit acceptance")
        self.query_total_count = _count(query_total_count, "snapshot summary query total count", query_model.MAX_TOTAL_COUNT)
        self.query_matched_count = _count(query_matched_count, "snapshot summary query matched count", query_model.MAX_TOTAL_COUNT)
        self.query_returned_count = _count(query_returned_count, "snapshot summary query returned count", query_model.MAX_LIMIT)
        self.state = _label(state, "snapshot summary state", required=True)
        if self.state not in STATES:
            raise ValidationError("snapshot summary state is unsupported")
        self.accepted = _bool(accepted, "snapshot summary acceptance")
        self.content_address = _address(content_address, "snapshot summary content address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.accepted != (self.runtime_accepted and self.query_audit_accepted) or self.state != ("ready" if self.accepted else "blocked") or self.query_matched_count > self.query_total_count or self.query_returned_count > self.query_matched_count or not _public(self.to_dict()):
            raise ValidationError("snapshot summary counters do not replay")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("snapshot summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "snapshot summary")
        _strict(value, set(cls.FIELDS), "snapshot summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotSummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotSummary):
        raise ValidationError("snapshot summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot:
    """A reloadable query-result snapshot over a runtime."""

    FIELDS = SNAPSHOT_FIELDS

    def __init__(self, snapshot_id: str, version: str, boundary: str, runtime_id: str, runtime_address: str, query_address: str, query_audit_address: str, runtime_accepted: bool, query_audit_accepted: bool, query_total_count: int, query_matched_count: int, query_returned_count: int, state: str, accepted: bool, content_address: str, query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery | None = None, query_audit: query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryAudit | None = None, summary: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotSummary | None = None, manifest: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotManifest | None = None) -> None:
        self.snapshot_id = _label(snapshot_id, "snapshot ID", required=True)
        self.version = _text(version, "snapshot version")
        self.boundary = _label(boundary, "snapshot boundary", required=True)
        self.runtime_id = _label(runtime_id, "snapshot runtime ID", required=True)
        self.runtime_address = _address(runtime_address, "snapshot runtime address", runtime_model.RUNTIME_PREFIX)
        self.query_address = _address(query_address, "snapshot query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "snapshot query audit address", query_audit_model.AUDIT_PREFIX)
        self.runtime_accepted = _bool(runtime_accepted, "snapshot runtime acceptance")
        self.query_audit_accepted = _bool(query_audit_accepted, "snapshot query audit acceptance")
        self.query_total_count = _count(query_total_count, "snapshot query total count", query_model.MAX_TOTAL_COUNT)
        self.query_matched_count = _count(query_matched_count, "snapshot query matched count", query_model.MAX_TOTAL_COUNT)
        self.query_returned_count = _count(query_returned_count, "snapshot query returned count", query_model.MAX_LIMIT)
        self.state = _label(state, "snapshot state", required=True)
        if self.state not in STATES:
            raise ValidationError("snapshot state is unsupported")
        self.accepted = _bool(accepted, "snapshot acceptance")
        self.content_address = _address(content_address, "snapshot content address", SNAPSHOT_PREFIX)
        self._query = query
        self._query_audit = query_audit
        self._summary = summary
        self._manifest = manifest
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.accepted != (self.runtime_accepted and self.query_audit_accepted) or self.state != ("ready" if self.accepted else "blocked"):
            raise ValidationError("snapshot acceptance or version does not replay")
        if self.query is not None and (self.query.runtime_address != self.runtime_address or self.query.runtime_id != self.runtime_id or self.query.content_address != self.query_address):
            raise ValidationError("snapshot query linkage does not replay")
        if self.query_audit is not None and (self.query_audit.query_address != self.query_address or self.query_audit.content_address != self.query_audit_address):
            raise ValidationError("snapshot query audit linkage does not replay")
        if self.query is not None and (self.query_total_count, self.query_matched_count, self.query_returned_count) != (self.query.total_count, self.query.matched_count, self.query.returned_count):
            raise ValidationError("snapshot query counts do not replay")
        if self.summary is not None and (self.summary.snapshot_address, self.summary.runtime_address, self.summary.query_address) != (self.content_address, self.runtime_address, self.query_address):
            raise ValidationError("snapshot summary linkage does not replay")
        if self.manifest is not None and (self.manifest.snapshot_address, self.manifest.snapshot_id) != (self.content_address, self.snapshot_id):
            raise ValidationError("snapshot manifest linkage does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("snapshot crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_snapshot(self) != self.content_address:
            raise ValidationError("snapshot address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary_document(self) -> dict[str, Any]:
        return self.summary.to_dict() if self.summary is not None else _build_summary(self).to_dict()

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

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "runtime query snapshot")
        _strict(value, set(cls.FIELDS), "runtime query snapshot")
        return cls(*(value[field] for field in cls.FIELDS))


def address_snapshot(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot):
        raise ValidationError("snapshot address requires a typed snapshot")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SNAPSHOT_PREFIX)


def _build_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotSummary:
    body = {"snapshot_id": value.snapshot_id, "snapshot_address": value.content_address, "runtime_id": value.runtime_id, "runtime_address": value.runtime_address, "query_address": value.query_address, "query_audit_address": value.query_audit_address, "runtime_accepted": value.runtime_accepted, "query_audit_accepted": value.query_audit_accepted, "query_total_count": value.query_total_count, "query_matched_count": value.query_matched_count, "query_returned_count": value.query_returned_count, "state": value.state, "accepted": value.accepted, "content_address": SUMMARY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotSummary(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotSummary(**(body | {"content_address": address_summary(provisional)}))


def _documents(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> dict[str, bytes]:
    if value.query is None or value.query_audit is None:
        raise ValidationError("snapshot persistence requires query and query audit receipts")
    summary = value.summary.to_dict() if value.summary is not None else _build_summary(value).to_dict()
    return {"snapshot.json": canonical_bytes(value.to_dict()), "query.json": canonical_bytes(value.query.to_dict()), "audit.json": canonical_bytes(value.query_audit.to_dict()), "summary.json": canonical_bytes(summary)}


def _build_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotManifest:
    documents = _documents(value)
    receipts = []
    for ordinal, name in enumerate(ARTIFACT_FILES, 1):
        artifact = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotArtifact(ordinal, name, len(documents[name]), hash_bytes(documents[name], prefix=ARTIFACT_PREFIX), ARTIFACT_PREFIX + ":pending")
        receipts.append(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotArtifact(ordinal, name, artifact.size, artifact.hash, address_artifact(artifact)))
    body = {"snapshot_id": value.snapshot_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": tuple(receipts), "snapshot_address": value.content_address, "manifest_address": MANIFEST_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotManifest(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotManifest(**(body | {"manifest_address": address_manifest(provisional)}))


def build_snapshot(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime | query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery, *, snapshot_id: str = DEFAULT_SNAPSHOT_ID, **filters: Any) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot:
    runtime_accepted = True
    if isinstance(value, runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime):
        runtime_accepted = value.accepted
        query = query_model.query_runtime(value, **filters)
    elif isinstance(value, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery):
        query = query_model.query_from_mapping(value.to_dict())
        if filters:
            raise ValidationError("snapshot filters require a typed runtime source")
    else:
        raise ValidationError("snapshot requires a typed runtime or runtime query")
    query_audit = query_audit_model.audit_query(query)
    body = {"snapshot_id": snapshot_id, "version": VERSION, "boundary": BOUNDARY, "runtime_id": query.runtime_id, "runtime_address": query.runtime_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "runtime_accepted": runtime_accepted, "query_audit_accepted": query_audit.accepted, "query_total_count": query.total_count, "query_matched_count": query.matched_count, "query_returned_count": query.returned_count, "state": "ready" if runtime_accepted and query_audit.accepted else "blocked", "accepted": runtime_accepted and query_audit.accepted, "content_address": SNAPSHOT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot(**body)
    snapshot = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot(**(body | {"content_address": address_snapshot(provisional)}), query=query, query_audit=query_audit)
    summary = _build_summary(snapshot)
    manifest = _build_manifest(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot(**snapshot.to_dict(), query=query, query_audit=query_audit, summary=summary))
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot(**snapshot.to_dict(), query=query, query_audit=query_audit, summary=summary, manifest=manifest)


def verify_snapshot(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot):
        raise ValidationError("snapshot verification requires a typed snapshot")
    value._validate()
    if not value.content_address.endswith(":pending") and address_snapshot(value) != value.content_address:
        raise ValidationError("snapshot address verification failed")
    return value


def snapshot_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot.from_mapping(value)


def snapshot_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> str:
    return canonical_json(snapshot_from_mapping(value.to_dict()).to_dict())


def snapshot_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> str:
    value = verify_snapshot(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=SNAPSHOT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(value.to_dict())
    return stream.getvalue()


def render_snapshot_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> str:
    value = verify_snapshot(value)
    mark = chr(96)
    lines = ["# Policy Package Registry Observatory Archive Runtime Query Snapshot", "", f"- Snapshot: {mark}{value.snapshot_id}{mark}", f"- Runtime: {mark}{value.runtime_id}{mark}", f"- Rows: {mark}{value.query_returned_count}{mark} of {mark}{value.query_matched_count}{mark}", f"- State: {mark}{value.state}{mark}", f"- Accepted: {mark}{value.accepted}{mark}", f"- Address: {mark}{value.content_address}{mark}"]
    return "\n".join(lines) + "\n"


def manifest_document(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> dict[str, Any]:
    return _build_manifest(verify_snapshot(value)).to_dict()


def summary_document(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot) -> dict[str, Any]:
    return _build_summary(verify_snapshot(value)).to_dict()


def _write(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)


def persist_snapshot(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_snapshot(value)
    documents = _documents(value)
    manifest = _build_manifest(value)
    members = {"manifest.json": canonical_bytes(manifest.to_dict()), **documents}
    target = Path(destination)
    if target.exists():
        if target.is_symlink() or not target.is_dir() or not overwrite:
            raise ValidationError("snapshot destination exists; explicit overwrite is required")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
    try:
        for filename in FILES:
            _write(temporary / filename, members[filename])
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("snapshot could not be persisted atomically") from error
    return target


def _read_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = _mapping(json.loads(raw.decode("utf-8")), f"snapshot member {path.name}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"snapshot member {path.name} is not valid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"snapshot member {path.name} is not canonical")
    return value, raw


def load_snapshot(destination: str | Path):
    root = Path(destination)
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("snapshot source must be a regular directory")
    entries = tuple(root.iterdir())
    if tuple(sorted(item.name for item in entries)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in entries):
        raise ValidationError("snapshot directory has an unexpected file set")
    manifest_raw, manifest_bytes = _read_json(root / "manifest.json")
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotManifest.from_mapping(manifest_raw)
    snapshot_raw, _ = _read_json(root / "snapshot.json")
    snapshot = snapshot_from_mapping(snapshot_raw)
    query_raw, _ = _read_json(root / "query.json")
    query = query_model.query_from_mapping(query_raw)
    audit_raw, _ = _read_json(root / "audit.json")
    query_audit = query_audit_model.audit_from_mapping(audit_raw)
    summary_raw, _ = _read_json(root / "summary.json")
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotSummary.from_mapping(summary_raw)
    candidate = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot(**snapshot.to_dict(), query=query, query_audit=query_audit, summary=summary, manifest=manifest)
    expected_summary = _build_summary(candidate)
    expected_manifest = _build_manifest(candidate)
    if summary.to_dict() != expected_summary.to_dict() or manifest.to_dict() != expected_manifest.to_dict() or manifest_bytes != canonical_bytes(expected_manifest.to_dict()):
        raise ValidationError("snapshot manifest or summary does not replay")
    documents = _documents(candidate)
    expected_members = {"manifest.json": canonical_bytes(expected_manifest.to_dict()), **documents}
    for filename in FILES:
        if (root / filename).read_bytes() != expected_members[filename]:
            raise ValidationError(f"snapshot member {filename} does not replay")
    for receipt in manifest.artifacts:
        raw = expected_members[receipt.name]
        if receipt.size != len(raw) or receipt.hash != hash_bytes(raw, prefix=ARTIFACT_PREFIX) or receipt.content_address != address_artifact(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotArtifact(receipt.ordinal, receipt.name, len(raw), receipt.hash, ARTIFACT_PREFIX + ":pending")):
            raise ValidationError("snapshot artifact receipt does not replay")
    return verify_snapshot(candidate)


def run_snapshot(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime | query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery | str | Path, *, snapshot_id: str = DEFAULT_SNAPSHOT_ID, destination: str | Path | None = None, overwrite: bool = False, **filters: Any):
    if isinstance(value, (str, Path)):
        value = runtime_model.load_runtime(value)
    snapshot = build_snapshot(value, snapshot_id=snapshot_id, **filters)
    if destination is not None:
        persist_snapshot(snapshot, destination, overwrite=overwrite)
    return snapshot


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"snapshot_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": list(ARTIFACT_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "size": {"type": "integer", "minimum": 1}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}, "content_address": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}, "minItems": len(ARTIFACT_FILES), "maxItems": len(ARTIFACT_FILES)}, "snapshot_address": {"type": "string", "pattern": "^" + SNAPSHOT_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"snapshot_id": {"type": "string"}, "snapshot_address": {"type": "string", "pattern": "^" + SNAPSHOT_PREFIX + ":"}, "runtime_id": {"type": "string"}, "runtime_address": {"type": "string", "pattern": "^" + runtime_model.RUNTIME_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "query_audit_address": {"type": "string", "pattern": "^" + query_audit_model.AUDIT_PREFIX + ":"}, "runtime_accepted": {"type": "boolean"}, "query_audit_accepted": {"type": "boolean"}, "query_total_count": {"type": "integer", "minimum": 0}, "query_matched_count": {"type": "integer", "minimum": 0}, "query_returned_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + SUMMARY_PREFIX + ":"}}}


def snapshot_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query snapshot", "type": "object", "additionalProperties": False, "required": list(SNAPSHOT_FIELDS), "properties": {"snapshot_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "runtime_id": {"type": "string"}, "runtime_address": {"type": "string", "pattern": "^" + runtime_model.RUNTIME_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "query_audit_address": {"type": "string", "pattern": "^" + query_audit_model.AUDIT_PREFIX + ":"}, "runtime_accepted": {"type": "boolean"}, "query_audit_accepted": {"type": "boolean"}, "query_total_count": {"type": "integer", "minimum": 0}, "query_matched_count": {"type": "integer", "minimum": 0}, "query_returned_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + SNAPSHOT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "snapshot_prefix": SNAPSHOT_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "summary_prefix": SUMMARY_PREFIX, "files": list(FILES), "artifact_files": list(ARTIFACT_FILES), "operations": ["build_snapshot", "snapshot_from_mapping", "snapshot_json", "snapshot_csv", "render_snapshot_markdown", "manifest_document", "summary_document", "persist_snapshot", "load_snapshot", "run_snapshot"], "features": ["exact five-file persistence", "canonical JSON reload", "per-file byte receipts", "atomic writes", "query and audit linkage", "runtime acceptance folding", "fail-closed tamper detection", "JSON CSV and Markdown projections"]}


__all__ = ["ARTIFACT_FIELDS", "ARTIFACT_FILES", "ARTIFACT_PREFIX", "BOUNDARY", "DEFAULT_SNAPSHOT_ID", "FILES", "MANIFEST_FIELDS", "MANIFEST_PREFIX", "MAX_SNAPSHOT_BYTES", "SNAPSHOT_FIELDS", "SNAPSHOT_PREFIX", "STATES", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshot", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotArtifact", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuerySnapshotSummary", "address_artifact", "address_manifest", "address_snapshot", "address_summary", "build_snapshot", "capabilities", "load_snapshot", "manifest_document", "manifest_schema", "persist_snapshot", "run_snapshot", "snapshot_csv", "snapshot_from_mapping", "snapshot_json", "snapshot_schema", "summary_document", "summary_schema", "render_snapshot_markdown", "verify_snapshot"]
