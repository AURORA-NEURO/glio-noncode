"""End-to-end execution receipt for registry federation consensus.

This boundary composes directory loading, federation evidence, quorum
resolution, independent auditing, bounded projection, and optional durable
storage into one replayable public value.  The composition is intentionally
read-only with respect to source registries: persistence writes only the
derived consensus package.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus as consensus_model
from . import registry_federation_consensus_audit as audit_model
from . import registry_federation_consensus_query as query_model
from . import registry_federation_consensus_remediation as remediation_model
from . import registry_federation_consensus_remediation_audit as remediation_audit_model
from . import registry_federation_consensus_remediation_query as remediation_query_model
from . import registry_federation_consensus_remediation_query_audit as remediation_query_audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = consensus_model.VERSION + "-runtime-v1"
BOUNDARY = consensus_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-runtime"
MAX_TEXT = federation_model.MAX_TEXT
CHECK_IDS = ("exact-fields", "federation-link", "consensus-link", "audit-link", "query-link", "persistence-state", "acceptance-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
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


class RegistryFederationConsensusRuntime:
    """A complete, independently auditable consensus execution receipt."""

    FIELDS = ("runtime_id", "federation", "consensus", "audit", "remediation", "remediation_audit", "query", "remediation_query", "remediation_query_audit", "persisted", "content_address")

    def __init__(self, runtime_id: str, federation: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation, consensus: consensus_model.RegistryFederationConsensus, audit: audit_model.RegistryFederationConsensusAudit, remediation: remediation_model.RegistryFederationConsensusRemediation, remediation_audit: remediation_audit_model.RegistryFederationConsensusRemediationAudit, query: query_model.RegistryFederationConsensusQueryResult, remediation_query: remediation_query_model.RegistryFederationConsensusRemediationQueryResult, remediation_query_audit: remediation_query_audit_model.RegistryFederationConsensusRemediationQueryAudit, persisted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "consensus runtime ID")
        if not isinstance(federation, federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) or not isinstance(consensus, consensus_model.RegistryFederationConsensus) or not isinstance(audit, audit_model.RegistryFederationConsensusAudit) or not isinstance(remediation, remediation_model.RegistryFederationConsensusRemediation) or not isinstance(remediation_audit, remediation_audit_model.RegistryFederationConsensusRemediationAudit) or not isinstance(query, query_model.RegistryFederationConsensusQueryResult) or not isinstance(remediation_query, remediation_query_model.RegistryFederationConsensusRemediationQueryResult) or not isinstance(remediation_query_audit, remediation_query_audit_model.RegistryFederationConsensusRemediationQueryAudit):
            raise ValidationError("consensus runtime members must be typed")
        self.federation = federation_model.verify_federation(federation)
        self.consensus = consensus_model.verify_consensus(consensus)
        self.audit = audit_model.verify_audit(audit)
        self.remediation = remediation_model.verify_remediation(remediation)
        self.remediation_audit = remediation_audit_model.verify_audit(remediation_audit)
        self.query = query_model.verify_query_result(query)
        self.remediation_query = remediation_query_model.verify_query_result(remediation_query)
        self.remediation_query_audit = remediation_query_audit_model.verify_audit(remediation_query_audit)
        self.persisted = _bool(persisted, "consensus runtime persisted")
        if self.consensus.federation_address != self.federation.content_address or self.consensus.federation_id != self.federation.federation_id:
            raise ValidationError("consensus runtime federation link does not replay")
        if self.audit.consensus_address != self.consensus.content_address or self.remediation.consensus_address != self.consensus.content_address or self.remediation_audit.remediation_address != self.remediation.content_address or self.query.query.consensus_address != self.consensus.content_address or self.remediation_query.query.remediation_address != self.remediation.content_address or self.remediation_query_audit.result_address != self.remediation_query.content_address:
            raise ValidationError("consensus runtime child links do not replay")
        self.content_address = _address(content_address, "consensus runtime content address", RUNTIME_PREFIX)
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("consensus runtime content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "federation": self.federation.to_dict(), "consensus": self.consensus.to_dict(), "audit": self.audit.to_dict(), "remediation": self.remediation.to_dict(), "remediation_audit": self.remediation_audit.to_dict(), "query": self.query.to_dict(), "remediation_query": self.remediation_query.to_dict(), "remediation_query_audit": self.remediation_query_audit.to_dict(), "persisted": self.persisted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "federation_id": self.federation.federation_id, "federation_address": self.federation.content_address, "consensus_id": self.consensus.consensus_id, "consensus_address": self.consensus.content_address, "state": self.consensus.state, "decision": self.consensus.decision, "accepted": self.consensus.accepted, "audit_accepted": self.audit.accepted, "audit_failed_count": self.audit.failed_count, "remediation_ready": self.remediation.ready, "remediation_step_count": self.remediation.step_count, "remediation_blocking_count": self.remediation.blocking_count, "remediation_audit_accepted": self.remediation_audit.accepted, "remediation_query_total_count": self.remediation_query.total_count, "remediation_query_audit_accepted": self.remediation_query_audit.accepted, "query_total_count": self.query.total_count, "query_returned_count": self.query.returned_count, "persisted": self.persisted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusRuntime:
        value = _mapping(value, "consensus runtime")
        _strict(value, set(cls.FIELDS), "consensus runtime")
        return cls(value["runtime_id"], federation_model.federation_from_mapping(value["federation"]), consensus_model.consensus_from_mapping(value["consensus"]), audit_model.audit_from_mapping(value["audit"]), remediation_model.remediation_from_mapping(value["remediation"]), remediation_audit_model.audit_from_mapping(value["remediation_audit"]), query_model.query_from_mapping(value["query"]), remediation_query_model.query_from_mapping(value["remediation_query"]), remediation_query_audit_model.audit_from_mapping(value["remediation_query_audit"]), value["persisted"], value["content_address"])


def address_runtime(value: RegistryFederationConsensusRuntime) -> str:
    if not isinstance(value, RegistryFederationConsensusRuntime):
        raise ValidationError("consensus runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def run_consensus_runtime(peers: Sequence[tuple[str, str | Path]], *, runtime_id: str = "consensus-runtime", federation_id: str = federation_model.DEFAULT_FEDERATION_ID, consensus_id: str = "federation-consensus", quorum: int | None = None, destination: str | Path | None = None, overwrite: bool = False, resources: Sequence[str] = query_model.DEFAULT_RESOURCES, package_id: str = "", resolution: str = "", severity: str = "", kind: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationConsensusRuntime:
    federation = federation_model.build_federation_from_directories(peers, federation_id=federation_id, quorum=quorum)
    consensus = consensus_model.build_consensus(federation, consensus_id=consensus_id, quorum=quorum)
    audit = audit_model.audit_consensus(consensus)
    remediation = remediation_model.build_remediation(consensus)
    remediation_audit = remediation_audit_model.audit_remediation(remediation)
    query = query_model.query_consensus(consensus, resources=resources, package_id=package_id, resolution=resolution, severity=severity, kind=kind, offset=offset, limit=limit)
    remediation_query = remediation_query_model.query_remediation(remediation, package_id=package_id, severity=severity, kind=kind, offset=offset, limit=limit)
    remediation_query_audit = remediation_query_audit_model.audit_query(remediation_query)
    if destination is not None:
        consensus_model.write_consensus(consensus, destination, overwrite=overwrite)
    provisional = RegistryFederationConsensusRuntime(runtime_id, federation, consensus, audit, remediation, remediation_audit, query, remediation_query, remediation_query_audit, destination is not None, RUNTIME_PREFIX + ":pending")
    return RegistryFederationConsensusRuntime(provisional.runtime_id, provisional.federation, provisional.consensus, provisional.audit, provisional.remediation, provisional.remediation_audit, provisional.query, provisional.remediation_query, provisional.remediation_query_audit, provisional.persisted, address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusRuntime:
    return verify_runtime(RegistryFederationConsensusRuntime.from_mapping(value))


def verify_runtime(value: RegistryFederationConsensusRuntime) -> RegistryFederationConsensusRuntime:
    if not isinstance(value, RegistryFederationConsensusRuntime) or (not value.content_address.endswith(":pending") and address_runtime(value) != value.content_address):
        raise ValidationError("consensus runtime is not valid")
    return value


def runtime_json(value: RegistryFederationConsensusRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusRuntime.FIELDS), "properties": {"runtime_id": {"type": "string"}, "federation": federation_model.federation_schema(), "consensus": consensus_model.consensus_schema(), "audit": audit_model.audit_schema(), "remediation": remediation_model.remediation_schema(), "remediation_audit": remediation_audit_model.audit_schema(), "query": query_model.result_schema(), "remediation_query": remediation_query_model.result_schema(), "remediation_query_audit": remediation_query_audit_model.audit_schema(), "persisted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "runtime_prefix": RUNTIME_PREFIX, "check_ids": CHECK_IDS, "features": ("directory-to-consensus orchestration", "independent consensus audit", "typed remediation plan", "independent remediation audit", "bounded consensus and remediation queries", "optional atomic consensus persistence", "acceptance conservation", "single runtime content address", "JSON export"), "schemas": ("runtime",)}


__all__ = ["BOUNDARY", "CHECK_IDS", "RUNTIME_PREFIX", "VERSION", "RegistryFederationConsensusRuntime", "address_runtime", "capabilities", "run_consensus_runtime", "runtime_from_mapping", "runtime_json", "runtime_schema", "verify_runtime"]
