"""Exact-file runtime closure for compatibility remediation handoffs."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_profile_contract_compatibility as compatibility_model
from . import downloaded_data_profile_contract_compatibility_remediation as remediation_model
from . import downloaded_data_profile_contract_compatibility_remediation_audit as audit_model
from . import downloaded_data_profile_contract_compatibility_remediation_query as query_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_query_audit as query_audit_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-runtime-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_runtime"
RUNTIME_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = RUNTIME_PREFIX
FILES = ("manifest.json", "gate.json", "plan.json", "audit.json", "query.json", "query-audit.json", "runtime.json")
MANIFEST_ARTIFACT_FILES = ("gate.json", "plan.json", "audit.json", "query.json", "query-audit.json")
MANIFEST_FIELDS = ("runtime_id", "files", "artifact_addresses", "content_address")
RUNTIME_FIELDS = (
    "runtime_id",
    "version",
    "boundary",
    "gate_id",
    "gate_address",
    "plan_id",
    "plan_address",
    "audit_address",
    "query_address",
    "query_audit_address",
    "action_count",
    "required_action_count",
    "accepted",
    "release_ready",
    "state",
    "manifest",
    "gate",
    "plan",
    "audit",
    "query",
    "query_audit",
    "content_address",
)
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
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in compatibility_model.ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, files: tuple[str, ...] | list[str], artifact_addresses: tuple[str, ...] | list[str], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "remediation runtime manifest ID")
        self.files = tuple(_label(item, "remediation runtime manifest file") for item in _sequence(files, "remediation runtime manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "remediation runtime manifest artifact address") for item in _sequence(artifact_addresses, "remediation runtime manifest artifact addresses", MAX_ARTIFACTS))
        self.content_address = _address(content_address, "remediation runtime manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != MAX_ARTIFACTS or not _public(self.to_dict()):
            raise ValidationError("remediation runtime manifest is not canonical")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("remediation runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationManifest:
        value = _mapping(value, "remediation runtime manifest")
        _strict(value, set(cls.FIELDS), "remediation runtime manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationManifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationRuntime:
    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, gate_id: str, gate_address: str, plan_id: str, plan_address: str, audit_address: str, query_address: str, query_audit_address: str, action_count: int, required_action_count: int, accepted: bool, release_ready: bool, state: str, manifest: DownloadedDataProfileContractCompatibilityRemediationManifest | Mapping[str, Any], gate: compatibility_model.DownloadedDataProfileContractCompatibilityGate | Mapping[str, Any], plan: remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan | Mapping[str, Any], audit: audit_model.DownloadedDataProfileContractCompatibilityRemediationAudit | Mapping[str, Any], query: query_model.DownloadedDataProfileContractCompatibilityRemediationQuery | Mapping[str, Any], query_audit: query_audit_model.DownloadedDataProfileContractCompatibilityRemediationQueryAudit | Mapping[str, Any], content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "remediation runtime ID")
        self.version = _text(version, "remediation runtime version")
        self.boundary = _text(boundary, "remediation runtime boundary", 512)
        self.gate_id = _label(gate_id, "remediation runtime gate ID")
        self.gate_address = _address(gate_address, "remediation runtime gate address", compatibility_model.GATE_PREFIX)
        self.plan_id = _label(plan_id, "remediation runtime plan ID")
        self.plan_address = _address(plan_address, "remediation runtime plan address", remediation_model.PLAN_PREFIX)
        self.audit_address = _address(audit_address, "remediation runtime audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "remediation runtime query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "remediation runtime query audit address", query_audit_model.AUDIT_PREFIX)
        self.action_count = _count(action_count, "remediation runtime action count", remediation_model.MAX_ACTIONS)
        self.required_action_count = _count(required_action_count, "remediation runtime required action count", remediation_model.MAX_ACTIONS)
        self.accepted = _bool(accepted, "remediation runtime acceptance")
        self.release_ready = _bool(release_ready, "remediation runtime release readiness")
        self.state = _label(state, "remediation runtime state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("remediation runtime state is unsupported")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationManifest) else DownloadedDataProfileContractCompatibilityRemediationManifest.from_mapping(manifest)
        self.gate = gate if isinstance(gate, compatibility_model.DownloadedDataProfileContractCompatibilityGate) else compatibility_model.compatibility_from_mapping(gate)
        self.plan = plan if isinstance(plan, remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan) else remediation_model.plan_from_mapping(plan)
        self.audit = audit if isinstance(audit, audit_model.DownloadedDataProfileContractCompatibilityRemediationAudit) else audit_model.audit_from_mapping(audit)
        self.query = query if isinstance(query, query_model.DownloadedDataProfileContractCompatibilityRemediationQuery) else query_model.query_from_mapping(query)
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.DownloadedDataProfileContractCompatibilityRemediationQueryAudit) else query_audit_model.audit_from_mapping(query_audit)
        self.content_address = _address(content_address, "remediation runtime address", RUNTIME_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("remediation runtime version or boundary is not current")
        if (self.gate_id, self.gate_address) != (self.gate.gate_id, self.gate.content_address) or (self.plan_id, self.plan_address) != (self.plan.plan_id, self.plan.content_address):
            raise ValidationError("remediation runtime identity or address does not replay")
        if self.plan.gate_address != self.gate_address or self.audit.plan_address != self.plan_address or self.query.plan_address != self.plan_address or self.query_audit.query_address != self.query_address:
            raise ValidationError("remediation runtime component links do not replay")
        if (self.audit_address, self.query_address, self.query_audit_address) != (self.audit.content_address, self.query.content_address, self.query_audit.content_address):
            raise ValidationError("remediation runtime artifact addresses do not replay")
        if (self.action_count, self.required_action_count) != (self.plan.action_count, self.plan.required_action_count):
            raise ValidationError("remediation runtime aggregates do not replay")
        expected_accepted = self.plan.accepted and self.audit.accepted and self.query_audit.accepted
        if self.accepted != expected_accepted or self.release_ready != expected_accepted or (self.state == "complete") != expected_accepted:
            raise ValidationError("remediation runtime readiness does not replay")
        if self.manifest.runtime_id != self.runtime_id or not _public(self.to_dict()):
            raise ValidationError("remediation runtime manifest or public boundary failed")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("remediation runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "gate_id": self.gate_id, "gate_address": self.gate_address, "plan_id": self.plan_id, "plan_address": self.plan_address, "audit_address": self.audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "action_count": self.action_count, "required_action_count": self.required_action_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "manifest": self.manifest.to_dict(), "gate": self.gate.to_dict(), "plan": self.plan.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        summary = {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "gate", "plan", "audit", "query", "query_audit"}}
        summary["query_returned_count"] = self.query.returned_count
        summary["query_truncated"] = self.query.truncated
        summary["gate_state"] = self.gate.state
        summary["gate_decision"] = self.gate.decision
        return summary

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationRuntime:
        value = _mapping(value, "remediation runtime")
        _strict(value, set(cls.FIELDS), "remediation runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: DownloadedDataProfileContractCompatibilityRemediationRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(gate: compatibility_model.DownloadedDataProfileContractCompatibilityGate, *, runtime_id: str = DEFAULT_RUNTIME_ID, plan_id: str = remediation_model.DEFAULT_PLAN_ID, resources: tuple[str, ...] = query_model.RESOURCES, outcome: str = "", resource: str = "", priority: str = "", action: str = "", required: bool = False, identity: str = "", reason: str = "", text: str = "", offset: int = 0, limit: int = query_model.MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationRuntime:
    if not isinstance(gate, compatibility_model.DownloadedDataProfileContractCompatibilityGate):
        raise ValidationError("remediation runtime requires a typed compatibility gate")
    plan = remediation_model.build_plan(gate, plan_id=plan_id)
    audit = audit_model.audit_plan(plan)
    query = query_model.query_plan(plan, resources=resources, outcome=outcome, resource=resource, priority=priority, action=action, required=required, identity=identity, reason=reason, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    manifest_body = {"runtime_id": runtime_id, "files": FILES, "artifact_addresses": (gate.content_address, plan.content_address, audit.content_address, query.content_address, query_audit.content_address)}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataProfileContractCompatibilityRemediationManifest(**manifest_body, content_address=address_manifest(manifest_provisional))
    accepted = plan.accepted and audit.accepted and query_audit.accepted
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "gate_id": gate.gate_id, "gate_address": gate.content_address, "plan_id": plan.plan_id, "plan_address": plan.content_address, "audit_address": audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "action_count": plan.action_count, "required_action_count": plan.required_action_count, "accepted": accepted, "release_ready": accepted, "state": "complete" if accepted else "incomplete", "manifest": manifest, "gate": gate, "plan": plan, "audit": audit, "query": query, "query_audit": query_audit}
    provisional = DownloadedDataProfileContractCompatibilityRemediationRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationRuntime(**body, content_address=address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationRuntime:
    return DownloadedDataProfileContractCompatibilityRemediationRuntime.from_mapping(value)


def runtime_json(value: DownloadedDataProfileContractCompatibilityRemediationRuntime) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationRuntime.from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: DownloadedDataProfileContractCompatibilityRemediationRuntime) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationRuntime.from_mapping(value.to_dict())
    rows = ((field, value.to_dict()[field]) for field in RUNTIME_FIELDS if field not in {"manifest", "gate", "plan", "audit", "query", "query_audit"})
    return "field,value\n" + "\n".join(f"{key},{json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in rows) + "\n"


def render_runtime_markdown(value: DownloadedDataProfileContractCompatibilityRemediationRuntime) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationRuntime.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Gate: `{value.gate_address}`", f"- Plan: `{value.plan_address}`", f"- Actions: `{value.action_count}`", f"- Required: `{value.required_action_count}`", f"- Gate decision: `{value.gate.decision}`", f"- Plan decision: `{value.plan.decision}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| component | address |", "| --- | --- |"]
    lines.extend(f"| {name} | `{address}` |" for name, address in (("gate", value.gate_address), ("plan", value.plan_address), ("audit", value.audit_address), ("query", value.query_address), ("query-audit", value.query_audit_address), ("manifest", value.manifest.content_address)))
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_runtime(value: DownloadedDataProfileContractCompatibilityRemediationRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationRuntime):
        raise ValidationError("remediation runtime persistence requires a typed runtime")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("remediation runtime destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-remediation-runtime-", dir=str(parent)))
    try:
        _write(temporary / "manifest.json", value.manifest.to_dict())
        _write(temporary / "gate.json", value.gate.to_dict())
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
        raise ValidationError("remediation runtime destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("remediation runtime artifact is not valid JSON") from error
    return _mapping(value, "remediation runtime artifact")


def load_runtime(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationRuntime:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("remediation runtime destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("remediation runtime directory does not contain the exact file set")
    runtime = DownloadedDataProfileContractCompatibilityRemediationRuntime.from_mapping(_read_json(destination / "runtime.json"))
    manifest = DownloadedDataProfileContractCompatibilityRemediationManifest.from_mapping(_read_json(destination / "manifest.json"))
    if manifest.to_dict() != runtime.manifest.to_dict():
        raise ValidationError("remediation runtime manifest differs from runtime.json")
    artifact_values = {"gate.json": compatibility_model.compatibility_from_mapping(_read_json(destination / "gate.json")), "plan.json": remediation_model.plan_from_mapping(_read_json(destination / "plan.json")), "audit.json": audit_model.audit_from_mapping(_read_json(destination / "audit.json")), "query.json": query_model.query_from_mapping(_read_json(destination / "query.json")), "query-audit.json": query_audit_model.audit_from_mapping(_read_json(destination / "query-audit.json"))}
    expected = {"gate.json": runtime.gate, "plan.json": runtime.plan, "audit.json": runtime.audit, "query.json": runtime.query, "query-audit.json": runtime.query_audit}
    for name, document in expected.items():
        if artifact_values[name].to_dict() != document.to_dict():
            raise ValidationError(f"remediation runtime artifact {name} differs from runtime.json")
    if tuple(runtime.manifest.artifact_addresses) != tuple(artifact_values[name].content_address for name in MANIFEST_ARTIFACT_FILES):
        raise ValidationError("remediation runtime manifest artifact addresses do not replay")
    return runtime


def run_runtime(gate: compatibility_model.DownloadedDataProfileContractCompatibilityGate, *, runtime_id: str = DEFAULT_RUNTIME_ID, plan_id: str = remediation_model.DEFAULT_PLAN_ID, resources: tuple[str, ...] = query_model.RESOURCES, outcome: str = "", resource: str = "", priority: str = "", action: str = "", required: bool = False, identity: str = "", reason: str = "", text: str = "", offset: int = 0, limit: int = query_model.MAX_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationRuntime:
    value = build_runtime(gate, runtime_id=runtime_id, plan_id=plan_id, resources=resources, outcome=outcome, resource=resource, priority=priority, action=action, required=required, identity=identity, reason=reason, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": MAX_ARTIFACTS, "maxItems": MAX_ARTIFACTS}, "content_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "gate_id": {"type": "string"}, "gate_address": {"type": "string"}, "plan_id": {"type": "string"}, "plan_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "action_count": {"type": "integer", "minimum": 0}, "required_action_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["complete", "incomplete"]}, "manifest": manifest_schema(), "gate": compatibility_model.compatibility_schema(), "plan": remediation_model.plan_schema(), "audit": audit_model.audit_schema(), "query": query_model.query_schema(), "query_audit": query_audit_model.audit_schema(), "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "files": FILES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"max_artifacts": MAX_ARTIFACTS}}


__all__ = ["BOUNDARY", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ARTIFACTS", "RUNTIME_FIELDS", "RUNTIME_PREFIX", "DownloadedDataProfileContractCompatibilityRemediationManifest", "DownloadedDataProfileContractCompatibilityRemediationRuntime", "address_manifest", "address_runtime", "build_runtime", "capabilities", "load_runtime", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema"]
