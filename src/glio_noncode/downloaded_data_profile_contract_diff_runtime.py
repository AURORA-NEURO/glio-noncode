"""Exact-file runtime closure for downloaded-data contract evolution diffs."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_profile_contract as contract_model
from . import downloaded_data_profile_contract_diff as diff_model
from . import downloaded_data_profile_contract_diff_audit as audit_model
from . import downloaded_data_profile_contract_diff_query as query_model
from . import downloaded_data_profile_contract_diff_query_audit as query_audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-diff-runtime-v1"
BOUNDARY = "public_downloaded_data_profile_contract_diff_runtime"
RUNTIME_PREFIX = "glio-noncode-download-profile-contract-diff-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = "glio-noncode-downloaded-data-profile-contract-diff-runtime"
DEFAULT_LIMIT = 100
FILES = ("manifest.json", "diff.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("diff.json", "audit.json", "query.json", "query-audit.json")
RUNTIME_FIELDS = (
    "runtime_id", "version", "boundary", "left_contract_address", "right_contract_address", "diff_address", "audit_address",
    "query_address", "query_audit_address", "left_record_count", "right_record_count", "left_field_count", "right_field_count",
    "left_member_count", "right_member_count", "total_item_count", "accepted", "release_ready", "state", "manifest", "diff",
    "audit", "query", "query_audit", "content_address",
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
        return all(str(key).casefold() not in {"agent", "agent_id", "agent_name", "assistant", "assistant_id", "author", "author_id", "author_name", "email", "language", "model", "model_id", "programming_language"} and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractDiffManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "diff runtime manifest ID")
        self.files = tuple(_label(item, "diff runtime manifest file") for item in _sequence(files, "diff runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "diff runtime manifest artifact address") for item in _sequence(artifact_addresses, "diff runtime manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "diff runtime manifest address", MANIFEST_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff runtime manifest address")
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("diff runtime manifest does not replay")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("diff runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffManifest:
        value = _mapping(value, "downloaded data profile contract diff runtime manifest")
        _strict(value, set(cls.FIELDS), "downloaded data profile contract diff runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractDiffManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractDiffRuntime:
    """Joined diff, audits, bounded query, and exact-file manifest."""

    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, left_contract_address: str, right_contract_address: str, diff_address: str, audit_address: str, query_address: str, query_audit_address: str, left_record_count: int, right_record_count: int, left_field_count: int, right_field_count: int, left_member_count: int, right_member_count: int, total_item_count: int, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataProfileContractDiffManifest | Mapping[str, Any], diff: diff_model.DownloadedDataProfileContractDiff | Mapping[str, Any], audit: audit_model.DownloadedDataProfileContractDiffAudit | Mapping[str, Any], query: query_model.DownloadedDataProfileContractDiffQuery | Mapping[str, Any], query_audit: query_audit_model.DownloadedDataProfileContractDiffQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "diff runtime ID")
        self.version = _text(version, "diff runtime version")
        self.boundary = _text(boundary, "diff runtime boundary", 512)
        self.left_contract_address = _address(left_contract_address, "diff runtime left contract address", contract_model.CONTRACT_PREFIX)
        self.right_contract_address = _address(right_contract_address, "diff runtime right contract address", contract_model.CONTRACT_PREFIX)
        self.diff_address = _address(diff_address, "diff runtime diff address", diff_model.DIFF_PREFIX)
        self.audit_address = _address(audit_address, "diff runtime audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "diff runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "diff runtime query audit address", query_audit_model.AUDIT_PREFIX)
        for field in ("left_record_count", "right_record_count"):
            setattr(self, field, _count(locals()[field], f"diff runtime {field}", 10_000_000))
        for field in ("left_field_count", "right_field_count", "left_member_count", "right_member_count", "total_item_count"):
            setattr(self, field, _count(locals()[field], f"diff runtime {field}", diff_model.MAX_ITEMS))
        self.accepted = _bool(accepted, "diff runtime acceptance")
        self.release_ready = _bool(release_ready, "diff runtime release readiness")
        self.state = _label(state, "diff runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("diff runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractDiffManifest) else DownloadedDataProfileContractDiffManifest.from_mapping(manifest)
        self.diff = diff if isinstance(diff, diff_model.DownloadedDataProfileContractDiff) else diff_model.diff_from_mapping(diff)
        self.audit = audit if isinstance(audit, audit_model.DownloadedDataProfileContractDiffAudit) else audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataProfileContractDiffQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataProfileContractDiffQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "diff runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff runtime address")
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("diff runtime version or boundary is not current")
        if (self.left_contract_address, self.right_contract_address) != (self.diff.left_contract_address, self.diff.right_contract_address):
            raise ValidationError("diff runtime contract lineage does not replay")
        if (self.diff_address, self.audit_address, self.query_address, self.query_audit_address) != (self.diff.content_address, self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("diff runtime component addresses do not replay")
        if self.query.diff_address != self.diff_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("diff runtime query lineage does not replay")
        if (self.left_record_count, self.right_record_count, self.left_field_count, self.right_field_count, self.left_member_count, self.right_member_count, self.total_item_count) != (self.diff.left_record_count, self.diff.right_record_count, self.diff.left_field_count, self.diff.right_field_count, self.diff.left_member_count, self.diff.right_member_count, len(self.diff.items)):
            raise ValidationError("diff runtime aggregates do not replay")
        if self.manifest.runtime_id != self.runtime_id or self.accepted != (self.audit.accepted and self.query_audit.accepted) or self.release_ready != self.accepted or (self.state == "complete") != self.release_ready or not _public(self.to_dict()):
            raise ValidationError("diff runtime readiness, manifest, or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("diff runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "left_contract_address": self.left_contract_address, "right_contract_address": self.right_contract_address, "diff_address": self.diff_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "left_record_count": self.left_record_count, "right_record_count": self.right_record_count, "left_field_count": self.left_field_count, "right_field_count": self.right_field_count, "left_member_count": self.left_member_count, "right_member_count": self.right_member_count, "total_item_count": self.total_item_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "diff": self.diff.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "diff", "audit", "query", "query_audit"}}
        summary["query_returned_count"] = self.query.returned_count
        summary["query_truncated"] = self.query.truncated
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffRuntime:
        value = _mapping(value, "downloaded data profile contract diff runtime")
        _strict(value, set(cls.FIELDS), "downloaded data profile contract diff runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataProfileContractDiffRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(left: contract_model.DownloadedDataProfileContract, right: contract_model.DownloadedDataProfileContract, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = query_model.RESOURCES, change: str = "", identity: str = "", attribute: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataProfileContractDiffRuntime:
    if not isinstance(left, contract_model.DownloadedDataProfileContract) or not isinstance(right, contract_model.DownloadedDataProfileContract):
        raise ValidationError("diff runtime requires two typed contracts")
    diff = diff_model.build_diff(left, right)
    audit = audit_model.audit_diff(diff)
    query = query_model.query_diff(diff, resources=resources, change=change, identity=identity, attribute=attribute, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (diff.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataProfileContractDiffManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataProfileContractDiffManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    accepted = audit.accepted and query_audit.accepted
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "left_contract_address": left.content_address, "right_contract_address": right.content_address, "diff_address": diff.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "left_record_count": diff.left_record_count, "right_record_count": diff.right_record_count, "left_field_count": diff.left_field_count, "right_field_count": diff.right_field_count, "left_member_count": diff.left_member_count, "right_member_count": diff.right_member_count, "total_item_count": len(diff.items), "accepted": accepted, "release_ready": accepted, "state": "complete" if accepted else "incomplete", "manifest": manifest, "diff": diff, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataProfileContractDiffRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataProfileContractDiffRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffRuntime:
    return DownloadedDataProfileContractDiffRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataProfileContractDiffRuntime) -> str:
    return canonical_json(DownloadedDataProfileContractDiffRuntime.from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataProfileContractDiffRuntime) -> str:
    value = DownloadedDataProfileContractDiffRuntime.from_mapping(value.to_dict())
    return "field,value\n" + "\n".join(f"{field},{json.dumps(value.to_dict()[field], ensure_ascii=False, sort_keys=True)}" for field in RUNTIME_FIELDS if field not in {"manifest", "diff", "audit", "query", "query_audit"}) + "\n"


def render_runtime_markdown(value: DownloadedDataProfileContractDiffRuntime) -> str:
    value = DownloadedDataProfileContractDiffRuntime.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Diff Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Left contract: `{value.left_contract_address}`", f"- Right contract: `{value.right_contract_address}`", f"- Records: `{value.left_record_count} -> {value.right_record_count}`", f"- Fields: `{value.left_field_count} -> {value.right_field_count}`", f"- Members: `{value.left_member_count} -> {value.right_member_count}`", f"- Items: `{value.total_item_count}`", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("diff", value.diff_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: DownloadedDataProfileContractDiffRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractDiffRuntime):
        raise ValidationError("diff runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("diff runtime destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-contract-diff-runtime-", dir=str(destination.parent)))
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
        raise ValidationError("diff runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("diff runtime artifact is not valid JSON") from error
    return _mapping(value, "diff runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataProfileContractDiffRuntime:
    destination = Path(destination)
    if not destination.is_dir() or tuple(sorted(path.name for path in destination.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("diff runtime destination does not contain the exact file set")
    runtime = DownloadedDataProfileContractDiffRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataProfileContractDiffManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("diff runtime manifest differs from runtime.json")
    artifacts = {"diff.json": diff_model.diff_from_mapping(_read_json(destination / "diff.json")), "audit.json": audit_model.audit_from_mapping(_read_json(destination / "audit.json")), "query.json": query_model.query_from_mapping(_read_json(destination / "query.json")), "query-audit.json": query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json"))}
    expected = {"diff.json": runtime.diff, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifacts[name].to_dict() != document.to_dict():
            raise ValidationError(f"diff runtime artifact {name} differs from runtime.json")
    return runtime


def run_runtime(left: contract_model.DownloadedDataProfileContract, right: contract_model.DownloadedDataProfileContract, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = query_model.RESOURCES, change: str = "", identity: str = "", attribute: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractDiffRuntime:
    value = build_runtime(left, right, runtime_id=runtime_id, resources=resources, change=change, identity=identity, attribute=attribute, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract diff runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract diff runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "left_contract_address": {"type": "string"}, "right_contract_address": {"type": "string"}, "diff_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "left_record_count": {"type": "integer", "minimum": 0}, "right_record_count": {"type": "integer", "minimum": 0}, "left_field_count": {"type": "integer", "minimum": 0}, "right_field_count": {"type": "integer", "minimum": 0}, "left_member_count": {"type": "integer", "minimum": 0}, "right_member_count": {"type": "integer", "minimum": 0}, "total_item_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "diff": diff_model.diff_schema(), "audit": audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"default_limit": DEFAULT_LIMIT, "max_artifacts": len(MANIFEST_ARTIFACT_FILES)}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "DownloadedDataProfileContractDiffManifest", "DownloadedDataProfileContractDiffRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
