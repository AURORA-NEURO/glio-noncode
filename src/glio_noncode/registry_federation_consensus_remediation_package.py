"""Durable, replayable package for a consensus remediation handoff."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_remediation as remediation_model
from . import registry_federation_consensus_remediation_audit as audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = remediation_model.VERSION + "-package-v1"
BOUNDARY = remediation_model.BOUNDARY + "_package"
PACKAGE_PREFIX = registry_model.REGISTRY_PREFIX + "-consensus-remediation-package"
MANIFEST_NAME = "manifest.json"
PACKAGE_NAME = "package.json"
REMEDIATION_NAME = "remediation.json"
AUDIT_NAME = "audit.json"
FILES = (MANIFEST_NAME, PACKAGE_NAME, REMEDIATION_NAME, AUDIT_NAME)
CHECK_IDS = ("exact-fields", "public-boundary", "remediation-link", "audit-link", "package-address", "manifest-conservation", "remediation-projection", "audit-projection", "canonical-members", "mapping-round-trip", "content-address", "path-free")


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


class RegistryFederationConsensusRemediationPackage:
    FIELDS = ("package_id", "remediation", "audit", "content_address")

    def __init__(self, package_id: str, remediation: remediation_model.RegistryFederationConsensusRemediation, audit: audit_model.RegistryFederationConsensusRemediationAudit, content_address: str) -> None:
        self.package_id = _label(package_id, "remediation package ID")
        if not isinstance(remediation, remediation_model.RegistryFederationConsensusRemediation) or not isinstance(audit, audit_model.RegistryFederationConsensusRemediationAudit):
            raise ValidationError("remediation package members must be typed")
        self.remediation = remediation_model.verify_remediation(remediation)
        self.audit = audit_model.verify_audit(audit)
        if self.audit.remediation_address != self.remediation.content_address:
            raise ValidationError("remediation package audit link does not replay")
        self.content_address = _address(content_address, "remediation package content address", PACKAGE_PREFIX)
        if not self.content_address.endswith(":pending") and address_package(self) != self.content_address:
            raise ValidationError("remediation package content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("remediation package crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "remediation": self.remediation.to_dict(), "audit": self.audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "remediation_address": self.remediation.content_address, "audit_address": self.audit.content_address, "step_count": self.remediation.step_count, "blocking_count": self.remediation.blocking_count, "ready": self.remediation.ready, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusRemediationPackage:
        value = _mapping(value, "remediation package")
        _strict(value, set(cls.FIELDS), "remediation package")
        return cls(value["package_id"], remediation_model.remediation_from_mapping(value["remediation"]), audit_model.audit_from_mapping(value["audit"]), value["content_address"])


def address_package(value: RegistryFederationConsensusRemediationPackage) -> str:
    if not isinstance(value, RegistryFederationConsensusRemediationPackage):
        raise ValidationError("remediation package address requires a typed package")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PACKAGE_PREFIX)


def build_package(remediation: remediation_model.RegistryFederationConsensusRemediation, *, package_id: str = "consensus-remediation-package") -> RegistryFederationConsensusRemediationPackage:
    remediation = remediation_model.verify_remediation(remediation)
    audit = audit_model.audit_remediation(remediation)
    provisional = RegistryFederationConsensusRemediationPackage(package_id, remediation, audit, PACKAGE_PREFIX + ":pending")
    return RegistryFederationConsensusRemediationPackage(provisional.package_id, provisional.remediation, provisional.audit, address_package(provisional))


def package_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusRemediationPackage:
    return verify_package(RegistryFederationConsensusRemediationPackage.from_mapping(value))


def verify_package(value: RegistryFederationConsensusRemediationPackage) -> RegistryFederationConsensusRemediationPackage:
    if not isinstance(value, RegistryFederationConsensusRemediationPackage) or (not value.content_address.endswith(":pending") and address_package(value) != value.content_address):
        raise ValidationError("remediation package is not valid")
    return value


def package_json(value: RegistryFederationConsensusRemediationPackage) -> str:
    return canonical_json(verify_package(value).to_dict())


def _manifest(value: RegistryFederationConsensusRemediationPackage) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "package_id": value.package_id, "files": tuple(sorted(FILES)), "package_address": value.content_address, "remediation_address": value.remediation.content_address, "audit_address": value.audit.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=PACKAGE_PREFIX + "-manifest")}


def package_bytes(value: RegistryFederationConsensusRemediationPackage) -> dict[str, bytes]:
    value = verify_package(value)
    remediation_projection = {"steps": tuple(item.to_dict() for item in value.remediation.steps), "content_address": content_hash({"steps": tuple(item.to_dict() for item in value.remediation.steps), "content_address": None}, prefix=remediation_model.STEP_PREFIX + "-document")}
    return {MANIFEST_NAME: canonical_bytes(_manifest(value)), PACKAGE_NAME: canonical_bytes(value.to_dict()), REMEDIATION_NAME: canonical_bytes(remediation_projection), AUDIT_NAME: canonical_bytes(value.audit.to_dict())}


def write_package(value: RegistryFederationConsensusRemediationPackage, directory: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_package(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("remediation package destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="consensus-remediation-package-staging-", dir=str(destination.parent)))
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


def load_package(directory: str | Path) -> RegistryFederationConsensusRemediationPackage:
    source = Path(directory)
    if not source.is_dir() or tuple(sorted(path.name for path in source.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("remediation package directory does not contain exact canonical members")
    raw = {name: (source / name).read_bytes() for name in FILES}
    decoded = {name: json.loads(payload.decode("utf-8")) for name, payload in raw.items()}
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("remediation package member is not canonical JSON")
    value = package_from_mapping(decoded[PACKAGE_NAME])
    if canonical_bytes(decoded[MANIFEST_NAME]) != canonical_bytes(_manifest(value)):
        raise ValidationError("remediation package manifest does not replay")
    remediation_projection = {"steps": tuple(item.to_dict() for item in value.remediation.steps), "content_address": content_hash({"steps": tuple(item.to_dict() for item in value.remediation.steps), "content_address": None}, prefix=remediation_model.STEP_PREFIX + "-document")}
    if canonical_bytes(decoded[REMEDIATION_NAME]) != canonical_bytes(remediation_projection) or canonical_bytes(decoded[AUDIT_NAME]) != canonical_bytes(value.audit.to_dict()):
        raise ValidationError("remediation package projections do not replay")
    return value


def verify_package_directory(directory: str | Path) -> RegistryFederationConsensusRemediationPackage:
    return load_package(directory)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "package_id", "files", "package_address", "remediation_address", "audit_address", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "package_id": {"type": "string"}, "files": {"type": "array"}, "package_address": {"type": "string"}, "remediation_address": {"type": "string"}, "audit_address": {"type": "string"}, "manifest_address": {"type": "string"}}}


def package_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusRemediationPackage.FIELDS), "properties": {"package_id": {"type": "string"}, "remediation": remediation_model.remediation_schema(), "audit": audit_model.audit_schema(), "content_address": {"type": "string", "pattern": "^" + PACKAGE_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "package_prefix": PACKAGE_PREFIX, "files": FILES, "check_ids": CHECK_IDS, "features": ("four-file remediation handoff", "atomic directory replacement", "canonical reload verification", "manifest and projection replay", "embedded independent audit", "JSON export"), "schemas": ("manifest", "package")}


__all__ = ["AUDIT_NAME", "BOUNDARY", "CHECK_IDS", "FILES", "MANIFEST_NAME", "PACKAGE_NAME", "PACKAGE_PREFIX", "REMEDIATION_NAME", "RegistryFederationConsensusRemediationPackage", "VERSION", "address_package", "build_package", "capabilities", "load_package", "manifest_schema", "package_bytes", "package_from_mapping", "package_json", "package_schema", "verify_package", "verify_package_directory", "write_package"]
