"""Federated package-registry reconciliation with durable, path-free receipts.

This boundary joins independently verified package registries without copying
their private directories into public documents. Each peer contributes a
content-addressed registry receipt. The federation computes package presence,
address divergence, quorum health, deterministic review actions, and an
operator-facing accept/review/reject disposition. The complete result can be
atomically persisted as five canonical JSON members and reloaded byte-for-byte.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = registry_model.VERSION + "-federation-v1"
BOUNDARY = registry_model.BOUNDARY + "_federation"
FEDERATION_PREFIX = registry_model.REGISTRY_PREFIX + "-federation"
PEER_PREFIX = FEDERATION_PREFIX + "-peer"
CONFLICT_PREFIX = FEDERATION_PREFIX + "-conflict"
RECONCILIATION_PREFIX = FEDERATION_PREFIX + "-reconciliation"
ACTION_PREFIX = FEDERATION_PREFIX + "-action"
MANIFEST_NAME = "manifest.json"
FEDERATION_NAME = "federation.json"
PEERS_NAME = "peers.json"
RECONCILIATION_NAME = "reconciliation.json"
ACTIONS_NAME = "actions.json"
FILES = (MANIFEST_NAME, FEDERATION_NAME, PEERS_NAME, RECONCILIATION_NAME, ACTIONS_NAME)
ARTIFACT_FILES = tuple(sorted(FILES[1:]))
RESOURCES = ("summary", "peers", "healthy", "degraded", "packages", "conflicts", "missing", "divergent", "actions", "evidence")
PEER_STATES = ("healthy", "degraded", "invalid")
CONFLICT_KINDS = ("missing", "divergent")
SEVERITIES = ("review", "blocking")
STATES = ("consistent", "degraded", "conflicted")
DECISIONS = ("accept", "review", "reject")
DEFAULT_FEDERATION_ID = "glio-noncode-catalog-promotion-package-federation"
DEFAULT_QUORUM = 1
MAX_PEERS = 32
MAX_PACKAGES = registry_model.MAX_ENTRIES
MAX_CONFLICTS = MAX_PACKAGES
MAX_ACTIONS = MAX_CONFLICTS + 1
MAX_TEXT = registry_model.MAX_TEXT
CHECK_IDS = ("exact-fields", "public-boundary", "peer-conservation", "peer-identity", "peer-audit-conservation", "package-union-conservation", "conflict-conservation", "quorum-conservation", "state-conservation", "action-conservation", "manifest-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _label(value: Any, field: str, maximum: int = 256) -> str:
    value = _text(value, field, maximum)
    if ":" in value or "/" in value or "\\" in value or any(character.isspace() for character in value):
        raise ValidationError(f"{field} must be a stable path-free label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an invalid public content address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _labels(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = _sequence(value, field, maximum)
    result = tuple(_label(item, field) for item in values)
    if len(set(result)) != len(result) or result != tuple(sorted(result)):
        raise ValidationError(f"{field} must be unique and canonically sorted")
    return result


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = _sequence(value, field, maximum)
    result = tuple(_address(item, field) for item in values)
    if len(set(result)) != len(result) or result != tuple(sorted(result)):
        raise ValidationError(f"{field} must be unique and canonically sorted")
    return result


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer:
    """Public receipt for one independently verified registry peer."""

    FIELDS = ("ordinal", "peer_id", "registry_id", "registry_address", "manifest_address", "entry_count", "accepted_count", "release_ready_count", "held_count", "blocked_count", "artifact_count", "file_count", "package_ids", "package_addresses", "peer_state", "audit_state", "audit_accepted", "content_address")

    def __init__(self, ordinal: int, peer_id: str, registry_id: str, registry_address: str, manifest_address: str, entry_count: int, accepted_count: int, release_ready_count: int, held_count: int, blocked_count: int, artifact_count: int, file_count: int, package_ids: Sequence[str], package_addresses: Sequence[str], peer_state: str, audit_state: str, audit_accepted: bool, content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation peer ordinal", MAX_PEERS, positive=True)
        self.peer_id = _label(peer_id, "federation peer ID")
        self.registry_id = _label(registry_id, "federation peer registry ID")
        self.registry_address = _address(registry_address, "federation peer registry address", registry_model.REGISTRY_PREFIX)
        self.manifest_address = _address(manifest_address, "federation peer manifest address", registry_model.REGISTRY_PREFIX + "-manifest")
        self.entry_count = _count(entry_count, "federation peer entry count", MAX_PACKAGES)
        self.accepted_count = _count(accepted_count, "federation peer accepted count", self.entry_count)
        self.release_ready_count = _count(release_ready_count, "federation peer release-ready count", self.entry_count)
        self.held_count = _count(held_count, "federation peer held count", self.entry_count)
        self.blocked_count = _count(blocked_count, "federation peer blocked count", self.entry_count)
        self.artifact_count = _count(artifact_count, "federation peer artifact count", MAX_PACKAGES * registry_model.package_model.MAX_ARTIFACTS)
        self.file_count = _count(file_count, "federation peer file count", MAX_PACKAGES * len(registry_model.package_model.FILES))
        self.package_ids = _labels(package_ids, "federation peer package IDs", MAX_PACKAGES)
        self.package_addresses = _addresses(package_addresses, "federation peer package addresses", MAX_PACKAGES)
        self.peer_state = _text(peer_state, "federation peer state", 32)
        self.audit_state = _text(audit_state, "federation peer audit state", 32)
        self.audit_accepted = _bool(audit_accepted, "federation peer audit accepted")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.entry_count != len(self.package_ids) or self.entry_count != len(self.package_addresses):
            raise ValidationError("federation peer package identities are not conserved")
        if self.accepted_count + self.blocked_count != self.entry_count or self.release_ready_count + self.held_count + self.blocked_count != self.entry_count:
            raise ValidationError("federation peer disposition counters are not conserved")
        if self.peer_state not in PEER_STATES or self.audit_state not in ("complete", "incomplete"):
            raise ValidationError("federation peer state is unsupported")
        if self.peer_state == "healthy" and not self.audit_accepted:
            raise ValidationError("healthy federation peers require accepted audits")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "federation peer content address")
        elif address_peer(self) != self.content_address:
            raise ValidationError("federation peer content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("federation peer crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer:
        value = _mapping(value, "federation peer")
        _strict(value, set(cls.FIELDS), "federation peer")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"federation peer is missing fields: {missing}")
        return cls(*(value[field] for field in cls.FIELDS))


def address_peer(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer):
        raise ValidationError("federation peer address requires a typed peer")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PEER_PREFIX)


def _peer(peer_id: str, ordinal: int, value: registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer:
    value = registry_model.verify_registry(value)
    assurance = registry_model.audit_registry(value)
    ordered_entries = tuple(sorted(value.entries, key=lambda entry: entry.package_id))
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer(ordinal, peer_id, value.registry_id, value.content_address, value.manifest["manifest_address"], value.entry_count, value.accepted_count, value.release_ready_count, value.held_count, value.blocked_count, value.artifact_count, value.file_count, tuple(entry.package_id for entry in ordered_entries), tuple(entry.package_address for entry in ordered_entries), "healthy" if assurance.accepted else "degraded", assurance.state, assurance.accepted, "pending:federation-peer")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer(provisional.ordinal, provisional.peer_id, provisional.registry_id, provisional.registry_address, provisional.manifest_address, provisional.entry_count, provisional.accepted_count, provisional.release_ready_count, provisional.held_count, provisional.blocked_count, provisional.artifact_count, provisional.file_count, provisional.package_ids, provisional.package_addresses, provisional.peer_state, provisional.audit_state, provisional.audit_accepted, address_peer(provisional))


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict:
    """One missing or divergent package identity across peers."""

    FIELDS = ("ordinal", "package_id", "kind", "peer_ids", "addresses", "expected_peer_count", "observed_peer_count", "severity", "detail", "content_address")

    def __init__(self, ordinal: int, package_id: str, kind: str, peer_ids: Sequence[str], addresses: Sequence[str], expected_peer_count: int, observed_peer_count: int, severity: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation conflict ordinal", MAX_CONFLICTS, positive=True)
        self.package_id = _label(package_id, "federation conflict package ID")
        if kind not in CONFLICT_KINDS or severity not in SEVERITIES:
            raise ValidationError("federation conflict kind or severity is unsupported")
        self.kind = kind
        self.peer_ids = _labels(peer_ids, "federation conflict peer IDs", MAX_PEERS)
        self.addresses = _addresses(addresses, "federation conflict addresses", MAX_PEERS)
        self.expected_peer_count = _count(expected_peer_count, "federation conflict expected peer count", MAX_PEERS, positive=True)
        self.observed_peer_count = _count(observed_peer_count, "federation conflict observed peer count", self.expected_peer_count, positive=True)
        self.severity = severity
        self.detail = _text(detail, "federation conflict detail", MAX_TEXT)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.observed_peer_count != len(self.peer_ids) or self.kind == "missing" and self.severity != "review" or self.kind == "divergent" and self.severity != "blocking":
            raise ValidationError("federation conflict observations are not conserved")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "federation conflict content address")
        elif address_conflict(self) != self.content_address:
            raise ValidationError("federation conflict content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("federation conflict crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict:
        value = _mapping(value, "federation conflict")
        _strict(value, set(cls.FIELDS), "federation conflict")
        return cls(*(value[field] for field in cls.FIELDS))


def address_conflict(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict):
        raise ValidationError("federation conflict address requires a typed conflict")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CONFLICT_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction:
    """An addressed review or blocking action produced by reconciliation."""

    FIELDS = ("ordinal", "action_id", "kind", "package_id", "severity", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, action_id: str, kind: str, package_id: str, severity: str, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation action ordinal", MAX_ACTIONS, positive=True)
        self.action_id = _label(action_id, "federation action ID")
        if kind not in ("conflict", "quorum") or severity not in SEVERITIES:
            raise ValidationError("federation action kind or severity is unsupported")
        self.kind = kind
        self.package_id = _label(package_id, "federation action package ID")
        self.severity = severity
        self.detail = _text(detail, "federation action detail", MAX_TEXT)
        self.evidence_addresses = _addresses(evidence_addresses, "federation action evidence addresses", MAX_PEERS + 1)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses:
            raise ValidationError("federation actions require evidence addresses")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "federation action content address")
        elif address_action(self) != self.content_address:
            raise ValidationError("federation action content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("federation action crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction:
        value = _mapping(value, "federation action")
        _strict(value, set(cls.FIELDS), "federation action")
        return cls(*(value[field] for field in cls.FIELDS))


def address_action(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction):
        raise ValidationError("federation action address requires a typed action")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ACTION_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation:
    """Deterministic package-level reconciliation across federation peers."""

    FIELDS = ("reconciliation_id", "peer_count", "quorum", "healthy_peer_count", "package_count", "consistent_package_count", "missing_package_count", "divergent_package_count", "conflict_count", "conflicts", "state", "decision", "accepted", "content_address")

    def __init__(self, reconciliation_id: str, peer_count: int, quorum: int, healthy_peer_count: int, package_count: int, consistent_package_count: int, missing_package_count: int, divergent_package_count: int, conflict_count: int, conflicts: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict], state: str, decision: str, accepted: bool, content_address: str) -> None:
        self.reconciliation_id = _label(reconciliation_id, "federation reconciliation ID")
        self.peer_count = _count(peer_count, "federation reconciliation peer count", MAX_PEERS, positive=True)
        self.quorum = _count(quorum, "federation reconciliation quorum", self.peer_count, positive=True)
        self.healthy_peer_count = _count(healthy_peer_count, "federation reconciliation healthy peer count", self.peer_count)
        self.package_count = _count(package_count, "federation reconciliation package count", MAX_PACKAGES)
        self.consistent_package_count = _count(consistent_package_count, "federation reconciliation consistent package count", self.package_count)
        self.missing_package_count = _count(missing_package_count, "federation reconciliation missing package count", self.package_count)
        self.divergent_package_count = _count(divergent_package_count, "federation reconciliation divergent package count", self.package_count)
        self.conflict_count = _count(conflict_count, "federation reconciliation conflict count", MAX_CONFLICTS)
        self.conflicts = tuple(conflicts)
        if state not in STATES or decision not in DECISIONS:
            raise ValidationError("federation reconciliation state or decision is unsupported")
        self.state = state
        self.decision = decision
        self.accepted = _bool(accepted, "federation reconciliation accepted")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.conflict_count != len(self.conflicts) or self.missing_package_count + self.divergent_package_count != self.conflict_count or self.consistent_package_count + self.conflict_count != self.package_count:
            raise ValidationError("federation reconciliation package observations are not conserved")
        if any(not isinstance(conflict, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict) for conflict in self.conflicts):
            raise ValidationError("federation reconciliation conflicts must be typed")
        if tuple(conflict.ordinal for conflict in self.conflicts) != tuple(range(1, self.conflict_count + 1)):
            raise ValidationError("federation reconciliation conflict ordinals are not canonical")
        expected = "conflicted" if self.divergent_package_count else "degraded" if self.missing_package_count or self.healthy_peer_count < self.quorum else "consistent"
        expected_decision = {"consistent": "accept", "degraded": "review", "conflicted": "reject"}[expected]
        if self.state != expected or self.decision != expected_decision or self.accepted != (expected == "consistent"):
            raise ValidationError("federation reconciliation state is not conserved")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "federation reconciliation content address")
        elif address_reconciliation(self) != self.content_address:
            raise ValidationError("federation reconciliation content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("federation reconciliation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"reconciliation_id": self.reconciliation_id, "peer_count": self.peer_count, "quorum": self.quorum, "healthy_peer_count": self.healthy_peer_count, "package_count": self.package_count, "consistent_package_count": self.consistent_package_count, "missing_package_count": self.missing_package_count, "divergent_package_count": self.divergent_package_count, "conflict_count": self.conflict_count, "conflicts": tuple(conflict.to_dict() for conflict in self.conflicts), "state": self.state, "decision": self.decision, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "conflicts"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation:
        value = _mapping(value, "federation reconciliation")
        _strict(value, set(cls.FIELDS), "federation reconciliation")
        conflicts = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict.from_mapping(item) for item in _sequence(value["conflicts"], "federation reconciliation conflicts", MAX_CONFLICTS))
        return cls(value["reconciliation_id"], value["peer_count"], value["quorum"], value["healthy_peer_count"], value["package_count"], value["consistent_package_count"], value["missing_package_count"], value["divergent_package_count"], value["conflict_count"], conflicts, value["state"], value["decision"], value["accepted"], value["content_address"])


def address_reconciliation(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation):
        raise ValidationError("federation reconciliation address requires a typed reconciliation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RECONCILIATION_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation:
    """A verified federation of package-registry peers."""

    FIELDS = ("federation_id", "manifest", "peers", "reconciliation", "actions", "peer_count", "healthy_peer_count", "package_count", "conflict_count", "action_count", "state", "decision", "accepted", "content_address")

    def __init__(self, federation_id: str, manifest: Mapping[str, Any], peers: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer], reconciliation: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation, actions: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction], peer_count: int, healthy_peer_count: int, package_count: int, conflict_count: int, action_count: int, state: str, decision: str, accepted: bool, content_address: str) -> None:
        self.federation_id = _label(federation_id, "federation ID")
        self.manifest = dict(_mapping(manifest, "federation manifest"))
        self.peers = tuple(peers)
        if not isinstance(reconciliation, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation):
            raise ValidationError("federation reconciliation must be typed")
        self.reconciliation = reconciliation
        self.actions = tuple(actions)
        self.peer_count = _count(peer_count, "federation peer count", MAX_PEERS, positive=True)
        self.healthy_peer_count = _count(healthy_peer_count, "federation healthy peer count", self.peer_count)
        self.package_count = _count(package_count, "federation package count", MAX_PACKAGES)
        self.conflict_count = _count(conflict_count, "federation conflict count", MAX_CONFLICTS)
        self.action_count = _count(action_count, "federation action count", MAX_ACTIONS)
        if state not in STATES or decision not in DECISIONS:
            raise ValidationError("federation state or decision is unsupported")
        self.state = state
        self.decision = decision
        self.accepted = _bool(accepted, "federation accepted")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _strict(self.manifest, {"version", "boundary", "federation_id", "peer_count", "quorum", "files", "peers_address", "reconciliation_address", "actions_address", "manifest_address"}, "federation manifest")
        manifest_addresses = (self.manifest.get("peers_address"), self.manifest.get("reconciliation_address"), self.manifest.get("actions_address"), self.manifest.get("manifest_address"))
        allowed_prefixes = (PEER_PREFIX + "-document:", RECONCILIATION_PREFIX + "-document:", ACTION_PREFIX + "-document:", FEDERATION_PREFIX + "-manifest:")
        if self.manifest.get("version") != VERSION or self.manifest.get("boundary") != BOUNDARY or self.manifest.get("federation_id") != self.federation_id or self.manifest.get("peer_count") != self.peer_count or tuple(self.manifest.get("files", ())) != ARTIFACT_FILES or any(not isinstance(address, str) or (not address.startswith("pending:") and not address.startswith(prefix)) for address, prefix in zip(manifest_addresses, allowed_prefixes, strict=True)):
            raise ValidationError("federation manifest is not conserved")
        if len(self.peers) != self.peer_count or not self.peers or any(not isinstance(peer, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer) for peer in self.peers):
            raise ValidationError("federation peers are outside their bound")
        if tuple(peer.ordinal for peer in self.peers) != tuple(range(1, self.peer_count + 1)) or len({peer.peer_id for peer in self.peers}) != self.peer_count:
            raise ValidationError("federation peer identity or ordering is not canonical")
        if self.reconciliation.peer_count != self.peer_count or self.reconciliation.healthy_peer_count != self.healthy_peer_count or self.reconciliation.package_count != self.package_count or self.reconciliation.conflict_count != self.conflict_count:
            raise ValidationError("federation reconciliation counts are not linked")
        if len(self.actions) != self.action_count or tuple(action.ordinal for action in self.actions) != tuple(range(1, self.action_count + 1)) or any(not isinstance(action, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction) for action in self.actions):
            raise ValidationError("federation actions are not canonical")
        if self.state != self.reconciliation.state or self.decision != self.reconciliation.decision or self.accepted != self.reconciliation.accepted:
            raise ValidationError("federation disposition is not linked to reconciliation")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "federation content address")
        elif address_federation(self) != self.content_address:
            raise ValidationError("federation content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("federation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"federation_id": self.federation_id, "manifest": self.manifest, "peers": tuple(peer.to_dict() for peer in self.peers), "reconciliation": self.reconciliation.to_dict(), "actions": tuple(action.to_dict() for action in self.actions), "peer_count": self.peer_count, "healthy_peer_count": self.healthy_peer_count, "package_count": self.package_count, "conflict_count": self.conflict_count, "action_count": self.action_count, "state": self.state, "decision": self.decision, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"manifest", "peers", "reconciliation", "actions"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation:
        value = _mapping(value, "federation")
        _strict(value, set(cls.FIELDS), "federation")
        peers = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer.from_mapping(item) for item in _sequence(value["peers"], "federation peers", MAX_PEERS))
        reconciliation = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation.from_mapping(_mapping(value["reconciliation"], "federation reconciliation"))
        actions = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction.from_mapping(item) for item in _sequence(value["actions"], "federation actions", MAX_ACTIONS))
        manifest = dict(_mapping(value["manifest"], "federation manifest"))
        if isinstance(manifest.get("files"), list):
            manifest["files"] = tuple(manifest["files"])
        return cls(value["federation_id"], manifest, peers, reconciliation, actions, value["peer_count"], value["healthy_peer_count"], value["package_count"], value["conflict_count"], value["action_count"], value["state"], value["decision"], value["accepted"], value["content_address"])


def address_reconciliation_document(value: Mapping[str, Any]) -> str:
    return content_hash(dict(_mapping(value, "federation reconciliation document")) | {"content_address": None}, prefix=RECONCILIATION_PREFIX + "-document")


def address_peers_document(value: Mapping[str, Any]) -> str:
    return content_hash(dict(_mapping(value, "federation peers document")) | {"content_address": None}, prefix=PEER_PREFIX + "-document")


def address_actions_document(value: Mapping[str, Any]) -> str:
    return content_hash(dict(_mapping(value, "federation actions document")) | {"content_address": None}, prefix=ACTION_PREFIX + "-document")


def address_manifest(value: Mapping[str, Any]) -> str:
    return content_hash(dict(_mapping(value, "federation manifest")) | {"manifest_address": None}, prefix=FEDERATION_PREFIX + "-manifest")


def address_federation(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation):
        raise ValidationError("federation address requires a typed federation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FEDERATION_PREFIX)


def _documents(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    peers = {"peers": tuple(peer.to_dict() for peer in value.peers)}
    peers["content_address"] = address_peers_document(peers)
    reconciliation = {"reconciliation": value.reconciliation.to_dict()}
    reconciliation["content_address"] = address_reconciliation_document(reconciliation)
    actions = {"actions": tuple(action.to_dict() for action in value.actions)}
    actions["content_address"] = address_actions_document(actions)
    return peers, reconciliation, actions


def _manifest(federation_id: str, peer_count: int, quorum: int, documents: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]) -> dict[str, Any]:
    peers, reconciliation, actions = documents
    body = {"version": VERSION, "boundary": BOUNDARY, "federation_id": federation_id, "peer_count": peer_count, "quorum": quorum, "files": ARTIFACT_FILES, "peers_address": peers["content_address"], "reconciliation_address": reconciliation["content_address"], "actions_address": actions["content_address"]}
    return body | {"manifest_address": address_manifest(body)}


def _make_conflict(ordinal: int, package_id: str, peer_map: Mapping[str, str], peer_count: int) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict:
    addresses = tuple(sorted(set(peer_map.values())))
    kind = "divergent" if len(addresses) > 1 else "missing"
    severity = "blocking" if kind == "divergent" else "review"
    detail = "package has divergent content addresses across federation peers" if kind == "divergent" else "package is missing from one or more federation peers"
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict(ordinal, package_id, kind, tuple(sorted(peer_map)), addresses, peer_count, len(peer_map), severity, detail, "pending:federation-conflict")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict(provisional.ordinal, provisional.package_id, provisional.kind, provisional.peer_ids, provisional.addresses, provisional.expected_peer_count, provisional.observed_peer_count, provisional.severity, provisional.detail, address_conflict(provisional))


def _reconciliation(peer_id_to_peer: Mapping[str, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer], reconciliation_id: str, quorum: int) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation:
    peer_count = len(peer_id_to_peer)
    package_map: dict[str, dict[str, str]] = {}
    for peer_id, peer in peer_id_to_peer.items():
        package_map.update({package_id: package_map.get(package_id, {}) | {peer_id: address} for package_id, address in zip(peer.package_ids, peer.package_addresses, strict=True)})
    conflicts: list[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict] = []
    consistent = 0
    for ordinal, package_id in enumerate(sorted(package_map), start=1):
        observations = package_map[package_id]
        if len(set(observations.values())) > 1 or len(observations) != peer_count:
            conflicts.append(_make_conflict(ordinal, package_id, observations, peer_count))
        else:
            consistent += 1
    missing = sum(conflict.kind == "missing" for conflict in conflicts)
    divergent = sum(conflict.kind == "divergent" for conflict in conflicts)
    healthy = sum(peer.peer_state == "healthy" for peer in peer_id_to_peer.values())
    state = "conflicted" if divergent else "degraded" if missing or healthy < quorum else "consistent"
    decision = {"consistent": "accept", "degraded": "review", "conflicted": "reject"}[state]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation(reconciliation_id, peer_count, quorum, healthy, len(package_map), consistent, missing, divergent, len(conflicts), tuple(conflicts), state, decision, decision == "accept", "pending:federation-reconciliation")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation(provisional.reconciliation_id, provisional.peer_count, provisional.quorum, provisional.healthy_peer_count, provisional.package_count, provisional.consistent_package_count, provisional.missing_package_count, provisional.divergent_package_count, provisional.conflict_count, provisional.conflicts, provisional.state, provisional.decision, provisional.accepted, address_reconciliation(provisional))


def _actions(reconciliation: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation) -> tuple[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction, ...]:
    values: list[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction] = []
    for ordinal, conflict in enumerate(reconciliation.conflicts, start=1):
        provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction(ordinal, f"conflict-{conflict.package_id}", "conflict", conflict.package_id, conflict.severity, conflict.detail, (conflict.content_address, *conflict.addresses), "pending:federation-action")
        values.append(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction(provisional.ordinal, provisional.action_id, provisional.kind, provisional.package_id, provisional.severity, provisional.detail, provisional.evidence_addresses, address_action(provisional)))
    if reconciliation.healthy_peer_count < reconciliation.quorum:
        ordinal = len(values) + 1
        detail = "healthy federation peer count is below the declared quorum"
        evidence = tuple(sorted({address for conflict in reconciliation.conflicts for address in conflict.addresses})) or (reconciliation.content_address,)
        provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction(ordinal, "quorum-review", "quorum", "federation", "blocking", detail, evidence, "pending:federation-action")
        values.append(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction(provisional.ordinal, provisional.action_id, provisional.kind, provisional.package_id, provisional.severity, provisional.detail, provisional.evidence_addresses, address_action(provisional)))
    return tuple(values)


def _peer_inputs(peers: Sequence[tuple[str, registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry]]) -> tuple[tuple[str, registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry], ...]:
    if isinstance(peers, (str, bytes)) or not isinstance(peers, (list, tuple)) or not peers or len(peers) > MAX_PEERS:
        raise ValidationError("federation peers are outside their bound")
    values: list[tuple[str, registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry]] = []
    for item in peers:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValidationError("federation peers require peer ID and typed registry")
        peer_id, registry_value = item
        if not isinstance(registry_value, registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry):
            raise ValidationError("federation peer registry must be typed")
        values.append((_label(peer_id, "federation peer ID"), registry_model.verify_registry(registry_value)))
    if len({peer_id for peer_id, _ in values}) != len(values):
        raise ValidationError("federation peer IDs must be unique")
    return tuple(sorted(values, key=lambda item: item[0]))


def build_federation(peers: Sequence[tuple[str, registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry]], *, federation_id: str = DEFAULT_FEDERATION_ID, reconciliation_id: str | None = None, quorum: int | None = None) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation:
    inputs = _peer_inputs(peers)
    federation_id = _label(federation_id, "federation ID")
    peer_models = tuple(_peer(peer_id, ordinal, value) for ordinal, (peer_id, value) in enumerate(inputs, start=1))
    quorum = (len(peer_models) + 1) // 2 if quorum is None else _count(quorum, "federation quorum", len(peer_models), positive=True)
    peer_map = {peer.peer_id: peer for peer in peer_models}
    reconciliation = _reconciliation(peer_map, _label(reconciliation_id or federation_id + "-reconciliation", "federation reconciliation ID"), quorum)
    actions = _actions(reconciliation)
    documents = _documents(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation(federation_id, {"version": VERSION, "boundary": BOUNDARY, "federation_id": federation_id, "peer_count": len(peer_models), "quorum": quorum, "files": ARTIFACT_FILES, "peers_address": "pending:peers-document", "reconciliation_address": "pending:reconciliation-document", "actions_address": "pending:actions-document", "manifest_address": "pending:federation-manifest"}, peer_models, reconciliation, actions, len(peer_models), reconciliation.healthy_peer_count, reconciliation.package_count, reconciliation.conflict_count, len(actions), reconciliation.state, reconciliation.decision, reconciliation.accepted, "pending:federation"))
    manifest = _manifest(federation_id, len(peer_models), quorum, documents)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation(federation_id, manifest, peer_models, reconciliation, actions, len(peer_models), reconciliation.healthy_peer_count, reconciliation.package_count, reconciliation.conflict_count, len(actions), reconciliation.state, reconciliation.decision, reconciliation.accepted, "pending:federation")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation(federation_id, manifest, peer_models, reconciliation, actions, provisional.peer_count, provisional.healthy_peer_count, provisional.package_count, provisional.conflict_count, provisional.action_count, provisional.state, provisional.decision, provisional.accepted, address_federation(provisional))


def build_federation_from_directories(peers: Sequence[tuple[str, str | Path]], *, federation_id: str = DEFAULT_FEDERATION_ID, reconciliation_id: str | None = None, quorum: int | None = None) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation:
    if isinstance(peers, (str, bytes)) or not isinstance(peers, (list, tuple)):
        raise ValidationError("federation peer directories must be a sequence")
    return build_federation(tuple((_label(peer_id, "federation peer ID"), registry_model.load_registry(directory)) for peer_id, directory in peers), federation_id=federation_id, reconciliation_id=reconciliation_id, quorum=quorum)


def federation_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation:
    return verify_federation(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation.from_mapping(value))


def verify_federation(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation):
        raise ValidationError("federation verification requires a typed federation")
    value._validate()
    if address_federation(value) != value.content_address:
        raise ValidationError("federation content address does not replay")
    return value


def federation_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> str:
    return canonical_json(verify_federation(value).to_dict())


def federation_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> str:
    value = verify_federation(value)
    fields = ("ordinal", "peer_id", "registry_id", "registry_address", "entry_count", "accepted_count", "release_ready_count", "held_count", "blocked_count", "peer_state", "audit_state", "audit_accepted", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: peer.to_dict()[field] for field in fields} for peer in value.peers)
    return output.getvalue()


def render_federation_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> str:
    value = verify_federation(value)
    lines = ["# Catalog Promotion Package Registry Federation", "", f"- Federation: `{value.federation_id}`", f"- State: `{value.state}`", f"- Decision: `{value.decision}`", f"- Peers: `{value.peer_count}`", f"- Healthy peers: `{value.healthy_peer_count}`", f"- Packages: `{value.package_count}`", f"- Conflicts: `{value.conflict_count}`", f"- Actions: `{value.action_count}`", f"- Content address: `{value.content_address}`", "", "| ordinal | peer | registry | peer state | audit | entries |", "| ---: | --- | --- | --- | --- | ---: |"]
    lines.extend(f"| {peer.ordinal} | `{peer.peer_id}` | `{peer.registry_id}` | `{peer.peer_state}` | `{peer.audit_state}` | {peer.entry_count} |" for peer in value.peers)
    return "\n".join(lines) + "\n"


def federation_manifest_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> str:
    return canonical_json(verify_federation(value).manifest)


def package_bytes(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> dict[str, bytes]:
    value = verify_federation(value)
    peers, reconciliation, actions = _documents(value)
    if value.manifest["peers_address"] != peers["content_address"] or value.manifest["reconciliation_address"] != reconciliation["content_address"] or value.manifest["actions_address"] != actions["content_address"]:
        raise ValidationError("federation document addresses do not link to the manifest")
    return {MANIFEST_NAME: canonical_bytes(value.manifest), FEDERATION_NAME: canonical_bytes(value.to_dict()), PEERS_NAME: canonical_bytes(peers), RECONCILIATION_NAME: canonical_bytes(reconciliation), ACTIONS_NAME: canonical_bytes(actions)}


def write_federation(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation, directory: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_federation(value)
    destination = Path(directory)
    if destination.exists():
        if not destination.is_dir() or not overwrite or tuple(sorted(item.name for item in destination.iterdir())) != tuple(sorted(FILES)):
            raise ValidationError("federation destination already exists or has an incompatible shape")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="federation-staging-", dir=str(destination.parent)))
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


def load_federation(directory: str | Path) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation:
    source = Path(directory)
    if not source.is_dir() or tuple(sorted(item.name for item in source.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("federation directory does not contain the exact canonical members")
    raw = {name: (source / name).read_bytes() for name in FILES}
    if any(canonical_bytes(json.loads(payload.decode("utf-8"))) != payload for payload in raw.values()):
        raise ValidationError("federation member is not canonical JSON")
    value = federation_from_mapping(json.loads(raw[FEDERATION_NAME].decode("utf-8")))
    manifest = json.loads(raw[MANIFEST_NAME].decode("utf-8"))
    if isinstance(manifest.get("files"), list):
        manifest["files"] = tuple(manifest["files"])
    if manifest != value.manifest:
        raise ValidationError("federation manifest does not match federation document")
    peers = json.loads(raw[PEERS_NAME].decode("utf-8"))
    reconciliation = json.loads(raw[RECONCILIATION_NAME].decode("utf-8"))
    actions = json.loads(raw[ACTIONS_NAME].decode("utf-8"))
    expected_peers, expected_reconciliation, expected_actions = _documents(value)
    for actual, expected in ((peers, expected_peers), (reconciliation, expected_reconciliation), (actions, expected_actions)):
        if canonical_bytes(actual) != canonical_bytes(expected):
            raise ValidationError("federation projection document does not replay")
    if {name: raw[name] for name in FILES} != package_bytes(value):
        raise ValidationError("federation member bytes do not replay")
    return value


def verify_federation_directory(directory: str | Path) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation:
    return load_federation(directory)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "federation_id", "peer_count", "quorum", "files", "peers_address", "reconciliation_address", "actions_address", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "federation_id": {"type": "string"}, "peer_count": {"type": "integer", "minimum": 1, "maximum": MAX_PEERS}, "quorum": {"type": "integer", "minimum": 1, "maximum": MAX_PEERS}, "files": {"type": "array", "const": list(ARTIFACT_FILES)}, "peers_address": {"type": "string", "pattern": "^" + PEER_PREFIX + "-document:"}, "reconciliation_address": {"type": "string", "pattern": "^" + RECONCILIATION_PREFIX + ":"}, "actions_address": {"type": "string", "pattern": "^" + ACTION_PREFIX + "-document:"}, "manifest_address": {"type": "string", "pattern": "^" + FEDERATION_PREFIX + "-manifest:"}}}


def peer_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_PEERS}, "peer_id": {"type": "string"}, "registry_id": {"type": "string"}, "registry_address": {"type": "string"}, "manifest_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES}, "package_ids": {"type": "array", "maxItems": MAX_PACKAGES}, "package_addresses": {"type": "array", "maxItems": MAX_PACKAGES}, "peer_state": {"type": "string", "enum": list(PEER_STATES)}, "audit_state": {"type": "string"}, "audit_accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + PEER_PREFIX + ":"}}}


def conflict_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CONFLICTS}, "package_id": {"type": "string"}, "kind": {"type": "string", "enum": list(CONFLICT_KINDS)}, "peer_ids": {"type": "array"}, "addresses": {"type": "array"}, "expected_peer_count": {"type": "integer"}, "observed_peer_count": {"type": "integer"}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CONFLICT_PREFIX + ":"}}}


def action_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_ACTIONS}, "action_id": {"type": "string"}, "kind": {"type": "string", "enum": ["conflict", "quorum"]}, "package_id": {"type": "string"}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string", "pattern": "^" + ACTION_PREFIX + ":"}}}


def reconciliation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation.FIELDS), "properties": {"reconciliation_id": {"type": "string"}, "peer_count": {"type": "integer"}, "quorum": {"type": "integer"}, "healthy_peer_count": {"type": "integer"}, "package_count": {"type": "integer"}, "consistent_package_count": {"type": "integer"}, "missing_package_count": {"type": "integer"}, "divergent_package_count": {"type": "integer"}, "conflict_count": {"type": "integer"}, "conflicts": {"type": "array", "maxItems": MAX_CONFLICTS, "items": conflict_schema()}, "state": {"type": "string", "enum": list(STATES)}, "decision": {"type": "string", "enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RECONCILIATION_PREFIX + ":"}}}


def federation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation.FIELDS), "properties": {"federation_id": {"type": "string"}, "manifest": manifest_schema(), "peers": {"type": "array", "minItems": 1, "maxItems": MAX_PEERS, "items": peer_schema()}, "reconciliation": reconciliation_schema(), "actions": {"type": "array", "maxItems": MAX_ACTIONS, "items": action_schema()}, "peer_count": {"type": "integer"}, "healthy_peer_count": {"type": "integer"}, "package_count": {"type": "integer"}, "conflict_count": {"type": "integer"}, "action_count": {"type": "integer"}, "state": {"type": "string", "enum": list(STATES)}, "decision": {"type": "string", "enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + FEDERATION_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "federation_prefix": FEDERATION_PREFIX, "peer_prefix": PEER_PREFIX, "conflict_prefix": CONFLICT_PREFIX, "reconciliation_prefix": RECONCILIATION_PREFIX, "action_prefix": ACTION_PREFIX, "files": FILES, "artifact_files": ARTIFACT_FILES, "resources": RESOURCES, "peer_states": PEER_STATES, "conflict_kinds": CONFLICT_KINDS, "severities": SEVERITIES, "states": STATES, "decisions": DECISIONS, "check_ids": CHECK_IDS, "limits": {"max_peers": MAX_PEERS, "max_packages": MAX_PACKAGES, "max_conflicts": MAX_CONFLICTS, "max_actions": MAX_ACTIONS}, "features": ("verified registry peer ingestion", "quorum-aware reconciliation", "missing and divergent package detection", "addressed review and blocking actions", "five-file atomic federation persistence", "strict byte-for-byte reload", "path-free public projection", "JSON CSV and Markdown exports"), "schemas": ("manifest", "peer", "conflict", "action", "reconciliation", "federation")}


__all__ = [
    "ACTION_PREFIX", "ARTIFACT_FILES", "BOUNDARY", "CHECK_IDS", "CONFLICT_KINDS", "CONFLICT_PREFIX", "DECISIONS", "DEFAULT_FEDERATION_ID", "DEFAULT_QUORUM", "FEDERATION_PREFIX", "FILES", "MAX_ACTIONS", "MAX_CONFLICTS", "MAX_PACKAGES", "MAX_PEERS", "MAX_TEXT", "PEER_PREFIX", "PEER_STATES", "RECONCILIATION_PREFIX", "RESOURCES", "SEVERITIES", "STATES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationAction", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationConflict", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationReconciliation",
    "action_schema", "address_action", "address_actions_document", "address_conflict", "address_federation", "address_manifest", "address_peer", "address_peers_document", "address_reconciliation", "address_reconciliation_document", "build_federation", "build_federation_from_directories", "capabilities", "conflict_schema", "federation_csv", "federation_from_mapping", "federation_json", "federation_manifest_json", "federation_schema", "load_federation", "manifest_schema", "package_bytes", "peer_schema", "reconciliation_schema", "render_federation_markdown", "verify_federation", "verify_federation_directory", "write_federation",
]
