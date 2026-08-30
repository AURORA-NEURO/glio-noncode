"""Exact-file durable packages for consensus gate certificates.

The certificate is a compact release handoff, while this package preserves the
certificate, its runtime, gate, independent audit, query, and policy as
canonical members.  Loaders reject extra members, non-canonical bytes, link
drift, and address drift before returning a typed value.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from . import registry_federation_consensus_gate_audit as gate_audit_model
from . import registry_federation_consensus_gate_certificate as certificate_model
from . import registry_federation_consensus_gate_certificate_audit as audit_model
from . import registry_federation_consensus_gate_certificate_query as certificate_query_model
from . import registry_federation_consensus_gate_query as gate_query_model
from . import registry_federation_consensus_gate_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = certificate_model.VERSION + "-package-v1"
BOUNDARY = certificate_model.BOUNDARY + "_package"
PACKAGE_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-package"
MANIFEST_NAME = "manifest.json"
PACKAGE_NAME = "package.json"
CERTIFICATE_NAME = "certificate.json"
RUNTIME_NAME = "runtime.json"
GATE_NAME = "gate.json"
GATE_AUDIT_NAME = "gate-audit.json"
GATE_QUERY_NAME = "gate-query.json"
CERTIFICATE_AUDIT_NAME = "certificate-audit.json"
CERTIFICATE_QUERY_NAME = "certificate-query.json"
FILES = (MANIFEST_NAME, PACKAGE_NAME, CERTIFICATE_NAME, RUNTIME_NAME, GATE_NAME, GATE_AUDIT_NAME, GATE_QUERY_NAME, CERTIFICATE_AUDIT_NAME, CERTIFICATE_QUERY_NAME)
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "certificate-link",
    "runtime-link",
    "gate-link",
    "audit-link",
    "query-link",
    "policy-link",
    "package-address",
    "manifest-conservation",
    "certificate-projection",
    "runtime-projection",
    "gate-projection",
    "audit-projection",
    "query-projection",
    "policy-projection",
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
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateCertificatePackage:
    """One nine-file certificate release handoff."""

    FIELDS = ("package_id", "certificate", "runtime", "gate", "gate_audit", "gate_query", "certificate_audit", "certificate_query", "content_address")

    def __init__(self, package_id: str, certificate: certificate_model.RegistryFederationConsensusGateCertificate, runtime: runtime_model.RegistryFederationConsensusGateRuntime, gate: gate_model.RegistryFederationConsensusGate, gate_audit: gate_audit_model.RegistryFederationConsensusGateAudit, gate_query: gate_query_model.RegistryFederationConsensusGateQueryResult, certificate_audit: audit_model.RegistryFederationConsensusGateCertificateAudit, certificate_query: certificate_query_model.RegistryFederationConsensusGateCertificateQueryResult, content_address: str) -> None:
        self.package_id = _label(package_id, "certificate package ID")
        if not isinstance(certificate, certificate_model.RegistryFederationConsensusGateCertificate) or not isinstance(runtime, runtime_model.RegistryFederationConsensusGateRuntime) or not isinstance(gate, gate_model.RegistryFederationConsensusGate) or not isinstance(gate_audit, gate_audit_model.RegistryFederationConsensusGateAudit) or not isinstance(gate_query, gate_query_model.RegistryFederationConsensusGateQueryResult) or not isinstance(certificate_audit, audit_model.RegistryFederationConsensusGateCertificateAudit) or not isinstance(certificate_query, certificate_query_model.RegistryFederationConsensusGateCertificateQueryResult):
            raise ValidationError("certificate package members must be typed")
        self.certificate = certificate_model.verify_certificate(certificate)
        self.runtime = runtime_model.verify_runtime(runtime)
        self.gate = gate_model.verify_gate(gate)
        self.gate_audit = gate_audit_model.verify_audit(gate_audit)
        self.gate_query = gate_query_model.verify_query_result(gate_query)
        self.certificate_audit = audit_model.verify_audit(certificate_audit)
        self.certificate_query = certificate_query_model.verify_query_result(certificate_query)
        if self.certificate.runtime_address != self.runtime.content_address or self.certificate.gate_address != self.gate.content_address or self.certificate.audit_address != self.gate_audit.content_address or self.certificate.query_address != self.gate_query.content_address:
            raise ValidationError("certificate package certificate links do not replay")
        if self.certificate_audit.certificate_address != self.certificate.content_address or self.certificate_query.query.certificate_address != self.certificate.content_address:
            raise ValidationError("certificate package certificate audit/query links do not replay")
        if self.gate.runtime_address != self.runtime.consensus_runtime.content_address or self.gate_audit.gate_address != self.gate.content_address or self.gate_query.query.gate_address != self.gate.content_address:
            raise ValidationError("certificate package nested links do not replay")
        self.content_address = _address(content_address, "certificate package address", PACKAGE_PREFIX)
        if not self.content_address.endswith(":pending") and address_package(self) != self.content_address:
            raise ValidationError("certificate package content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate package crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "certificate": self.certificate.to_dict(), "runtime": self.runtime.to_dict(), "gate": self.gate.to_dict(), "gate_audit": self.gate_audit.to_dict(), "gate_query": self.gate_query.to_dict(), "certificate_audit": self.certificate_audit.to_dict(), "certificate_query": self.certificate_query.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "certificate_address": self.certificate.content_address, "runtime_address": self.runtime.content_address, "gate_address": self.gate.content_address, "gate_audit_address": self.gate_audit.content_address, "gate_query_address": self.gate_query.content_address, "certificate_audit_address": self.certificate_audit.content_address, "certificate_query_address": self.certificate_query.content_address, "accepted": self.certificate.accepted, "state": self.certificate.certificate_state, "decision": self.certificate.certificate_decision, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificatePackage:
        value = _mapping(value, "consensus gate certificate package")
        _strict(value, set(cls.FIELDS), "consensus gate certificate package")
        return cls(value["package_id"], certificate_model.certificate_from_mapping(value["certificate"]), runtime_model.runtime_from_mapping(value["runtime"]), gate_model.gate_from_mapping(value["gate"]), gate_audit_model.audit_from_mapping(value["gate_audit"]), gate_query_model.query_from_mapping(value["gate_query"]), audit_model.audit_from_mapping(value["certificate_audit"]), certificate_query_model.query_from_mapping(value["certificate_query"]), value["content_address"])


def address_package(value: RegistryFederationConsensusGateCertificatePackage) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificatePackage):
        raise ValidationError("certificate package address requires a typed package")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PACKAGE_PREFIX)


def build_package(runtime: runtime_model.RegistryFederationConsensusGateRuntime, certificate: certificate_model.RegistryFederationConsensusGateCertificate, *, package_id: str = "consensus-release-certificate-package", gate: gate_model.RegistryFederationConsensusGate | None = None, gate_audit: gate_audit_model.RegistryFederationConsensusGateAudit | None = None, gate_query: gate_query_model.RegistryFederationConsensusGateQueryResult | None = None, certificate_audit: audit_model.RegistryFederationConsensusGateCertificateAudit | None = None, certificate_query: certificate_query_model.RegistryFederationConsensusGateCertificateQueryResult | None = None) -> RegistryFederationConsensusGateCertificatePackage:
    runtime = runtime_model.verify_runtime(runtime)
    certificate = certificate_model.verify_certificate(certificate)
    selected_gate = runtime.gate if gate is None else gate_model.verify_gate(gate)
    selected_gate_audit = runtime.audit if gate_audit is None else gate_audit_model.verify_audit(gate_audit)
    selected_gate_query = runtime.query if gate_query is None else gate_query_model.verify_query_result(gate_query)
    selected_certificate_audit = audit_model.audit_certificate(certificate) if certificate_audit is None else audit_model.verify_audit(certificate_audit)
    selected_certificate_query = certificate_query_model.query_certificate(certificate) if certificate_query is None else certificate_query_model.verify_query_result(certificate_query)
    provisional = RegistryFederationConsensusGateCertificatePackage(package_id, certificate, runtime, selected_gate, selected_gate_audit, selected_gate_query, selected_certificate_audit, selected_certificate_query, PACKAGE_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificatePackage(provisional.package_id, provisional.certificate, provisional.runtime, provisional.gate, provisional.gate_audit, provisional.gate_query, provisional.certificate_audit, provisional.certificate_query, address_package(provisional))


def package_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificatePackage:
    return verify_package(RegistryFederationConsensusGateCertificatePackage.from_mapping(value))


def verify_package(value: RegistryFederationConsensusGateCertificatePackage) -> RegistryFederationConsensusGateCertificatePackage:
    if not isinstance(value, RegistryFederationConsensusGateCertificatePackage) or (not value.content_address.endswith(":pending") and address_package(value) != value.content_address):
        raise ValidationError("certificate package is not valid")
    return value


def package_json(value: RegistryFederationConsensusGateCertificatePackage) -> str:
    return canonical_json(verify_package(value).to_dict())


def _manifest(value: RegistryFederationConsensusGateCertificatePackage) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "package_id": value.package_id, "files": FILES, "package_address": value.content_address, "certificate_address": value.certificate.content_address, "runtime_address": value.runtime.content_address, "gate_address": value.gate.content_address, "gate_audit_address": value.gate_audit.content_address, "gate_query_address": value.gate_query.content_address, "certificate_audit_address": value.certificate_audit.content_address, "certificate_query_address": value.certificate_query.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=PACKAGE_PREFIX + "-manifest")}


def package_bytes(value: RegistryFederationConsensusGateCertificatePackage) -> dict[str, bytes]:
    value = verify_package(value)
    return {MANIFEST_NAME: canonical_bytes(_manifest(value)), PACKAGE_NAME: canonical_bytes(value.to_dict()), CERTIFICATE_NAME: canonical_bytes(value.certificate.to_dict()), RUNTIME_NAME: canonical_bytes(value.runtime.to_dict()), GATE_NAME: canonical_bytes(value.gate.to_dict()), GATE_AUDIT_NAME: canonical_bytes(value.gate_audit.to_dict()), GATE_QUERY_NAME: canonical_bytes(value.gate_query.to_dict()), CERTIFICATE_AUDIT_NAME: canonical_bytes(value.certificate_audit.to_dict()), CERTIFICATE_QUERY_NAME: canonical_bytes(value.certificate_query.to_dict())}


def _write_atomic(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir() or (not overwrite and any(destination.iterdir())):
            raise ValidationError("certificate package destination is not writable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="certificate-package-staging-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (staging / name).write_bytes(payload[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def write_package(value: RegistryFederationConsensusGateCertificatePackage, directory: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic(Path(directory), package_bytes(value), overwrite=overwrite)


def load_package(directory: str | Path) -> RegistryFederationConsensusGateCertificatePackage:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir() or {item.name for item in source.iterdir()} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in source.iterdir()):
        raise ValidationError("certificate package directory does not contain exact canonical members")
    raw = {name: (source / name).read_bytes() for name in FILES}
    try:
        decoded = {name: json.loads(payload.decode("utf-8")) for name, payload in raw.items()}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("certificate package contains invalid JSON") from error
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("certificate package member is not canonical JSON")
    value = package_from_mapping(decoded[PACKAGE_NAME])
    if canonical_bytes(decoded[MANIFEST_NAME]) != canonical_bytes(_manifest(value)):
        raise ValidationError("certificate package manifest does not replay")
    projections = ((CERTIFICATE_NAME, value.certificate.to_dict()), (RUNTIME_NAME, value.runtime.to_dict()), (GATE_NAME, value.gate.to_dict()), (GATE_AUDIT_NAME, value.gate_audit.to_dict()), (GATE_QUERY_NAME, value.gate_query.to_dict()), (CERTIFICATE_AUDIT_NAME, value.certificate_audit.to_dict()), (CERTIFICATE_QUERY_NAME, value.certificate_query.to_dict()))
    if any(canonical_bytes(decoded[name]) != canonical_bytes(expected) for name, expected in projections):
        raise ValidationError("certificate package projections do not replay")
    return value


def verify_package_directory(directory: str | Path) -> RegistryFederationConsensusGateCertificatePackage:
    return load_package(directory)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "package_id", "files", "package_address", "certificate_address", "runtime_address", "gate_address", "gate_audit_address", "gate_query_address", "certificate_audit_address", "certificate_query_address", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "package_id": {"type": "string"}, "files": {"type": "array"}, "package_address": {"type": "string"}, "certificate_address": {"type": "string"}, "runtime_address": {"type": "string"}, "gate_address": {"type": "string"}, "gate_audit_address": {"type": "string"}, "gate_query_address": {"type": "string"}, "certificate_audit_address": {"type": "string"}, "certificate_query_address": {"type": "string"}, "manifest_address": {"type": "string"}}}


def package_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificatePackage.FIELDS), "properties": {"package_id": {"type": "string"}, "certificate": certificate_model.certificate_schema(), "runtime": runtime_model.runtime_schema(), "gate": gate_model.gate_schema(), "gate_audit": gate_audit_model.audit_schema(), "gate_query": gate_query_model.result_schema(), "certificate_audit": audit_model.audit_schema(), "certificate_query": certificate_query_model.result_schema(), "content_address": {"type": "string", "pattern": "^" + PACKAGE_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "package_prefix": PACKAGE_PREFIX, "files": FILES, "check_ids": CHECK_IDS, "features": ("nine-file certificate handoff", "atomic directory replacement", "canonical reload verification", "manifest and projection replay", "embedded gate runtime and independent gate audit", "certificate audit and query closure", "JSON export"), "schemas": ("manifest", "package")}


__all__ = ["BOUNDARY", "CERTIFICATE_AUDIT_NAME", "CERTIFICATE_NAME", "CERTIFICATE_QUERY_NAME", "CHECK_IDS", "FILES", "GATE_AUDIT_NAME", "GATE_NAME", "GATE_QUERY_NAME", "MANIFEST_NAME", "PACKAGE_NAME", "PACKAGE_PREFIX", "RUNTIME_NAME", "RegistryFederationConsensusGateCertificatePackage", "VERSION", "address_package", "build_package", "capabilities", "load_package", "manifest_schema", "package_bytes", "package_from_mapping", "package_json", "package_schema", "verify_package", "verify_package_directory", "write_package"]
