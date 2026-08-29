"""High-level execution boundary for federation build, audit, query, and write."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_audit as audit_model
from . import registry_federation_query as query_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-runtime-v1"
BOUNDARY = federation_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = federation_model.FEDERATION_PREFIX + "-runtime"
MAX_PEERS = federation_model.MAX_PEERS
MAX_TEXT = federation_model.MAX_TEXT
CHECK_IDS = ("exact-fields", "peer-source-conservation", "federation-audit", "query-conservation", "persistence-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512)
    if not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationRuntime:
    """A complete federation execution receipt."""

    FIELDS = ("runtime_id", "federation", "audit", "query", "persisted", "content_address")

    def __init__(self, runtime_id: str, federation: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation, audit: audit_model.RegistryFederationAudit, query: query_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult, persisted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "runtime ID")
        if not isinstance(federation, federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) or not isinstance(audit, audit_model.RegistryFederationAudit) or not isinstance(query, query_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationQueryResult):
            raise ValidationError("runtime members must be typed")
        self.federation = federation_model.verify_federation(federation)
        self.audit = audit_model.verify_audit(audit)
        self.query = query_model.verify_query_result(query)
        self.persisted = _bool(persisted, "runtime persisted")
        if self.audit.federation_address != self.federation.content_address or self.query.federation_id != self.federation.federation_id:
            raise ValidationError("runtime members do not refer to the same federation")
        self.content_address = _address(content_address, "runtime content address", RUNTIME_PREFIX)
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("runtime content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "federation": self.federation.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "persisted": self.persisted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "federation_id": self.federation.federation_id, "federation_address": self.federation.content_address, "state": self.federation.state, "decision": self.federation.decision, "accepted": self.federation.accepted, "audit_accepted": self.audit.accepted, "query_returned_count": self.query.returned_count, "persisted": self.persisted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationRuntime:
        value = _mapping(value, "federation runtime")
        _strict(value, set(cls.FIELDS), "federation runtime")
        return cls(value["runtime_id"], federation_model.federation_from_mapping(value["federation"]), audit_model.audit_from_mapping(value["audit"]), query_model.query_result_from_mapping(value["query"]), value["persisted"], value["content_address"])


def address_runtime(value: RegistryFederationRuntime) -> str:
    if not isinstance(value, RegistryFederationRuntime):
        raise ValidationError("runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def run_federation_runtime(peers: Sequence[tuple[str, str | Path]], *, runtime_id: str = "federation-runtime", federation_id: str = federation_model.DEFAULT_FEDERATION_ID, reconciliation_id: str | None = None, quorum: int | None = None, destination: str | Path | None = None, overwrite: bool = False, resources: Sequence[str] = query_model.DEFAULT_RESOURCES, peer_id: str = "", package_id: str = "", kind: str = "", severity: str = "", text: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationRuntime:
    federation = federation_model.build_federation_from_directories(peers, federation_id=federation_id, reconciliation_id=reconciliation_id, quorum=quorum)
    audit = audit_model.audit_federation(federation)
    query = query_model.query_federation(federation, resources=resources, peer_id=peer_id, package_id=package_id, kind=kind, severity=severity, text=text, offset=offset, limit=limit)
    if destination is not None:
        federation_model.write_federation(federation, destination, overwrite=overwrite)
    provisional = RegistryFederationRuntime(runtime_id, federation, audit, query, destination is not None, RUNTIME_PREFIX + ":pending")
    return RegistryFederationRuntime(provisional.runtime_id, provisional.federation, provisional.audit, provisional.query, provisional.persisted, address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryFederationRuntime:
    return verify_runtime(RegistryFederationRuntime.from_mapping(value))


def verify_runtime(value: RegistryFederationRuntime) -> RegistryFederationRuntime:
    if not isinstance(value, RegistryFederationRuntime) or (not value.content_address.endswith(":pending") and address_runtime(value) != value.content_address):
        raise ValidationError("federation runtime is not valid")
    return value


def runtime_json(value: RegistryFederationRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationRuntime.FIELDS), "properties": {"runtime_id": {"type": "string"}, "federation": federation_model.federation_schema(), "audit": audit_model.audit_schema(), "query": query_model.result_schema(), "persisted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "runtime_prefix": RUNTIME_PREFIX, "check_ids": CHECK_IDS, "features": ("directory federation build", "independent federation audit", "bounded federation query", "optional atomic persistence", "single runtime content address", "JSON export"), "schemas": ("runtime",)}


__all__ = ["BOUNDARY", "CHECK_IDS", "RUNTIME_PREFIX", "VERSION", "RegistryFederationRuntime", "address_runtime", "capabilities", "run_federation_runtime", "runtime_from_mapping", "runtime_json", "runtime_schema", "verify_runtime"]
