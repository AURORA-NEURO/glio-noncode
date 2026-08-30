"""Persisted runtime closure for federation resolution and reconciliation.

This runtime is the executable read-only handoff for the resolution and plan
layers.  It loads registry directories or public registry JSON documents,
builds the federation and quorum evidence, derives the resolution and
per-peer plan, and can persist every projection as canonical JSON.  A replay
requires an exact nine-file directory, canonical bytes, manifest receipts,
and nested content-address links.  No operation in this module mutates a
source registry; the only write is an explicitly requested output handoff.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_audit as federation_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus as consensus_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus_audit as consensus_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan as plan_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan_audit as plan_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution as resolution_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution_audit as resolution_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_runtime as source_runtime_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = plan_model.VERSION + "-runtime-v1"
BOUNDARY = plan_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = plan_model.PLAN_PREFIX + "-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
ARTIFACT_PREFIX = RUNTIME_PREFIX + "-artifact"
DEFAULT_RUNTIME_ID = "consensus-certificate-observatory-archive-registry-federation-reconciliation-runtime"
MANIFEST_NAME = "manifest.json"
RUNTIME_NAME = "runtime.json"
FEDERATION_NAME = "federation.json"
FEDERATION_AUDIT_NAME = "federation-audit.json"
CONSENSUS_NAME = "consensus.json"
RESOLUTION_NAME = "resolution.json"
RESOLUTION_AUDIT_NAME = "resolution-audit.json"
PLAN_NAME = "plan.json"
PLAN_AUDIT_NAME = "plan-audit.json"
FILES = (MANIFEST_NAME, RUNTIME_NAME, FEDERATION_NAME, FEDERATION_AUDIT_NAME, CONSENSUS_NAME, RESOLUTION_NAME, RESOLUTION_AUDIT_NAME, PLAN_NAME, PLAN_AUDIT_NAME)
MAX_SOURCE_COUNT = federation_model.MAX_PEERS


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
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
    return plan_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime:
    """A complete resolution, plan, and audit handoff."""

    FIELDS = ("runtime_id", "version", "boundary", "federation", "federation_audit", "consensus", "consensus_audit", "resolution", "resolution_audit", "plan", "plan_audit", "source_count", "accepted", "release_ready", "state", "content_address")

    def __init__(self, runtime_id: str, version: str, boundary: str, federation: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation, federation_audit: federation_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit, consensus: consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus, consensus_audit: consensus_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit, resolution: resolution_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution, resolution_audit: resolution_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionAudit, plan: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan, plan_audit: plan_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit, source_count: int, accepted: bool, release_ready: bool, state: str, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "reconciliation runtime ID")
        self.version = _text(version, "reconciliation runtime version")
        self.boundary = _text(boundary, "reconciliation runtime boundary", 512)
        self.federation = federation_model.verify_federation(federation)
        self.federation_audit = federation_audit_model.verify_audit(federation_audit)
        self.consensus = consensus_model.verify_consensus(consensus)
        self.consensus_audit = consensus_audit_model.verify_audit(consensus_audit)
        self.resolution = resolution_model.verify_resolution(resolution)
        self.resolution_audit = resolution_audit_model.verify_audit(resolution_audit)
        self.plan = plan_model.verify_plan(plan)
        self.plan_audit = plan_audit_model.verify_audit(plan_audit)
        self.source_count = _count(source_count, "reconciliation runtime source count", MAX_SOURCE_COUNT, positive=True)
        self.accepted = _bool(accepted, "reconciliation runtime acceptance")
        self.release_ready = _bool(release_ready, "reconciliation runtime release readiness")
        self.state = _label(state, "reconciliation runtime state")
        self.content_address = _address(content_address, "reconciliation runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "reconciliation runtime address")
        self._validate()

    def _validate(self) -> None:
        audits_accepted = self.federation_audit.accepted and self.consensus_audit.accepted and self.resolution_audit.accepted and self.plan_audit.accepted
        if self.source_count != self.federation.peer_count or self.state not in {"ready", "review", "blocked"} or self.accepted != audits_accepted or self.release_ready != self.plan.release_ready or self.state != self.plan.state:
            raise ValidationError("reconciliation runtime outcome does not replay")
        if self.consensus.federation_address != self.federation.content_address or self.resolution.federation_address != self.federation.content_address or self.resolution.consensus_address != self.consensus.content_address or self.plan.federation_address != self.federation.content_address or self.plan.resolution_address != self.resolution.content_address:
            raise ValidationError("reconciliation runtime nested links do not replay")
        if self.federation_audit.federation_address != self.federation.content_address or self.consensus_audit.consensus_address != self.consensus.content_address or self.resolution_audit.resolution_address != self.resolution.content_address or self.plan_audit.plan_address != self.plan.content_address:
            raise ValidationError("reconciliation runtime audit links do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("reconciliation runtime crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("reconciliation runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "federation": self.federation.to_dict(), "federation_audit": self.federation_audit.to_dict(), "consensus": self.consensus.to_dict(), "consensus_audit": self.consensus_audit.to_dict(), "resolution": self.resolution.to_dict(), "resolution_audit": self.resolution_audit.to_dict(), "plan": self.plan.to_dict(), "plan_audit": self.plan_audit.to_dict(), "source_count": self.source_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "federation_id": self.federation.federation_id, "federation_address": self.federation.content_address, "consensus_address": self.consensus.content_address, "resolution_address": self.resolution.content_address, "plan_address": self.plan.content_address, "source_count": self.source_count, "peer_count": self.federation.peer_count, "entry_count": self.resolution.entry_count, "resolved_count": self.resolution.resolved_count, "review_count": self.resolution.review_count, "blocked_count": self.resolution.blocked_count, "operation_count": self.plan.operation_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime":
        value = _mapping(value, "reconciliation runtime")
        _strict(value, set(cls.FIELDS), "reconciliation runtime")
        return cls(value["runtime_id"], value["version"], value["boundary"], federation_model.federation_from_mapping(value["federation"]), federation_audit_model.audit_from_mapping(value["federation_audit"]), consensus_model.consensus_from_mapping(value["consensus"]), consensus_audit_model.audit_from_mapping(value["consensus_audit"]), resolution_model.resolution_from_mapping(value["resolution"]), resolution_audit_model.audit_from_mapping(value["resolution_audit"]), plan_model.plan_from_mapping(value["plan"]), plan_audit_model.audit_from_mapping(value["plan_audit"]), value["source_count"], value["accepted"], value["release_ready"], value["state"], value["content_address"])


def address_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(
    federation: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation,
    *,
    runtime_id: str = DEFAULT_RUNTIME_ID,
    consensus: consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus | None = None,
    resolution: resolution_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution | None = None,
    plan: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan | None = None,
) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime:
    federation = federation_model.verify_federation(federation)
    federation_audit = federation_audit_model.audit_federation(federation)
    selected_consensus = consensus_model.build_consensus(federation) if consensus is None else consensus_model.verify_consensus(consensus)
    consensus_audit = consensus_audit_model.audit_consensus(selected_consensus)
    selected_resolution = resolution_model.build_resolution(federation, consensus=selected_consensus) if resolution is None else resolution_model.verify_resolution(resolution)
    resolution_audit = resolution_audit_model.audit_resolution(selected_resolution)
    selected_plan = plan_model.build_plan(federation, selected_resolution, consensus=selected_consensus) if plan is None else plan_model.verify_plan(plan)
    plan_audit = plan_audit_model.audit_plan(selected_plan)
    accepted = federation_audit.accepted and consensus_audit.accepted and resolution_audit.accepted and plan_audit.accepted
    state = selected_plan.state
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime(runtime_id, VERSION, BOUNDARY, federation, federation_audit, selected_consensus, consensus_audit, selected_resolution, resolution_audit, selected_plan, plan_audit, federation.peer_count, accepted, selected_plan.release_ready, state, RUNTIME_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime(provisional.runtime_id, provisional.version, provisional.boundary, provisional.federation, provisional.federation_audit, provisional.consensus, provisional.consensus_audit, provisional.resolution, provisional.resolution_audit, provisional.plan, provisional.plan_audit, provisional.source_count, provisional.accepted, provisional.release_ready, provisional.state, address_runtime(provisional))


def _load_json_file(source: Path) -> Mapping[str, Any]:
    if source.is_symlink() or not source.is_file():
        raise ValidationError("reconciliation runtime source must be a regular file")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("reconciliation runtime source JSON is invalid") from error
    return _mapping(value, "reconciliation runtime source JSON")


def load_registry_input(source: Any) -> federation_model.registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry:
    if isinstance(source, federation_model.registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry):
        return federation_model.registry_model.verify_registry(source)
    if isinstance(source, Mapping):
        return federation_model.registry_model.registry_from_mapping(source)
    path = Path(source)
    if path.is_symlink():
        raise ValidationError("reconciliation runtime source cannot be a symlink")
    if path.is_dir():
        return federation_model.registry_model.load_registry(path)
    return federation_model.registry_model.registry_from_mapping(_load_json_file(path))


def run_runtime(sources: Sequence[Any], *, peer_ids: Sequence[str] | None = None, federation_id: str = federation_model.DEFAULT_FEDERATION_ID, runtime_id: str = DEFAULT_RUNTIME_ID, quorum: int | None = None, destination: str | Path | None = None, overwrite: bool = False) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime:
    inputs = tuple(_sequence(sources, "reconciliation runtime sources", MAX_SOURCE_COUNT))
    if not inputs:
        raise ValidationError("reconciliation runtime requires at least one registry source")
    registries = tuple(load_registry_input(source) for source in inputs)
    federation = federation_model.build_federation(registries, peer_ids=peer_ids, federation_id=federation_id)
    consensus = consensus_model.build_consensus(federation, quorum=quorum)
    value = build_runtime(federation, runtime_id=runtime_id, consensus=consensus)
    if destination is not None:
        write_runtime(value, destination, overwrite=overwrite)
    return value


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime:
    return verify_runtime(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime.from_mapping(value))


def verify_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime):
        raise ValidationError("reconciliation runtime verification requires a typed runtime")
    value._validate()
    if not value.content_address.endswith(":pending") and address_runtime(value) != value.content_address:
        raise ValidationError("reconciliation runtime address verification failed")
    return value


def runtime_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime) -> str:
    value = verify_runtime(value)
    lines = ["field,value"]
    for key, field_value in value.summary().items():
        lines.append(f"{key},{json.dumps(field_value, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def render_runtime_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime) -> str:
    value = verify_runtime(value)
    lines = ["# Archive Registry Federation Reconciliation Runtime", "", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Sources: `{value.source_count}`", f"- Entries: `{value.resolution.entry_count}`", f"- Resolved: `{value.resolution.resolved_count}`", f"- Review: `{value.resolution.review_count}`", f"- Blocked: `{value.resolution.blocked_count}`", f"- Operations: `{value.plan.operation_count}`", f"- Runtime address: `{value.content_address}`", "", plan_model.render_plan_markdown(value.plan)]
    return "\n".join(lines) + "\n"


def _artifact(name: str, raw: bytes) -> dict[str, Any]:
    return {"name": name, "size": len(raw), "hash": hash_bytes(raw, prefix=ARTIFACT_PREFIX)}


def _payload(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime) -> dict[str, bytes]:
    value = verify_runtime(value)
    return {RUNTIME_NAME: canonical_bytes(value.to_dict()), FEDERATION_NAME: canonical_bytes(value.federation.to_dict()), FEDERATION_AUDIT_NAME: canonical_bytes(value.federation_audit.to_dict()), CONSENSUS_NAME: canonical_bytes(value.consensus.to_dict()), RESOLUTION_NAME: canonical_bytes(value.resolution.to_dict()), RESOLUTION_AUDIT_NAME: canonical_bytes(value.resolution_audit.to_dict()), PLAN_NAME: canonical_bytes(value.plan.to_dict()), PLAN_AUDIT_NAME: canonical_bytes(value.plan_audit.to_dict())}


def manifest_document(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime) -> dict[str, Any]:
    value = verify_runtime(value)
    payload = _payload(value)
    body = {"version": VERSION, "boundary": BOUNDARY, "runtime_id": value.runtime_id, "runtime_address": value.content_address, "files": FILES, "artifacts": tuple(_artifact(name, payload[name]) for name in FILES[1:])}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def runtime_bytes(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime) -> Mapping[str, bytes]:
    payload = _payload(value)
    return {MANIFEST_NAME: canonical_bytes(manifest_document(value)), **payload}


def _write_atomic_directory(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("reconciliation runtime destination is not writable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="certificate-observatory-reconciliation-runtime-staging-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (staging / name).write_bytes(payload[name])
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix="certificate-observatory-reconciliation-runtime-backup-", dir=str(destination.parent)))
            backup.rmdir()
            os.replace(destination, backup)
            try:
                os.replace(staging, destination)
            except Exception:
                os.replace(backup, destination)
                raise
            shutil.rmtree(backup)
        else:
            os.replace(staging, destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def write_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_directory(Path(destination), runtime_bytes(value), overwrite=overwrite)


def _read_directory(source: str | Path) -> dict[str, bytes]:
    path = Path(source)
    if path.is_symlink() or not path.is_dir():
        raise ValidationError("reconciliation runtime input must be a regular directory")
    names = tuple(item.name for item in path.iterdir())
    if set(names) != set(FILES) or len(names) != len(FILES):
        raise ValidationError("reconciliation runtime member set is not exact")
    result = {}
    for name in FILES:
        member = path / name
        if member.is_symlink() or not member.is_file():
            raise ValidationError("reconciliation runtime member must be a regular file")
        result[name] = member.read_bytes()
    return result


def load_runtime(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime:
    raw = _read_directory(source)
    try:
        decoded = {name: json.loads(value.decode("utf-8")) for name, value in raw.items()}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("reconciliation runtime contains invalid JSON") from error
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("reconciliation runtime contains non-canonical JSON")
    manifest = _mapping(decoded[MANIFEST_NAME], "reconciliation runtime manifest")
    _strict(manifest, {"version", "boundary", "runtime_id", "runtime_address", "files", "artifacts", "manifest_address"}, "reconciliation runtime manifest")
    if tuple(manifest["files"]) != FILES or manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("reconciliation runtime manifest does not replay")
    artifacts = _sequence(manifest["artifacts"], "reconciliation runtime artifacts", len(FILES) - 1)
    if len(artifacts) != len(FILES) - 1:
        raise ValidationError("reconciliation runtime artifact count does not replay")
    for item in artifacts:
        item = _mapping(item, "reconciliation runtime artifact")
        _strict(item, {"name", "size", "hash"}, "reconciliation runtime artifact")
        name = item["name"]
        if name not in FILES[1:] or item["size"] != len(raw[name]) or item["hash"] != hash_bytes(raw[name], prefix=ARTIFACT_PREFIX):
            raise ValidationError("reconciliation runtime artifact receipt does not replay")
    value = runtime_from_mapping(decoded[RUNTIME_NAME])
    if value.runtime_id != manifest["runtime_id"] or value.content_address != manifest["runtime_address"]:
        raise ValidationError("reconciliation runtime manifest links do not replay")
    expected = {FEDERATION_NAME: value.federation.to_dict(), FEDERATION_AUDIT_NAME: value.federation_audit.to_dict(), CONSENSUS_NAME: value.consensus.to_dict(), RESOLUTION_NAME: value.resolution.to_dict(), RESOLUTION_AUDIT_NAME: value.resolution_audit.to_dict(), PLAN_NAME: value.plan.to_dict(), PLAN_AUDIT_NAME: value.plan_audit.to_dict()}
    if any(raw[name] != canonical_bytes(body) for name, body in expected.items()):
        raise ValidationError("reconciliation runtime projections do not replay")
    return value


def verify_runtime_directory(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime:
    return load_runtime(source)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "runtime_id", "runtime_address", "files", "artifacts", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "runtime_id": {"type": "string"}, "runtime_address": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}, "artifacts": {"type": "array", "items": {"type": "object"}}, "manifest_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime.FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "federation": federation_model.federation_schema(), "federation_audit": federation_audit_model.audit_schema(), "consensus": consensus_model.consensus_schema(), "consensus_audit": consensus_audit_model.audit_schema(), "resolution": resolution_model.resolution_schema(), "resolution_audit": resolution_audit_model.audit_schema(), "plan": plan_model.plan_schema(), "plan_audit": plan_audit_model.audit_schema(), "source_count": {"type": "integer", "minimum": 1}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["ready", "review", "blocked"]}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "analysis_only": True, "operations": ("run_runtime", "build_runtime", "load_registry_input", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "write_runtime", "load_runtime", "verify_runtime_directory"), "files": FILES, "max_sources": MAX_SOURCE_COUNT}


__all__ = ["ARTIFACT_PREFIX", "BOUNDARY", "CONSENSUS_NAME", "DEFAULT_RUNTIME_ID", "FEDERATION_AUDIT_NAME", "FEDERATION_NAME", "FILES", "MANIFEST_NAME", "MANIFEST_PREFIX", "PLAN_AUDIT_NAME", "PLAN_NAME", "RESOLUTION_AUDIT_NAME", "RESOLUTION_NAME", "RUNTIME_NAME", "RUNTIME_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationRuntime", "address_runtime", "build_runtime", "capabilities", "load_registry_input", "load_runtime", "manifest_document", "manifest_schema", "render_runtime_markdown", "run_runtime", "runtime_bytes", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema", "verify_runtime", "verify_runtime_directory", "write_runtime"]
