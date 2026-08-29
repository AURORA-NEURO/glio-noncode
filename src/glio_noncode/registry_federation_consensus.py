"""Quorum-safe package address consensus and remediation receipts.

The federation boundary identifies disagreement.  This module explains what
could be selected safely, what remains unresolved, and which explicit actions
an operator must review.  It never edits a registry and never treats a
majority as permission to discard dissenting evidence.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = federation_model.VERSION + "-consensus-v1"
BOUNDARY = federation_model.BOUNDARY + "_consensus"
CONSENSUS_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus"
CANDIDATE_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-candidate"
PACKAGE_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-package"
ACTION_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-action"
MANIFEST_NAME = "manifest.json"
CONSENSUS_NAME = "consensus.json"
PACKAGES_NAME = "packages.json"
ACTIONS_NAME = "actions.json"
FILES = (MANIFEST_NAME, CONSENSUS_NAME, PACKAGES_NAME, ACTIONS_NAME)
MAX_PEERS = federation_model.MAX_PEERS
MAX_PACKAGES = federation_model.MAX_PACKAGES
MAX_CANDIDATES = MAX_PEERS
MAX_ACTIONS = federation_model.MAX_ACTIONS * 2
MAX_TEXT = federation_model.MAX_TEXT
STATES = federation_model.STATES
DECISIONS = federation_model.DECISIONS
RESOLUTIONS = ("selected", "unresolved", "absent")
ACTION_KINDS = ("inspect-divergence", "replicate-missing", "hold-package")
SEVERITIES = federation_model.SEVERITIES
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "federation-conservation",
    "quorum-conservation",
    "package-conservation",
    "candidate-conservation",
    "candidate-support-conservation",
    "selection-conservation",
    "resolution-conservation",
    "state-conservation",
    "decision-conservation",
    "action-conservation",
    "manifest-conservation",
    "content-address",
    "mapping-round-trip",
    "path-free",
)


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _required_text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    value = _text(value, field, maximum)
    if not value:
        raise ValidationError(f"{field} must not be empty")
    return value


def _label(value: Any, field: str) -> str:
    value = _required_text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _required_text(value, field, 512)
    if "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a path-free address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _optional_address(value: Any, field: str) -> str:
    if value == "":
        return ""
    return _address(value, field)


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
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _labels(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if len(set(labels)) != len(labels):
        raise ValidationError(f"{field} must not contain duplicates")
    return tuple(sorted(labels))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    addresses = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(set(addresses)) != len(addresses):
        raise ValidationError(f"{field} must not contain duplicate addresses")
    return tuple(sorted(addresses))


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


def _address_with_prefix(value: Any, field: str, prefix: str) -> str:
    return _address(value, field, prefix)


class RegistryFederationConsensusCandidate:
    """One package content address and its supporting peers."""

    FIELDS = ("ordinal", "package_id", "address", "peer_ids", "support_count", "expected_peer_count", "quorum", "selected", "content_address")

    def __init__(self, ordinal: int, package_id: str, address: str, peer_ids: Sequence[str], support_count: int, expected_peer_count: int, quorum: int, selected: bool, content_address: str) -> None:
        self.ordinal = _count(ordinal, "candidate ordinal", MAX_CANDIDATES, positive=True)
        self.package_id = _label(package_id, "candidate package ID")
        self.address = _address(address, "candidate package address")
        self.peer_ids = _labels(peer_ids, "candidate peer IDs", MAX_PEERS)
        self.support_count = _count(support_count, "candidate support count", MAX_PEERS)
        self.expected_peer_count = _count(expected_peer_count, "candidate expected peer count", MAX_PEERS, positive=True)
        self.quorum = _count(quorum, "candidate quorum", self.expected_peer_count, positive=True)
        self.selected = _bool(selected, "candidate selected flag")
        if self.support_count != len(self.peer_ids) or self.support_count > self.expected_peer_count:
            raise ValidationError("candidate support is not conserved")
        if self.selected and self.support_count < self.quorum:
            raise ValidationError("candidate selection does not meet quorum")
        self.content_address = _address_with_prefix(content_address, "candidate content address", CANDIDATE_PREFIX)
        if not self.content_address.endswith(":pending") and address_candidate(self) != self.content_address:
            raise ValidationError("candidate content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("candidate crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusCandidate:
        value = _mapping(value, "consensus candidate")
        _strict(value, set(cls.FIELDS), "consensus candidate")
        return cls(*(value[field] for field in cls.FIELDS))


def address_candidate(value: RegistryFederationConsensusCandidate) -> str:
    if not isinstance(value, RegistryFederationConsensusCandidate):
        raise ValidationError("candidate address requires a typed candidate")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CANDIDATE_PREFIX)


class RegistryFederationConsensusPackage:
    """All address candidates and the safe selection state for one package."""

    FIELDS = ("ordinal", "package_id", "expected_peer_count", "observed_peer_count", "candidate_count", "candidates", "selected_address", "resolution", "severity", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, package_id: str, expected_peer_count: int, observed_peer_count: int, candidate_count: int, candidates: Sequence[RegistryFederationConsensusCandidate], selected_address: str, resolution: str, severity: str, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "consensus package ordinal", MAX_PACKAGES, positive=True)
        self.package_id = _label(package_id, "consensus package ID")
        self.expected_peer_count = _count(expected_peer_count, "package expected peer count", MAX_PEERS, positive=True)
        self.observed_peer_count = _count(observed_peer_count, "package observed peer count", self.expected_peer_count)
        self.candidates = tuple(candidates)
        if len(self.candidates) > MAX_CANDIDATES or any(not isinstance(item, RegistryFederationConsensusCandidate) for item in self.candidates):
            raise ValidationError("package candidates are outside the bound")
        self.candidate_count = _count(candidate_count, "package candidate count", MAX_CANDIDATES)
        self.selected_address = _optional_address(selected_address, "package selected address")
        if self.candidate_count != len(self.candidates) or len({item.address for item in self.candidates}) != self.candidate_count or any(item.package_id != self.package_id or item.expected_peer_count != self.expected_peer_count for item in self.candidates):
            raise ValidationError("package candidates are not conserved")
        selected = tuple(item for item in self.candidates if item.selected)
        if len(selected) > 1 or (selected and selected[0].address != self.selected_address) or (not selected and self.selected_address):
            raise ValidationError("package selected address is not conserved")
        if self.candidate_count == 0:
            expected_resolution = "absent"
        elif selected:
            expected_resolution = "selected"
        else:
            expected_resolution = "unresolved"
        if resolution not in RESOLUTIONS or resolution != expected_resolution:
            raise ValidationError("package resolution is not conserved")
        self.resolution = resolution
        if severity not in SEVERITIES:
            raise ValidationError("package severity is unsupported")
        expected_severity = "review" if resolution == "selected" else "blocking" if self.candidate_count > 1 else "review"
        if severity != expected_severity:
            raise ValidationError("package severity is not conserved")
        self.severity = severity
        self.detail = _required_text(detail, "package detail")
        self.evidence_addresses = _addresses(evidence_addresses, "package evidence addresses", MAX_PEERS * (MAX_CANDIDATES + 1))
        if not self.evidence_addresses and self.candidate_count:
            raise ValidationError("package candidates require evidence")
        self.content_address = _address_with_prefix(content_address, "package content address", PACKAGE_PREFIX)
        if not self.content_address.endswith(":pending") and address_package(self) != self.content_address:
            raise ValidationError("package content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus package crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "package_id": self.package_id, "expected_peer_count": self.expected_peer_count, "observed_peer_count": self.observed_peer_count, "candidate_count": self.candidate_count, "candidates": tuple(item.to_dict() for item in self.candidates), "selected_address": self.selected_address, "resolution": self.resolution, "severity": self.severity, "detail": self.detail, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusPackage:
        value = _mapping(value, "consensus package")
        _strict(value, set(cls.FIELDS), "consensus package")
        candidates = tuple(value["candidates"]) if isinstance(value["candidates"], list) else value["candidates"]
        return cls(value["ordinal"], value["package_id"], value["expected_peer_count"], value["observed_peer_count"], value["candidate_count"], tuple(RegistryFederationConsensusCandidate.from_mapping(item) for item in candidates), value["selected_address"], value["resolution"], value["severity"], value["detail"], value["evidence_addresses"], value["content_address"])


def address_package(value: RegistryFederationConsensusPackage) -> str:
    if not isinstance(value, RegistryFederationConsensusPackage):
        raise ValidationError("package address requires a typed package")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PACKAGE_PREFIX)


class RegistryFederationConsensusAction:
    """An explicit remediation or review action derived from a package row."""

    FIELDS = ("ordinal", "action_id", "kind", "package_id", "severity", "detail", "peer_ids", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, action_id: str, kind: str, package_id: str, severity: str, detail: str, peer_ids: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "consensus action ordinal", MAX_ACTIONS, positive=True)
        self.action_id = _label(action_id, "consensus action ID")
        if kind not in ACTION_KINDS:
            raise ValidationError("consensus action kind is unsupported")
        self.kind = kind
        self.package_id = _label(package_id, "consensus action package ID")
        if severity not in SEVERITIES:
            raise ValidationError("consensus action severity is unsupported")
        self.severity = severity
        self.detail = _required_text(detail, "consensus action detail")
        self.peer_ids = _labels(peer_ids, "consensus action peer IDs", MAX_PEERS)
        self.evidence_addresses = _addresses(evidence_addresses, "consensus action evidence addresses", MAX_PEERS * (MAX_CANDIDATES + 1))
        self.content_address = _address_with_prefix(content_address, "consensus action content address", ACTION_PREFIX)
        if not self.content_address.endswith(":pending") and address_action(self) != self.content_address:
            raise ValidationError("consensus action content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus action crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusAction:
        value = _mapping(value, "consensus action")
        _strict(value, set(cls.FIELDS), "consensus action")
        return cls(*(value[field] for field in cls.FIELDS))


def address_action(value: RegistryFederationConsensusAction) -> str:
    if not isinstance(value, RegistryFederationConsensusAction):
        raise ValidationError("action address requires a typed action")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ACTION_PREFIX)


class RegistryFederationConsensus:
    """A complete, immutable consensus and remediation receipt."""

    FIELDS = ("consensus_id", "federation_id", "federation_address", "quorum", "packages", "actions", "package_count", "resolvable_count", "unresolved_count", "selected_count", "action_count", "state", "decision", "accepted", "content_address")

    def __init__(self, consensus_id: str, federation_id: str, federation_address: str, quorum: int, packages: Sequence[RegistryFederationConsensusPackage], actions: Sequence[RegistryFederationConsensusAction], package_count: int, resolvable_count: int, unresolved_count: int, selected_count: int, action_count: int, state: str, decision: str, accepted: bool, content_address: str) -> None:
        self.consensus_id = _label(consensus_id, "consensus ID")
        self.federation_id = _label(federation_id, "consensus federation ID")
        self.federation_address = _address_with_prefix(federation_address, "consensus federation address", federation_model.FEDERATION_PREFIX)
        self.quorum = _count(quorum, "consensus quorum", MAX_PEERS, positive=True)
        self.packages = tuple(packages)
        self.actions = tuple(actions)
        if len(self.packages) > MAX_PACKAGES or any(not isinstance(item, RegistryFederationConsensusPackage) for item in self.packages):
            raise ValidationError("consensus packages are outside the bound")
        if len(self.actions) > MAX_ACTIONS or any(not isinstance(item, RegistryFederationConsensusAction) for item in self.actions):
            raise ValidationError("consensus actions are outside the bound")
        self.package_count = _count(package_count, "consensus package count", MAX_PACKAGES, positive=True)
        self.resolvable_count = _count(resolvable_count, "consensus resolvable count", self.package_count)
        self.unresolved_count = _count(unresolved_count, "consensus unresolved count", self.package_count)
        self.selected_count = _count(selected_count, "consensus selected count", self.package_count)
        self.action_count = _count(action_count, "consensus action count", MAX_ACTIONS)
        if len(self.packages) != self.package_count or tuple(item.ordinal for item in self.packages) != tuple(range(1, self.package_count + 1)) or len({item.package_id for item in self.packages}) != self.package_count:
            raise ValidationError("consensus package ordering is not conserved")
        if self.resolvable_count != sum(item.resolution != "unresolved" for item in self.packages) or self.unresolved_count != sum(item.resolution == "unresolved" for item in self.packages) or self.selected_count != sum(item.resolution == "selected" for item in self.packages) or self.action_count != len(self.actions) or tuple(item.ordinal for item in self.actions) != tuple(range(1, self.action_count + 1)):
            raise ValidationError("consensus counters are not conserved")
        if state not in STATES or decision not in DECISIONS:
            raise ValidationError("consensus disposition is unsupported")
        self.accepted = _bool(accepted, "consensus acceptance")
        expected_state = "conflicted" if any(item.candidate_count > 1 and item.resolution == "unresolved" for item in self.packages) else "degraded" if self.unresolved_count else "consistent"
        expected_decision = "accept" if self.accepted else "reject" if expected_state == "conflicted" else "review"
        if state != expected_state or decision != expected_decision:
            raise ValidationError("consensus disposition is not conserved")
        self.state = state
        self.decision = decision
        if self.accepted != (self.state == "consistent" and self.decision == "accept" and self.unresolved_count == 0 and self.action_count == 0):
            raise ValidationError("consensus acceptance is not conserved")
        self.content_address = _address_with_prefix(content_address, "consensus content address", CONSENSUS_PREFIX)
        if not self.content_address.endswith(":pending") and address_consensus(self) != self.content_address:
            raise ValidationError("consensus content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"consensus_id": self.consensus_id, "federation_id": self.federation_id, "federation_address": self.federation_address, "quorum": self.quorum, "packages": tuple(item.to_dict() for item in self.packages), "actions": tuple(item.to_dict() for item in self.actions), "package_count": self.package_count, "resolvable_count": self.resolvable_count, "unresolved_count": self.unresolved_count, "selected_count": self.selected_count, "action_count": self.action_count, "state": self.state, "decision": self.decision, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"packages", "actions"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensus:
        value = _mapping(value, "federation consensus")
        _strict(value, set(cls.FIELDS), "federation consensus")
        packages = tuple(value["packages"]) if isinstance(value["packages"], list) else value["packages"]
        actions = tuple(value["actions"]) if isinstance(value["actions"], list) else value["actions"]
        return cls(value["consensus_id"], value["federation_id"], value["federation_address"], value["quorum"], tuple(RegistryFederationConsensusPackage.from_mapping(item) for item in packages), tuple(RegistryFederationConsensusAction.from_mapping(item) for item in actions), value["package_count"], value["resolvable_count"], value["unresolved_count"], value["selected_count"], value["action_count"], value["state"], value["decision"], value["accepted"], value["content_address"])


def address_consensus(value: RegistryFederationConsensus) -> str:
    if not isinstance(value, RegistryFederationConsensus):
        raise ValidationError("consensus address requires a typed receipt")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CONSENSUS_PREFIX)


def _candidate_rows(package_id: str, peer_maps: Mapping[str, Mapping[str, str]], expected_peer_count: int, quorum: int) -> tuple[RegistryFederationConsensusCandidate, ...]:
    address_peers: dict[str, list[str]] = defaultdict(list)
    for peer_id in sorted(peer_maps):
        if package_id in peer_maps[peer_id]:
            address_peers[peer_maps[peer_id][package_id]].append(peer_id)
    ranked = sorted(address_peers.items(), key=lambda item: (-len(item[1]), item[0]))
    candidates = []
    for ordinal, (address, peer_ids) in enumerate(ranked, start=1):
        stronger = bool(ranked and len(peer_ids) >= quorum and len(peer_ids) > max((len(other_peers) for other_address, other_peers in ranked if other_address != address), default=0))
        provisional = RegistryFederationConsensusCandidate(ordinal, package_id, address, tuple(peer_ids), len(peer_ids), expected_peer_count, quorum, stronger, CANDIDATE_PREFIX + ":pending")
        candidates.append(RegistryFederationConsensusCandidate(provisional.ordinal, provisional.package_id, provisional.address, provisional.peer_ids, provisional.support_count, provisional.expected_peer_count, provisional.quorum, provisional.selected, address_candidate(provisional)))
    return tuple(candidates)


def _package_row(ordinal: int, package_id: str, peer_maps: Mapping[str, Mapping[str, str]], peer_addresses: Mapping[str, str], expected_peer_count: int, quorum: int) -> RegistryFederationConsensusPackage:
    candidates = _candidate_rows(package_id, peer_maps, expected_peer_count, quorum)
    observed_peer_count = sum(package_id in peer_map for peer_map in peer_maps.values())
    selected = tuple(item for item in candidates if item.selected)
    selected_address = selected[0].address if selected else ""
    resolution = "selected" if selected else "unresolved" if candidates else "absent"
    severity = "review" if resolution == "selected" else "blocking" if candidates else "review"
    detail = f"{observed_peer_count} of {expected_peer_count} peers observed package; {len(candidates)} address candidates; " + (f"selected {selected_address}" if selected_address else "no quorum-safe selection")
    evidence = set(peer_addresses.values())
    evidence.update(item.content_address for item in candidates)
    provisional = RegistryFederationConsensusPackage(ordinal, package_id, expected_peer_count, observed_peer_count, len(candidates), candidates, selected_address, resolution, severity, detail, tuple(sorted(evidence)), PACKAGE_PREFIX + ":pending")
    return RegistryFederationConsensusPackage(provisional.ordinal, provisional.package_id, provisional.expected_peer_count, provisional.observed_peer_count, provisional.candidate_count, provisional.candidates, provisional.selected_address, provisional.resolution, provisional.severity, provisional.detail, provisional.evidence_addresses, address_package(provisional))


def _action(ordinal: int, kind: str, package: RegistryFederationConsensusPackage, detail: str, peer_ids: Sequence[str], severity: str) -> RegistryFederationConsensusAction:
    action_id = f"{kind}-{package.package_id}"
    provisional = RegistryFederationConsensusAction(ordinal, action_id, kind, package.package_id, severity, detail, peer_ids, (package.content_address, *package.evidence_addresses), ACTION_PREFIX + ":pending")
    return RegistryFederationConsensusAction(provisional.ordinal, provisional.action_id, provisional.kind, provisional.package_id, provisional.severity, provisional.detail, provisional.peer_ids, provisional.evidence_addresses, address_action(provisional))


def _actions(packages: Sequence[RegistryFederationConsensusPackage], peer_maps: Mapping[str, Mapping[str, str]]) -> tuple[RegistryFederationConsensusAction, ...]:
    actions: list[RegistryFederationConsensusAction] = []
    for package in packages:
        supporting = tuple(sorted(peer_id for peer_id, peer_map in peer_maps.items() if package.package_id in peer_map))
        if package.candidate_count > 1:
            severity = "review" if package.resolution == "selected" else "blocking"
            actions.append(_action(len(actions) + 1, "inspect-divergence", package, "review dissenting package addresses before any promotion or repair", supporting, severity))
        if package.observed_peer_count < package.expected_peer_count:
            severity = "review" if package.resolution == "selected" else "blocking"
            actions.append(_action(len(actions) + 1, "replicate-missing", package, "replicate or explain the package on every expected peer", supporting, severity))
        if package.resolution == "unresolved":
            actions.append(_action(len(actions) + 1, "hold-package", package, "hold the package until a quorum-supported address is established", supporting, "blocking"))
    return tuple(actions)


def build_consensus(value: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation, *, consensus_id: str = "federation-consensus", quorum: int | None = None) -> RegistryFederationConsensus:
    value = federation_model.verify_federation(value)
    peer_maps = {peer.peer_id: dict(zip(peer.package_ids, peer.package_addresses, strict=True)) for peer in value.peers}
    peer_addresses = {peer.peer_id: peer.content_address for peer in value.peers}
    effective_quorum = value.reconciliation.quorum if quorum is None else _count(quorum, "consensus quorum", value.peer_count, positive=True)
    package_ids = tuple(sorted({package_id for peer_map in peer_maps.values() for package_id in peer_map}))
    if not package_ids:
        raise ValidationError("consensus requires at least one package")
    packages = tuple(_package_row(ordinal, package_id, peer_maps, peer_addresses, value.peer_count, effective_quorum) for ordinal, package_id in enumerate(package_ids, start=1))
    actions = _actions(packages, peer_maps)
    unresolved_count = sum(item.resolution == "unresolved" for item in packages)
    selected_count = sum(item.resolution == "selected" for item in packages)
    resolvable_count = sum(item.resolution != "unresolved" for item in packages)
    state = "conflicted" if any(item.candidate_count > 1 and item.resolution == "unresolved" for item in packages) else "degraded" if unresolved_count else "consistent"
    accepted = state == "consistent" and value.accepted and not actions
    decision = "accept" if accepted else "reject" if state == "conflicted" else "review"
    provisional = RegistryFederationConsensus(consensus_id, value.federation_id, value.content_address, effective_quorum, packages, actions, len(packages), resolvable_count, unresolved_count, selected_count, len(actions), state, decision, accepted, CONSENSUS_PREFIX + ":pending")
    return RegistryFederationConsensus(provisional.consensus_id, provisional.federation_id, provisional.federation_address, provisional.quorum, provisional.packages, provisional.actions, provisional.package_count, provisional.resolvable_count, provisional.unresolved_count, provisional.selected_count, provisional.action_count, provisional.state, provisional.decision, provisional.accepted, address_consensus(provisional))


def consensus_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensus:
    return verify_consensus(RegistryFederationConsensus.from_mapping(value))


def verify_consensus(value: RegistryFederationConsensus) -> RegistryFederationConsensus:
    if not isinstance(value, RegistryFederationConsensus) or (not value.content_address.endswith(":pending") and address_consensus(value) != value.content_address):
        raise ValidationError("federation consensus is not valid")
    return value


def consensus_json(value: RegistryFederationConsensus) -> str:
    return canonical_json(verify_consensus(value).to_dict())


def consensus_csv(value: RegistryFederationConsensus) -> str:
    value = verify_consensus(value)
    stream = io.StringIO()
    fields = ("ordinal", "package_id", "expected_peer_count", "observed_peer_count", "candidate_count", "selected_address", "resolution", "severity", "detail", "evidence_addresses", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for package in value.packages:
        record = {field: package.to_dict()[field] for field in fields}
        record["evidence_addresses"] = "|".join(package.evidence_addresses)
        writer.writerow(record)
    return stream.getvalue()


def action_csv(value: RegistryFederationConsensus) -> str:
    value = verify_consensus(value)
    stream = io.StringIO()
    fields = ("ordinal", "action_id", "kind", "package_id", "severity", "detail", "peer_ids", "evidence_addresses", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for action in value.actions:
        record = action.to_dict()
        record["peer_ids"] = "|".join(action.peer_ids)
        record["evidence_addresses"] = "|".join(action.evidence_addresses)
        writer.writerow(record)
    return stream.getvalue()


def render_consensus_markdown(value: RegistryFederationConsensus) -> str:
    value = verify_consensus(value)
    lines = ["# Package Registry Federation Consensus", "", f"- Federation: `{value.federation_id}`", f"- Quorum: `{value.quorum}`", f"- State: `{value.state}`", f"- Decision: `{value.decision}`", f"- Selected: `{value.selected_count}/{value.package_count}`", f"- Consensus address: `{value.content_address}`", "", "| package | observed | candidates | selected address | resolution | severity |", "| --- | ---: | ---: | --- | --- | --- |"]
    lines.extend(f"| `{package.package_id}` | {package.observed_peer_count}/{package.expected_peer_count} | {package.candidate_count} | `{package.selected_address}` | `{package.resolution}` | `{package.severity}` |" for package in value.packages)
    if value.actions:
        lines.extend(("", "## Actions", "", "| action | kind | package | severity | detail |", "| --- | --- | --- | --- | --- |"))
        lines.extend(f"| `{action.action_id}` | `{action.kind}` | `{action.package_id}` | `{action.severity}` | {action.detail} |" for action in value.actions)
    return "\n".join(lines) + "\n"


def _manifest(value: RegistryFederationConsensus) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "consensus_id": value.consensus_id, "federation_id": value.federation_id, "quorum": value.quorum, "files": tuple(sorted(FILES)), "consensus_address": value.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=CONSENSUS_PREFIX + "-manifest")}


def package_bytes(value: RegistryFederationConsensus) -> dict[str, bytes]:
    value = verify_consensus(value)
    package_document = {"packages": tuple(item.to_dict() for item in value.packages), "content_address": content_hash({"packages": tuple(item.to_dict() for item in value.packages), "content_address": None}, prefix=PACKAGE_PREFIX + "-document")}
    action_document = {"actions": tuple(item.to_dict() for item in value.actions), "content_address": content_hash({"actions": tuple(item.to_dict() for item in value.actions), "content_address": None}, prefix=ACTION_PREFIX + "-document")}
    return {MANIFEST_NAME: canonical_bytes(_manifest(value)), CONSENSUS_NAME: canonical_bytes(value.to_dict()), PACKAGES_NAME: canonical_bytes(package_document), ACTIONS_NAME: canonical_bytes(action_document)}


def write_consensus(value: RegistryFederationConsensus, directory: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_consensus(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("consensus destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="federation-consensus-staging-", dir=str(destination.parent)))
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


def load_consensus(directory: str | Path) -> RegistryFederationConsensus:
    source = Path(directory)
    if not source.is_dir() or tuple(sorted(path.name for path in source.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("consensus directory does not contain exact canonical members")
    raw = {name: (source / name).read_bytes() for name in FILES}
    decoded = {name: json.loads(payload.decode("utf-8")) for name, payload in raw.items()}
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("consensus member is not canonical JSON")
    value = consensus_from_mapping(decoded[CONSENSUS_NAME])
    manifest = decoded[MANIFEST_NAME]
    if manifest.get("consensus_address") != value.content_address or manifest.get("consensus_id") != value.consensus_id or manifest.get("federation_id") != value.federation_id:
        raise ValidationError("consensus manifest does not match receipt")
    if canonical_bytes(manifest) != canonical_bytes(_manifest(value)):
        raise ValidationError("consensus manifest does not replay")
    package_document = {"packages": tuple(item.to_dict() for item in value.packages), "content_address": content_hash({"packages": tuple(item.to_dict() for item in value.packages), "content_address": None}, prefix=PACKAGE_PREFIX + "-document")}
    action_document = {"actions": tuple(item.to_dict() for item in value.actions), "content_address": content_hash({"actions": tuple(item.to_dict() for item in value.actions), "content_address": None}, prefix=ACTION_PREFIX + "-document")}
    if canonical_bytes(decoded[PACKAGES_NAME]) != canonical_bytes(package_document) or canonical_bytes(decoded[ACTIONS_NAME]) != canonical_bytes(action_document):
        raise ValidationError("consensus projections do not replay")
    return value


def verify_consensus_directory(directory: str | Path) -> RegistryFederationConsensus:
    return load_consensus(directory)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "consensus_id", "federation_id", "quorum", "files", "consensus_address", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "consensus_id": {"type": "string"}, "federation_id": {"type": "string"}, "quorum": {"type": "integer", "minimum": 1}, "files": {"type": "array", "minItems": 4, "maxItems": 4}, "consensus_address": {"type": "string", "pattern": "^" + CONSENSUS_PREFIX + ":"}, "manifest_address": {"type": "string"}}}


def candidate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusCandidate.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "package_id": {"type": "string"}, "address": {"type": "string"}, "peer_ids": {"type": "array"}, "support_count": {"type": "integer", "minimum": 0}, "expected_peer_count": {"type": "integer", "minimum": 1}, "quorum": {"type": "integer", "minimum": 1}, "selected": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + CANDIDATE_PREFIX + ":"}}}


def package_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusPackage.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "package_id": {"type": "string"}, "expected_peer_count": {"type": "integer", "minimum": 1}, "observed_peer_count": {"type": "integer", "minimum": 0}, "candidate_count": {"type": "integer", "minimum": 0}, "candidates": {"type": "array", "items": candidate_schema()}, "selected_address": {"type": "string"}, "resolution": {"type": "string", "enum": list(RESOLUTIONS)}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string", "pattern": "^" + PACKAGE_PREFIX + ":"}}}


def action_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusAction.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "action_id": {"type": "string"}, "kind": {"type": "string", "enum": list(ACTION_KINDS)}, "package_id": {"type": "string"}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "detail": {"type": "string"}, "peer_ids": {"type": "array"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string", "pattern": "^" + ACTION_PREFIX + ":"}}}


def consensus_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensus.FIELDS), "properties": {"consensus_id": {"type": "string"}, "federation_id": {"type": "string"}, "federation_address": {"type": "string", "pattern": "^" + federation_model.FEDERATION_PREFIX + ":"}, "quorum": {"type": "integer", "minimum": 1}, "packages": {"type": "array", "minItems": 1, "items": package_schema()}, "actions": {"type": "array", "items": action_schema()}, "package_count": {"type": "integer", "minimum": 1}, "resolvable_count": {"type": "integer", "minimum": 0}, "unresolved_count": {"type": "integer", "minimum": 0}, "selected_count": {"type": "integer", "minimum": 0}, "action_count": {"type": "integer", "minimum": 0}, "state": {"type": "string", "enum": list(STATES)}, "decision": {"type": "string", "enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + CONSENSUS_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "consensus_prefix": CONSENSUS_PREFIX, "candidate_prefix": CANDIDATE_PREFIX, "package_prefix": PACKAGE_PREFIX, "action_prefix": ACTION_PREFIX, "files": FILES, "resolutions": RESOLUTIONS, "action_kinds": ACTION_KINDS, "check_ids": CHECK_IDS, "limits": {"max_peers": MAX_PEERS, "max_packages": MAX_PACKAGES, "max_candidates": MAX_CANDIDATES, "max_actions": MAX_ACTIONS}, "features": ("quorum-safe package address candidates", "strict-majority selection", "dissent retention", "missing-peer detection", "explicit inspect, replicate, and hold actions", "four-file atomic persistence", "canonical reload verification", "JSON CSV and Markdown exports"), "schemas": ("manifest", "candidate", "package", "action", "consensus")}


__all__ = ["ACTION_KINDS", "ACTION_PREFIX", "ACTIONS_NAME", "BOUNDARY", "CANDIDATE_PREFIX", "CHECK_IDS", "CONSENSUS_NAME", "CONSENSUS_PREFIX", "DECISIONS", "FILES", "MANIFEST_NAME", "PACKAGE_PREFIX", "PACKAGES_NAME", "RESOLUTIONS", "RegistryFederationConsensus", "RegistryFederationConsensusAction", "RegistryFederationConsensusCandidate", "RegistryFederationConsensusPackage", "SEVERITIES", "STATES", "VERSION", "action_csv", "action_schema", "address_action", "address_candidate", "address_consensus", "address_package", "build_consensus", "candidate_schema", "capabilities", "consensus_from_mapping", "consensus_json", "consensus_schema", "load_consensus", "manifest_schema", "package_bytes", "package_schema", "render_consensus_markdown", "verify_consensus", "verify_consensus_directory", "write_consensus"]
