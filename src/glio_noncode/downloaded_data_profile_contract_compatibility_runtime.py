"""Exact-file offline runtime for downloaded-data compatibility decisions."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility as compatibility_model
from . import downloaded_data_profile_contract_compatibility_audit as audit_model
from . import downloaded_data_profile_contract_compatibility_query as query_model
from . import downloaded_data_profile_contract_compatibility_query_audit as query_audit_model
from . import downloaded_data_profile_contract_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-runtime-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_runtime"
RUNTIME_PREFIX = "glio-noncode-download-profile-contract-compatibility-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
DEFAULT_LIMIT = 100
FILES = ("manifest.json", "diff.json", "gate.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("diff.json", "gate.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = (
    "runtime_id",
    "version",
    "boundary",
    "diff_id",
    "diff_address",
    "gate_id",
    "gate_address",
    "audit_address",
    "query_address",
    "query_audit_address",
    "finding_count",
    "safe_count",
    "review_count",
    "breaking_count",
    "accepted",
    "release_ready",
    "state",
    "manifest",
    "diff",
    "gate",
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
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityManifest:
    """Manifest for the exact seven-file compatibility runtime."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "compatibility runtime manifest ID")
        self.files = tuple(_label(item, "compatibility runtime manifest file") for item in _sequence(files, "compatibility runtime manifest files", len(FILES)))
        if self.files != FILES:
            raise ValidationError("compatibility runtime manifest files are not canonical")
        self.artifact_addresses = tuple(_address(item, "compatibility runtime artifact address") for item in _sequence(artifact_addresses, "compatibility runtime artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        if len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES):
            raise ValidationError("compatibility runtime manifest artifacts are incomplete")
        self.content_address = _address(content_address, "compatibility runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("compatibility runtime manifest crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("compatibility runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityManifest:
        value = _mapping(value, "compatibility runtime manifest")
        _strict(value, set(cls.FIELDS), "compatibility runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRuntime:
    """Joined diff, policy gate, audits, query, and exact-file manifest."""

    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, diff_id: str, diff_address: str, gate_id: str, gate_address: str, audit_address: str, query_address: str, query_audit_address: str, finding_count: int, safe_count: int, review_count: int, breaking_count: int, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataProfileContractCompatibilityManifest | Mapping[str, Any], diff: diff_model.DownloadedDataProfileContractDiff | Mapping[str, Any], gate: compatibility_model.DownloadedDataProfileContractCompatibilityGate | Mapping[str, Any], audit: audit_model.DownloadedDataProfileContractCompatibilityAudit | Mapping[str, Any], query: query_model.DownloadedDataProfileContractCompatibilityQuery | Mapping[str, Any], query_audit: query_audit_model.DownloadedDataProfileContractCompatibilityQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "compatibility runtime ID")
        self.version = _text(version, "compatibility runtime version")
        self.boundary = _text(boundary, "compatibility runtime boundary", 512)
        self.diff_id = _label(diff_id, "compatibility runtime diff ID")
        self.diff_address = _address(diff_address, "compatibility runtime diff address", diff_model.DIFF_PREFIX)
        self.gate_id = _label(gate_id, "compatibility runtime gate ID")
        self.gate_address = _address(gate_address, "compatibility runtime gate address", compatibility_model.GATE_PREFIX)
        self.audit_address = _address(audit_address, "compatibility runtime audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "compatibility runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "compatibility runtime query audit address", query_audit_model.AUDIT_PREFIX)
        self.finding_count = _count(finding_count, "compatibility runtime finding count", compatibility_model.MAX_FINDINGS)
        self.safe_count = _count(safe_count, "compatibility runtime safe count", compatibility_model.MAX_FINDINGS)
        self.review_count = _count(review_count, "compatibility runtime review count", compatibility_model.MAX_FINDINGS)
        self.breaking_count = _count(breaking_count, "compatibility runtime breaking count", compatibility_model.MAX_FINDINGS)
        self.accepted = _bool(accepted, "compatibility runtime acceptance")
        self.release_ready = _bool(release_ready, "compatibility runtime release readiness")
        self.state = _label(state, "compatibility runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("compatibility runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityManifest) else DownloadedDataProfileContractCompatibilityManifest.from_mapping(manifest)
        self.diff = diff if isinstance(diff, diff_model.DownloadedDataProfileContractDiff) else diff_model.diff_from_mapping(diff)
        self.gate = gate if isinstance(gate, compatibility_model.DownloadedDataProfileContractCompatibilityGate) else compatibility_model.compatibility_from_mapping(gate)
        self.audit = audit if isinstance(audit, audit_model.DownloadedDataProfileContractCompatibilityAudit) else audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataProfileContractCompatibilityQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataProfileContractCompatibilityQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "compatibility runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("compatibility runtime version or boundary is not current")
        if (self.diff_id, self.diff_address) != (self.diff.diff_id, self.diff.content_address) or (self.gate_id, self.gate_address) != (self.gate.gate_id, self.gate.content_address):
            raise ValidationError("compatibility runtime identity or address does not replay")
        if self.gate.diff_address != self.diff_address or self.audit.gate_address != self.gate_address or self.query.gate_address != self.gate_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("compatibility runtime component links do not replay")
        if (self.audit_address, self.query_address, self.query_audit_address) != (self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("compatibility runtime artifact addresses do not replay")
        if (self.finding_count, self.safe_count, self.review_count, self.breaking_count) != (self.gate.finding_count, self.gate.safe_count, self.gate.review_count, self.gate.breaking_count):
            raise ValidationError("compatibility runtime aggregates do not replay")
        expected_accepted = self.gate.accepted and self.audit.accepted and self.query_audit.accepted
        if self.accepted != expected_accepted or self.release_ready != expected_accepted or (self.state == "complete") != expected_accepted:
            raise ValidationError("compatibility runtime readiness does not replay")
        if self.manifest.runtime_id != self.runtime_id or not _public(self.to_dict()):
            raise ValidationError("compatibility runtime manifest or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("compatibility runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "diff_id": self.diff_id, "diff_address": self.diff_address, "gate_id": self.gate_id, "gate_address": self.gate_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "finding_count": self.finding_count, "safe_count": self.safe_count, "review_count": self.review_count, "breaking_count": self.breaking_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "diff": self.diff.to_dict(), "gate": self.gate.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "diff", "gate", "audit", "query", "query_audit"}}
        summary["query_returned_count"] = self.query.returned_count
        summary["query_truncated"] = self.query.truncated
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRuntime:
        value = _mapping(value, "compatibility runtime")
        _strict(value, set(cls.FIELDS), "compatibility runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataProfileContractCompatibilityRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(diff: diff_model.DownloadedDataProfileContractDiff, *, runtime_id: str = DEFAULT_RUNTIME_ID, gate_id: str = compatibility_model.DEFAULT_GATE_ID, policy: compatibility_model.DownloadedDataProfileContractCompatibilityPolicy | None = None, resources: Sequence[str] = query_model.RESOURCES, outcome: str = "", resource: str = "", identity: str = "", reason: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataProfileContractCompatibilityRuntime:
    if not isinstance(diff, diff_model.DownloadedDataProfileContractDiff):
        raise ValidationError("compatibility runtime requires a typed contract diff")
    gate = compatibility_model.evaluate(diff, policy=policy, gate_id=gate_id)
    audit = audit_model.audit_gate(gate)
    query = query_model.query_gate(gate, resources=resources, outcome=outcome, resource=resource, identity=identity, reason=reason, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (diff.content_address, gate.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataProfileContractCompatibilityManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataProfileContractCompatibilityManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    accepted = gate.accepted and audit.accepted and query_audit.accepted
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "diff_id": diff.diff_id, "diff_address": diff.content_address, "gate_id": gate.gate_id, "gate_address": gate.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "finding_count": gate.finding_count, "safe_count": gate.safe_count, "review_count": gate.review_count, "breaking_count": gate.breaking_count, "accepted": accepted, "release_ready": accepted, "state": "complete" if accepted else "incomplete", "manifest": manifest, "diff": diff, "gate": gate, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataProfileContractCompatibilityRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRuntime:
    return DownloadedDataProfileContractCompatibilityRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataProfileContractCompatibilityRuntime) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRuntime.from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataProfileContractCompatibilityRuntime) -> str:
    value = DownloadedDataProfileContractCompatibilityRuntime.from_mapping(value.to_dict())
    rows = ((field, value.to_dict()[field]) for field in RUNTIME_FIELDS if field not in {"manifest", "diff", "gate", "audit", "query", "query_audit"})
    return "field,value\n" + "\n".join(f"{key},{json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in rows) + "\n"


def render_runtime_markdown(value: DownloadedDataProfileContractCompatibilityRuntime) -> str:
    value = DownloadedDataProfileContractCompatibilityRuntime.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Diff: `{value.diff_address}`", f"- Gate: `{value.gate_address}`", f"- Findings: `{value.finding_count}`", f"- Safe / review / breaking: `{value.safe_count} / {value.review_count} / {value.breaking_count}`", f"- State: `{value.state}`", f"- Decision: `{value.gate.decision}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("diff", value.diff_address), ("gate", value.gate_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: DownloadedDataProfileContractCompatibilityRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRuntime):
        raise ValidationError("compatibility runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("compatibility runtime destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-compatibility-runtime-", dir=str(parent)))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "diff.json", value.diff.to_dict())
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
        raise ValidationError("compatibility runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("compatibility runtime artifact is not valid JSON") from error
    return _mapping(value, "compatibility runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRuntime:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("compatibility runtime destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("compatibility runtime directory does not contain the exact file set")
    runtime = DownloadedDataProfileContractCompatibilityRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataProfileContractCompatibilityManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("compatibility runtime manifest differs from runtime.json")
    artifact_values = {"diff.json": diff_model.diff_from_mapping(_read_json(destination / "diff.json")), "gate.json": compatibility_model.compatibility_from_mapping(_read_json(destination / "gate.json")), "audit.json": audit_model.audit_from_mapping(_read_json(destination / "audit.json")), "query.json": query_model.query_from_mapping(_read_json(destination / "query.json")), "query-audit.json": query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json"))}
    expected = {"diff.json": runtime.diff, "gate.json": runtime.gate, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifact_values[name].to_dict() != document.to_dict():
            raise ValidationError(f"compatibility runtime artifact {name} differs from runtime.json")
    return runtime


def run_runtime(diff: diff_model.DownloadedDataProfileContractDiff, *, runtime_id: str = DEFAULT_RUNTIME_ID, gate_id: str = compatibility_model.DEFAULT_GATE_ID, policy: compatibility_model.DownloadedDataProfileContractCompatibilityPolicy | None = None, resources: Sequence[str] = query_model.RESOURCES, outcome: str = "", resource: str = "", identity: str = "", reason: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRuntime:
    value = build_runtime(diff, runtime_id=runtime_id, gate_id=gate_id, policy=policy, resources=resources, outcome=outcome, resource=resource, identity=identity, reason=reason, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "gate_id": {"type": "string"}, "gate_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "finding_count": {"type": "integer", "minimum": 0}, "safe_count": {"type": "integer", "minimum": 0}, "review_count": {"type": "integer", "minimum": 0}, "breaking_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "diff": diff_model.diff_schema(), "gate": compatibility_model.compatibility_schema(), "audit": audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"default_limit": DEFAULT_LIMIT, "max_artifacts": len(MANIFEST_ARTIFACT_FILES)}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "RUNTIME_FIELDS", "RUNTIME_PREFIX", "DownloadedDataProfileContractCompatibilityManifest", "DownloadedDataProfileContractCompatibilityRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
