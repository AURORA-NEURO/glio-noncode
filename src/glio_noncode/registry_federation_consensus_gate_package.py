"""Durable release-control package for a consensus gate decision.

The package is a transport boundary for an already-derived result.  It
contains the full execution receipt, policy gate, independent gate audit, and
bounded inspection result.  Writing is atomic and source registries are never
modified.  Reload checks every canonical member, manifest address, nested
link, and projection so a copied package cannot silently drift.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from . import registry_federation_consensus_gate_audit as audit_model
from . import registry_federation_consensus_gate_query as query_model
from . import registry_federation_consensus_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = gate_model.VERSION + "-package-v1"
BOUNDARY = gate_model.BOUNDARY + "_package"
PACKAGE_PREFIX = gate_model.GATE_PREFIX + "-package"
MANIFEST_NAME = "manifest.json"
PACKAGE_NAME = "package.json"
RUNTIME_NAME = "runtime.json"
GATE_NAME = "gate.json"
AUDIT_NAME = "audit.json"
QUERY_NAME = "query.json"
FILES = (MANIFEST_NAME, PACKAGE_NAME, RUNTIME_NAME, GATE_NAME, AUDIT_NAME, QUERY_NAME)
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "runtime-link",
    "gate-link",
    "audit-link",
    "query-link",
    "package-address",
    "manifest-conservation",
    "runtime-projection",
    "gate-projection",
    "audit-projection",
    "query-projection",
    "canonical-members",
    "mapping-round-trip",
    "content-address",
    "path-free",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGatePackage:
    """One replayable handoff containing all release-control evidence."""

    FIELDS = ("package_id", "runtime", "gate", "audit", "query", "content_address")

    def __init__(self, package_id: str, runtime: runtime_model.RegistryFederationConsensusRuntime, gate: gate_model.RegistryFederationConsensusGate, audit: audit_model.RegistryFederationConsensusGateAudit, query: query_model.RegistryFederationConsensusGateQueryResult, content_address: str) -> None:
        self.package_id = _label(package_id, "gate package ID")
        if not isinstance(runtime, runtime_model.RegistryFederationConsensusRuntime) or not isinstance(gate, gate_model.RegistryFederationConsensusGate) or not isinstance(audit, audit_model.RegistryFederationConsensusGateAudit) or not isinstance(query, query_model.RegistryFederationConsensusGateQueryResult):
            raise ValidationError("gate package members must be typed")
        self.runtime = runtime_model.verify_runtime(runtime)
        self.gate = gate_model.verify_gate(gate)
        self.audit = audit_model.verify_audit(audit)
        self.query = query_model.verify_query_result(query)
        if self.gate.runtime_address != self.runtime.content_address or self.gate.consensus_address != self.runtime.consensus.content_address:
            raise ValidationError("gate package runtime links do not replay")
        if self.audit.gate_address != self.gate.content_address:
            raise ValidationError("gate package audit link does not replay")
        if self.query.query.gate_address != self.gate.content_address:
            raise ValidationError("gate package query link does not replay")
        self.content_address = _address(content_address, "gate package content address", PACKAGE_PREFIX)
        if not self.content_address.endswith(":pending") and address_package(self) != self.content_address:
            raise ValidationError("gate package content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate package crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "runtime": self.runtime.to_dict(), "gate": self.gate.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "runtime_address": self.runtime.content_address, "gate_address": self.gate.content_address, "audit_address": self.audit.content_address, "query_address": self.query.content_address, "accepted": self.gate.accepted, "state": self.gate.state, "decision": self.gate.decision, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGatePackage:
        value = _mapping(value, "consensus gate package")
        _strict(value, set(cls.FIELDS), "consensus gate package")
        return cls(value["package_id"], runtime_model.runtime_from_mapping(value["runtime"]), gate_model.gate_from_mapping(value["gate"]), audit_model.audit_from_mapping(value["audit"]), query_model.query_from_mapping(value["query"]), value["content_address"])


def address_package(value: RegistryFederationConsensusGatePackage) -> str:
    if not isinstance(value, RegistryFederationConsensusGatePackage):
        raise ValidationError("gate package address requires a typed package")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PACKAGE_PREFIX)


def build_package(runtime: runtime_model.RegistryFederationConsensusRuntime, gate: gate_model.RegistryFederationConsensusGate, *, audit: audit_model.RegistryFederationConsensusGateAudit | None = None, query: query_model.RegistryFederationConsensusGateQueryResult | None = None, package_id: str = "consensus-gate-package") -> RegistryFederationConsensusGatePackage:
    runtime = runtime_model.verify_runtime(runtime)
    gate = gate_model.verify_gate(gate)
    if gate.runtime_address != runtime.content_address:
        raise ValidationError("gate package gate does not refer to runtime")
    audit = audit_model.audit_gate(gate) if audit is None else audit_model.verify_audit(audit)
    query = query_model.query_gate(gate) if query is None else query_model.verify_query_result(query)
    provisional = RegistryFederationConsensusGatePackage(package_id, runtime, gate, audit, query, PACKAGE_PREFIX + ":pending")
    return RegistryFederationConsensusGatePackage(provisional.package_id, provisional.runtime, provisional.gate, provisional.audit, provisional.query, address_package(provisional))


def package_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGatePackage:
    return verify_package(RegistryFederationConsensusGatePackage.from_mapping(value))


def verify_package(value: RegistryFederationConsensusGatePackage) -> RegistryFederationConsensusGatePackage:
    if not isinstance(value, RegistryFederationConsensusGatePackage) or (not value.content_address.endswith(":pending") and address_package(value) != value.content_address):
        raise ValidationError("consensus gate package is not valid")
    return value


def package_json(value: RegistryFederationConsensusGatePackage) -> str:
    return canonical_json(verify_package(value).to_dict())


def _manifest(value: RegistryFederationConsensusGatePackage) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "package_id": value.package_id, "files": tuple(sorted(FILES)), "package_address": value.content_address, "runtime_address": value.runtime.content_address, "gate_address": value.gate.content_address, "audit_address": value.audit.content_address, "query_address": value.query.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=PACKAGE_PREFIX + "-manifest")}


def package_bytes(value: RegistryFederationConsensusGatePackage) -> dict[str, bytes]:
    value = verify_package(value)
    return {MANIFEST_NAME: canonical_bytes(_manifest(value)), PACKAGE_NAME: canonical_bytes(value.to_dict()), RUNTIME_NAME: canonical_bytes(value.runtime.to_dict()), GATE_NAME: canonical_bytes(value.gate.to_dict()), AUDIT_NAME: canonical_bytes(value.audit.to_dict()), QUERY_NAME: canonical_bytes(value.query.to_dict())}


def write_package(value: RegistryFederationConsensusGatePackage, directory: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_package(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("gate package destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="consensus-gate-package-staging-", dir=str(destination.parent)))
        for name, raw in package_bytes(value).items():
            (staging / name).write_bytes(raw)
        if destination.exists():
            shutil.rmtree(destination)
        staging.replace(destination)
        staging = None
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
    return destination


def load_package(directory: str | Path) -> RegistryFederationConsensusGatePackage:
    source = Path(directory)
    if not source.is_dir() or tuple(sorted(path.name for path in source.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("gate package directory does not contain exact canonical members")
    raw = {name: (source / name).read_bytes() for name in FILES}
    decoded = {name: json.loads(payload.decode("utf-8")) for name, payload in raw.items()}
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("gate package member is not canonical JSON")
    value = package_from_mapping(decoded[PACKAGE_NAME])
    if canonical_bytes(decoded[MANIFEST_NAME]) != canonical_bytes(_manifest(value)):
        raise ValidationError("gate package manifest does not replay")
    projections = ((RUNTIME_NAME, value.runtime.to_dict()), (GATE_NAME, value.gate.to_dict()), (AUDIT_NAME, value.audit.to_dict()), (QUERY_NAME, value.query.to_dict()))
    if any(canonical_bytes(decoded[name]) != canonical_bytes(expected) for name, expected in projections):
        raise ValidationError("gate package projections do not replay")
    return value


def verify_package_directory(directory: str | Path) -> RegistryFederationConsensusGatePackage:
    return load_package(directory)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "package_id", "files", "package_address", "runtime_address", "gate_address", "audit_address", "query_address", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "package_id": {"type": "string"}, "files": {"type": "array"}, "package_address": {"type": "string"}, "runtime_address": {"type": "string"}, "gate_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "manifest_address": {"type": "string"}}}


def package_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGatePackage.FIELDS), "properties": {"package_id": {"type": "string"}, "runtime": runtime_model.runtime_schema(), "gate": gate_model.gate_schema(), "audit": audit_model.audit_schema(), "query": query_model.result_schema(), "content_address": {"type": "string", "pattern": "^" + PACKAGE_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "package_prefix": PACKAGE_PREFIX, "files": FILES, "check_ids": CHECK_IDS, "features": ("six-file release-control handoff", "atomic directory replacement", "canonical reload verification", "manifest and projection replay", "embedded runtime and independent audit", "bounded query transport", "JSON export"), "schemas": ("manifest", "package")}


__all__ = ["AUDIT_NAME", "BOUNDARY", "CHECK_IDS", "FILES", "GATE_NAME", "MANIFEST_NAME", "PACKAGE_NAME", "PACKAGE_PREFIX", "QUERY_NAME", "RUNTIME_NAME", "RegistryFederationConsensusGatePackage", "VERSION", "address_package", "build_package", "capabilities", "load_package", "manifest_schema", "package_bytes", "package_from_mapping", "package_json", "package_schema", "verify_package", "verify_package_directory", "write_package"]
