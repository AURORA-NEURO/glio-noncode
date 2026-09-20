"""Exact-file runtime closure for downloaded-data quality comparisons."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality as quality_model
from . import downloaded_data_quality_diff as diff_model
from . import downloaded_data_quality_diff_audit as audit_model
from . import downloaded_data_quality_diff_query as query_model
from . import downloaded_data_quality_diff_query_audit as query_audit_model
from ._safe_persistence import atomic_write_text, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-runtime-v1"
BOUNDARY = "public_downloaded_data_quality_diff_runtime"
RUNTIME_PREFIX = "glio-noncode-download-quality-diff-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
DEFAULT_LIMIT = 100
FILES = ("manifest.json", "diff.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("diff.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = (
    "runtime_id", "version", "boundary", "left_quality_address", "right_quality_address", "diff_address", "audit_address", "query_address", "query_audit_address",
    "left_record_count", "right_record_count", "left_member_count", "right_member_count", "left_field_count", "right_field_count", "total_item_count",
    "accepted", "release_ready", "state", "manifest", "diff", "audit", "query", "query_audit", "content_address",
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


class DownloadedDataQualityDiffManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "quality diff runtime manifest ID")
        self.files = tuple(_label(item, "quality diff runtime manifest file") for item in _sequence(files, "quality diff runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "quality diff runtime manifest artifact address") for item in _sequence(artifact_addresses, "quality diff runtime manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "quality diff runtime manifest address", MANIFEST_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff runtime manifest address")
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("quality diff runtime manifest does not replay")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("quality diff runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffManifest":
        value = _mapping(value, "downloaded data quality diff runtime manifest")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataQualityDiffManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataQualityDiffRuntime:
    """Joined quality diff, audits, bounded query, and exact-file manifest."""

    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, left_quality_address: str, right_quality_address: str, diff_address: str, audit_address: str, query_address: str, query_audit_address: str, left_record_count: int, right_record_count: int, left_member_count: int, right_member_count: int, left_field_count: int, right_field_count: int, total_item_count: int, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataQualityDiffManifest | Mapping[str, Any], diff: diff_model.DownloadedDataQualityDiff | Mapping[str, Any], audit: audit_model.DownloadedDataQualityDiffAudit | Mapping[str, Any], query: query_model.DownloadedDataQualityDiffQuery | Mapping[str, Any], query_audit: query_audit_model.DownloadedDataQualityDiffQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "quality diff runtime ID")
        self.version = _text(version, "quality diff runtime version")
        self.boundary = _text(boundary, "quality diff runtime boundary", 512)
        self.left_quality_address = _address(left_quality_address, "quality diff runtime left quality address", quality_model.QUALITY_PREFIX)
        self.right_quality_address = _address(right_quality_address, "quality diff runtime right quality address", quality_model.QUALITY_PREFIX)
        self.diff_address = _address(diff_address, "quality diff runtime diff address", diff_model.DIFF_PREFIX)
        self.audit_address = _address(audit_address, "quality diff runtime audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "quality diff runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "quality diff runtime query audit address", query_audit_model.AUDIT_PREFIX)
        for field in ("left_record_count", "right_record_count"):
            setattr(self, field, _count(locals()[field], f"quality diff runtime {field}", 10_000_000))
        for field in ("left_member_count", "right_member_count", "left_field_count", "right_field_count", "total_item_count"):
            setattr(self, field, _count(locals()[field], f"quality diff runtime {field}", diff_model.MAX_ITEMS))
        self.accepted = _bool(accepted, "quality diff runtime acceptance")
        self.release_ready = _bool(release_ready, "quality diff runtime release readiness")
        self.state = _label(state, "quality diff runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("quality diff runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataQualityDiffManifest) else DownloadedDataQualityDiffManifest.from_mapping(manifest)
        self.diff = diff if isinstance(diff, diff_model.DownloadedDataQualityDiff) else diff_model.diff_from_mapping(diff)
        self.audit = audit if isinstance(audit, audit_model.DownloadedDataQualityDiffAudit) else audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataQualityDiffQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataQualityDiffQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "quality diff runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff runtime address")
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality diff runtime version or boundary is not current")
        if (self.left_quality_address, self.right_quality_address) != (self.diff.left_quality_address, self.diff.right_quality_address):
            raise ValidationError("quality diff runtime quality lineage does not replay")
        if (self.diff_address, self.audit_address, self.query_address, self.query_audit_address) != (self.diff.content_address, self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("quality diff runtime component addresses do not replay")
        if self.query.diff_address != self.diff_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("quality diff runtime query lineage does not replay")
        if (self.left_record_count, self.right_record_count, self.left_member_count, self.right_member_count, self.left_field_count, self.right_field_count, self.total_item_count) != (self.diff.left_record_count, self.diff.right_record_count, self.diff.left_member_count, self.diff.right_member_count, self.diff.left_field_count, self.diff.right_field_count, len(self.diff.items)):
            raise ValidationError("quality diff runtime aggregates do not replay")
        if self.manifest.runtime_id != self.runtime_id or self.accepted != (self.audit.accepted and self.query_audit.accepted) or self.release_ready != self.accepted or (self.state == "complete") != self.release_ready or not _public(self.to_dict()):
            raise ValidationError("quality diff runtime readiness, manifest, or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("quality diff runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "left_quality_address": self.left_quality_address, "right_quality_address": self.right_quality_address, "diff_address": self.diff_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "left_record_count": self.left_record_count, "right_record_count": self.right_record_count, "left_member_count": self.left_member_count, "right_member_count": self.right_member_count, "left_field_count": self.left_field_count, "right_field_count": self.right_field_count, "total_item_count": self.total_item_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "diff": self.diff.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "diff", "audit", "query", "query_audit"}}
        summary["query_returned_count"] = self.query.returned_count
        summary["query_truncated"] = self.query.truncated
        summary["regressed_count"] = self.diff.regressed_count
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffRuntime":
        value = _mapping(value, "downloaded data quality diff runtime")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataQualityDiffRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(left: quality_model.DownloadedDataQuality, right: quality_model.DownloadedDataQuality, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = query_model.RESOURCES, change: str = "", direction: str = "", identity: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataQualityDiffRuntime:
    if not isinstance(left, quality_model.DownloadedDataQuality) or not isinstance(right, quality_model.DownloadedDataQuality):
        raise ValidationError("quality diff runtime requires two typed quality results")
    diff = diff_model.build_diff(left, right)
    audit = audit_model.audit_diff(diff)
    query = query_model.query_diff(diff, resources=resources, change=change, direction=direction, identity=identity, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (diff.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataQualityDiffManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataQualityDiffManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    accepted = audit.accepted and query_audit.accepted
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "left_quality_address": left.content_address, "right_quality_address": right.content_address, "diff_address": diff.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "left_record_count": diff.left_record_count, "right_record_count": diff.right_record_count, "left_member_count": diff.left_member_count, "right_member_count": diff.right_member_count, "left_field_count": diff.left_field_count, "right_field_count": diff.right_field_count, "total_item_count": len(diff.items), "accepted": accepted, "release_ready": accepted, "state": "complete" if accepted else "incomplete", "manifest": manifest, "diff": diff, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataQualityDiffRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataQualityDiffRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffRuntime:
    return DownloadedDataQualityDiffRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataQualityDiffRuntime) -> str:
    return canonical_json(DownloadedDataQualityDiffRuntime.from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataQualityDiffRuntime) -> str:
    value = DownloadedDataQualityDiffRuntime.from_mapping(value.to_dict())
    return "field,value\n" + "\n".join(f"{field},{json.dumps(value.to_dict()[field], ensure_ascii=False, sort_keys=True)}" for field in RUNTIME_FIELDS if field not in {"manifest", "diff", "audit", "query", "query_audit"}) + "\n"


def render_runtime_markdown(value: DownloadedDataQualityDiffRuntime) -> str:
    value = DownloadedDataQualityDiffRuntime.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Left quality: `{value.left_quality_address}`", f"- Right quality: `{value.right_quality_address}`", f"- Checks: `{value.left_field_count + value.left_member_count} -> {value.right_field_count + value.right_member_count}`", f"- Items: `{value.total_item_count}`", f"- Regressed: `{value.diff.regressed_count}`", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("diff", value.diff_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    atomic_write_text(path, canonical_json(value))


def persist_runtime(value: DownloadedDataQualityDiffRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataQualityDiffRuntime):
        raise ValidationError("quality diff runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or not overwrite):
        raise ValidationError("quality diff runtime destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-quality-diff-runtime-", dir=str(destination.parent)))
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
        raise ValidationError("quality diff runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        text = read_text(path, field="quality diff runtime artifact")
        value = _strict_json_loads(text)
        if canonical_json(value) != text:
            raise ValidationError("quality diff runtime artifact is not canonical JSON")
    except ValidationError:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("quality diff runtime artifact is not valid JSON") from error
    return _mapping(value, "quality diff runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataQualityDiffRuntime:
    destination = Path(destination)
    if destination.is_symlink() or not destination.is_dir() or tuple(sorted(path.name for path in destination.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("quality diff runtime destination does not contain the exact file set")
    runtime = DownloadedDataQualityDiffRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataQualityDiffManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("quality diff runtime manifest differs from runtime.json")
    artifacts = {"diff.json": diff_model.diff_from_mapping(_read_json(destination / "diff.json")), "audit.json": audit_model.audit_from_mapping(_read_json(destination / "audit.json")), "query.json": query_model.query_from_mapping(_read_json(destination / "query.json")), "query-audit.json": query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json"))}
    expected = {"diff.json": runtime.diff, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifacts[name].to_dict() != document.to_dict():
            raise ValidationError(f"quality diff runtime artifact {name} differs from runtime.json")
    return runtime


def run_runtime(left: quality_model.DownloadedDataQuality, right: quality_model.DownloadedDataQuality, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] = query_model.RESOURCES, change: str = "", direction: str = "", identity: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataQualityDiffRuntime:
    value = build_runtime(left, right, runtime_id=runtime_id, resources=resources, change=change, direction=direction, identity=identity, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "left_quality_address": {"type": "string"}, "right_quality_address": {"type": "string"}, "diff_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "left_record_count": {"type": "integer", "minimum": 0}, "right_record_count": {"type": "integer", "minimum": 0}, "left_member_count": {"type": "integer", "minimum": 0}, "right_member_count": {"type": "integer", "minimum": 0}, "left_field_count": {"type": "integer", "minimum": 0}, "right_field_count": {"type": "integer", "minimum": 0}, "total_item_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "diff": diff_model.diff_schema(), "audit": audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"default_limit": DEFAULT_LIMIT, "max_artifacts": len(MANIFEST_ARTIFACT_FILES)}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "RUNTIME_FIELDS", "DownloadedDataQualityDiffManifest", "DownloadedDataQualityDiffRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
