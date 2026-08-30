"""End-to-end runtime for consensus gate certificate issuance."""

# ruff: noqa: E501, I001

from __future__ import annotations

import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate as certificate_model
from . import registry_federation_consensus_gate_certificate_audit as certificate_audit_model
from . import registry_federation_consensus_gate_certificate_package as package_model
from . import registry_federation_consensus_gate_certificate_query as certificate_query_model
from . import registry_federation_consensus_gate_runtime as gate_runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = certificate_model.VERSION + "-runtime-v1"
BOUNDARY = certificate_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-runtime"
MAX_TEXT = certificate_model.MAX_TEXT
FIELDS = ("runtime_id", "gate_runtime", "certificate", "certificate_audit", "certificate_query", "package_address", "persisted", "content_address")
CHECK_IDS = ("exact-fields", "gate-runtime-link", "certificate-link", "audit-link", "query-link", "package-link", "persistence-state", "acceptance-conservation", "content-address", "mapping-round-trip", "path-free")


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
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateCertificateRuntime:
    """One complete certificate issuance and handoff receipt."""

    def __init__(self, runtime_id: str, gate_runtime: gate_runtime_model.RegistryFederationConsensusGateRuntime, certificate: certificate_model.RegistryFederationConsensusGateCertificate, certificate_audit: certificate_audit_model.RegistryFederationConsensusGateCertificateAudit, certificate_query: certificate_query_model.RegistryFederationConsensusGateCertificateQueryResult, package_address: str, persisted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "certificate runtime ID")
        if not isinstance(gate_runtime, gate_runtime_model.RegistryFederationConsensusGateRuntime) or not isinstance(certificate, certificate_model.RegistryFederationConsensusGateCertificate) or not isinstance(certificate_audit, certificate_audit_model.RegistryFederationConsensusGateCertificateAudit) or not isinstance(certificate_query, certificate_query_model.RegistryFederationConsensusGateCertificateQueryResult):
            raise ValidationError("certificate runtime members must be typed")
        self.gate_runtime = gate_runtime_model.verify_runtime(gate_runtime)
        self.certificate = certificate_model.verify_certificate(certificate)
        self.certificate_audit = certificate_audit_model.verify_audit(certificate_audit)
        self.certificate_query = certificate_query_model.verify_query_result(certificate_query)
        self.package_address = _address(package_address, "certificate runtime package address", package_model.PACKAGE_PREFIX, optional=True)
        self.persisted = _bool(persisted, "certificate runtime persisted flag")
        if self.persisted != bool(self.package_address):
            raise ValidationError("certificate runtime persistence state does not conserve package address")
        if self.certificate.runtime_address != self.gate_runtime.content_address or self.certificate.gate_address != self.gate_runtime.gate.content_address or self.certificate.audit_address != self.gate_runtime.audit.content_address or self.certificate.query_address != self.gate_runtime.query.content_address:
            raise ValidationError("certificate runtime source links do not replay")
        if self.certificate_audit.certificate_address != self.certificate.content_address or self.certificate_query.query.certificate_address != self.certificate.content_address:
            raise ValidationError("certificate runtime child links do not replay")
        self.content_address = _address(content_address, "certificate runtime address", RUNTIME_PREFIX)
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("certificate runtime content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "gate_runtime": self.gate_runtime.to_dict(), "certificate": self.certificate.to_dict(), "certificate_audit": self.certificate_audit.to_dict(), "certificate_query": self.certificate_query.to_dict(), "package_address": self.package_address, "persisted": self.persisted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "gate_runtime_address": self.gate_runtime.content_address, "certificate_id": self.certificate.certificate_id, "certificate_address": self.certificate.content_address, "state": self.certificate.certificate_state, "decision": self.certificate.certificate_decision, "accepted": self.certificate.accepted, "audit_accepted": self.certificate_audit.accepted, "query_returned_count": self.certificate_query.returned_count, "package_address": self.package_address, "persisted": self.persisted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateRuntime:
        value = _mapping(value, "consensus gate certificate runtime")
        _strict(value, set(FIELDS), "consensus gate certificate runtime")
        return cls(value["runtime_id"], gate_runtime_model.runtime_from_mapping(value["gate_runtime"]), certificate_model.certificate_from_mapping(value["certificate"]), certificate_audit_model.audit_from_mapping(value["certificate_audit"]), certificate_query_model.query_from_mapping(value["certificate_query"]), value["package_address"], value["persisted"], value["content_address"])


def address_runtime(value: RegistryFederationConsensusGateCertificateRuntime) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateRuntime):
        raise ValidationError("certificate runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def run_certificate_runtime(peers: Sequence[tuple[str, str | Path]], *, runtime_id: str = "consensus-certificate-runtime", federation_id: str = "catalog-federation", consensus_id: str = "federation-consensus", quorum: int | None = None, gate_id: str = "consensus-release-gate", gate_policy: Any = None, certificate_id: str = "consensus-release-certificate", certificate_policy: certificate_model.RegistryFederationConsensusGateCertificatePolicy | None = None, package_id: str = "consensus-release-certificate-package", destination: str | Path | None = None, overwrite: bool = False, gate_resources: Sequence[str] = ("summary", "checks", "failures", "evidence"), certificate_resources: Sequence[str] = certificate_query_model.DEFAULT_RESOURCES, certificate_check_id: str = "", certificate_passed: bool | None = None, certificate_state: str = "", certificate_decision: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateCertificateRuntime:
    """Run gate evidence, issue a certificate, and optionally persist its package."""

    certificate_policy = certificate_model.default_policy() if certificate_policy is None else certificate_policy
    if not isinstance(certificate_policy, certificate_model.RegistryFederationConsensusGateCertificatePolicy):
        raise ValidationError("certificate policy must be typed")
    if certificate_policy.require_package and destination is not None:
        with tempfile.TemporaryDirectory(prefix="certificate-gate-runtime-") as temporary:
            gate_runtime = gate_runtime_model.run_gate_runtime(peers, runtime_id=runtime_id + "-gate", federation_id=federation_id, consensus_id=consensus_id, quorum=quorum, gate_id=gate_id, policy=gate_policy, destination=Path(temporary) / "gate-package", overwrite=False, resources=gate_resources, limit=limit)
            return _finish_runtime(gate_runtime, runtime_id, certificate_id, certificate_policy, package_id, destination, overwrite, certificate_resources, certificate_check_id, certificate_passed, certificate_state, certificate_decision, offset, limit)
    gate_runtime = gate_runtime_model.run_gate_runtime(peers, runtime_id=runtime_id + "-gate", federation_id=federation_id, consensus_id=consensus_id, quorum=quorum, gate_id=gate_id, policy=gate_policy, destination=None, resources=gate_resources, limit=limit)
    return _finish_runtime(gate_runtime, runtime_id, certificate_id, certificate_policy, package_id, destination, overwrite, certificate_resources, certificate_check_id, certificate_passed, certificate_state, certificate_decision, offset, limit)


def _finish_runtime(gate_runtime: gate_runtime_model.RegistryFederationConsensusGateRuntime, runtime_id: str, certificate_id: str, certificate_policy: certificate_model.RegistryFederationConsensusGateCertificatePolicy, package_id: str, destination: str | Path | None, overwrite: bool, certificate_resources: Sequence[str], certificate_check_id: str, certificate_passed: bool | None, certificate_state: str, certificate_decision: str, offset: int, limit: int) -> RegistryFederationConsensusGateCertificateRuntime:
    certificate = certificate_model.evaluate_certificate(gate_runtime, policy=certificate_policy, certificate_id=certificate_id)
    certificate_audit = certificate_audit_model.audit_certificate(certificate)
    certificate_query = certificate_query_model.query_certificate(certificate, resources=certificate_resources, check_id=certificate_check_id, passed=certificate_passed, state=certificate_state, decision=certificate_decision, offset=offset, limit=limit)
    package_address = ""
    persisted = False
    if destination is not None:
        package = package_model.build_package(gate_runtime, certificate, certificate_audit=certificate_audit, certificate_query=certificate_query, package_id=package_id)
        package_model.write_package(package, destination, overwrite=overwrite)
        package_address = package.content_address
        persisted = True
    provisional = RegistryFederationConsensusGateCertificateRuntime(runtime_id, gate_runtime, certificate, certificate_audit, certificate_query, package_address, persisted, RUNTIME_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateRuntime(provisional.runtime_id, provisional.gate_runtime, provisional.certificate, provisional.certificate_audit, provisional.certificate_query, provisional.package_address, provisional.persisted, address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateRuntime:
    return verify_runtime(RegistryFederationConsensusGateCertificateRuntime.from_mapping(value))


def verify_runtime(value: RegistryFederationConsensusGateCertificateRuntime) -> RegistryFederationConsensusGateCertificateRuntime:
    if not isinstance(value, RegistryFederationConsensusGateCertificateRuntime) or (not value.content_address.endswith(":pending") and address_runtime(value) != value.content_address):
        raise ValidationError("certificate runtime is not valid")
    return value


def runtime_json(value: RegistryFederationConsensusGateCertificateRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(FIELDS), "properties": {"runtime_id": {"type": "string"}, "gate_runtime": gate_runtime_model.runtime_schema(), "certificate": certificate_model.certificate_schema(), "certificate_audit": certificate_audit_model.audit_schema(), "certificate_query": certificate_query_model.result_schema(), "package_address": {"type": "string"}, "persisted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "runtime_prefix": RUNTIME_PREFIX, "check_ids": CHECK_IDS, "features": ("directory-to-gate-to-certificate orchestration", "policy-gated issuance", "independent certificate audit", "bounded certificate query", "optional atomic nine-file package", "package-required strict mode", "single runtime content address", "JSON export"), "schemas": ("runtime",)}


__all__ = ["BOUNDARY", "CHECK_IDS", "FIELDS", "RUNTIME_PREFIX", "RegistryFederationConsensusGateCertificateRuntime", "VERSION", "address_runtime", "capabilities", "run_certificate_runtime", "runtime_from_mapping", "runtime_json", "runtime_schema", "verify_runtime"]
