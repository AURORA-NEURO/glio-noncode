"""Exact-file offline runtime for downloaded-data quality decisions."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile as profile_model
from . import downloaded_data_quality as quality_model
from . import downloaded_data_quality_audit as audit_model
from . import downloaded_data_quality_query as query_model
from . import downloaded_data_quality_query_audit as query_audit_model
from ._safe_persistence import atomic_write_text, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = "downloaded-data-quality-runtime-v1"
BOUNDARY = "public_downloaded_data_quality_runtime"
RUNTIME_PREFIX = "glio-noncode-download-quality-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = "glio-noncode-downloaded-data-quality-runtime"
DEFAULT_LIMIT = 100
FILES = ("manifest.json", "policy.json", "quality.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("policy.json", "quality.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = (
    "runtime_id",
    "version",
    "boundary",
    "profile_address",
    "policy_address",
    "quality_address",
    "audit_address",
    "query_address",
    "query_audit_address",
    "record_count",
    "member_count",
    "field_count",
    "accepted",
    "release_ready",
    "state",
    "manifest",
    "policy",
    "quality",
    "audit",
    "query",
    "query_audit",
    "content_address",
)


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
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataQualityManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "quality runtime manifest ID")
        self.files = tuple(_label(item, "quality runtime manifest file") for item in _sequence(files, "quality runtime manifest files", len(FILES)))
        if self.files != FILES:
            raise ValidationError("quality runtime manifest files are not canonical")
        self.artifact_addresses = tuple(_address(item, "quality runtime artifact address") for item in _sequence(artifact_addresses, "quality runtime artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        if len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES):
            raise ValidationError("quality runtime manifest artifacts are incomplete")
        self.content_address = _address(content_address, "quality runtime manifest address", MANIFEST_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality runtime manifest address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality runtime manifest crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("quality runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataQualityManifest:
        value = _mapping(value, "downloaded data quality runtime manifest")
        _strict(value, set(cls.FIELDS), "downloaded data quality runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataQualityManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataQualityRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, profile_address: str, policy_address: str, quality_address: str, audit_address: str, query_address: str, query_audit_address: str, record_count: int, member_count: int, field_count: int, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataQualityManifest | Mapping[str, Any], policy: quality_model.DownloadedDataQualityPolicy | Mapping[str, Any], quality: quality_model.DownloadedDataQuality | Mapping[str, Any], audit: audit_model.DownloadedDataQualityAudit | Mapping[str, Any], query: query_model.DownloadedDataQualityQuery | Mapping[str, Any], query_audit: query_audit_model.DownloadedDataQualityQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "quality runtime ID")
        self.version = _text(version, "quality runtime version")
        self.boundary = _text(boundary, "quality runtime boundary", 512)
        self.profile_address = _address(profile_address, "quality runtime profile address", profile_model.PROFILE_PREFIX)
        self.policy_address = _address(policy_address, "quality runtime policy address", quality_model.POLICY_PREFIX)
        self.quality_address = _address(quality_address, "quality runtime quality address", quality_model.QUALITY_PREFIX)
        self.audit_address = _address(audit_address, "quality runtime audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "quality runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "quality runtime query audit address", query_audit_model.AUDIT_PREFIX)
        self.record_count = _count(record_count, "quality runtime record count", profile_model.MAX_RECORDS)
        self.member_count = _count(member_count, "quality runtime member count", profile_model.MAX_MEMBERS)
        self.field_count = _count(field_count, "quality runtime field count", profile_model.MAX_FIELDS)
        self.accepted = _bool(accepted, "quality runtime acceptance")
        self.release_ready = _bool(release_ready, "quality runtime release readiness")
        self.state = _label(state, "quality runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("quality runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataQualityManifest) else DownloadedDataQualityManifest.from_mapping(manifest)
        self.policy = policy if isinstance(policy, quality_model.DownloadedDataQualityPolicy) else quality_model.policy_from_mapping(policy)
        self.quality = quality if isinstance(quality, quality_model.DownloadedDataQuality) else quality_model.quality_from_mapping(quality)
        self.audit = audit if isinstance(audit, audit_model.DownloadedDataQualityAudit) else audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataQualityQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataQualityQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "quality runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality runtime address")
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality runtime version or boundary is not current")
        if self.profile_address != self.quality.profile_address or self.policy_address != self.policy.content_address or self.quality_address != self.quality.content_address or self.audit_address != self.audit.content_address or self.query_address != self.query.content_address or self.query_audit_address != self.query_audit.content_address:
            raise ValidationError("quality runtime lineage does not replay")
        if self.quality.policy.content_address != self.policy_address or self.audit.quality_address != self.quality_address or self.query.quality_address != self.quality_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("quality runtime component links do not replay")
        if self.record_count != self.quality.record_count or self.member_count != self.quality.member_count or self.field_count != self.quality.field_count:
            raise ValidationError("quality runtime aggregates do not replay")
        expected_accepted = self.quality.accepted and self.audit.accepted and self.query_audit.accepted
        if self.accepted != expected_accepted or self.release_ready != expected_accepted or (self.state == "complete") != expected_accepted:
            raise ValidationError("quality runtime readiness does not replay")
        if self.manifest.runtime_id != self.runtime_id or not _public(self.to_dict()):
            raise ValidationError("quality runtime manifest or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("quality runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "profile_address": self.profile_address, "policy_address": self.policy_address, "quality_address": self.quality_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "record_count": self.record_count, "member_count": self.member_count, "field_count": self.field_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "policy": self.policy.to_dict(), "quality": self.quality.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "policy", "quality", "audit", "query", "query_audit"}}
        summary["query_returned_count"] = self.query.returned_count
        summary["query_truncated"] = self.query.truncated
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataQualityRuntime:
        value = _mapping(value, "downloaded data quality runtime")
        _strict(value, set(cls.FIELDS), "downloaded data quality runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataQualityRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(profile: profile_model.DownloadedDataProfile, *, policy: quality_model.DownloadedDataQualityPolicy | Mapping[str, Any] | None = None, runtime_id: str = DEFAULT_RUNTIME_ID, result_id: str = "glio-noncode-downloaded-data-quality", resources: Sequence[str] = ("summary", "findings"), rule_id: str = "", scope: str = "", severity: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataQualityRuntime:
    if not isinstance(profile, profile_model.DownloadedDataProfile):
        raise ValidationError("quality runtime requires a typed structural profile")
    resolved_policy = policy if isinstance(policy, quality_model.DownloadedDataQualityPolicy) else (quality_model.build_policy() if policy is None else quality_model.policy_from_mapping(policy))
    quality = quality_model.build_quality(profile, policy=resolved_policy, result_id=result_id)
    audit = audit_model.audit_quality(quality)
    query = query_model.query_quality(quality, resources=resources, rule_id=rule_id, scope=scope, severity=severity, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (resolved_policy.content_address, quality.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataQualityManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataQualityManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    accepted = quality.accepted and audit.accepted and query_audit.accepted
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "profile_address": profile.content_address, "policy_address": resolved_policy.content_address, "quality_address": quality.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "record_count": profile.record_count, "member_count": profile.member_count, "field_count": profile.field_count, "accepted": accepted, "release_ready": accepted, "state": "complete" if accepted else "incomplete", "manifest": manifest, "policy": resolved_policy, "quality": quality, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataQualityRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataQualityRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityRuntime:
    return DownloadedDataQualityRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataQualityRuntime) -> str:
    return canonical_json(DownloadedDataQualityRuntime.from_mapping(value.to_dict()).to_dict())


def render_runtime_markdown(value: DownloadedDataQualityRuntime) -> str:
    value = DownloadedDataQualityRuntime.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Profile: `{value.profile_address}`", f"- Records: `{value.record_count}`", f"- Members: `{value.member_count}`", f"- Fields: `{value.field_count}`", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("policy", value.policy_address), ("quality", value.quality_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    atomic_write_text(path, canonical_json(value))


def persist_runtime(value: DownloadedDataQualityRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataQualityRuntime):
        raise ValidationError("quality runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or not overwrite):
        raise ValidationError("quality runtime destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-quality-runtime-", dir=str(parent)))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "policy.json", value.policy.to_dict())
        _write(temporary / "quality.json", value.quality.to_dict())
        _write(temporary / "audit.json", value.audit.to_dict())
        _write(temporary / "query.json", value.query.to_dict())
        _write(temporary / "query-audit.json", value.query_audit.to_dict())
        _write(temporary / "runtime.json", value.to_dict())
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("quality runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = _strict_json_loads(read_text(path, field="quality runtime artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("quality runtime artifact is not valid JSON") from error
    return _mapping(value, "quality runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataQualityRuntime:
    destination = Path(destination)
    if destination.is_symlink() or not destination.is_dir():
        raise ValidationError("quality runtime destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("quality runtime directory does not contain the exact file set")
    runtime = DownloadedDataQualityRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataQualityManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("quality runtime manifest differs from runtime.json")
    artifacts = {
        "policy.json": quality_model.policy_from_mapping(_read_json(destination / "policy.json")),
        "quality.json": quality_model.quality_from_mapping(_read_json(destination / "quality.json")),
        "audit.json": audit_model.audit_from_mapping(_read_json(destination / "audit.json")),
        "query.json": query_model.query_from_mapping(_read_json(destination / "query.json")),
        "query-audit.json": query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json")),
    }
    if tuple(value.content_address for value in artifacts.values()) != runtime.manifest.artifact_addresses:
        raise ValidationError("quality runtime manifest artifact addresses do not replay")
    if artifacts["policy.json"].to_dict() != runtime.policy.to_dict() or artifacts["quality.json"].to_dict() != runtime.quality.to_dict() or artifacts["audit.json"].to_dict() != runtime.audit.to_dict() or artifacts["query.json"].to_dict() != runtime.query.to_dict() or artifacts["query-audit.json"].to_dict() != runtime.query_audit.to_dict():
        raise ValidationError("quality runtime artifacts differ from runtime.json")
    return runtime


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "profile_address": {"type": "string"}, "policy_address": {"type": "string"}, "quality_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "record_count": {"type": "integer", "minimum": 0}, "member_count": {"type": "integer", "minimum": 0}, "field_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": {"type": "object"}, "policy": quality_model.policy_schema(), "quality": quality_model.quality_schema(), "audit": audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}, "artifact_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "persist_runtime", "load_runtime", "render_runtime_markdown"), "limits": {"max_query_limit": DEFAULT_LIMIT}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_FIELDS", "MANIFEST_PREFIX", "RUNTIME_FIELDS", "RUNTIME_PREFIX", "DownloadedDataQualityManifest", "DownloadedDataQualityRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "runtime_from_mapping", "runtime_json", "runtime_schema"]
