"""End-to-end runtime for consensus release eligibility and handoff."""

# ruff: noqa: E501, I001

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from . import registry_federation_consensus_gate_audit as audit_model
from . import registry_federation_consensus_gate_package as package_model
from . import registry_federation_consensus_gate_query as query_model
from . import registry_federation_consensus_runtime as consensus_runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = package_model.VERSION + "-runtime-v1"
BOUNDARY = package_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = gate_model.GATE_PREFIX + "-runtime"
MAX_TEXT = gate_model.MAX_TEXT
FIELDS = ("runtime_id", "consensus_runtime", "gate", "audit", "query", "package_address", "persisted", "content_address")
CHECK_IDS = ("exact-fields", "consensus-runtime-link", "gate-link", "audit-link", "query-link", "package-link", "persistence-state", "acceptance-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, optional: bool = False) -> str:
    if optional and value == "":
        return ""
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
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


class RegistryFederationConsensusGateRuntime:
    """One addressed execution value for release-control operations."""

    def __init__(self, runtime_id: str, consensus_runtime: consensus_runtime_model.RegistryFederationConsensusRuntime, gate: gate_model.RegistryFederationConsensusGate, audit: audit_model.RegistryFederationConsensusGateAudit, query: query_model.RegistryFederationConsensusGateQueryResult, package_address: str, persisted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "gate runtime ID")
        if not isinstance(consensus_runtime, consensus_runtime_model.RegistryFederationConsensusRuntime) or not isinstance(gate, gate_model.RegistryFederationConsensusGate) or not isinstance(audit, audit_model.RegistryFederationConsensusGateAudit) or not isinstance(query, query_model.RegistryFederationConsensusGateQueryResult):
            raise ValidationError("gate runtime members must be typed")
        self.consensus_runtime = consensus_runtime_model.verify_runtime(consensus_runtime)
        self.gate = gate_model.verify_gate(gate)
        self.audit = audit_model.verify_audit(audit)
        self.query = query_model.verify_query_result(query)
        self.package_address = _address(package_address, "gate runtime package address", package_model.PACKAGE_PREFIX, optional=True)
        self.persisted = _bool(persisted, "gate runtime persisted flag")
        if self.persisted != bool(self.package_address):
            raise ValidationError("gate runtime persistence state does not conserve package address")
        if self.gate.runtime_address != self.consensus_runtime.content_address or self.gate.consensus_address != self.consensus_runtime.consensus.content_address:
            raise ValidationError("gate runtime gate link does not replay")
        if self.audit.gate_address != self.gate.content_address or self.query.query.gate_address != self.gate.content_address:
            raise ValidationError("gate runtime child links do not replay")
        self.content_address = _address(content_address, "gate runtime content address", RUNTIME_PREFIX)
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("gate runtime content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "consensus_runtime": self.consensus_runtime.to_dict(), "gate": self.gate.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "package_address": self.package_address, "persisted": self.persisted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "consensus_runtime_address": self.consensus_runtime.content_address, "gate_id": self.gate.gate_id, "gate_address": self.gate.content_address, "state": self.gate.state, "decision": self.gate.decision, "accepted": self.gate.accepted, "audit_accepted": self.audit.accepted, "failed_count": self.gate.failed_count, "query_returned_count": self.query.returned_count, "package_address": self.package_address, "persisted": self.persisted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateRuntime:
        value = _mapping(value, "consensus gate runtime")
        _strict(value, set(cls.FIELDS), "consensus gate runtime")
        return cls(value["runtime_id"], consensus_runtime_model.runtime_from_mapping(value["consensus_runtime"]), gate_model.gate_from_mapping(value["gate"]), audit_model.audit_from_mapping(value["audit"]), query_model.query_from_mapping(value["query"]), value["package_address"], value["persisted"], value["content_address"])


RegistryFederationConsensusGateRuntime.FIELDS = FIELDS


def address_runtime(value: RegistryFederationConsensusGateRuntime) -> str:
    if not isinstance(value, RegistryFederationConsensusGateRuntime):
        raise ValidationError("gate runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def run_gate_runtime(peers: Sequence[tuple[str, str | Path]], *, runtime_id: str = "consensus-gate-runtime", federation_id: str = "catalog-federation", consensus_id: str = "federation-consensus", quorum: int | None = None, gate_id: str = "consensus-release-gate", policy: gate_model.RegistryFederationConsensusGatePolicy | None = None, package_id: str = "consensus-gate-package", destination: str | Path | None = None, overwrite: bool = False, resources: Sequence[str] = query_model.DEFAULT_RESOURCES, check_id: str = "", passed: bool | None = None, state: str = "", decision: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateRuntime:
    consensus_runtime = consensus_runtime_model.run_consensus_runtime(peers, runtime_id=runtime_id + "-consensus", federation_id=federation_id, consensus_id=consensus_id, quorum=quorum, resources=("summary", "packages", "candidates", "actions"), limit=limit)
    gate = gate_model.evaluate_gate(consensus_runtime, policy=policy, gate_id=gate_id)
    audit = audit_model.audit_gate(gate)
    query = query_model.query_gate(gate, resources=resources, check_id=check_id, passed=passed, state=state, decision=decision, offset=offset, limit=limit)
    package_address = ""
    persisted = False
    if destination is not None:
        package = package_model.build_package(consensus_runtime, gate, audit=audit, query=query, package_id=package_id)
        package_model.write_package(package, destination, overwrite=overwrite)
        package_address = package.content_address
        persisted = True
    provisional = RegistryFederationConsensusGateRuntime(runtime_id, consensus_runtime, gate, audit, query, package_address, persisted, RUNTIME_PREFIX + ":pending")
    return RegistryFederationConsensusGateRuntime(provisional.runtime_id, provisional.consensus_runtime, provisional.gate, provisional.audit, provisional.query, provisional.package_address, provisional.persisted, address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateRuntime:
    return verify_runtime(RegistryFederationConsensusGateRuntime.from_mapping(value))


def verify_runtime(value: RegistryFederationConsensusGateRuntime) -> RegistryFederationConsensusGateRuntime:
    if not isinstance(value, RegistryFederationConsensusGateRuntime) or (not value.content_address.endswith(":pending") and address_runtime(value) != value.content_address):
        raise ValidationError("consensus gate runtime is not valid")
    return value


def runtime_json(value: RegistryFederationConsensusGateRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(FIELDS), "properties": {"runtime_id": {"type": "string"}, "consensus_runtime": consensus_runtime_model.runtime_schema(), "gate": gate_model.gate_schema(), "audit": audit_model.audit_schema(), "query": query_model.result_schema(), "package_address": {"type": "string"}, "persisted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "runtime_prefix": RUNTIME_PREFIX, "check_ids": CHECK_IDS, "features": ("directory-to-consensus-to-gate orchestration", "independent gate audit", "bounded gate query", "optional atomic release-control package", "single runtime content address", "JSON export"), "schemas": ("runtime",)}


__all__ = ["BOUNDARY", "CHECK_IDS", "FIELDS", "RUNTIME_PREFIX", "RegistryFederationConsensusGateRuntime", "VERSION", "address_runtime", "capabilities", "run_gate_runtime", "runtime_from_mapping", "runtime_json", "runtime_schema", "verify_runtime"]
