"""Exact-file runtime closure for remediation resolution handoffs."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_profile_contract_compatibility_remediation as remediation_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution as resolution_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_audit as audit_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_query as query_model,
)
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_query_audit as query_audit_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-runtime-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_runtime"
RUNTIME_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
FILES = ("manifest.json", "plan.json", "resolution.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("plan.json", "resolution.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = ("runtime_id", "version", "boundary", "plan_id", "plan_address", "resolution_id", "resolution_address", "audit_address", "query_address", "query_audit_address", "resolution_count", "required_open_count", "accepted", "release_ready", "state", "manifest", "plan", "resolution", "audit", "query", "query_audit", "content_address")
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


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
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
        return all(str(key).casefold() not in resolution_model.ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationResolutionManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "resolution runtime manifest ID")
        self.files = tuple(_label(item, "resolution runtime manifest file") for item in _sequence(files, "resolution runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "resolution runtime artifact address") for item in _sequence(artifact_addresses, "resolution runtime artifact addresses", MAX_ARTIFACTS))
        self.content_address = _address(content_address, "resolution runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != MAX_ARTIFACTS or not _public(self.to_dict()):
            raise ValidationError("resolution runtime manifest is not canonical")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("resolution runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionManifest:
        value = _mapping(value, "resolution runtime manifest")
        _strict(value, set(cls.FIELDS), "resolution runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionManifest):
        raise ValidationError("resolution manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, plan_id: str, plan_address: str, resolution_id: str, resolution_address: str, audit_address: str, query_address: str, query_audit_address: str, resolution_count: int, required_open_count: int, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataProfileContractCompatibilityRemediationResolutionManifest | Mapping[str, Any], plan: remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan | Mapping[str, Any], resolution: resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution | Mapping[str, Any], audit: audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionAudit | Mapping[str, Any], query: query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionQuery | Mapping[str, Any], query_audit: query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "resolution runtime ID")
        self.version = _text(version, "resolution runtime version")
        self.boundary = _text(boundary, "resolution runtime boundary", 512)
        self.plan_id = _label(plan_id, "resolution runtime plan ID")
        self.plan_address = _address(plan_address, "resolution runtime plan address", remediation_model.PLAN_PREFIX)
        self.resolution_id = _label(resolution_id, "resolution runtime resolution ID")
        self.resolution_address = _address(resolution_address, "resolution runtime resolution address", resolution_model.RESOLUTION_PREFIX)
        self.audit_address = _address(audit_address, "resolution runtime audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "resolution runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "resolution runtime query audit address", query_audit_model.AUDIT_PREFIX)
        self.resolution_count = _count(resolution_count, "resolution runtime entry count", resolution_model.MAX_ENTRIES)
        self.required_open_count = _count(required_open_count, "resolution runtime open count", resolution_model.MAX_ENTRIES)
        self.accepted = _bool(accepted, "resolution runtime acceptance")
        self.release_ready = _bool(release_ready, "resolution runtime release readiness")
        self.state = _label(state, "resolution runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("resolution runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionManifest.from_mapping(manifest)
        self.plan = plan if isinstance(plan, remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan) else remediation_model.plan_from_mapping(plan)
        self.resolution = resolution if isinstance(resolution, resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution) else resolution_model.resolution_from_mapping(resolution)
        self.audit = audit if isinstance(audit, audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionAudit) else audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataProfileContractCompatibilityRemediationResolutionQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataProfileContractCompatibilityRemediationResolutionQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "resolution runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("resolution runtime version or boundary is not current")
        if (self.plan_id, self.plan_address) != (self.plan.plan_id, self.plan.content_address) or (self.resolution_id, self.resolution_address) != (self.resolution.resolution_id, self.resolution.content_address):
            raise ValidationError("resolution runtime identity or address does not replay")
        if self.resolution.plan_address != self.plan_address or self.audit.resolution_address != self.resolution_address or self.query.resolution_address != self.resolution_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("resolution runtime component links do not replay")
        if (self.audit_address, self.query_address, self.query_audit_address) != (self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("resolution runtime artifact addresses do not replay")
        if (self.resolution_count, self.required_open_count) != (self.resolution.resolution_count, self.resolution.required_open_count):
            raise ValidationError("resolution runtime aggregates do not replay")
        expected_accepted = self.resolution.accepted and self.audit.accepted and self.query_audit.accepted
        if self.accepted != expected_accepted or self.release_ready != expected_accepted or (self.state == "complete") != expected_accepted:
            raise ValidationError("resolution runtime readiness does not replay")
        if self.manifest.runtime_id != self.runtime_id or not _public(self.to_dict()):
            raise ValidationError("resolution runtime manifest or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("resolution runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "plan_id": self.plan_id, "plan_address": self.plan_address, "resolution_id": self.resolution_id, "resolution_address": self.resolution_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "resolution_count": self.resolution_count, "required_open_count": self.required_open_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "plan": self.plan.to_dict(), "resolution": self.resolution.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "plan", "resolution", "audit", "query", "query_audit"}}
        summary["query_returned_count"] = self.query.returned_count
        summary["query_truncated"] = self.query.truncated
        summary["resolution_state"] = self.resolution.state
        summary["resolution_decision"] = self.resolution.decision
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime:
        value = _mapping(value, "resolution runtime")
        _strict(value, set(cls.FIELDS), "resolution runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime):
        raise ValidationError("resolution runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(plan: remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan, *, runtime_id: str = DEFAULT_RUNTIME_ID, resolution_id: str = resolution_model.DEFAULT_RESOLUTION_ID, statuses: Mapping[str, str] | None = None, rationales: Mapping[str, str] | None = None, evidence: Mapping[str, Sequence[str]] | None = None, resources: Sequence[str] = query_model.RESOURCES, status: str = "", action: str = "", priority: str = "", required: bool = False, identity: str = "", text: str = "", offset: int = 0, limit: int = query_model.MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime:
    if not isinstance(plan, remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan):
        raise ValidationError("resolution runtime requires a typed remediation plan")
    resolution = resolution_model.build_resolution(plan, resolution_id=resolution_id, statuses=statuses, rationales=rationales, evidence=evidence)
    audit = audit_model.audit_resolution(resolution)
    query = query_model.query_resolution(resolution, resources=resources, status=status, action=action, priority=priority, required=required, identity=identity, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (plan.content_address, resolution.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    accepted = resolution.accepted and audit.accepted and query_audit.accepted
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "plan_id": plan.plan_id, "plan_address": plan.content_address, "resolution_id": resolution.resolution_id, "resolution_address": resolution.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "resolution_count": resolution.resolution_count, "required_open_count": resolution.required_open_count, "accepted": accepted, "release_ready": accepted, "state": "complete" if accepted else "incomplete", "manifest": manifest, "plan": plan, "resolution": resolution, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime.from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime.from_mapping(value.to_dict())
    rows = ((field, value.to_dict()[field]) for field in RUNTIME_FIELDS if field not in {"manifest", "plan", "resolution", "audit", "query", "query_audit"})
    return "field,value\n" + "\n".join(f"{key},{json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in rows) + "\n"


def render_runtime_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Plan: `{value.plan_address}`", f"- Resolution: `{value.resolution_address}`", f"- Entries: `{value.resolution_count}`", f"- Open required: `{value.required_open_count}`", f"- Resolution decision: `{value.resolution.decision}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("plan", value.plan_address), ("resolution", value.resolution_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime):
        raise ValidationError("resolution runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("resolution runtime destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-resolution-runtime-", dir=str(parent)))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "plan.json", value.plan.to_dict())
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
        raise ValidationError("resolution runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("resolution runtime artifact is not valid JSON") from error
    return _mapping(value, "resolution runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("resolution runtime destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("resolution runtime directory does not contain the exact file set")
    runtime = DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("resolution runtime manifest differs from runtime.json")
    artifacts = {"plan.json": remediation_model.plan_from_mapping(_read_json(destination / "plan.json")), "resolution.json": resolution_model.resolution_from_mapping(_read_json(destination / "resolution.json")), "audit.json": audit_model.audit_from_mapping(_read_json(destination / "audit.json")), "query.json": query_model.query_from_mapping(_read_json(destination / "query.json")), "query-audit.json": query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json"))}
    expected = {"plan.json": runtime.plan, "resolution.json": runtime.resolution, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifacts[name].to_dict() != document.to_dict():
            raise ValidationError(f"resolution runtime artifact {name} differs from runtime.json")
    if tuple(runtime.manifest.artifact_addresses) != tuple(artifacts[name].content_address for name in MANIFEST_ARTIFACT_FILES):
        raise ValidationError("resolution runtime manifest artifact addresses do not replay")
    return runtime


def run_runtime(plan: remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan, *, runtime_id: str = DEFAULT_RUNTIME_ID, resolution_id: str = resolution_model.DEFAULT_RESOLUTION_ID, statuses: Mapping[str, str] | None = None, rationales: Mapping[str, str] | None = None, evidence: Mapping[str, Sequence[str]] | None = None, resources: Sequence[str] = query_model.RESOURCES, status: str = "", action: str = "", priority: str = "", required: bool = False, identity: str = "", text: str = "", offset: int = 0, limit: int = query_model.MAX_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime:
    value = build_runtime(plan, runtime_id=runtime_id, resolution_id=resolution_id, statuses=statuses, rationales=rationales, evidence=evidence, resources=resources, status=status, action=action, priority=priority, required=required, identity=identity, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": MAX_ARTIFACTS, "maxItems": MAX_ARTIFACTS}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "plan_id": {"type": "string"}, "plan_address": {"type": "string"}, "resolution_id": {"type": "string"}, "resolution_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "resolution_count": {"type": "integer", "minimum": 0}, "required_open_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "plan": remediation_model.plan_schema(), "resolution": resolution_model.resolution_schema(), "audit": audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"max_artifacts": MAX_ARTIFACTS}}


__all__ = ["BOUNDARY", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ARTIFACTS", "RUNTIME_FIELDS", "RUNTIME_PREFIX", "DownloadedDataProfileContractCompatibilityRemediationResolutionManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
