"""Exact-file runtime closure for remediation-resolution history handoffs."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history as history_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_audit as audit_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_query as query_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_query_audit as query_audit_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-runtime-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_runtime"
RUNTIME_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
FILES = ("manifest.json", "history.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("history.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = ("runtime_id", "version", "boundary", "history_id", "history_address", "audit_address", "query_address", "query_audit_address", "entry_count", "latest_required_open_count", "accepted", "release_ready", "state", "manifest", "history", "audit", "query", "query_audit", "content_address")
MAX_ARTIFACTS = len(MANIFEST_ARTIFACT_FILES)


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
        raise ValidationError(f"{field} has an unsupported address")
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
        return all(str(key).casefold() not in history_model.ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history runtime manifest ID")
        self.files = tuple(_label(item, "history runtime manifest file") for item in _sequence(files, "history runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "history runtime artifact address") for item in _sequence(artifact_addresses, "history runtime artifact addresses", MAX_ARTIFACTS))
        self.content_address = _address(content_address, "history runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != MAX_ARTIFACTS or not _public(self.to_dict()):
            raise ValidationError("history runtime manifest is not canonical")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("history runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest:
        value = _mapping(value, "history runtime manifest")
        _strict(value, set(cls.FIELDS), "history runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest):
        raise ValidationError("history manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, history_id: str, history_address: str, audit_address: str, query_address: str, query_audit_address: str, entry_count: int, latest_required_open_count: int, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest | Mapping[str, Any], history: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory | Mapping[str, Any], audit: audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit | Mapping[str, Any], query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery | Mapping[str, Any], query_audit: query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history runtime ID")
        self.version = _text(version, "history runtime version")
        self.boundary = _text(boundary, "history runtime boundary", 512)
        self.history_id = _label(history_id, "history runtime history ID")
        self.history_address = _address(history_address, "history runtime history address", history_model.HISTORY_PREFIX)
        self.audit_address = _address(audit_address, "history runtime audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "history runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "history runtime query audit address", query_audit_model.AUDIT_PREFIX)
        self.entry_count = _count(entry_count, "history runtime entry count", history_model.MAX_ENTRIES)
        self.latest_required_open_count = _count(latest_required_open_count, "history runtime open count", history_model.MAX_ENTRIES)
        self.accepted = _bool(accepted, "history runtime acceptance")
        self.release_ready = _bool(release_ready, "history runtime release readiness")
        self.state = _label(state, "history runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("history runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest.from_mapping(manifest)
        self.history = history if isinstance(history, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory) else history_model.history_from_mapping(history)
        self.audit = audit if isinstance(audit, audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit) else audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "history runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history runtime version or boundary is not current")
        if (self.history_id, self.history_address) != (self.history.history_id, self.history.content_address):
            raise ValidationError("history runtime identity or address does not replay")
        if self.audit.history_address != self.history_address or self.query.history_address != self.history_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("history runtime component links do not replay")
        if (self.audit_address, self.query_address, self.query_audit_address) != (self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("history runtime artifact addresses do not replay")
        if (self.entry_count, self.latest_required_open_count) != (self.history.entry_count, self.history.latest_required_open_count):
            raise ValidationError("history runtime aggregates do not replay")
        expected_accepted = self.history.accepted and self.audit.accepted and self.query_audit.accepted
        if self.accepted != expected_accepted or self.release_ready != (expected_accepted and self.history.release_ready) or (self.state == "complete") != expected_accepted:
            raise ValidationError("history runtime readiness does not replay")
        if self.manifest.runtime_id != self.runtime_id or not _public(self.to_dict()):
            raise ValidationError("history runtime manifest or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("history runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "history_id": self.history_id, "history_address": self.history_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "entry_count": self.entry_count, "latest_required_open_count": self.latest_required_open_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "history": self.history.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "history", "audit", "query", "query_audit"}}
        summary["history_state"] = self.history.state
        summary["history_decision"] = self.history.decision
        summary["query_returned_count"] = self.query.returned_count
        summary["query_truncated"] = self.query.truncated
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime:
        value = _mapping(value, "history runtime")
        _strict(value, set(cls.FIELDS), "history runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime):
        raise ValidationError("history runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(history: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = query_model.RESOURCES, state: str = "", decision: str = "", transition: str = "", release_ready: bool = False, plan_id: str = "", resolution_id: str = "", text: str = "", offset: int = 0, limit: int = query_model.MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime:
    if not isinstance(history, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory):
        raise ValidationError("history runtime requires a typed history")
    audit = audit_model.audit_history(history)
    query = query_model.query_history(history, resources=resources, state=state, decision=decision, transition=transition, release_ready=release_ready, plan_id=plan_id, resolution_id=resolution_id, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (history.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    accepted = history.accepted and audit.accepted and query_audit.accepted
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "history_id": history.history_id, "history_address": history.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "entry_count": history.entry_count, "latest_required_open_count": history.latest_required_open_count, "accepted": accepted, "release_ready": accepted and history.release_ready, "state": "complete" if accepted else "incomplete", "manifest": manifest, "history": history, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime) -> str:
    return canonical_json(runtime_from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    rows = ((field, value.to_dict()[field]) for field in RUNTIME_FIELDS if field not in {"manifest", "history", "audit", "query", "query_audit"})
    return "field,value\n" + "\n".join(f"{key},{json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in rows) + "\n"


def render_runtime_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- History: `{value.history_address}`", f"- Entries: `{value.entry_count}`", f"- Latest open required: `{value.latest_required_open_count}`", f"- History decision: `{value.history.decision}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("history", value.history_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime):
        raise ValidationError("history runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("history runtime destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-resolution-history-runtime-", dir=str(parent)))
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
        raise ValidationError("history runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("history runtime artifact is not valid JSON") from error
    return _mapping(value, "history runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("history runtime destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("history runtime directory does not contain the exact file set")
    runtime = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("history runtime manifest differs from runtime.json")
    artifacts = {"history.json": history_model.history_from_mapping(_read_json(destination / "history.json")), "audit.json": audit_model.audit_from_mapping(_read_json(destination / "audit.json")), "query.json": query_model.query_from_mapping(_read_json(destination / "query.json")), "query-audit.json": query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json"))}
    expected = {"history.json": runtime.history, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifacts[name].to_dict() != document.to_dict():
            raise ValidationError(f"history runtime artifact {name} differs from runtime.json")
    if tuple(runtime.manifest.artifact_addresses) != tuple(artifacts[name].content_address for name in MANIFEST_ARTIFACT_FILES):
        raise ValidationError("history runtime manifest artifact addresses do not replay")
    return runtime


def run_runtime(history: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = query_model.RESOURCES, state: str = "", decision: str = "", transition: str = "", release_ready: bool = False, plan_id: str = "", resolution_id: str = "", text: str = "", offset: int = 0, limit: int = query_model.MAX_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime:
    value = build_runtime(history, runtime_id=runtime_id, resources=resources, state=state, decision=decision, transition=transition, release_ready=release_ready, plan_id=plan_id, resolution_id=resolution_id, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": MAX_ARTIFACTS, "maxItems": MAX_ARTIFACTS}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "history_id": {"type": "string"}, "history_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "latest_required_open_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "history": history_model.history_schema(), "audit": audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"max_artifacts": MAX_ARTIFACTS}}


__all__ = ["BOUNDARY", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ARTIFACTS", "RUNTIME_FIELDS", "RUNTIME_PREFIX", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
