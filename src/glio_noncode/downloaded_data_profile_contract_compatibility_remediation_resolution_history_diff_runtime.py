"""Exact-file runtime closure for remediation-resolution history diffs."""

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
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff as diff_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_audit as audit_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_query as query_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_query_audit as query_audit_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-runtime-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_runtime"
RUNTIME_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
FILES = ("manifest.json", "diff.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("diff.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = ("runtime_id", "version", "boundary", "diff_id", "diff_address", "audit_address", "query_address", "query_audit_address", "added_count", "removed_count", "changed_count", "unchanged_count", "direction", "state", "accepted", "release_ready", "manifest", "diff", "audit", "query", "query_audit", "content_address")
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


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in history_model.ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history diff runtime manifest ID")
        self.files = tuple(_label(item, "history diff runtime manifest file") for item in _sequence(files, "history diff runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "history diff runtime artifact address") for item in _sequence(artifact_addresses, "history diff runtime artifact addresses", MAX_ARTIFACTS))
        self.content_address = _address(content_address, "history diff runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != MAX_ARTIFACTS or not _public(self.to_dict()):
            raise ValidationError("history diff runtime manifest is not canonical")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("history diff runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest:
        value = _mapping(value, "history diff runtime manifest")
        _strict(value, set(cls.FIELDS), "history diff runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest):
        raise ValidationError("history diff manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, diff_id: str, diff_address: str, audit_address: str, query_address: str, query_audit_address: str, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, direction: str, state: str, accepted: bool, release_ready: bool, manifest: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest | Mapping[str, Any], diff: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff | Mapping[str, Any], audit: audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit | Mapping[str, Any], query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery | Mapping[str, Any], query_audit: Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "history diff runtime ID")
        self.version = _text(version, "history diff runtime version")
        self.boundary = _text(boundary, "history diff runtime boundary", 512)
        self.diff_id = _label(diff_id, "history diff runtime diff ID")
        self.diff_address = _address(diff_address, "history diff runtime diff address", diff_model.DIFF_PREFIX)
        self.audit_address = _address(audit_address, "history diff runtime audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "history diff runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "history diff runtime query audit address", query_audit_model.AUDIT_PREFIX)
        for field in ("added_count", "removed_count", "changed_count", "unchanged_count"):
            setattr(self, field, _count(locals()[field], f"history diff runtime {field}", diff_model.MAX_ITEMS))
        self.direction = _label(direction, "history diff runtime direction")
        if self.direction not in diff_model.DIRECTIONS:
            raise ValidationError("history diff runtime direction is unsupported")
        self.state = _label(state, "history diff runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("history diff runtime state is unsupported")
        self.accepted = _bool(accepted, "history diff runtime acceptance")
        self.release_ready = _bool(release_ready, "history diff runtime release readiness")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest.from_mapping(manifest)
        self.diff = diff if isinstance(diff, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff) else diff_model.diff_from_mapping(diff)
        self.audit = audit if isinstance(audit, audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffAudit) else audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "history diff runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff runtime version or boundary is not current")
        if (self.diff_id, self.diff_address) != (self.diff.diff_id, self.diff.content_address):
            raise ValidationError("history diff runtime identity or address does not replay")
        if self.audit.diff_address != self.diff_address or self.query.diff_address != self.diff_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("history diff runtime component links do not replay")
        if (self.audit_address, self.query_address, self.query_audit_address) != (self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("history diff runtime artifact addresses do not replay")
        if (self.added_count, self.removed_count, self.changed_count, self.unchanged_count) != (self.diff.added_count, self.diff.removed_count, self.diff.changed_count, self.diff.unchanged_count) or self.direction != self.diff.direction:
            raise ValidationError("history diff runtime aggregates do not replay")
        expected_accepted = self.audit.accepted and self.query_audit.accepted
        expected_ready = expected_accepted and self.direction in {"improved", "unchanged"}
        if self.accepted != expected_accepted or self.release_ready != expected_ready or (self.state == "complete") != expected_accepted:
            raise ValidationError("history diff runtime readiness does not replay")
        if self.manifest.runtime_id != self.runtime_id or not _public(self.to_dict()):
            raise ValidationError("history diff runtime manifest or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("history diff runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "diff_id": self.diff_id, "diff_address": self.diff_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "direction": self.direction, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "manifest": self.manifest.to_dict(), "diff": self.diff.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "diff", "audit", "query", "query_audit"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime:
        value = _mapping(value, "history diff runtime")
        _strict(value, set(cls.FIELDS), "history diff runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime):
        raise ValidationError("history diff runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(diff: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = query_model.RESOURCES, resource: str = "", change: str = "", direction: str = "", identity: str = "", text: str = "", offset: int = 0, limit: int = query_model.MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime:
    if not isinstance(diff, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff):
        raise ValidationError("history diff runtime requires a typed diff")
    audit = audit_model.audit_diff(diff)
    query = query_model.query_diff(diff, resources=resources, resource=resource, change=change, direction=direction, identity=identity, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (diff.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    accepted = audit.accepted and query_audit.accepted
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "diff_id": diff.diff_id, "diff_address": diff.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "added_count": diff.added_count, "removed_count": diff.removed_count, "changed_count": diff.changed_count, "unchanged_count": diff.unchanged_count, "direction": diff.direction, "state": "complete" if accepted else "incomplete", "accepted": accepted, "release_ready": accepted and diff.direction in {"improved", "unchanged"}, "manifest": manifest, "diff": diff, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime) -> str:
    return canonical_json(runtime_from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    rows = ((field, value.to_dict()[field]) for field in RUNTIME_FIELDS if field not in {"manifest", "diff", "audit", "query", "query_audit"})
    return "field,value\n" + "\n".join(f"{key},{json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in rows) + "\n"


def render_runtime_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Diff Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Diff: `{value.diff_address}`", f"- Direction: `{value.direction}`", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Unchanged: `{value.unchanged_count}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("diff", value.diff_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime):
        raise ValidationError("history diff runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("history diff runtime destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-resolution-history-diff-runtime-", dir=str(parent)))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "diff.json", value.diff.to_dict())
        _write(temporary / "audit.json", value.audit.to_dict())
        _write(temporary / "query.json", value.query.to_dict())
        _write(temporary / "query-audit.json", value.query_audit.to_dict())
        _write(temporary / "runtime.json", value.to_dict())
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("history diff runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("history diff runtime artifact is not valid JSON") from error
    return _mapping(value, "history diff runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("history diff runtime destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("history diff runtime directory does not contain the exact file set")
    runtime = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("history diff runtime manifest differs from runtime.json")
    artifacts = {"diff.json": diff_model.diff_from_mapping(_read_json(destination / "diff.json")), "audit.json": audit_model.audit_from_mapping(_read_json(destination / "audit.json")), "query.json": query_model.query_from_mapping(_read_json(destination / "query.json")), "query-audit.json": query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json"))}
    expected = {"diff.json": runtime.diff, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifacts[name].to_dict() != document.to_dict():
            raise ValidationError(f"history diff runtime artifact {name} differs from runtime.json")
    if tuple(runtime.manifest.artifact_addresses) != tuple(artifacts[name].content_address for name in MANIFEST_ARTIFACT_FILES):
        raise ValidationError("history diff runtime manifest artifact addresses do not replay")
    return runtime


def run_runtime(diff: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = query_model.RESOURCES, resource: str = "", change: str = "", direction: str = "", identity: str = "", text: str = "", offset: int = 0, limit: int = query_model.MAX_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime:
    value = build_runtime(diff, runtime_id=runtime_id, resources=resources, resource=resource, change=change, direction=direction, identity=identity, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": MAX_ARTIFACTS, "maxItems": MAX_ARTIFACTS}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "direction": {"enum": list(diff_model.DIRECTIONS)}, "state": {"enum": ["complete", "incomplete"]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "manifest": manifest_schema(), "diff": diff_model.diff_schema(), "audit": audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"max_artifacts": MAX_ARTIFACTS}}


__all__ = ["BOUNDARY", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ARTIFACTS", "RUNTIME_FIELDS", "RUNTIME_PREFIX", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
