"""Exact-file runtime handoff for quality-gate remediation plans."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate as gate_model
from . import downloaded_data_quality_diff_gate_remediation as remediation_model
from . import downloaded_data_quality_diff_gate_remediation_audit as remediation_audit_model
from . import downloaded_data_quality_diff_gate_remediation_query as remediation_query_model
from . import downloaded_data_quality_diff_gate_remediation_query_audit as remediation_query_audit_model
from ._safe_persistence import atomic_write_text, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-remediation-runtime-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_remediation_runtime"
RUNTIME_PREFIX = "glio-noncode-download-quality-diff-gate-remediation-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
DEFAULT_LIMIT = remediation_query_model.DEFAULT_LIMIT
DEFAULT_RESOURCES = ("summary", "actions", "required", "blocked")
FILES = ("manifest.json", "plan.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("plan.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = (
    "runtime_id", "version", "boundary", "gate_address", "plan_address", "audit_address",
    "query_address", "query_audit_address", "action_count", "required_action_count",
    "critical_action_count", "query_returned_count", "query_truncated", "accepted",
    "release_ready", "state", "manifest", "plan", "audit", "query", "query_audit",
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
        raise ValidationError(f"{field} must be a content address")
    namespace, digest = value.split(":", 1)
    if not namespace or (digest != "pending" and (len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest))):
        raise ValidationError(f"{field} must be a canonical content address")
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


class DownloadedDataQualityDiffGateRemediationManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "quality gate remediation runtime manifest ID")
        self.files = tuple(_label(item, "quality gate remediation runtime manifest file") for item in _sequence(files, "quality gate remediation runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "quality gate remediation runtime manifest artifact address") for item in _sequence(artifact_addresses, "quality gate remediation runtime manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "quality gate remediation runtime manifest address", MANIFEST_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality gate remediation runtime manifest address")
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("quality gate remediation runtime manifest does not replay")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("quality gate remediation runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationManifest":
        value = _mapping(value, "quality gate remediation runtime manifest")
        _strict(value, set(cls.FIELDS), "quality gate remediation runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataQualityDiffGateRemediationManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataQualityDiffGateRemediationRuntime:
    """Joined plan, audits, query, and exact manifest closure."""

    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, gate_address: str, plan_address: str, audit_address: str, query_address: str, query_audit_address: str, action_count: int, required_action_count: int, critical_action_count: int, query_returned_count: int, query_truncated: bool, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataQualityDiffGateRemediationManifest | Mapping[str, Any], plan: remediation_model.DownloadedDataQualityDiffGateRemediationPlan | Mapping[str, Any], audit: remediation_audit_model.DownloadedDataQualityDiffGateRemediationAudit | Mapping[str, Any], query: remediation_query_model.DownloadedDataQualityDiffGateRemediationQuery | Mapping[str, Any], query_audit: remediation_query_audit_model.DownloadedDataQualityDiffGateRemediationQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "quality gate remediation runtime ID")
        self.version = _text(version, "quality gate remediation runtime version")
        self.boundary = _text(boundary, "quality gate remediation runtime boundary", 512)
        self.gate_address = _address(gate_address, "quality gate remediation runtime gate address", gate_model.GATE_PREFIX)
        self.plan_address = _address(plan_address, "quality gate remediation runtime plan address", remediation_model.PLAN_PREFIX)
        self.audit_address = _address(audit_address, "quality gate remediation runtime audit address", remediation_audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "quality gate remediation runtime query address", remediation_query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "quality gate remediation runtime query audit address", remediation_query_audit_model.AUDIT_PREFIX)
        for field in ("action_count", "required_action_count", "critical_action_count"):
            setattr(self, field, _count(locals()[field], f"quality gate remediation runtime {field}", remediation_model.MAX_ACTIONS))
        self.query_returned_count = _count(query_returned_count, "quality gate remediation runtime query returned count", remediation_query_model.MAX_TOTAL_COUNT)
        self.query_truncated = _bool(query_truncated, "quality gate remediation runtime query truncation")
        self.accepted = _bool(accepted, "quality gate remediation runtime acceptance")
        self.release_ready = _bool(release_ready, "quality gate remediation runtime release readiness")
        self.state = _label(state, "quality gate remediation runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("quality gate remediation runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataQualityDiffGateRemediationManifest) else DownloadedDataQualityDiffGateRemediationManifest.from_mapping(manifest)
        self.plan = plan if isinstance(plan, remediation_model.DownloadedDataQualityDiffGateRemediationPlan) else remediation_model.plan_from_mapping(plan)
        self.audit = audit if isinstance(audit, remediation_audit_model.DownloadedDataQualityDiffGateRemediationAudit) else remediation_audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, remediation_query_model.DownloadedDataQualityDiffGateRemediationQuery) else remediation_query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, remediation_query_audit_model.DownloadedDataQualityDiffGateRemediationQueryAudit) else remediation_query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "quality gate remediation runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality gate remediation runtime address")
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality gate remediation runtime version or boundary is not current")
        if self.gate_address != self.plan.gate_address or self.plan_address != self.plan.content_address:
            raise ValidationError("quality gate remediation runtime gate or plan lineage does not replay")
        if (self.audit_address, self.query_address, self.query_audit_address) != (self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("quality gate remediation runtime component addresses do not replay")
        if self.audit.plan_address != self.plan_address or self.query.plan_address != self.plan_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("quality gate remediation runtime nested lineage does not replay")
        if self.manifest.artifact_addresses != (self.plan_address, self.audit_address, self.query_address, self.query_audit_address):
            raise ValidationError("quality gate remediation runtime manifest artifacts do not replay")
        if (self.action_count, self.required_action_count, self.critical_action_count) != (self.plan.action_count, self.plan.required_action_count, self.plan.critical_action_count):
            raise ValidationError("quality gate remediation runtime action counters do not replay")
        if (self.query_returned_count, self.query_truncated) != (self.query.returned_count, self.query.truncated):
            raise ValidationError("quality gate remediation runtime query counters do not replay")
        complete = self.audit.accepted and self.query_audit.accepted and not self.query.truncated
        if self.manifest.runtime_id != self.runtime_id or self.accepted != complete or self.release_ready != (complete and self.plan.accepted) or (self.state == "complete") != complete or not _public(self.to_dict()):
            raise ValidationError("quality gate remediation runtime readiness, manifest, or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("quality gate remediation runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary,
            "gate_address": self.gate_address, "plan_address": self.plan_address,
            "audit_address": self.audit_address, "query_address": self.query_address,
            "query_audit_address": self.query_audit_address, "action_count": self.action_count,
            "required_action_count": self.required_action_count, "critical_action_count": self.critical_action_count,
            "query_returned_count": self.query_returned_count, "query_truncated": self.query_truncated,
            "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state,
            "manifest": self.manifest.to_dict(), "plan": self.plan.to_dict(), "audit": self.audit.to_dict(),
            "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "plan", "audit", "query", "query_audit"}}
        summary.update({"gate_id": self.plan.gate_id, "plan_state": self.plan.state, "plan_decision": self.plan.decision})
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateRemediationRuntime":
        value = _mapping(value, "quality gate remediation runtime")
        _strict(value, set(cls.FIELDS), "quality gate remediation runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataQualityDiffGateRemediationRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(gate: gate_model.DownloadedDataQualityDiffGate, *, runtime_id: str = DEFAULT_RUNTIME_ID, plan_id: str = remediation_model.DEFAULT_PLAN_ID, resources: Sequence[str] = DEFAULT_RESOURCES, outcome: str = "", action: str = "", priority: str = "", required_only: bool = False, identity: str = "", reason: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> DownloadedDataQualityDiffGateRemediationRuntime:
    if not isinstance(gate, gate_model.DownloadedDataQualityDiffGate):
        raise ValidationError("quality gate remediation runtime requires a typed gate")
    plan = remediation_model.build_plan(gate, plan_id=plan_id)
    audit = remediation_audit_model.audit_plan(plan)
    query = remediation_query_model.query_plan(plan, resources=resources, outcome=outcome, action=action, priority=priority, required_only=required_only, identity=identity, reason=reason, text=text, offset=offset, limit=limit)
    query_audit = remediation_query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (plan.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataQualityDiffGateRemediationManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataQualityDiffGateRemediationManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    complete = audit.accepted and query_audit.accepted and not query.truncated
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "gate_address": gate.content_address, "plan_address": plan.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "action_count": plan.action_count, "required_action_count": plan.required_action_count, "critical_action_count": plan.critical_action_count, "query_returned_count": query.returned_count, "query_truncated": query.truncated, "accepted": complete, "release_ready": complete and plan.accepted, "state": "complete" if complete else "incomplete", "manifest": manifest, "plan": plan, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataQualityDiffGateRemediationRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateRemediationRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateRemediationRuntime:
    return DownloadedDataQualityDiffGateRemediationRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataQualityDiffGateRemediationRuntime) -> str:
    return canonical_json(runtime_from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataQualityDiffGateRemediationRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    return "field,value\n" + "\n".join(f"{field},{json.dumps(value.to_dict()[field], ensure_ascii=False, sort_keys=True)}" for field in RUNTIME_FIELDS if field not in {"manifest", "plan", "audit", "query", "query_audit"}) + "\n"


def render_runtime_markdown(value: DownloadedDataQualityDiffGateRemediationRuntime) -> str:
    value = runtime_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Remediation Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Plan state / decision: `{value.plan.state}` / `{value.plan.decision}`", f"- Actions: `{value.action_count}` (`{value.required_action_count}` required, `{value.critical_action_count}` critical)", f"- Query rows: `{value.query_returned_count}`", f"- Query truncated: `{value.query_truncated}`", f"- Runtime state: `{value.state}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("gate", value.gate_address), ("plan", value.plan_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    atomic_write_text(path, canonical_json(value))


def persist_runtime(value: DownloadedDataQualityDiffGateRemediationRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataQualityDiffGateRemediationRuntime):
        raise ValidationError("quality gate remediation runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or not overwrite):
        raise ValidationError("quality gate remediation runtime destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-quality-gate-remediation-runtime-", dir=str(destination.parent)))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "plan.json", value.plan.to_dict())
        _write(temporary / "audit.json", value.audit.to_dict())
        _write(temporary / "query.json", value.query.to_dict())
        _write(temporary / "query-audit.json", value.query_audit.to_dict())
        _write(temporary / "runtime.json", value.to_dict())
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("quality gate remediation runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        text = read_text(path, field="quality gate remediation runtime artifact")
        value = _strict_json_loads(text)
        if canonical_json(value) != text:
            raise ValidationError("quality gate remediation runtime artifact is not canonical JSON")
    except ValidationError:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("quality gate remediation runtime artifact is not valid JSON") from error
    return _mapping(value, "quality gate remediation runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataQualityDiffGateRemediationRuntime:
    destination = Path(destination)
    if destination.is_symlink() or not destination.is_dir() or tuple(sorted(path.name for path in destination.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("quality gate remediation runtime destination does not contain the exact file set")
    runtime = DownloadedDataQualityDiffGateRemediationRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataQualityDiffGateRemediationManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("quality gate remediation runtime manifest differs from runtime.json")
    artifacts = {
        "plan.json": remediation_model.plan_from_mapping(_read_json(destination / "plan.json")),
        "audit.json": remediation_audit_model.audit_from_mapping(_read_json(destination / "audit.json")),
        "query.json": remediation_query_model.query_from_mapping(_read_json(destination / "query.json")),
        "query-audit.json": remediation_query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json")),
    }
    expected = {"plan.json": runtime.plan, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifacts[name].to_dict() != document.to_dict():
            raise ValidationError(f"quality gate remediation runtime artifact {name} differs from runtime.json")
    return runtime


def run_runtime(gate: gate_model.DownloadedDataQualityDiffGate, *, runtime_id: str = DEFAULT_RUNTIME_ID, plan_id: str = remediation_model.DEFAULT_PLAN_ID, resources: Sequence[str] = DEFAULT_RESOURCES, outcome: str = "", action: str = "", priority: str = "", required_only: bool = False, identity: str = "", reason: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataQualityDiffGateRemediationRuntime:
    value = build_runtime(gate, runtime_id=runtime_id, plan_id=plan_id, resources=resources, outcome=outcome, action=action, priority=priority, required_only=required_only, identity=identity, reason=reason, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate remediation runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "gate_address": {"type": "string"}, "plan_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "action_count": {"type": "integer", "minimum": 0}, "required_action_count": {"type": "integer", "minimum": 0}, "critical_action_count": {"type": "integer", "minimum": 0}, "query_returned_count": {"type": "integer", "minimum": 0}, "query_truncated": {"type": "boolean"}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "plan": remediation_model.plan_schema(), "audit": remediation_audit_model.audit_schema(), "query": remediation_query_model.query_schema(), "query_audit": remediation_query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "default_resources": DEFAULT_RESOURCES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"default_limit": DEFAULT_LIMIT, "max_artifacts": len(MANIFEST_ARTIFACT_FILES)}}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RESOURCES", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "RUNTIME_FIELDS", "DownloadedDataQualityDiffGateRemediationManifest", "DownloadedDataQualityDiffGateRemediationRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
