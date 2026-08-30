"""Persisted inspection runtime for policy package registry observatory archives.

This module composes the archive envelope, its independent audit, a bounded
archive query, and the independent query audit into one path-free handoff.
The optional directory form is an exact seven-file contract. Every JSON file
is canonical, every materialized member has a byte receipt, and reloads replay
the same addresses before a caller can consume the handoff.
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
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory as observatory_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive as archive_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_audit as archive_audit_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_query as query_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_query_audit as query_audit_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = query_audit_model.VERSION + "-runtime-v1"
BOUNDARY = archive_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = archive_model.ARCHIVE_PREFIX + "-runtime"
STAGE_PREFIX = RUNTIME_PREFIX + "-stage"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
ARTIFACT_PREFIX = RUNTIME_PREFIX + "-artifact"
DEFAULT_RUNTIME_ID = "policy-package-registry-observatory-archive-runtime"
DEFAULT_LIMIT = query_model.MAX_LIMIT
STAGES = ("load", "verify", "audit", "query", "query-audit", "complete")
STATES = ("empty", "ready", "blocked")
FILES = ("manifest.json", "runtime.json", "archive.json", "archive-audit.json", "query.json", "query-audit.json", "summary.json")
ARTIFACT_FILES = FILES[1:]
STAGE_FIELDS = ("ordinal", "stage", "state", "accepted", "address", "detail", "content_address")
MANIFEST_ARTIFACT_FIELDS = ("ordinal", "name", "size", "hash", "content_address")
MANIFEST_FIELDS = ("runtime_id", "version", "boundary", "files", "artifacts", "runtime_address", "manifest_address")
RUNTIME_FIELDS = ("runtime_id", "version", "boundary", "archive_id", "archive_address", "archive_audit_address", "query_address", "query_audit_address", "stage_count", "stages", "state", "accepted", "content_address")
MAX_RUNTIME_BYTES = 128 * 1024 * 1024


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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
    private_markers = ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\")
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.casefold()
        return not any(marker in lowered for marker in private_markers)
    return value is None or isinstance(value, (bool, int, float))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeStage:
    """One deterministic stage receipt in the inspection state machine."""

    FIELDS = STAGE_FIELDS

    def __init__(self, ordinal: int, stage: str, state: str, accepted: bool, address: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime stage ordinal", len(STAGES), positive=True)
        if stage not in STAGES:
            raise ValidationError("runtime stage is unsupported")
        self.stage = stage
        self.state = _label(state, "runtime stage state")
        if self.state not in STATES:
            raise ValidationError("runtime stage state is unsupported")
        self.accepted = _bool(accepted, "runtime stage acceptance")
        self.address = _address(address, "runtime stage detail address")
        self.detail = _text(detail, "runtime stage detail", 2048)
        if isinstance(content_address, str) and content_address.startswith("pending:"):
            self.content_address = _text(content_address, "runtime stage address")
        else:
            self.content_address = _address(content_address, "runtime stage address", STAGE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime stage crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_stage(self) != self.content_address:
            raise ValidationError("runtime stage address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "runtime stage")
        _strict(value, set(cls.FIELDS), "runtime stage")
        return cls(*(value[field] for field in cls.FIELDS))


def address_stage(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeStage) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeStage):
        raise ValidationError("runtime stage address requires a typed stage")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=STAGE_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeArtifact:
    """A byte receipt for one materialized runtime document."""

    FIELDS = MANIFEST_ARTIFACT_FIELDS

    def __init__(self, ordinal: int, name: str, size: int, hash: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime artifact ordinal", len(ARTIFACT_FILES), positive=True)
        self.name = _label(name, "runtime artifact name")
        if self.name not in ARTIFACT_FILES or self.ordinal != ARTIFACT_FILES.index(self.name) + 1:
            raise ValidationError("runtime artifact order is not exact")
        self.size = _count(size, "runtime artifact size", MAX_RUNTIME_BYTES, positive=True)
        self.hash = _address(hash, "runtime artifact hash", ARTIFACT_PREFIX)
        self.content_address = _text(content_address, "runtime artifact content address") if str(content_address).startswith("pending:") else _address(content_address, "runtime artifact content address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime artifact crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_artifact(self) != self.content_address:
            raise ValidationError("runtime artifact address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "runtime artifact")
        _strict(value, set(cls.FIELDS), "runtime artifact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_artifact(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeArtifact) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeArtifact):
        raise ValidationError("runtime artifact address requires a typed artifact")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARTIFACT_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeManifest:
    """Exact directory vocabulary and byte receipts for a runtime handoff."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, files: Sequence[str], artifacts: Sequence[Any], runtime_address: str, manifest_address: str) -> None:
        self.runtime_id = _label(runtime_id, "runtime manifest ID")
        self.version = _text(version, "runtime manifest version", 1024)
        self.boundary = _label(boundary, "runtime manifest boundary")
        self.files = tuple(_label(item, "runtime manifest file") for item in _sequence(files, "runtime manifest files", len(FILES)))
        if self.files != FILES:
            raise ValidationError("runtime manifest files are not canonical")
        self.artifacts = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeArtifact) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeArtifact.from_mapping(item) for item in _sequence(artifacts, "runtime manifest artifacts", len(ARTIFACT_FILES)))
        if len(self.artifacts) != len(ARTIFACT_FILES) or tuple(item.name for item in self.artifacts) != ARTIFACT_FILES:
            raise ValidationError("runtime manifest artifacts are incomplete or unordered")
        self.runtime_address = _address(runtime_address, "runtime manifest runtime address", RUNTIME_PREFIX)
        self.manifest_address = _text(manifest_address, "runtime manifest address") if str(manifest_address).startswith("pending:") else _address(manifest_address, "runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime manifest crosses the public boundary")
        if not self.manifest_address.startswith("pending:") and address_manifest(self) != self.manifest_address:
            raise ValidationError("runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "files": self.files, "artifacts": tuple(item.to_dict() for item in self.artifacts), "runtime_address": self.runtime_address, "manifest_address": self.manifest_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "runtime manifest")
        _strict(value, set(cls.FIELDS), "runtime manifest")
        return cls(value["runtime_id"], value["version"], value["boundary"], value["files"], value["artifacts"], value["runtime_address"], value["manifest_address"])


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeManifest):
        raise ValidationError("runtime manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"manifest_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime:
    """Joined archive, audit, query, query-audit, and stage receipt."""

    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, archive_id: str, archive_address: str, archive_audit_address: str, query_address: str, query_audit_address: str, stage_count: int, stages: Sequence[Any], state: str, accepted: bool, content_address: str, archive: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive | None = None, archive_audit: archive_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveAudit | None = None, query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery | None = None, query_audit: query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit | None = None) -> None:
        self.runtime_id = _label(runtime_id, "runtime ID")
        self.version = _text(version, "runtime version", 1024)
        self.boundary = _label(boundary, "runtime boundary")
        self.archive_id = _label(archive_id, "runtime archive ID")
        self.archive_address = _address(archive_address, "runtime archive address", archive_model.ARCHIVE_PREFIX)
        self.archive_audit_address = _address(archive_audit_address, "runtime archive audit address", archive_audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "runtime query audit address", query_audit_model.AUDIT_PREFIX)
        self.stage_count = _count(stage_count, "runtime stage count", len(STAGES), positive=True)
        self.stages = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeStage) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeStage.from_mapping(item) for item in _sequence(stages, "runtime stages", len(STAGES)))
        self.state = _label(state, "runtime state")
        if self.state not in STATES or self.state == "empty":
            raise ValidationError("runtime state is unsupported")
        self.accepted = _bool(accepted, "runtime acceptance")
        self.content_address = _text(content_address, "runtime address") if str(content_address).startswith("pending:") else _address(content_address, "runtime address", RUNTIME_PREFIX)
        self._archive = archive
        self._archive_audit = archive_audit
        self._query = query
        self._query_audit = query_audit
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime version or boundary is unsupported")
        if self.stage_count != len(STAGES) or len(self.stages) != len(STAGES) or tuple(item.ordinal for item in self.stages) != tuple(range(1, len(STAGES) + 1)) or tuple(item.stage for item in self.stages) != STAGES:
            raise ValidationError("runtime stages are incomplete or unordered")
        if self.state != ("ready" if self.accepted else "blocked"):
            raise ValidationError("runtime state does not replay acceptance")
        expected_addresses = (self.archive_address, self.archive_address, self.archive_audit_address, self.query_address, self.query_audit_address, self.query_audit_address)
        if tuple(item.address for item in self.stages) != expected_addresses:
            raise ValidationError("runtime stage addresses do not replay lineage")
        if any(item.state not in STATES for item in self.stages) or self.stages[0].state != "ready" or self.stages[1].state != "ready" or self.stages[0].accepted is not True or self.stages[1].accepted is not True or self.stages[3].state != "ready" or self.stages[3].accepted is not True:
            raise ValidationError("runtime load, verify, or query stage is not ready")
        if self.stages[2].accepted != self.accepted or self.stages[4].accepted != self.accepted or self.stages[5].accepted != self.accepted:
            raise ValidationError("runtime stage acceptance does not replay")
        if any(item.state != ("ready" if item.accepted else "blocked") for item in self.stages):
            raise ValidationError("runtime stage state does not replay acceptance")
        if self._archive is not None:
            archive_model.verify_archive(self._archive)
            if self._archive.archive_id != self.archive_id or self._archive.content_address != self.archive_address:
                raise ValidationError("runtime archive identity does not replay")
        if self._archive_audit is not None and (self._archive_audit.archive_address != self.archive_address or self._archive_audit.content_address != self.archive_audit_address):
            raise ValidationError("runtime archive audit linkage does not replay")
        if self._query is not None and (self._query.archive_address != self.archive_address or self._query.content_address != self.query_address):
            raise ValidationError("runtime query linkage does not replay")
        if self._query_audit is not None and (self._query_audit.query_address != self.query_address or self._query_audit.content_address != self.query_audit_address):
            raise ValidationError("runtime query audit linkage does not replay")
        if self._archive_audit is not None and self._query_audit is not None and self.accepted != (self._archive_audit.accepted and self._query_audit.accepted):
            raise ValidationError("runtime component acceptance does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_runtime(self) != self.content_address:
            raise ValidationError("runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "archive_id": self.archive_id, "archive_address": self.archive_address, "archive_audit_address": self.archive_audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "stage_count": self.stage_count, "stages": tuple(item.to_dict() for item in self.stages), "state": self.state, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        result = self.to_dict()
        result["stage_states"] = tuple({"stage": item.stage, "state": item.state, "accepted": item.accepted} for item in self.stages)
        if self._archive_audit is not None:
            result["archive_audit_check_count"] = self._archive_audit.check_count
            result["archive_audit_accepted"] = self._archive_audit.accepted
        if self._query is not None:
            result["query_total_count"] = self._query.total_count
            result["query_matched_count"] = self._query.matched_count
            result["query_returned_count"] = self._query.returned_count
        if self._query_audit is not None:
            result["query_audit_check_count"] = self._query_audit.check_count
            result["query_audit_accepted"] = self._query_audit.accepted
        return result

    @property
    def archive(self):
        return self._archive

    @property
    def archive_audit(self):
        return self._archive_audit

    @property
    def query(self):
        return self._query

    @property
    def query_audit(self):
        return self._query_audit

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "archive inspection runtime")
        _strict(value, set(cls.FIELDS), "archive inspection runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime):
        raise ValidationError("runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def _stage(ordinal: int, stage: str, accepted: bool, address: str, detail: str) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeStage:
    state = "ready" if accepted else "blocked"
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeStage(ordinal, stage, state, accepted, address, detail, "pending:stage")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeStage(ordinal, stage, state, accepted, address, detail, address_stage(provisional))


def _coerce_archive(source: str | Path | bytes | archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive, *, archive_id: str) -> archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive:
    if isinstance(source, archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive):
        return archive_model.verify_archive(source)
    if isinstance(source, bytes):
        return archive_model.load_archive(source)
    path = Path(source)
    if path.is_dir():
        return archive_model.build_archive_from_directory(path, archive_id=archive_id)
    if path.suffix.casefold() == ".zip":
        return archive_model.load_archive(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("runtime source is not a readable archive or observatory JSON") from error
    raw = _mapping(raw, "runtime source JSON")
    nested_archive = raw.get("archive")
    if isinstance(nested_archive, Mapping):
        return archive_model.archive_from_mapping(nested_archive)
    if "archive_id" in raw and "archive_size" in raw and "artifacts" in raw:
        return archive_model.archive_from_mapping(raw)
    nested_observatory = raw.get("observatory")
    observatory = observatory_model.observatory_from_mapping(nested_observatory if isinstance(nested_observatory, Mapping) else raw)
    return archive_model.build_archive(observatory, archive_id=archive_id)


def _build_stages(archive: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive, archive_audit: archive_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveAudit, query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery, query_audit: query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeStage, ...]:
    accepted = archive_audit.accepted and query_audit.accepted
    return (
        _stage(1, "load", True, archive.content_address, "archive input loaded and normalized"),
        _stage(2, "verify", True, archive.content_address, "archive envelope and byte model verified"),
        _stage(3, "audit", archive_audit.accepted, archive_audit.content_address, "independent archive audit completed"),
        _stage(4, "query", True, query.content_address, "bounded archive inspection query completed"),
        _stage(5, "query-audit", query_audit.accepted, query_audit.content_address, "independent query-result audit completed"),
        _stage(6, "complete", accepted, query_audit.content_address, "inspection handoff is ready for consumption" if accepted else "inspection handoff is blocked by an audit result"),
    )


def build_runtime(source: str | Path | bytes | archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive, *, runtime_id: str = DEFAULT_RUNTIME_ID, archive_id: str = archive_model.DEFAULT_ARCHIVE_ID, resources: Sequence[str] | None = None, name: str = "", hash: str = "", observatory_id: str = "", history_id: str = "", state: str = "", decision: str = "", accepted: bool | None = None, release_ready: bool | None = None, transition: str = "", trend: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime:
    archive = _coerce_archive(source, archive_id=archive_id)
    archive_audit = archive_audit_model.audit_archive(archive)
    query = query_model.query_archive(archive, resources=resources, name=name, hash=hash, observatory_id=observatory_id, history_id=history_id, state=state, decision=decision, accepted=accepted, release_ready=release_ready, transition=transition, trend=trend, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    stages = _build_stages(archive, archive_audit, query, query_audit)
    accepted_value = archive_audit.accepted and query_audit.accepted
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "archive_id": archive.archive_id, "archive_address": archive.content_address, "archive_audit_address": archive_audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "stage_count": len(STAGES), "stages": stages, "state": "ready" if accepted_value else "blocked", "accepted": accepted_value}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime(**body, content_address="pending:runtime", archive=archive, archive_audit=archive_audit, query=query, query_audit=query_audit)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime(**body, content_address=address_runtime(provisional), archive=archive, archive_audit=archive_audit, query=query, query_audit=query_audit)


def verify_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime):
        raise ValidationError("runtime verification requires a typed runtime")
    value._validate()
    if not value.content_address.startswith("pending:") and address_runtime(value) != value.content_address:
        raise ValidationError("runtime address verification failed")
    return value


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> str:
    return canonical_json(runtime_from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> str:
    value = verify_runtime(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=("runtime_id", "archive_id", "archive_address", "archive_audit_address", "query_address", "query_audit_address", "stage_count", "state", "accepted", "content_address"), lineterminator="\n")
    writer.writeheader()
    writer.writerow({field: value.to_dict()[field] for field in writer.fieldnames})
    return stream.getvalue()


def render_runtime_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> str:
    value = verify_runtime(value)
    lines = ["# Policy Package Registry Observatory Archive Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Archive: `{value.archive_id}`", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | stage | state | accepted | address |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.stage}` | `{item.state}` | `{item.accepted}` | `{item.address}` |" for item in value.stages)
    return "\n".join(lines) + "\n"


def _documents(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> dict[str, bytes]:
    if any(item is None for item in (value.archive, value.archive_audit, value.query, value.query_audit)):
        raise ValidationError("runtime persistence requires composed component receipts")
    return {
        "runtime.json": canonical_bytes(value.to_dict()),
        "archive.json": canonical_bytes(value.archive.to_dict()),
        "archive-audit.json": canonical_bytes(value.archive_audit.to_dict()),
        "query.json": canonical_bytes(value.query.to_dict()),
        "query-audit.json": canonical_bytes(value.query_audit.to_dict()),
        "summary.json": canonical_bytes(value.summary()),
    }


def _build_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeManifest:
    documents = _documents(value)
    receipts = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeArtifact(index, name, len(documents[name]), hash_bytes(documents[name], prefix=ARTIFACT_PREFIX), "pending:artifact") for index, name in enumerate(ARTIFACT_FILES, 1))
    # Artifact addresses are independent receipts; resolve each provisional address before building the manifest.
    receipts = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeArtifact(item.ordinal, item.name, item.size, item.hash, address_artifact(item)) for item in receipts)
    body = {"runtime_id": value.runtime_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": receipts, "runtime_address": value.content_address}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeManifest(**body, manifest_address="pending:manifest")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeManifest(**body, manifest_address=address_manifest(provisional))


def manifest_document(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> dict[str, Any]:
    return _build_manifest(verify_runtime(value)).to_dict()


def manifest_schema() -> dict[str, Any]:
    artifact = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime artifact", "type": "object", "additionalProperties": False, "required": list(MANIFEST_ARTIFACT_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "size": {"type": "integer", "minimum": 1}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}, "content_address": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "items": artifact, "minItems": len(ARTIFACT_FILES), "maxItems": len(ARTIFACT_FILES)}, "runtime_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def stage_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime stage", "type": "object", "additionalProperties": False, "required": list(STAGE_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": len(STAGES)}, "stage": {"type": "string", "enum": list(STAGES)}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "address": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + STAGE_PREFIX + ":"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive inspection runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "archive_id": {"type": "string"}, "archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "archive_audit_address": {"type": "string", "pattern": "^" + archive_audit_model.AUDIT_PREFIX + ":"}, "query_address": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}, "query_audit_address": {"type": "string", "pattern": "^" + query_audit_model.AUDIT_PREFIX + ":"}, "stage_count": {"type": "integer", "const": len(STAGES)}, "stages": {"type": "array", "items": stage_schema(), "minItems": len(STAGES), "maxItems": len(STAGES)}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "runtime_prefix": RUNTIME_PREFIX, "stage_prefix": STAGE_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "files": FILES, "stages": STAGES, "states": STATES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "manifest_document", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"default_limit": DEFAULT_LIMIT, "max_runtime_bytes": MAX_RUNTIME_BYTES}}


def _write(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)


def persist_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_runtime(value)
    documents = _documents(value)
    manifest = _build_manifest(value)
    members = {"manifest.json": canonical_bytes(manifest.to_dict()), **documents}
    target = Path(destination)
    if target.exists():
        if not overwrite:
            raise ValidationError("runtime destination exists; explicit overwrite is required")
        if target.is_symlink() or not target.is_dir():
            raise ValidationError("runtime destination must be a regular directory")
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
        raise ValidationError("runtime could not be persisted atomically") from error
    return target


def _read_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = _mapping(json.loads(raw.decode("utf-8")), f"runtime member {path.name}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"runtime member {path.name} is not valid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"runtime member {path.name} is not canonical")
    return value, raw


def _compose(runtime: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime, archive: archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive, archive_audit: archive_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveAudit, query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQuery, query_audit: query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveQueryAudit) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime:
    body = runtime.to_dict()
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime(**body, archive=archive, archive_audit=archive_audit, query=query, query_audit=query_audit)


def load_runtime(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime:
    root = Path(destination)
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("runtime source must be a regular directory")
    entries = tuple(root.iterdir())
    if tuple(sorted(item.name for item in entries)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in entries):
        raise ValidationError("runtime directory has an unexpected file set")
    manifest_raw, manifest_bytes = _read_json(root / "manifest.json")
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeManifest.from_mapping(manifest_raw)
    runtime_raw, _ = _read_json(root / "runtime.json")
    runtime = runtime_from_mapping(runtime_raw)
    archive_raw, _ = _read_json(root / "archive.json")
    archive = archive_model.archive_from_mapping(archive_raw)
    archive_audit_raw, _ = _read_json(root / "archive-audit.json")
    archive_audit = archive_audit_model.audit_from_mapping(archive_audit_raw)
    query_raw, _ = _read_json(root / "query.json")
    query = query_model.query_from_mapping(query_raw)
    query_audit_raw, _ = _read_json(root / "query-audit.json")
    query_audit = query_audit_model.audit_from_mapping(query_audit_raw)
    candidate = _compose(runtime, archive, archive_audit, query, query_audit)
    expected_manifest = _build_manifest(candidate)
    if manifest.to_dict() != expected_manifest.to_dict() or manifest_bytes != canonical_bytes(expected_manifest.to_dict()):
        raise ValidationError("runtime manifest does not replay")
    documents = _documents(candidate)
    expected_members = {"manifest.json": canonical_bytes(expected_manifest.to_dict()), **documents}
    for filename in FILES:
        actual = (root / filename).read_bytes()
        if actual != expected_members[filename]:
            raise ValidationError(f"runtime member {filename} does not replay")
    for receipt in manifest.artifacts:
        raw = expected_members[receipt.name]
        if receipt.size != len(raw) or receipt.hash != hash_bytes(raw, prefix=ARTIFACT_PREFIX) or receipt.content_address != address_artifact(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeArtifact(receipt.ordinal, receipt.name, len(raw), receipt.hash, "pending:artifact")):
            raise ValidationError("runtime artifact receipt does not replay")
    return verify_runtime(candidate)


def run_runtime(source: str | Path | bytes | archive_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive, *, runtime_id: str = DEFAULT_RUNTIME_ID, archive_id: str = archive_model.DEFAULT_ARCHIVE_ID, resources: Sequence[str] | None = None, name: str = "", hash: str = "", observatory_id: str = "", history_id: str = "", state: str = "", decision: str = "", accepted: bool | None = None, release_ready: bool | None = None, transition: str = "", trend: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime:
    if isinstance(source, (str, Path)) and Path(source).is_dir() and tuple(sorted(item.name for item in Path(source).iterdir())) == tuple(sorted(FILES)):
        value = load_runtime(source)
    else:
        value = build_runtime(source, runtime_id=runtime_id, archive_id=archive_id, resources=resources, name=name, hash=hash, observatory_id=observatory_id, history_id=history_id, state=state, decision=decision, accepted=accepted, release_ready=release_ready, transition=transition, trend=trend, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


__all__ = ["ARTIFACT_FILES", "ARTIFACT_PREFIX", "BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FIELDS", "MANIFEST_FIELDS", "MAX_RUNTIME_BYTES", "RUNTIME_FIELDS", "RUNTIME_PREFIX", "STAGE_FIELDS", "STAGE_PREFIX", "STAGES", "STATES", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeArtifact", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeStage", "address_artifact", "address_manifest", "address_runtime", "address_stage", "build_runtime", "capabilities", "load_runtime", "manifest_document", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema", "stage_schema", "verify_runtime", "VERSION"]
