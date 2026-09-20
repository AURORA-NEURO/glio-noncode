"""Exact-file runtime handoff for remediation resolution histories."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate_remediation_resolution_history as history_model
from . import downloaded_data_quality_diff_gate_remediation_resolution_history_audit as history_audit_model
from . import downloaded_data_quality_diff_gate_remediation_resolution_history_query as history_query_model
from . import downloaded_data_quality_diff_gate_remediation_resolution_history_query_audit as history_query_audit_model
from ._safe_persistence import atomic_write_text, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-remediation-resolution-history-runtime-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_remediation_resolution_history_runtime"
RUNTIME_PREFIX = "glio-noncode-download-quality-diff-gate-remediation-resolution-history-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
DEFAULT_LIMIT = history_query_model.DEFAULT_LIMIT
DEFAULT_RESOURCES = ("summary", "entries", "latest")
FILES = ("manifest.json", "history.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("history.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = ("runtime_id", "version", "boundary", "plan_id", "history_address", "audit_address", "query_address", "query_audit_address", "entry_count", "latest_required_open_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "query_returned_count", "query_truncated", "accepted", "release_ready", "state", "manifest", "history", "audit", "query", "query_audit", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be a content address")
    namespace, digest = value.split(":", 1)
    if not namespace or (digest != "pending" and (len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest))):
        raise ValidationError(f"{field} must be canonical")
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


class DownloadedDataQualityDiffGateRemediationResolutionHistoryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "resolution history runtime manifest ID")
        self.files = tuple(_label(item, "resolution history runtime manifest file") for item in _sequence(files, "resolution history runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "resolution history runtime manifest artifact address") for item in _sequence(artifact_addresses, "resolution history runtime manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "resolution history runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("resolution history runtime manifest does not replay")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("resolution history runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationResolutionHistoryManifest":
        value = _mapping(value, "resolution history runtime manifest")
        _strict(value, set(cls.FIELDS), "resolution history runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, plan_id: str, history_address: str, audit_address: str, query_address: str, query_audit_address: str, entry_count: int, latest_required_open_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, query_returned_count: int, query_truncated: bool, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataQualityDiffGateRemediationResolutionHistoryManifest | Mapping[str, Any], history: history_model.DownloadedDataQualityDiffGateRemediationResolutionHistory | Mapping[str, Any], audit: history_audit_model.DownloadedDataQualityDiffGateRemediationResolutionHistoryAudit | Mapping[str, Any], query: history_query_model.DownloadedDataQualityDiffGateRemediationResolutionHistoryQuery | Mapping[str, Any], query_audit: history_query_audit_model.DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "resolution history runtime ID")
        self.version = _text(version, "resolution history runtime version")
        self.boundary = _text(boundary, "resolution history runtime boundary", 512)
        self.plan_id = _label(plan_id, "resolution history runtime plan ID", required=False)
        self.history_address = _address(history_address, "resolution history runtime history address", history_model.HISTORY_PREFIX)
        self.audit_address = _address(audit_address, "resolution history runtime audit address", history_audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "resolution history runtime query address", history_query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "resolution history runtime query audit address", history_query_audit_model.AUDIT_PREFIX)
        self.entry_count = _count(entry_count, "resolution history runtime entry count", history_model.MAX_ENTRIES)
        self.latest_required_open_count = _count(latest_required_open_count, "resolution history runtime latest open count", history_model.MAX_ENTRIES)
        for field in ("initial_count", "improved_count", "regressed_count", "unchanged_count"):
            setattr(self, field, _count(locals()[field], f"resolution history runtime {field}", history_model.MAX_ENTRIES))
        self.query_returned_count = _count(query_returned_count, "resolution history runtime query returned count", history_query_model.MAX_TOTAL_COUNT)
        self.query_truncated = _bool(query_truncated, "resolution history runtime query truncation")
        self.accepted = _bool(accepted, "resolution history runtime acceptance")
        self.release_ready = _bool(release_ready, "resolution history runtime release readiness")
        self.state = _label(state, "resolution history runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("resolution history runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataQualityDiffGateRemediationResolutionHistoryManifest) else DownloadedDataQualityDiffGateRemediationResolutionHistoryManifest.from_mapping(manifest)
        self.history = history if isinstance(history, history_model.DownloadedDataQualityDiffGateRemediationResolutionHistory) else history_model.history_from_mapping(history)
        self.audit = audit if isinstance(audit, history_audit_model.DownloadedDataQualityDiffGateRemediationResolutionHistoryAudit) else history_audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, history_query_model.DownloadedDataQualityDiffGateRemediationResolutionHistoryQuery) else history_query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, history_query_audit_model.DownloadedDataQualityDiffGateRemediationResolutionHistoryQueryAudit) else history_query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "resolution history runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("resolution history runtime version or boundary is not current")
        if self.plan_id != self.history.plan_id or self.history_address != self.history.content_address:
            raise ValidationError("resolution history runtime plan or history lineage does not replay")
        if (self.audit_address, self.query_address, self.query_audit_address) != (self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("resolution history runtime component addresses do not replay")
        if self.audit.history_address != self.history_address or self.query.history_address != self.history_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("resolution history runtime nested lineage does not replay")
        if self.manifest.artifact_addresses != (self.history_address, self.audit_address, self.query_address, self.query_audit_address):
            raise ValidationError("resolution history runtime manifest artifacts do not replay")
        if (self.entry_count, self.latest_required_open_count, self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count) != (self.history.entry_count, self.history.latest_required_open_count, self.history.initial_count, self.history.improved_count, self.history.regressed_count, self.history.unchanged_count):
            raise ValidationError("resolution history runtime counters do not replay")
        if (self.query_returned_count, self.query_truncated) != (self.query.returned_count, self.query.truncated):
            raise ValidationError("resolution history runtime query counters do not replay")
        complete = self.audit.accepted and self.query_audit.accepted and not self.query.truncated
        if self.manifest.runtime_id != self.runtime_id or self.accepted != complete or self.release_ready != (complete and self.history.release_ready) or (self.state == "complete") != complete or not _public(self.to_dict()):
            raise ValidationError("resolution history runtime readiness, manifest, or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("resolution history runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "plan_id": self.plan_id, "history_address": self.history_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "entry_count": self.entry_count, "latest_required_open_count": self.latest_required_open_count, "initial_count": self.initial_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "unchanged_count": self.unchanged_count, "query_returned_count": self.query_returned_count, "query_truncated": self.query_truncated, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "history": self.history.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "history", "audit", "query", "query_audit"}}
        summary.update({"history_state": self.history.state, "history_decision": self.history.decision})
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime":
        value = _mapping(value, "resolution history runtime")
        _strict(value, set(cls.FIELDS), "resolution history runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(value: history_model.DownloadedDataQualityDiffGateRemediationResolutionHistory, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = DEFAULT_RESOURCES, state: str = "", decision: str = "", transition: str = "", snapshot_id: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime:
    if not isinstance(value, history_model.DownloadedDataQualityDiffGateRemediationResolutionHistory):
        raise ValidationError("resolution history runtime requires a typed history")
    audit = history_audit_model.audit_history(value)
    query = history_query_model.query_history(value, resources=resources, state=state, decision=decision, transition=transition, snapshot_id=snapshot_id, text=text, offset=offset, limit=limit)
    query_audit = history_query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (value.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataQualityDiffGateRemediationResolutionHistoryManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataQualityDiffGateRemediationResolutionHistoryManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    complete = audit.accepted and query_audit.accepted and not query.truncated
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "plan_id": value.plan_id, "history_address": value.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "entry_count": value.entry_count, "latest_required_open_count": value.latest_required_open_count, "initial_count": value.initial_count, "improved_count": value.improved_count, "regressed_count": value.regressed_count, "unchanged_count": value.unchanged_count, "query_returned_count": query.returned_count, "query_truncated": query.truncated, "accepted": complete, "release_ready": complete and value.release_ready, "state": "complete" if complete else "incomplete", "manifest": manifest, "history": value, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime:
    return DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime) -> str:
    return canonical_json(runtime_from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    return "field,value\n" + "\n".join(f"{field},{json.dumps(value.to_dict()[field], ensure_ascii=False, sort_keys=True)}" for field in RUNTIME_FIELDS if field not in {"manifest", "history", "audit", "query", "query_audit"}) + "\n"


def render_runtime_markdown(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Remediation Resolution History Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- History state / decision: `{value.history.state}` / `{value.history.decision}`", f"- Entries: `{value.entry_count}`", f"- Latest required open: `{value.latest_required_open_count}`", f"- Transitions: `{value.initial_count}/{value.improved_count}/{value.regressed_count}/{value.unchanged_count}`", f"- Query rows / truncated: `{value.query_returned_count}` / `{value.query_truncated}`", f"- Runtime state: `{value.state}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("history", value.history_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    atomic_write_text(path, canonical_json(value))


def persist_runtime(value: DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime):
        raise ValidationError("resolution history runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or not overwrite):
        raise ValidationError("resolution history runtime destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-quality-resolution-history-runtime-", dir=str(destination.parent)))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "history.json", value.history.to_dict())
        _write(temporary / "audit.json", value.audit.to_dict())
        _write(temporary / "query.json", value.query.to_dict())
        _write(temporary / "query-audit.json", value.query_audit.to_dict())
        _write(temporary / "runtime.json", value.to_dict())
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("resolution history runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        text = read_text(path, field="resolution history runtime artifact")
        value = _strict_json_loads(text)
        if canonical_json(value) != text:
            raise ValidationError("resolution history runtime artifact is not canonical JSON")
    except ValidationError:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("resolution history runtime artifact is not valid JSON") from error
    return _mapping(value, "resolution history runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime:
    destination = Path(destination)
    if destination.is_symlink() or not destination.is_dir() or tuple(sorted(path.name for path in destination.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("resolution history runtime destination does not contain the exact file set")
    runtime = runtime_from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataQualityDiffGateRemediationResolutionHistoryManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("resolution history runtime manifest differs from runtime.json")
    artifacts = {"history.json": history_model.history_from_mapping(_read_json(destination / "history.json")), "audit.json": history_audit_model.audit_from_mapping(_read_json(destination / "audit.json")), "query.json": history_query_model.query_from_mapping(_read_json(destination / "query.json")), "query-audit.json": history_query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json"))}
    expected = {"history.json": runtime.history, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifacts[name].to_dict() != document.to_dict():
            raise ValidationError(f"resolution history runtime artifact {name} differs from runtime.json")
    return runtime


def run_runtime(value: history_model.DownloadedDataQualityDiffGateRemediationResolutionHistory, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = DEFAULT_RESOURCES, state: str = "", decision: str = "", transition: str = "", snapshot_id: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime:
    result = build_runtime(value, runtime_id=runtime_id, resources=resources, state=state, decision=decision, transition=transition, snapshot_id=snapshot_id, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(result, destination, overwrite=overwrite)
    return result


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data remediation resolution history runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data remediation resolution history runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "plan_id": {"type": "string"}, "history_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "latest_required_open_count": {"type": "integer", "minimum": 0}, "initial_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "query_returned_count": {"type": "integer", "minimum": 0}, "query_truncated": {"type": "boolean"}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "history": history_model.history_schema(), "audit": history_audit_model.audit_schema(), "query": history_query_model.query_schema(), "query_audit": history_query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "default_resources": DEFAULT_RESOURCES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"default_limit": DEFAULT_LIMIT, "max_artifacts": len(MANIFEST_ARTIFACT_FILES)}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RESOURCES", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "RUNTIME_FIELDS", "VERSION", "DownloadedDataQualityDiffGateRemediationResolutionHistoryManifest", "DownloadedDataQualityDiffGateRemediationResolutionHistoryRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
