"""Exact-file offline runtime for downloaded-data structural profiles."""

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
from . import downloaded_data_profile_audit as audit_model
from . import downloaded_data_profile_query as query_model
from . import downloaded_data_profile_query_audit as query_audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-runtime-v1"
BOUNDARY = "public_downloaded_data_profile_runtime"
RUNTIME_PREFIX = "glio-noncode-download-profile-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = "glio-noncode-downloaded-data-profile-runtime"
DEFAULT_LIMIT = 100
FILES = ("manifest.json", "profile.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("profile.json", "audit.json", "query.json", "query-audit.json")
RUNTIME_FIELDS = (
    "runtime_id",
    "version",
    "boundary",
    "batch_address",
    "profile_address",
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
    "profile",
    "audit",
    "query",
    "query_audit",
    "content_address",
)
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")


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


class DownloadedDataProfileManifest:
    """Manifest for the exact six-file profile runtime."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "profile runtime manifest ID")
        self.files = tuple(_label(item, "profile runtime manifest file") for item in _sequence(files, "profile runtime manifest files", len(FILES)))
        if self.files != FILES:
            raise ValidationError("profile runtime manifest files are not canonical")
        self.artifact_addresses = tuple(_address(item, "profile runtime artifact address") for item in _sequence(artifact_addresses, "profile runtime artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        if len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES):
            raise ValidationError("profile runtime manifest artifacts are incomplete")
        self.content_address = _address(content_address, "profile runtime manifest address", MANIFEST_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "profile runtime manifest address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("profile runtime manifest crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("profile runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileManifest:
        value = _mapping(value, "profile runtime manifest")
        _strict(value, set(cls.FIELDS), "profile runtime manifest")
        return cls(value["runtime_id"], value["files"], value["artifact_addresses"], value["content_address"])


def address_manifest(value: DownloadedDataProfileManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileRuntime:
    """Joined profile, audits, query, and exact-file manifest."""

    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, batch_address: str, profile_address: str, audit_address: str, query_address: str, query_audit_address: str, record_count: int, member_count: int, field_count: int, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataProfileManifest | Mapping[str, Any], profile: profile_model.DownloadedDataProfile | Mapping[str, Any], audit: audit_model.DownloadedDataProfileAudit | Mapping[str, Any], query: query_model.DownloadedDataProfileQuery | Mapping[str, Any], query_audit: query_audit_model.DownloadedDataProfileQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "profile runtime ID")
        self.version = _text(version, "profile runtime version")
        self.boundary = _text(boundary, "profile runtime boundary", 512)
        self.batch_address = _address(batch_address, "profile runtime batch address", ingestion_model.INGEST_PREFIX)
        self.profile_address = _address(profile_address, "profile runtime profile address", profile_model.PROFILE_PREFIX)
        self.audit_address = _address(audit_address, "profile runtime audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "profile runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "profile runtime query audit address", query_audit_model.AUDIT_PREFIX)
        self.record_count = _count(record_count, "profile runtime record count", profile_model.MAX_RECORDS)
        self.member_count = _count(member_count, "profile runtime member count", profile_model.MAX_MEMBERS)
        self.field_count = _count(field_count, "profile runtime field count", profile_model.MAX_FIELDS)
        self.accepted = _bool(accepted, "profile runtime acceptance")
        self.release_ready = _bool(release_ready, "profile runtime release readiness")
        self.state = _label(state, "profile runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("profile runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileManifest) else DownloadedDataProfileManifest.from_mapping(manifest)
        self.profile = profile if isinstance(profile, profile_model.DownloadedDataProfile) else profile_model.profile_from_mapping(profile)
        self.audit = audit if isinstance(audit, audit_model.DownloadedDataProfileAudit) else audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataProfileQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataProfileQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "profile runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "profile runtime address")
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("profile runtime version or boundary is not current")
        if self.batch_address != self.profile.batch_address or self.profile_address != self.profile.content_address or self.audit_address != self.audit.content_address or self.query_address != self.query.content_address or self.query_audit_address != self.query_audit.content_address:
            raise ValidationError("profile runtime lineage does not replay")
        if self.query.profile_address != self.profile_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("profile runtime component links do not replay")
        if self.record_count != self.profile.record_count or self.member_count != self.profile.member_count or self.field_count != self.profile.field_count:
            raise ValidationError("profile runtime aggregates do not replay")
        if self.accepted != (self.audit.accepted and self.query_audit.accepted) or self.release_ready != self.accepted or (self.state == "complete") != self.release_ready:
            raise ValidationError("profile runtime readiness does not replay")
        if self.manifest.runtime_id != self.runtime_id or not _public(self.to_dict()):
            raise ValidationError("profile runtime manifest or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("profile runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "batch_address": self.batch_address, "profile_address": self.profile_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "record_count": self.record_count, "member_count": self.member_count, "field_count": self.field_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "profile": self.profile.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "profile", "audit", "query", "query_audit"}}
        summary["query_returned_count"] = self.query.returned_count
        summary["query_truncated"] = self.query.truncated
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileRuntime:
        value = _mapping(value, "downloaded data profile runtime")
        _strict(value, set(cls.FIELDS), "downloaded data profile runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataProfileRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(batch: ingestion_model.DownloadedDataIngestBatch, *, runtime_id: str = DEFAULT_RUNTIME_ID, profile_id: str = "glio-noncode-downloaded-data-profile", resources: Sequence[str] = ("summary", "members", "fields", "types"), member_name: str = "", data_kind: str = "", field_name: str = "", value_type: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataProfileRuntime:
    if not isinstance(batch, ingestion_model.DownloadedDataIngestBatch):
        raise ValidationError("profile runtime requires a typed ingestion batch")
    profile = profile_model.build_profile(batch, profile_id=profile_id)
    audit = audit_model.audit_profile(profile)
    query = query_model.query_profile(profile, resources=resources, member_name=member_name, data_kind=data_kind, field_name=field_name, value_type=value_type, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (profile.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataProfileManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataProfileManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "batch_address": batch.content_address, "profile_address": profile.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "record_count": profile.record_count, "member_count": profile.member_count, "field_count": profile.field_count, "accepted": audit.accepted and query_audit.accepted, "release_ready": audit.accepted and query_audit.accepted, "state": "complete" if audit.accepted and query_audit.accepted else "incomplete", "manifest": manifest, "profile": profile, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataProfileRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataProfileRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileRuntime:
    return DownloadedDataProfileRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataProfileRuntime) -> str:
    return canonical_json(DownloadedDataProfileRuntime.from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataProfileRuntime) -> str:
    value = DownloadedDataProfileRuntime.from_mapping(value.to_dict())
    rows = ((field, value.to_dict()[field]) for field in RUNTIME_FIELDS if field not in {"manifest", "profile", "audit", "query", "query_audit"})
    return "field,value\n" + "\n".join(f"{key},{json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in rows) + "\n"


def render_runtime_markdown(value: DownloadedDataProfileRuntime) -> str:
    value = DownloadedDataProfileRuntime.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Batch: `{value.batch_address}`", f"- Records: `{value.record_count}`", f"- Members: `{value.member_count}`", f"- Fields: `{value.field_count}`", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("profile", value.profile_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: DownloadedDataProfileRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileRuntime):
        raise ValidationError("profile runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("profile runtime destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-profile-runtime-", dir=str(parent)))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "profile.json", value.profile.to_dict())
        _write(temporary / "audit.json", value.audit.to_dict())
        _write(temporary / "query.json", value.query.to_dict())
        _write(temporary / "query-audit.json", value.query_audit.to_dict())
        _write(temporary / "runtime.json", value.to_dict())
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("profile runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("profile runtime artifact is not valid JSON") from error
    return _mapping(value, "profile runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataProfileRuntime:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("profile runtime destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("profile runtime directory does not contain the exact file set")
    runtime = DownloadedDataProfileRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataProfileManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("profile runtime manifest differs from runtime.json")
    artifact_values = {
        "profile.json": profile_model.profile_from_mapping(_read_json(destination / "profile.json")),
        "audit.json": audit_model.audit_from_mapping(_read_json(destination / "audit.json")),
        "query.json": query_model.query_from_mapping(_read_json(destination / "query.json")),
        "query-audit.json": query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json")),
    }
    expected = {"profile.json": runtime.profile, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifact_values[name].to_dict() != document.to_dict():
            raise ValidationError(f"profile runtime artifact {name} differs from runtime.json")
    return runtime


def run_runtime(batch: ingestion_model.DownloadedDataIngestBatch, *, runtime_id: str = DEFAULT_RUNTIME_ID, profile_id: str = "glio-noncode-downloaded-data-profile", resources: Sequence[str] = ("summary", "members", "fields", "types"), member_name: str = "", data_kind: str = "", field_name: str = "", value_type: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileRuntime:
    if isinstance(batch, (str, Path)):
        raise ValidationError("profile runtime run requires a typed ingestion batch; load it before running")
    value = build_runtime(batch, runtime_id=runtime_id, profile_id=profile_id, resources=resources, member_name=member_name, data_kind=data_kind, field_name=field_name, value_type=value_type, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "batch_address": {"type": "string"}, "profile_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "record_count": {"type": "integer", "minimum": 0}, "member_count": {"type": "integer", "minimum": 0}, "field_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "profile": profile_model.profile_schema(), "audit": audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"default_limit": DEFAULT_LIMIT, "max_artifacts": len(MANIFEST_ARTIFACT_FILES)}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "DownloadedDataProfileManifest", "DownloadedDataProfileRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
