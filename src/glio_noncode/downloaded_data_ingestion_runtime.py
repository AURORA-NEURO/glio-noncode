"""Replayable offline runtime for downloaded-data ingestion and inspection."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_catalog as catalog_model
from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_ingestion_audit as ingestion_audit_model
from . import downloaded_data_ingestion_query as query_model
from . import downloaded_data_ingestion_query_audit as query_audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-ingestion-runtime-v1"
BOUNDARY = "public_downloaded_data_ingestion_runtime"
RUNTIME_PREFIX = "glio-noncode-download-ingest-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = "glio-noncode-downloaded-data-runtime"
DEFAULT_LIMIT = 100
FILES = ("manifest.json", "catalog.json", "selection.json", "batch.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("catalog.json", "selection.json", "batch.json", "audit.json", "query.json", "query-audit.json")
RUNTIME_FIELDS = (
    "runtime_id",
    "version",
    "boundary",
    "source_name",
    "source_address",
    "catalog_address",
    "selection_address",
    "batch_address",
    "audit_address",
    "query_address",
    "query_audit_address",
    "selected_member_count",
    "record_count",
    "available_record_count",
    "complete",
    "accepted",
    "release_ready",
    "state",
    "manifest",
    "catalog",
    "selection",
    "batch",
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


class DownloadedDataIngestionManifest:
    """Exact file-set and artifact-address contract for a persisted runtime."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "runtime manifest ID")
        self.files = tuple(_label(item, "runtime manifest file") for item in _sequence(files, "runtime manifest files", len(FILES)))
        if self.files != FILES:
            raise ValidationError("runtime manifest files are not canonical")
        self.artifact_addresses = tuple(_address(item, "runtime manifest artifact address") for item in _sequence(artifact_addresses, "runtime manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        if len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES):
            raise ValidationError("runtime manifest artifact addresses are incomplete")
        self.content_address = _address(content_address, "runtime manifest address", MANIFEST_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "runtime manifest address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime manifest crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionManifest:
        value = _mapping(value, "runtime manifest")
        _strict(value, set(cls.FIELDS), "runtime manifest")
        return cls(value["runtime_id"], value["files"], value["artifact_addresses"], value["content_address"])


def address_manifest(value: DownloadedDataIngestionManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataIngestionRuntime:
    """Joined catalog, selection, batch, audits, query, and file manifest."""

    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, source_name: str, source_address: str, catalog_address: str, selection_address: str, batch_address: str, audit_address: str, query_address: str, query_audit_address: str, selected_member_count: int, record_count: int, available_record_count: int, complete: bool, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataIngestionManifest | Mapping[str, Any], catalog: catalog_model.DownloadedDataCatalog | Mapping[str, Any], selection: ingestion_model.DownloadedDataSelection | Mapping[str, Any], batch: ingestion_model.DownloadedDataIngestBatch | Mapping[str, Any], audit: ingestion_audit_model.DownloadedDataIngestionAudit | Mapping[str, Any], query: query_model.DownloadedDataIngestionQuery | Mapping[str, Any], query_audit: query_audit_model.DownloadedDataIngestionQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "runtime ID")
        self.version = _text(version, "runtime version")
        self.boundary = _text(boundary, "runtime boundary", 512)
        self.source_name = _text(source_name, "runtime source name", 1024)
        self.source_address = _address(source_address, "runtime source address", ingestion_model.SOURCE_PREFIX)
        self.catalog_address = _address(catalog_address, "runtime catalog address", catalog_model.CATALOG_PREFIX)
        self.selection_address = _address(selection_address, "runtime selection address", ingestion_model.SELECTION_PREFIX)
        self.batch_address = _address(batch_address, "runtime batch address", ingestion_model.INGEST_PREFIX)
        self.audit_address = _address(audit_address, "runtime audit address", ingestion_audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "runtime query audit address", query_audit_model.AUDIT_PREFIX)
        self.selected_member_count = _count(selected_member_count, "runtime selected member count", ingestion_model.MAX_SELECTED_MEMBERS)
        self.record_count = _count(record_count, "runtime record count", ingestion_model.MAX_RECORDS)
        self.available_record_count = _count(available_record_count, "runtime available record count", ingestion_model.MAX_TOTAL_RECORDS)
        self.complete = _bool(complete, "runtime completeness")
        self.accepted = _bool(accepted, "runtime acceptance")
        self.release_ready = _bool(release_ready, "runtime release readiness")
        self.state = _label(state, "runtime state")
        if self.state not in {"complete", "truncated"}:
            raise ValidationError("runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataIngestionManifest) else DownloadedDataIngestionManifest.from_mapping(manifest)
        self.catalog = catalog if isinstance(catalog, catalog_model.DownloadedDataCatalog) else catalog_model.catalog_from_mapping(catalog)
        self.selection = selection if isinstance(selection, ingestion_model.DownloadedDataSelection) else ingestion_model.selection_from_mapping(selection)
        self.batch = batch if isinstance(batch, ingestion_model.DownloadedDataIngestBatch) else ingestion_model.ingest_from_mapping(batch)
        self.audit = audit if isinstance(audit, ingestion_audit_model.DownloadedDataIngestionAudit) else ingestion_audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataIngestionQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataIngestionQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "runtime address")
        self._validate()

    def _validate(self) -> None:
        if self.source_address != self.batch.source_address or self.catalog_address != self.batch.catalog_address or self.selection_address != self.selection.content_address or self.batch_address != self.batch.content_address or self.audit_address != self.audit.content_address or self.query_address != self.query.content_address or self.query_audit_address != self.query_audit.content_address:
            raise ValidationError("runtime lineage links do not replay")
        if self.catalog.content_address != self.catalog_address or self.selection.catalog_address != self.catalog_address or self.query.batch_address != self.batch_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("runtime component addresses do not replay")
        if self.selected_member_count != self.batch.selected_member_count or self.record_count != self.batch.record_count or self.available_record_count != self.batch.available_record_count or self.complete != self.batch.complete or self.state != self.batch.state:
            raise ValidationError("runtime aggregate state does not replay")
        if self.accepted != (self.audit.accepted and self.query_audit.accepted) or self.release_ready != (self.accepted and self.complete):
            raise ValidationError("runtime acceptance state does not replay")
        if self.manifest.runtime_id != self.runtime_id or not _public(self.to_dict()):
            raise ValidationError("runtime manifest or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "source_name": self.source_name, "source_address": self.source_address, "catalog_address": self.catalog_address, "selection_address": self.selection_address, "batch_address": self.batch_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "selected_member_count": self.selected_member_count, "record_count": self.record_count, "available_record_count": self.available_record_count, "complete": self.complete, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "catalog": self.catalog.to_dict(), "selection": self.selection.to_dict(), "batch": self.batch.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "catalog", "selection", "batch", "audit", "query", "query_audit"}}
        summary["query_returned_count"] = self.query.returned_count
        summary["query_truncated"] = self.query.truncated
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionRuntime:
        value = _mapping(value, "downloaded ingestion runtime")
        _strict(value, set(cls.FIELDS), "downloaded ingestion runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataIngestionRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def _build_runtime_components(source: str | Path | bytes, *, selection: ingestion_model.DownloadedDataSelection | Mapping[str, Any] | None = None, selection_id: str, member_names: Sequence[str], suffixes: Sequence[str], data_kinds: Sequence[str], record_limit: int, overflow_policy: str, batch_id: str, resources: Sequence[str], offset: int, limit: int) -> tuple[catalog_model.DownloadedDataCatalog, ingestion_model.DownloadedDataIngestBatch, ingestion_audit_model.DownloadedDataIngestionAudit, query_model.DownloadedDataIngestionQuery, query_audit_model.DownloadedDataIngestionQueryAudit]:
    raw_zip, _, _ = ingestion_model._read_source(source)
    catalog = catalog_model.build_catalog(raw_zip)
    batch = ingestion_model.build_ingest(raw_zip, catalog=catalog, selection=selection, selection_id=selection_id, member_names=member_names, suffixes=suffixes, data_kinds=data_kinds, record_limit=record_limit, overflow_policy=overflow_policy, batch_id=batch_id)
    audit = ingestion_audit_model.audit_ingest(batch)
    query = query_model.query_batch(batch, resources=resources, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    return catalog, batch, audit, query, query_audit


def build_runtime(source: str | Path | bytes, *, runtime_id: str = DEFAULT_RUNTIME_ID, selection: ingestion_model.DownloadedDataSelection | Mapping[str, Any] | None = None, selection_id: str = "glio-noncode-downloaded-data-selection", member_names: Sequence[str] = (), suffixes: Sequence[str] = (), data_kinds: Sequence[str] = (), record_limit: int = ingestion_model.MAX_RECORDS, overflow_policy: str = "reject", batch_id: str = "glio-noncode-downloaded-data-ingest", resources: Sequence[str] = ("summary", "records"), offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataIngestionRuntime:
    raw_zip, source_name, source_address = ingestion_model._read_source(source)
    catalog, batch, audit, query, query_audit = _build_runtime_components(raw_zip, selection=selection, selection_id=selection_id, member_names=member_names, suffixes=suffixes, data_kinds=data_kinds, record_limit=record_limit, overflow_policy=overflow_policy, batch_id=batch_id, resources=resources, offset=offset, limit=limit)
    selection_value = batch.selection
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (catalog.content_address, selection_value.content_address, batch.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataIngestionManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataIngestionManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "source_name": source_name, "source_address": source_address, "catalog_address": catalog.content_address, "selection_address": selection_value.content_address, "batch_address": batch.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "selected_member_count": batch.selected_member_count, "record_count": batch.record_count, "available_record_count": batch.available_record_count, "complete": batch.complete, "accepted": audit.accepted and query_audit.accepted, "release_ready": audit.accepted and query_audit.accepted and batch.complete, "state": batch.state, "manifest": manifest, "catalog": catalog, "selection": selection_value, "batch": batch, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataIngestionRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataIngestionRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataIngestionRuntime:
    return DownloadedDataIngestionRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataIngestionRuntime) -> str:
    return canonical_json(DownloadedDataIngestionRuntime.from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataIngestionRuntime) -> str:
    value = DownloadedDataIngestionRuntime.from_mapping(value.to_dict())
    rows = ((field, value.to_dict()[field]) for field in RUNTIME_FIELDS if field not in {"manifest", "catalog", "selection", "batch", "audit", "query", "query_audit"})
    return "field,value\n" + "\n".join(f"{key},{json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in rows) + "\n"


def render_runtime_markdown(value: DownloadedDataIngestionRuntime) -> str:
    value = DownloadedDataIngestionRuntime.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Ingestion Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Source: `{value.source_name}`", f"- Members: `{value.selected_member_count}`", f"- Records: `{value.record_count}/{value.available_record_count}`", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend((f"| {name} | `{address}` |" for name, address in (("catalog", value.catalog_address), ("selection", value.selection_address), ("batch", value.batch_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address))))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: DownloadedDataIngestionRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = DownloadedDataIngestionRuntime.from_mapping(value.to_dict())
    target = Path(destination)
    if target.exists() and not overwrite:
        raise ValidationError("runtime destination exists; pass overwrite explicitly")
    target_parent = target.parent
    target_parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target_parent))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "catalog.json", value.catalog.to_dict())
        _write(temporary / "selection.json", value.selection.to_dict())
        _write(temporary / "batch.json", value.batch.to_dict())
        _write(temporary / "audit.json", value.audit.to_dict())
        _write(temporary / "query.json", value.query.to_dict())
        _write(temporary / "query-audit.json", value.query_audit.to_dict())
        _write(temporary / "runtime.json", value.to_dict())
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("runtime could not be persisted atomically") from error
    return target


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        return _mapping(json.loads(path.read_text(encoding="utf-8")), str(path))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"runtime member {path.name} is not valid JSON") from error


def load_runtime(destination: str | Path) -> DownloadedDataIngestionRuntime:
    root = Path(destination)
    if not root.is_dir():
        raise ValidationError("runtime source must be a directory")
    names = tuple(item.name for item in root.iterdir())
    if tuple(sorted(names)) != tuple(sorted(FILES)):
        raise ValidationError("runtime directory has an unexpected file set")
    raw_runtime = _read_json(root / "runtime.json")
    value = runtime_from_mapping(raw_runtime)
    persisted = {"manifest.json": value.manifest.to_dict(), "catalog.json": value.catalog.to_dict(), "selection.json": value.selection.to_dict(), "batch.json": value.batch.to_dict(), "audit.json": value.audit.to_dict(), "query.json": value.query.to_dict(), "query-audit.json": value.query_audit.to_dict(), "runtime.json": value.to_dict()}
    for filename, expected in persisted.items():
        actual = root.joinpath(filename).read_text(encoding="utf-8")
        if actual != canonical_json(expected):
            raise ValidationError(f"runtime member {filename} is not canonical")
    return value


def run_runtime(source: str | Path | bytes, *, runtime_id: str = DEFAULT_RUNTIME_ID, selection: ingestion_model.DownloadedDataSelection | Mapping[str, Any] | None = None, selection_id: str = "glio-noncode-downloaded-data-selection", member_names: Sequence[str] = (), suffixes: Sequence[str] = (), data_kinds: Sequence[str] = (), record_limit: int = ingestion_model.MAX_RECORDS, overflow_policy: str = "reject", batch_id: str = "glio-noncode-downloaded-data-ingest", resources: Sequence[str] = ("summary", "records"), offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataIngestionRuntime:
    if isinstance(source, (str, Path)) and Path(source).is_dir():
        value = load_runtime(source)
        if destination is not None:
            persist_runtime(value, destination, overwrite=overwrite)
        return value
    value = build_runtime(source, runtime_id=runtime_id, selection=selection, selection_id=selection_id, member_names=member_names, suffixes=suffixes, data_kinds=data_kinds, record_limit=record_limit, overflow_policy=overflow_policy, batch_id=batch_id, resources=resources, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "source_name": {"type": "string"}, "source_address": {"type": "string"}, "catalog_address": {"type": "string"}, "selection_address": {"type": "string"}, "batch_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "selected_member_count": {"type": "integer", "minimum": 0}, "record_count": {"type": "integer", "minimum": 0}, "available_record_count": {"type": "integer", "minimum": 0}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "truncated"]}, "manifest": manifest_schema(), "catalog": catalog_model.catalog_schema(), "selection": ingestion_model.selection_schema(), "batch": ingestion_model.ingest_schema(), "audit": ingestion_audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"default_limit": DEFAULT_LIMIT}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "DownloadedDataIngestionManifest", "DownloadedDataIngestionRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
