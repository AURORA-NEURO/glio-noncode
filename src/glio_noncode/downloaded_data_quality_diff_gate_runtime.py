"""Exact-file runtime handoff for downloaded-data quality diff gates."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff as diff_model
from . import downloaded_data_quality_diff_gate as gate_model
from . import downloaded_data_quality_diff_gate_audit as gate_audit_model
from . import downloaded_data_quality_diff_gate_query as gate_query_model
from . import downloaded_data_quality_diff_gate_query_audit as gate_query_audit_model
from ._safe_persistence import atomic_write_text, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-runtime-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_runtime"
RUNTIME_PREFIX = "glio-noncode-download-quality-diff-gate-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
DEFAULT_LIMIT = gate_query_model.MAX_LIMIT
DEFAULT_RESOURCES = ("summary", "findings")
FILES = ("manifest.json", "gate.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("gate.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = (
    "runtime_id", "version", "boundary", "diff_address", "gate_address", "audit_address",
    "query_address", "query_audit_address", "finding_count", "safe_count", "review_count",
    "blocked_count", "query_returned_count", "query_truncated", "accepted", "release_ready",
    "state", "manifest", "gate", "audit", "query", "query_audit", "content_address",
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


class DownloadedDataQualityDiffGateManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "quality diff gate runtime manifest ID")
        self.files = tuple(_label(item, "quality diff gate runtime manifest file") for item in _sequence(files, "quality diff gate runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "quality diff gate runtime manifest artifact address") for item in _sequence(artifact_addresses, "quality diff gate runtime manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "quality diff gate runtime manifest address", MANIFEST_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff gate runtime manifest address")
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("quality diff gate runtime manifest does not replay")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("quality diff gate runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateManifest":
        value = _mapping(value, "downloaded data quality diff gate runtime manifest")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataQualityDiffGateManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataQualityDiffGateRuntime:
    """Joined gate, independent audits, bounded query, and exact manifest."""

    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, diff_address: str, gate_address: str, audit_address: str, query_address: str, query_audit_address: str, finding_count: int, safe_count: int, review_count: int, blocked_count: int, query_returned_count: int, query_truncated: bool, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataQualityDiffGateManifest | Mapping[str, Any], gate: gate_model.DownloadedDataQualityDiffGate | Mapping[str, Any], audit: gate_audit_model.DownloadedDataQualityDiffGateAudit | Mapping[str, Any], query: gate_query_model.DownloadedDataQualityDiffGateQuery | Mapping[str, Any], query_audit: gate_query_audit_model.DownloadedDataQualityDiffGateQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "quality diff gate runtime ID")
        self.version = _text(version, "quality diff gate runtime version")
        self.boundary = _text(boundary, "quality diff gate runtime boundary", 512)
        self.diff_address = _address(diff_address, "quality diff gate runtime diff address", diff_model.DIFF_PREFIX)
        self.gate_address = _address(gate_address, "quality diff gate runtime gate address", gate_model.GATE_PREFIX)
        self.audit_address = _address(audit_address, "quality diff gate runtime audit address", gate_audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "quality diff gate runtime query address", gate_query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "quality diff gate runtime query audit address", gate_query_audit_model.AUDIT_PREFIX)
        for field in ("finding_count", "safe_count", "review_count", "blocked_count"):
            setattr(self, field, _count(locals()[field], f"quality diff gate runtime {field}", gate_model.MAX_FINDINGS))
        self.query_returned_count = _count(query_returned_count, "quality diff gate runtime query returned count", gate_query_model.MAX_TOTAL_COUNT)
        self.query_truncated = _bool(query_truncated, "quality diff gate runtime query truncation")
        self.accepted = _bool(accepted, "quality diff gate runtime acceptance")
        self.release_ready = _bool(release_ready, "quality diff gate runtime release readiness")
        self.state = _label(state, "quality diff gate runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("quality diff gate runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataQualityDiffGateManifest) else DownloadedDataQualityDiffGateManifest.from_mapping(manifest)
        self.gate = gate if isinstance(gate, gate_model.DownloadedDataQualityDiffGate) else gate_model.gate_from_mapping(gate)
        self.audit = audit if isinstance(audit, gate_audit_model.DownloadedDataQualityDiffGateAudit) else gate_audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, gate_query_model.DownloadedDataQualityDiffGateQuery) else gate_query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, gate_query_audit_model.DownloadedDataQualityDiffGateQueryAudit) else gate_query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "quality diff gate runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff gate runtime address")
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality diff gate runtime version or boundary is not current")
        if self.diff_address != self.gate.diff_address or self.gate_address != self.gate.content_address:
            raise ValidationError("quality diff gate runtime diff or gate lineage does not replay")
        if (self.audit_address, self.query_address, self.query_audit_address) != (self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("quality diff gate runtime component addresses do not replay")
        if self.query.gate_address != self.gate_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("quality diff gate runtime query lineage does not replay")
        if self.manifest.artifact_addresses != (self.gate_address, self.audit_address, self.query_address, self.query_audit_address):
            raise ValidationError("quality diff gate runtime manifest artifact addresses do not replay")
        if (self.finding_count, self.safe_count, self.review_count, self.blocked_count) != (self.gate.finding_count, self.gate.safe_count, self.gate.review_count, self.gate.blocked_count):
            raise ValidationError("quality diff gate runtime findings do not replay")
        if self.query_returned_count != self.query.returned_count or self.query_truncated != self.query.truncated:
            raise ValidationError("quality diff gate runtime query counters do not replay")
        complete = self.gate.accepted and self.audit.accepted and self.query_audit.accepted and not self.query.truncated
        if self.manifest.runtime_id != self.runtime_id or self.accepted != complete or self.release_ready != complete or (self.state == "complete") != complete or not _public(self.to_dict()):
            raise ValidationError("quality diff gate runtime readiness, manifest, or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("quality diff gate runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary,
            "diff_address": self.diff_address, "gate_address": self.gate_address,
            "audit_address": self.audit_address, "query_address": self.query_address,
            "query_audit_address": self.query_audit_address, "finding_count": self.finding_count,
            "safe_count": self.safe_count, "review_count": self.review_count,
            "blocked_count": self.blocked_count, "query_returned_count": self.query_returned_count,
            "query_truncated": self.query_truncated, "accepted": self.accepted,
            "release_ready": self.release_ready, "state": self.state,
            "manifest": self.manifest.to_dict(), "gate": self.gate.to_dict(),
            "audit": self.audit.to_dict(), "query": self.query.to_dict(),
            "query_audit": self.query_audit.to_dict(), "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "gate", "audit", "query", "query_audit"}}
        summary["decision"] = self.gate.decision
        summary["gate_state"] = self.gate.state
        summary["policy_address"] = self.gate.policy.content_address
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRuntime":
        value = _mapping(value, "downloaded data quality diff gate runtime")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataQualityDiffGateRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(diff: diff_model.DownloadedDataQualityDiff, *, policy: gate_model.DownloadedDataQualityDiffGatePolicy | None = None, runtime_id: str = DEFAULT_RUNTIME_ID, gate_id: str = gate_model.DEFAULT_GATE_ID, resources: Sequence[str] = DEFAULT_RESOURCES, outcome: str = "", direction: str = "", identity: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataQualityDiffGateRuntime:
    if not isinstance(diff, diff_model.DownloadedDataQualityDiff):
        raise ValidationError("quality diff gate runtime requires a typed diff")
    gate = gate_model.evaluate(diff, policy=policy, gate_id=gate_id)
    audit = gate_audit_model.audit_gate(gate)
    query = gate_query_model.query_gate(gate, resources=resources, outcome=outcome, direction=direction, identity=identity, text=text, offset=offset, limit=limit)
    query_audit = gate_query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (gate.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataQualityDiffGateManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataQualityDiffGateManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    complete = gate.accepted and audit.accepted and query_audit.accepted and not query.truncated
    body = {
        "runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY,
        "diff_address": diff.content_address, "gate_address": gate.content_address,
        "audit_address": audit.content_address, "query_address": query.content_address,
        "query_audit_address": query_audit.content_address, "finding_count": gate.finding_count,
        "safe_count": gate.safe_count, "review_count": gate.review_count,
        "blocked_count": gate.blocked_count, "query_returned_count": query.returned_count,
        "query_truncated": query.truncated, "accepted": complete, "release_ready": complete,
        "state": "complete" if complete else "incomplete", "manifest": manifest,
        "gate": gate, "audit": audit, "query": query, "query_audit": query_audit,
    }
    provisional = DownloadedDataQualityDiffGateRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRuntime:
    return DownloadedDataQualityDiffGateRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataQualityDiffGateRuntime) -> str:
    return canonical_json(DownloadedDataQualityDiffGateRuntime.from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataQualityDiffGateRuntime) -> str:
    value = DownloadedDataQualityDiffGateRuntime.from_mapping(value.to_dict())
    return "field,value\n" + "\n".join(f"{field},{json.dumps(value.to_dict()[field], ensure_ascii=False, sort_keys=True)}" for field in RUNTIME_FIELDS if field not in {"manifest", "gate", "audit", "query", "query_audit"}) + "\n"


def render_runtime_markdown(value: DownloadedDataQualityDiffGateRuntime) -> str:
    value = DownloadedDataQualityDiffGateRuntime.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Decision: `{value.gate.decision}`", f"- Gate state: `{value.gate.state}`", f"- Findings: `{value.finding_count}`", f"- Safe / review / blocked: `{value.safe_count} / {value.review_count} / {value.blocked_count}`", f"- Query rows: `{value.query_returned_count}`", f"- Query truncated: `{value.query_truncated}`", f"- Runtime state: `{value.state}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("diff", value.diff_address), ("gate", value.gate_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    atomic_write_text(path, canonical_json(value))


def persist_runtime(value: DownloadedDataQualityDiffGateRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataQualityDiffGateRuntime):
        raise ValidationError("quality diff gate runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or not overwrite):
        raise ValidationError("quality diff gate runtime destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-quality-diff-gate-runtime-", dir=str(destination.parent)))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "gate.json", value.gate.to_dict())
        _write(temporary / "audit.json", value.audit.to_dict())
        _write(temporary / "query.json", value.query.to_dict())
        _write(temporary / "query-audit.json", value.query_audit.to_dict())
        _write(temporary / "runtime.json", value.to_dict())
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("quality diff gate runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        text = read_text(path, field="quality diff gate runtime artifact")
        value = _strict_json_loads(text)
        if canonical_json(value) != text:
            raise ValidationError("quality diff gate runtime artifact is not canonical JSON")
    except ValidationError:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("quality diff gate runtime artifact is not valid JSON") from error
    return _mapping(value, "quality diff gate runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataQualityDiffGateRuntime:
    destination = Path(destination)
    if destination.is_symlink() or not destination.is_dir() or tuple(sorted(path.name for path in destination.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("quality diff gate runtime destination does not contain the exact file set")
    runtime = DownloadedDataQualityDiffGateRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataQualityDiffGateManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("quality diff gate runtime manifest differs from runtime.json")
    artifacts = {
        "gate.json": gate_model.gate_from_mapping(_read_json(destination / "gate.json")),
        "audit.json": gate_audit_model.audit_from_mapping(_read_json(destination / "audit.json")),
        "query.json": gate_query_model.query_from_mapping(_read_json(destination / "query.json")),
        "query-audit.json": gate_query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json")),
    }
    expected = {"gate.json": runtime.gate, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifacts[name].to_dict() != document.to_dict():
            raise ValidationError(f"quality diff gate runtime artifact {name} differs from runtime.json")
    return runtime


def run_runtime(diff: diff_model.DownloadedDataQualityDiff, *, policy: gate_model.DownloadedDataQualityDiffGatePolicy | None = None, runtime_id: str = DEFAULT_RUNTIME_ID, gate_id: str = gate_model.DEFAULT_GATE_ID, resources: Sequence[str] = DEFAULT_RESOURCES, outcome: str = "", direction: str = "", identity: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataQualityDiffGateRuntime:
    value = build_runtime(diff, policy=policy, runtime_id=runtime_id, gate_id=gate_id, resources=resources, outcome=outcome, direction=direction, identity=identity, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "diff_address": {"type": "string"}, "gate_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "finding_count": {"type": "integer", "minimum": 0}, "safe_count": {"type": "integer", "minimum": 0}, "review_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "query_returned_count": {"type": "integer", "minimum": 0}, "query_truncated": {"type": "boolean"}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "gate": gate_model.gate_schema(), "audit": gate_audit_model.audit_schema(), "query": gate_query_model.query_schema(), "query_audit": gate_query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "default_resources": DEFAULT_RESOURCES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"default_limit": DEFAULT_LIMIT, "max_artifacts": len(MANIFEST_ARTIFACT_FILES)}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RESOURCES", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "RUNTIME_FIELDS", "DownloadedDataQualityDiffGateManifest", "DownloadedDataQualityDiffGateRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
