"""End-to-end runtime and exact persistence for registry federation analysis."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_audit as federation_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus as consensus_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus_audit as consensus_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_report as report_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = federation_model.VERSION + "-runtime-v1"
BOUNDARY = federation_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = federation_model.FEDERATION_PREFIX + "-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
ARTIFACT_PREFIX = RUNTIME_PREFIX + "-artifact"
DEFAULT_RUNTIME_ID = "consensus-certificate-observatory-archive-registry-federation-runtime"
MANIFEST_NAME = "manifest.json"
RUNTIME_NAME = "runtime.json"
FEDERATION_NAME = "federation.json"
AUDITS_NAME = "audits.json"
CONSENSUS_NAME = "consensus.json"
REPORT_NAME = "report.json"
FILES = (MANIFEST_NAME, RUNTIME_NAME, FEDERATION_NAME, AUDITS_NAME, CONSENSUS_NAME, REPORT_NAME)
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
    return federation_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime:
    FIELDS = ("runtime_id", "federation", "federation_audit", "consensus", "consensus_audit", "report", "source_count", "accepted", "state", "content_address")

    def __init__(self, runtime_id: str, federation: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation, federation_audit: federation_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationAudit, consensus: consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus, consensus_audit: consensus_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusAudit, report: report_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport, source_count: int, accepted: bool, state: str, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "federation runtime ID")
        self.federation = federation_model.verify_federation(federation)
        self.federation_audit = federation_audit_model.verify_audit(federation_audit)
        self.consensus = consensus_model.verify_consensus(consensus)
        self.consensus_audit = consensus_audit_model.verify_audit(consensus_audit)
        self.report = report_model.verify_report(report)
        self.source_count = _count(source_count, "federation runtime source count", MAX_SOURCE_COUNT, positive=True)
        self.accepted = _bool(accepted, "federation runtime acceptance")
        self.state = _label(state, "federation runtime state")
        self.content_address = _address(content_address, "federation runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation runtime address")
        self._validate()

    def _validate(self) -> None:
        if self.source_count != self.federation.peer_count or self.state not in report_model.STATUSES or self.accepted != self.report.accepted or self.state != self.report.status:
            raise ValidationError("federation runtime source or outcome links do not replay")
        if self.federation.content_address != self.consensus.federation_address or self.federation.content_address != self.report.federation_address or self.consensus.content_address != self.report.consensus_address:
            raise ValidationError("federation runtime evidence links do not replay")
        if self.federation_audit.federation_address != self.federation.content_address or self.consensus_audit.consensus_address != self.consensus.content_address:
            raise ValidationError("federation runtime audit links do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("federation runtime crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("federation runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "federation": self.federation.to_dict(), "federation_audit": self.federation_audit.to_dict(), "consensus": self.consensus.to_dict(), "consensus_audit": self.consensus_audit.to_dict(), "report": self.report.to_dict(), "source_count": self.source_count, "accepted": self.accepted, "state": self.state, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "federation_id": self.federation.federation_id, "federation_address": self.federation.content_address, "consensus_address": self.consensus.content_address, "source_count": self.source_count, "peer_count": self.federation.peer_count, "observation_count": self.federation.observation_count, "conflict_count": self.federation.conflict_count, "selected_count": self.consensus.selected_count, "held_count": self.consensus.held_count, "status": self.report.status, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime":
        value = _mapping(value, "federation runtime")
        _strict(value, set(cls.FIELDS), "federation runtime")
        return cls(value["runtime_id"], federation_model.federation_from_mapping(value["federation"]), federation_audit_model.audit_from_mapping(value["federation_audit"]), consensus_model.consensus_from_mapping(value["consensus"]), consensus_audit_model.audit_from_mapping(value["consensus_audit"]), report_model.report_from_mapping(value["report"]), value["source_count"], value["accepted"], value["state"], value["content_address"])


def address_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(federation: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation, *, runtime_id: str = DEFAULT_RUNTIME_ID, consensus: consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus | None = None, report: report_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReport | None = None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime:
    federation = federation_model.verify_federation(federation)
    federation_audit = federation_audit_model.audit_federation(federation)
    selected_consensus = consensus_model.build_consensus(federation) if consensus is None else consensus_model.verify_consensus(consensus)
    selected_consensus_audit = consensus_audit_model.audit_consensus(selected_consensus)
    selected_report = report_model.build_report(federation, consensus=selected_consensus, federation_audit=federation_audit, consensus_audit=selected_consensus_audit) if report is None else report_model.verify_report(report)
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime(runtime_id, federation, federation_audit, selected_consensus, selected_consensus_audit, selected_report, federation.peer_count, selected_report.accepted, selected_report.status, RUNTIME_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime(provisional.runtime_id, provisional.federation, provisional.federation_audit, provisional.consensus, provisional.consensus_audit, provisional.report, provisional.source_count, provisional.accepted, provisional.state, address_runtime(provisional))


def _load_json_file(source: Path) -> Mapping[str, Any]:
    if source.is_symlink() or not source.is_file():
        raise ValidationError("federation registry input must be a regular file")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("federation registry JSON is invalid") from error
    return _mapping(value, "federation registry JSON")


def load_registry_input(source: Any) -> registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry:
    if isinstance(source, registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry):
        return registry_model.verify_registry(source)
    if isinstance(source, Mapping):
        return registry_model.registry_from_mapping(source)
    path = Path(source)
    if path.is_symlink():
        raise ValidationError("federation registry input cannot be a symlink")
    if path.is_dir():
        return registry_model.load_registry(path)
    return registry_model.registry_from_mapping(_load_json_file(path))


def run_runtime(sources: Sequence[Any], *, peer_ids: Sequence[str] | None = None, federation_id: str = federation_model.DEFAULT_FEDERATION_ID, runtime_id: str = DEFAULT_RUNTIME_ID, quorum: int | None = None, destination: str | Path | None = None, overwrite: bool = False) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime:
    inputs = tuple(_sequence(sources, "federation runtime sources", MAX_SOURCE_COUNT))
    if not inputs:
        raise ValidationError("federation runtime requires at least one registry source")
    registries = tuple(load_registry_input(source) for source in inputs)
    federation = federation_model.build_federation(registries, peer_ids=peer_ids, federation_id=federation_id)
    consensus = consensus_model.build_consensus(federation, quorum=quorum)
    value = build_runtime(federation, runtime_id=runtime_id, consensus=consensus)
    if destination is not None:
        write_runtime(value, destination, overwrite=overwrite)
    return value


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime:
    return verify_runtime(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime.from_mapping(value))


def verify_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime):
        raise ValidationError("federation runtime verification requires a typed runtime")
    value._validate()
    if not value.content_address.endswith(":pending") and address_runtime(value) != value.content_address:
        raise ValidationError("federation runtime address verification failed")
    return value


def runtime_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime) -> str:
    value = verify_runtime(value)
    lines = ["field,value"]
    for key, field_value in value.summary().items():
        lines.append(f"{key},{json.dumps(field_value, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def render_runtime_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime) -> str:
    value = verify_runtime(value)
    return "\n".join(["# Archive Registry Federation Runtime", "", f"- Status: `{value.state}`", f"- Sources: `{value.source_count}`", f"- Compared entries: `{value.federation.observation_count}`", f"- Conflicts: `{value.federation.conflict_count}`", f"- Selected: `{value.consensus.selected_count}`", f"- Held: `{value.consensus.held_count}`", f"- Runtime address: `{value.content_address}`", "", report_model.render_report_markdown(value.report)]) + "\n"


def _artifact(name: str, raw: bytes) -> dict[str, Any]:
    return {"name": name, "size": len(raw), "hash": hash_bytes(raw, prefix=ARTIFACT_PREFIX)}


def _payload(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime) -> dict[str, bytes]:
    value = verify_runtime(value)
    return {RUNTIME_NAME: canonical_bytes(value.to_dict()), FEDERATION_NAME: canonical_bytes(value.federation.to_dict()), AUDITS_NAME: canonical_bytes({"federation_audit": value.federation_audit.to_dict(), "consensus_audit": value.consensus_audit.to_dict()}), CONSENSUS_NAME: canonical_bytes(value.consensus.to_dict()), REPORT_NAME: canonical_bytes(value.report.to_dict())}


def manifest_document(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime) -> dict[str, Any]:
    value = verify_runtime(value)
    payload = _payload(value)
    body = {"version": VERSION, "boundary": BOUNDARY, "runtime_id": value.runtime_id, "runtime_address": value.content_address, "files": FILES, "artifacts": tuple(_artifact(name, payload[name]) for name in (RUNTIME_NAME, FEDERATION_NAME, AUDITS_NAME, CONSENSUS_NAME, REPORT_NAME))}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def runtime_bytes(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime) -> Mapping[str, bytes]:
    payload = _payload(value)
    return {MANIFEST_NAME: canonical_bytes(manifest_document(value)), **payload}


def _write_atomic_directory(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("federation runtime destination is not writable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="certificate-observatory-federation-runtime-staging-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (staging / name).write_bytes(payload[name])
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix="certificate-observatory-federation-runtime-backup-", dir=str(destination.parent)))
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


def write_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_directory(Path(destination), runtime_bytes(value), overwrite=overwrite)


def _read_directory(source: str | Path) -> dict[str, bytes]:
    path = Path(source)
    if path.is_symlink() or not path.is_dir():
        raise ValidationError("federation runtime input must be a regular directory")
    names = tuple(item.name for item in path.iterdir())
    if set(names) != set(FILES) or len(names) != len(FILES):
        raise ValidationError("federation runtime member set is not exact")
    result = {}
    for name in FILES:
        member = path / name
        if member.is_symlink() or not member.is_file():
            raise ValidationError("federation runtime member must be a regular file")
        result[name] = member.read_bytes()
    return result


def load_runtime(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime:
    raw = _read_directory(source)
    try:
        decoded = {name: json.loads(value.decode("utf-8")) for name, value in raw.items()}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("federation runtime contains invalid JSON") from error
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("federation runtime contains non-canonical JSON")
    manifest = _mapping(decoded[MANIFEST_NAME], "federation runtime manifest")
    _strict(manifest, {"version", "boundary", "runtime_id", "runtime_address", "files", "artifacts", "manifest_address"}, "federation runtime manifest")
    if tuple(manifest["files"]) != FILES or manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("federation runtime manifest does not replay")
    artifacts = _sequence(manifest["artifacts"], "federation runtime artifacts", len(FILES) - 1)
    for item in artifacts:
        item = _mapping(item, "federation runtime artifact")
        _strict(item, {"name", "size", "hash"}, "federation runtime artifact")
        name = item["name"]
        if name not in FILES[1:] or item["size"] != len(raw[name]) or item["hash"] != hash_bytes(raw[name], prefix=ARTIFACT_PREFIX):
            raise ValidationError("federation runtime artifact receipt does not replay")
    value = runtime_from_mapping(decoded[RUNTIME_NAME])
    if value.runtime_id != manifest["runtime_id"] or value.content_address != manifest["runtime_address"]:
        raise ValidationError("federation runtime manifest links do not replay")
    if raw[FEDERATION_NAME] != canonical_bytes(value.federation.to_dict()) or raw[CONSENSUS_NAME] != canonical_bytes(value.consensus.to_dict()) or raw[REPORT_NAME] != canonical_bytes(value.report.to_dict()) or raw[AUDITS_NAME] != canonical_bytes({"federation_audit": value.federation_audit.to_dict(), "consensus_audit": value.consensus_audit.to_dict()}):
        raise ValidationError("federation runtime projections do not replay")
    return value


def verify_runtime_directory(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime:
    return load_runtime(source)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "runtime_id", "runtime_address", "files", "artifacts", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "runtime_id": {"type": "string"}, "runtime_address": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}, "artifacts": {"type": "array"}, "manifest_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime.FIELDS), "properties": {"runtime_id": {"type": "string"}, "federation": federation_model.federation_schema(), "federation_audit": federation_audit_model.audit_schema(), "consensus": consensus_model.consensus_schema(), "consensus_audit": consensus_audit_model.audit_schema(), "report": report_model.report_schema(), "source_count": {"type": "integer", "minimum": 1}, "accepted": {"type": "boolean"}, "state": {"enum": list(report_model.STATUSES)}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "operations": ("run_runtime", "build_runtime", "load_registry_input", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "write_runtime", "load_runtime", "verify_runtime_directory"), "files": FILES, "max_sources": MAX_SOURCE_COUNT}


__all__ = ["AUDITS_NAME", "BOUNDARY", "CONSENSUS_NAME", "DEFAULT_RUNTIME_ID", "FEDERATION_NAME", "FILES", "MANIFEST_NAME", "REPORT_NAME", "RUNTIME_NAME", "RUNTIME_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationRuntime", "address_runtime", "build_runtime", "capabilities", "load_registry_input", "load_runtime", "manifest_document", "manifest_schema", "render_runtime_markdown", "run_runtime", "runtime_bytes", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema", "verify_runtime", "verify_runtime_directory", "write_runtime"]
