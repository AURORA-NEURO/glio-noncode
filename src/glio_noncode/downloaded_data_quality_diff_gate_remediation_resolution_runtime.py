"""Exact-file runtime handoff for quality remediation resolution ledgers."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate_remediation_resolution as resolution_model
from . import downloaded_data_quality_diff_gate_remediation_resolution_audit as resolution_audit_model
from . import downloaded_data_quality_diff_gate_remediation_resolution_query as resolution_query_model
from . import downloaded_data_quality_diff_gate_remediation_resolution_query_audit as resolution_query_audit_model
from ._safe_persistence import atomic_write_text, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-remediation-resolution-runtime-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_remediation_resolution_runtime"
RUNTIME_PREFIX = "glio-noncode-download-quality-diff-gate-remediation-resolution-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
DEFAULT_LIMIT = resolution_query_model.DEFAULT_LIMIT
DEFAULT_RESOURCES = ("summary", "entries", "open")
FILES = ("manifest.json", "resolution.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("resolution.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = ("runtime_id", "version", "boundary", "plan_address", "resolution_address", "audit_address", "query_address", "query_audit_address", "resolution_count", "pending_count", "resolved_count", "waived_count", "rejected_count", "required_open_count", "query_returned_count", "query_truncated", "accepted", "release_ready", "state", "manifest", "resolution", "audit", "query", "query_audit", "content_address")


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
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be a content address")
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


class DownloadedDataQualityDiffGateRemediationResolutionManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "quality resolution runtime manifest ID")
        self.files = tuple(_label(item, "quality resolution runtime manifest file") for item in _sequence(files, "quality resolution runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "quality resolution runtime manifest artifact address") for item in _sequence(artifact_addresses, "quality resolution runtime manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "quality resolution runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("quality resolution runtime manifest does not replay")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("quality resolution runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationResolutionManifest":
        value = _mapping(value, "quality resolution runtime manifest")
        _strict(value, set(cls.FIELDS), "quality resolution runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataQualityDiffGateRemediationResolutionManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataQualityDiffGateRemediationResolutionRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, plan_address: str, resolution_address: str, audit_address: str, query_address: str, query_audit_address: str, resolution_count: int, pending_count: int, resolved_count: int, waived_count: int, rejected_count: int, required_open_count: int, query_returned_count: int, query_truncated: bool, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataQualityDiffGateRemediationResolutionManifest | Mapping[str, Any], resolution: resolution_model.DownloadedDataQualityDiffGateRemediationResolution | Mapping[str, Any], audit: resolution_audit_model.DownloadedDataQualityDiffGateRemediationResolutionAudit | Mapping[str, Any], query: resolution_query_model.DownloadedDataQualityDiffGateRemediationResolutionQuery | Mapping[str, Any], query_audit: resolution_query_audit_model.DownloadedDataQualityDiffGateRemediationResolutionQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "quality resolution runtime ID")
        self.version = _text(version, "quality resolution runtime version")
        self.boundary = _text(boundary, "quality resolution runtime boundary", 512)
        self.plan_address = _address(plan_address, "quality resolution runtime plan address")
        self.resolution_address = _address(resolution_address, "quality resolution runtime resolution address", resolution_model.RESOLUTION_PREFIX)
        self.audit_address = _address(audit_address, "quality resolution runtime audit address", resolution_audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "quality resolution runtime query address", resolution_query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "quality resolution runtime query audit address", resolution_query_audit_model.AUDIT_PREFIX)
        for field in ("resolution_count", "pending_count", "resolved_count", "waived_count", "rejected_count", "required_open_count"):
            setattr(self, field, _count(locals()[field], f"quality resolution runtime {field}", resolution_model.MAX_ENTRIES))
        self.query_returned_count = _count(query_returned_count, "quality resolution runtime query returned count", resolution_query_model.MAX_TOTAL_COUNT)
        self.query_truncated = _bool(query_truncated, "quality resolution runtime query truncation")
        self.accepted = _bool(accepted, "quality resolution runtime acceptance")
        self.release_ready = _bool(release_ready, "quality resolution runtime release readiness")
        self.state = _label(state, "quality resolution runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("quality resolution runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataQualityDiffGateRemediationResolutionManifest) else DownloadedDataQualityDiffGateRemediationResolutionManifest.from_mapping(manifest)
        self.resolution = resolution if isinstance(resolution, resolution_model.DownloadedDataQualityDiffGateRemediationResolution) else resolution_model.resolution_from_mapping(resolution)
        self.audit = audit if isinstance(audit, resolution_audit_model.DownloadedDataQualityDiffGateRemediationResolutionAudit) else resolution_audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, resolution_query_model.DownloadedDataQualityDiffGateRemediationResolutionQuery) else resolution_query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, resolution_query_audit_model.DownloadedDataQualityDiffGateRemediationResolutionQueryAudit) else resolution_query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "quality resolution runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality resolution runtime version or boundary is not current")
        if self.plan_address != self.resolution.plan_address or self.resolution_address != self.resolution.content_address:
            raise ValidationError("quality resolution runtime plan or resolution lineage does not replay")
        if (self.audit_address, self.query_address, self.query_audit_address) != (self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("quality resolution runtime component addresses do not replay")
        if self.audit.resolution_address != self.resolution_address or self.query.resolution_address != self.resolution_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("quality resolution runtime nested lineage does not replay")
        if self.manifest.artifact_addresses != (self.resolution_address, self.audit_address, self.query_address, self.query_audit_address):
            raise ValidationError("quality resolution runtime manifest artifacts do not replay")
        counters = (self.resolution_count, self.pending_count, self.resolved_count, self.waived_count, self.rejected_count, self.required_open_count)
        if counters != (self.resolution.resolution_count, self.resolution.pending_count, self.resolution.resolved_count, self.resolution.waived_count, self.resolution.rejected_count, self.resolution.required_open_count):
            raise ValidationError("quality resolution runtime counters do not replay")
        if (self.query_returned_count, self.query_truncated) != (self.query.returned_count, self.query.truncated):
            raise ValidationError("quality resolution runtime query counters do not replay")
        complete = self.audit.accepted and self.query_audit.accepted and not self.query.truncated
        if self.manifest.runtime_id != self.runtime_id or self.accepted != complete or self.release_ready != (complete and self.resolution.release_ready) or (self.state == "complete") != complete or not _public(self.to_dict()):
            raise ValidationError("quality resolution runtime readiness, manifest, or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("quality resolution runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "plan_address": self.plan_address, "resolution_address": self.resolution_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "resolution_count": self.resolution_count, "pending_count": self.pending_count, "resolved_count": self.resolved_count, "waived_count": self.waived_count, "rejected_count": self.rejected_count, "required_open_count": self.required_open_count, "query_returned_count": self.query_returned_count, "query_truncated": self.query_truncated, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "resolution": self.resolution.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "resolution", "audit", "query", "query_audit"}}
        summary.update({"resolution_state": self.resolution.state, "resolution_decision": self.resolution.decision})
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationResolutionRuntime":
        value = _mapping(value, "quality resolution runtime")
        _strict(value, set(cls.FIELDS), "quality resolution runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataQualityDiffGateRemediationResolutionRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(value: resolution_model.DownloadedDataQualityDiffGateRemediationResolution, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = DEFAULT_RESOURCES, status: str = "", action: str = "", priority: str = "", required_only: bool = False, identity: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataQualityDiffGateRemediationResolutionRuntime:
    if not isinstance(value, resolution_model.DownloadedDataQualityDiffGateRemediationResolution):
        raise ValidationError("quality resolution runtime requires a typed resolution")
    audit = resolution_audit_model.audit_resolution(value)
    query = resolution_query_model.query_resolution(value, resources=resources, status=status, action=action, priority=priority, required_only=required_only, identity=identity, text=text, offset=offset, limit=limit)
    query_audit = resolution_query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (value.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataQualityDiffGateRemediationResolutionManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataQualityDiffGateRemediationResolutionManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    complete = audit.accepted and query_audit.accepted and not query.truncated
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "plan_address": value.plan_address, "resolution_address": value.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "resolution_count": value.resolution_count, "pending_count": value.pending_count, "resolved_count": value.resolved_count, "waived_count": value.waived_count, "rejected_count": value.rejected_count, "required_open_count": value.required_open_count, "query_returned_count": query.returned_count, "query_truncated": query.truncated, "accepted": complete, "release_ready": complete and value.release_ready, "state": "complete" if complete else "incomplete", "manifest": manifest, "resolution": value, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataQualityDiffGateRemediationResolutionRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateRemediationResolutionRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRemediationResolutionRuntime:
    return DownloadedDataQualityDiffGateRemediationResolutionRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataQualityDiffGateRemediationResolutionRuntime) -> str:
    return canonical_json(runtime_from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataQualityDiffGateRemediationResolutionRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    return "field,value\n" + "\n".join(f"{field},{json.dumps(value.to_dict()[field], ensure_ascii=False, sort_keys=True)}" for field in RUNTIME_FIELDS if field not in {"manifest", "resolution", "audit", "query", "query_audit"}) + "\n"


def render_runtime_markdown(value: DownloadedDataQualityDiffGateRemediationResolutionRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Remediation Resolution Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Resolution state / decision: `{value.resolution.state}` / `{value.resolution.decision}`", f"- Pending / resolved / waived / rejected: `{value.pending_count} / {value.resolved_count} / {value.waived_count} / {value.rejected_count}`", f"- Required open: `{value.required_open_count}`", f"- Query rows: `{value.query_returned_count}`", f"- Query truncated: `{value.query_truncated}`", f"- Runtime state: `{value.state}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("plan", value.plan_address), ("resolution", value.resolution_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    atomic_write_text(path, canonical_json(value))


def persist_runtime(value: DownloadedDataQualityDiffGateRemediationResolutionRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataQualityDiffGateRemediationResolutionRuntime):
        raise ValidationError("quality resolution runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or not overwrite):
        raise ValidationError("quality resolution runtime destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-quality-resolution-runtime-", dir=str(destination.parent)))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "resolution.json", value.resolution.to_dict())
        _write(temporary / "audit.json", value.audit.to_dict())
        _write(temporary / "query.json", value.query.to_dict())
        _write(temporary / "query-audit.json", value.query_audit.to_dict())
        _write(temporary / "runtime.json", value.to_dict())
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("quality resolution runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        text = read_text(path, field="quality resolution runtime artifact")
        value = _strict_json_loads(text)
        if canonical_json(value) != text:
            raise ValidationError("quality resolution runtime artifact is not canonical JSON")
    except ValidationError:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("quality resolution runtime artifact is not valid JSON") from error
    return _mapping(value, "quality resolution runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataQualityDiffGateRemediationResolutionRuntime:
    destination = Path(destination)
    if destination.is_symlink() or not destination.is_dir() or tuple(sorted(path.name for path in destination.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("quality resolution runtime destination does not contain the exact file set")
    runtime = DownloadedDataQualityDiffGateRemediationResolutionRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataQualityDiffGateRemediationResolutionManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("quality resolution runtime manifest differs from runtime.json")
    artifacts = {"resolution.json": resolution_model.resolution_from_mapping(_read_json(destination / "resolution.json")), "audit.json": resolution_audit_model.audit_from_mapping(_read_json(destination / "audit.json")), "query.json": resolution_query_model.query_from_mapping(_read_json(destination / "query.json")), "query-audit.json": resolution_query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json"))}
    expected = {"resolution.json": runtime.resolution, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifacts[name].to_dict() != document.to_dict():
            raise ValidationError(f"quality resolution runtime artifact {name} differs from runtime.json")
    return runtime


def run_runtime(value: resolution_model.DownloadedDataQualityDiffGateRemediationResolution, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = DEFAULT_RESOURCES, status: str = "", action: str = "", priority: str = "", required_only: bool = False, identity: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataQualityDiffGateRemediationResolutionRuntime:
    result = build_runtime(value, runtime_id=runtime_id, resources=resources, status=status, action=action, priority=priority, required_only=required_only, identity=identity, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(result, destination, overwrite=overwrite)
    return result


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality remediation resolution runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality remediation resolution runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "plan_address": {"type": "string"}, "resolution_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "resolution_count": {"type": "integer", "minimum": 0}, "pending_count": {"type": "integer", "minimum": 0}, "resolved_count": {"type": "integer", "minimum": 0}, "waived_count": {"type": "integer", "minimum": 0}, "rejected_count": {"type": "integer", "minimum": 0}, "required_open_count": {"type": "integer", "minimum": 0}, "query_returned_count": {"type": "integer", "minimum": 0}, "query_truncated": {"type": "boolean"}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "resolution": resolution_model.resolution_schema(), "audit": resolution_audit_model.audit_schema(), "query": resolution_query_model.query_schema(), "query_audit": resolution_query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "default_resources": DEFAULT_RESOURCES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"default_limit": DEFAULT_LIMIT, "max_artifacts": len(MANIFEST_ARTIFACT_FILES)}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RESOURCES", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "RUNTIME_FIELDS", "DownloadedDataQualityDiffGateRemediationResolutionManifest", "DownloadedDataQualityDiffGateRemediationResolutionRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
