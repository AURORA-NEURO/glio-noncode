"""Federate independently downloaded certificate-observatory archive registries.

The registry layer records one bounded downloaded view.  This module records
the comparison of several such views while retaining every peer as evidence.
It deliberately does not choose a winner: a conflict is represented as a
first-class addressed observation and is resolved only by the separate
consensus layer.  Paths, host names, credentials, timestamps, and agent
metadata never enter the public model.

The implementation is intentionally strict at the boundary.  Every object is
bounded, canonical, content addressed, and replayable from its public mapping.
The same input registries in any order produce byte-identical federation JSON.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-federation-v1"
BOUNDARY = registry_model.BOUNDARY + "_federation"
FEDERATION_PREFIX = registry_model.REGISTRY_PREFIX + "-federation"
PEER_PREFIX = FEDERATION_PREFIX + "-peer"
OBSERVATION_PREFIX = FEDERATION_PREFIX + "-observation"

DEFAULT_FEDERATION_ID = "consensus-certificate-observatory-archive-registry-federation"
MAX_PEERS = 32
MAX_ENTRIES = registry_model.MAX_ENTRIES * MAX_PEERS
MAX_TEXT = 1024

STATES = ("consistent", "divergent", "missing")


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value):
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and value and not value.startswith(prefix + ":"):
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
    return registry_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer:
    """The public receipt for one independently observed registry."""

    FIELDS = ("peer_id", "registry_id", "registry_address", "entry_count", "accepted_count", "held_count", "package_count", "content_address")

    def __init__(self, peer_id: str, registry_id: str, registry_address: str, entry_count: int, accepted_count: int, held_count: int, package_count: int, content_address: str) -> None:
        self.peer_id = _label(peer_id, "federation peer ID")
        self.registry_id = _label(registry_id, "federation peer registry ID")
        self.registry_address = _address(registry_address, "federation peer registry address", registry_model.REGISTRY_PREFIX)
        self.entry_count = _count(entry_count, "federation peer entry count", registry_model.MAX_ENTRIES, positive=True)
        self.accepted_count = _count(accepted_count, "federation peer accepted count", self.entry_count)
        self.held_count = _count(held_count, "federation peer held count", self.entry_count)
        self.package_count = _count(package_count, "federation peer package count", self.entry_count, positive=True)
        self.content_address = _address(content_address, "federation peer content address", PEER_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation peer content address")
        self._validate()

    def _validate(self) -> None:
        if self.accepted_count + self.held_count != self.entry_count or self.package_count > self.entry_count:
            raise ValidationError("federation peer counters are not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("federation peer crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_peer(self) != self.content_address:
            raise ValidationError("federation peer address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer":
        value = _mapping(value, "federation peer")
        _strict(value, set(cls.FIELDS), "federation peer")
        return cls(*(value[field] for field in cls.FIELDS))


def address_peer(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer):
        raise ValidationError("peer address requires a typed peer")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PEER_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation:
    """A lossless comparison row for one entry ID across federation peers."""

    FIELDS = ("entry_id", "package_id", "peer_ids", "observed_archive_addresses", "observed_package_addresses", "presence_count", "peer_count", "state", "content_address")

    def __init__(self, entry_id: str, package_id: str, peer_ids: Sequence[str], observed_archive_addresses: Sequence[str], observed_package_addresses: Sequence[str], presence_count: int, peer_count: int, state: str, content_address: str) -> None:
        self.entry_id = _label(entry_id, "federation observation entry ID")
        self.package_id = _label(package_id, "federation observation package ID", required=False)
        self.peer_ids = tuple(_label(item, "federation observation peer ID") for item in _sequence(peer_ids, "federation observation peer IDs", MAX_PEERS))
        self.observed_archive_addresses = tuple(_address(item, "federation observation archive address", registry_model.archive_model.ARCHIVE_PREFIX) for item in _sequence(observed_archive_addresses, "federation observed archive addresses", MAX_PEERS))
        self.observed_package_addresses = tuple(_address(item, "federation observation package address", registry_model.package_model.PACKAGE_PREFIX) for item in _sequence(observed_package_addresses, "federation observed package addresses", MAX_PEERS))
        self.presence_count = _count(presence_count, "federation observation presence count", MAX_PEERS)
        self.peer_count = _count(peer_count, "federation observation peer count", MAX_PEERS, positive=True)
        self.state = _label(state, "federation observation state")
        self.content_address = _address(content_address, "federation observation content address", OBSERVATION_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation observation content address")
        self._validate()

    def _validate(self) -> None:
        if self.state not in STATES:
            raise ValidationError("federation observation state is unsupported")
        if len(self.peer_ids) != self.peer_count or len(set(self.peer_ids)) != self.peer_count or tuple(sorted(self.peer_ids)) != self.peer_ids:
            raise ValidationError("federation observation peers must be unique and sorted")
        if len(self.observed_archive_addresses) != self.presence_count or len(self.observed_package_addresses) != self.presence_count:
            raise ValidationError("federation observation addresses do not match presence")
        if self.presence_count > self.peer_count:
            raise ValidationError("federation observation presence exceeds peers")
        if not self.package_id and self.presence_count:
            raise ValidationError("federation observation package ID is required when present")
        expected = "consistent" if self.presence_count == self.peer_count and len(self.observed_archive_addresses) > 0 and len(set(self.observed_archive_addresses)) == 1 and len(set(self.observed_package_addresses)) == 1 else "missing" if self.presence_count < self.peer_count else "divergent"
        if self.state != expected:
            raise ValidationError("federation observation state does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("federation observation crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_observation(self) != self.content_address:
            raise ValidationError("federation observation address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"observed_archive_addresses", "observed_package_addresses"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation":
        value = _mapping(value, "federation observation")
        _strict(value, set(cls.FIELDS), "federation observation")
        return cls(*(value[field] for field in cls.FIELDS))


def address_observation(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation):
        raise ValidationError("observation address requires a typed observation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATION_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation:
    """A bounded, addressed comparison of registry snapshots."""

    FIELDS = ("federation_id", "version", "boundary", "peers", "observations", "peer_count", "observation_count", "consistent_count", "divergent_count", "missing_count", "conflict_count", "content_address")

    def __init__(self, federation_id: str, version: str, boundary: str, peers: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer], observations: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation], peer_count: int, observation_count: int, consistent_count: int, divergent_count: int, missing_count: int, conflict_count: int, content_address: str) -> None:
        self.federation_id = _label(federation_id, "archive registry federation ID")
        self.version = _text(version, "archive registry federation version")
        self.boundary = _text(boundary, "archive registry federation boundary", 512)
        self.peers = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer.from_mapping(item) for item in _sequence(peers, "archive registry federation peers", MAX_PEERS))
        self.observations = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation.from_mapping(item) for item in _sequence(observations, "archive registry federation observations", MAX_ENTRIES))
        self.peer_count = _count(peer_count, "archive registry federation peer count", MAX_PEERS, positive=True)
        self.observation_count = _count(observation_count, "archive registry federation observation count", MAX_ENTRIES, positive=True)
        self.consistent_count = _count(consistent_count, "archive registry federation consistent count", self.observation_count)
        self.divergent_count = _count(divergent_count, "archive registry federation divergent count", self.observation_count)
        self.missing_count = _count(missing_count, "archive registry federation missing count", self.observation_count)
        self.conflict_count = _count(conflict_count, "archive registry federation conflict count", self.observation_count)
        self.content_address = _address(content_address, "archive registry federation content address", FEDERATION_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "archive registry federation content address")
        self._validate()

    def _validate(self) -> None:
        if self.peer_count != len(self.peers) or not self.peers or len({item.peer_id for item in self.peers}) != self.peer_count or tuple(item.peer_id for item in self.peers) != tuple(sorted(item.peer_id for item in self.peers)):
            raise ValidationError("archive registry federation peers are not canonical")
        if self.observation_count != len(self.observations) or not self.observations or tuple(item.entry_id for item in self.observations) != tuple(sorted(item.entry_id for item in self.observations)) or len({item.entry_id for item in self.observations}) != self.observation_count:
            raise ValidationError("archive registry federation observations are not canonical")
        if self.consistent_count + self.divergent_count + self.missing_count != self.observation_count or self.conflict_count != self.divergent_count + self.missing_count:
            raise ValidationError("archive registry federation counters are not conserved")
        if any(item.peer_count != self.peer_count or not set(item.peer_ids).issubset({peer.peer_id for peer in self.peers}) for item in self.observations):
            raise ValidationError("archive registry federation observation peer links do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("archive registry federation crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_federation(self) != self.content_address:
            raise ValidationError("archive registry federation address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"federation_id": self.federation_id, "version": self.version, "boundary": self.boundary, "peers": tuple(item.to_dict() for item in self.peers), "observations": tuple(item.to_dict() for item in self.observations), "peer_count": self.peer_count, "observation_count": self.observation_count, "consistent_count": self.consistent_count, "divergent_count": self.divergent_count, "missing_count": self.missing_count, "conflict_count": self.conflict_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("federation_id", "version", "boundary", "peer_count", "observation_count", "consistent_count", "divergent_count", "missing_count", "conflict_count", "content_address")}

    def peer(self, peer_id: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer:
        peer_id = _label(peer_id, "federation peer ID")
        for peer in self.peers:
            if peer.peer_id == peer_id:
                return peer
        raise ValidationError("federation peer was not found")

    def observation(self, entry_id: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation:
        entry_id = _label(entry_id, "federation observation entry ID")
        for observation in self.observations:
            if observation.entry_id == entry_id:
                return observation
        raise ValidationError("federation observation was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation":
        value = _mapping(value, "archive registry federation")
        _strict(value, set(cls.FIELDS), "archive registry federation")
        peers = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer.from_mapping(item) for item in _sequence(value["peers"], "archive registry federation peers", MAX_PEERS))
        observations = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation.from_mapping(item) for item in _sequence(value["observations"], "archive registry federation observations", MAX_ENTRIES))
        return cls(value["federation_id"], value["version"], value["boundary"], peers, observations, value["peer_count"], value["observation_count"], value["consistent_count"], value["divergent_count"], value["missing_count"], value["conflict_count"], value["content_address"])


def address_federation(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation):
        raise ValidationError("federation address requires a typed federation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FEDERATION_PREFIX)


def _peer(peer_id: str, value: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer:
    metrics = value.metrics
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer(peer_id, value.registry_id, value.content_address, value.entry_count, metrics.accepted_count, metrics.held_count, metrics.unique_package_count, PEER_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer(provisional.peer_id, provisional.registry_id, provisional.registry_address, provisional.entry_count, provisional.accepted_count, provisional.held_count, provisional.package_count, address_peer(provisional))


def _observation(entry_id: str, peer_rows: Sequence[tuple[str, registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry | None]]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation:
    present = tuple((peer_id, entry) for peer_id, entry in peer_rows if entry is not None)
    package_id = present[0][1].package_id if present else ""
    peer_ids = tuple(peer_id for peer_id, _ in peer_rows)
    archive_addresses = tuple(entry.archive_address for _, entry in present)
    package_addresses = tuple(entry.package_address for _, entry in present)
    state = "consistent" if len(present) == len(peer_rows) and len(set(archive_addresses)) == 1 and len(set(package_addresses)) == 1 else "missing" if len(present) < len(peer_rows) else "divergent"
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation(entry_id, package_id, peer_ids, archive_addresses, package_addresses, len(present), len(peer_rows), state, OBSERVATION_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation(provisional.entry_id, provisional.package_id, provisional.peer_ids, provisional.observed_archive_addresses, provisional.observed_package_addresses, provisional.presence_count, provisional.peer_count, provisional.state, address_observation(provisional))


def build_federation(values: Sequence[registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry], *, peer_ids: Sequence[str] | None = None, federation_id: str = DEFAULT_FEDERATION_ID) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation:
    registries = tuple(registry_model.verify_registry(item) for item in _sequence(values, "federation registries", MAX_PEERS))
    if not registries:
        raise ValidationError("registry federation requires at least one registry")
    selected_peer_ids = _default_peer_ids(registries) if peer_ids is None else tuple(_label(item, "federation peer ID") for item in _sequence(peer_ids, "federation peer IDs", MAX_PEERS))
    if len(selected_peer_ids) != len(registries) or len(set(selected_peer_ids)) != len(selected_peer_ids):
        raise ValidationError("federation peer IDs must match registries and be unique")
    ordered = tuple(sorted(zip(selected_peer_ids, registries), key=lambda item: item[0]))
    peers = tuple(_peer(peer_id, registry) for peer_id, registry in ordered)
    by_entry: dict[str, dict[str, registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry]] = {}
    for peer_id, registry in ordered:
        for entry in registry.entries:
            by_entry.setdefault(entry.entry_id, {})[peer_id] = entry
    observations = tuple(_observation(entry_id, tuple((peer_id, mapping.get(peer_id)) for peer_id, _ in ordered)) for entry_id, mapping in sorted(by_entry.items()))
    counts = {state: sum(item.state == state for item in observations) for state in STATES}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation(federation_id, VERSION, BOUNDARY, peers, observations, len(peers), len(observations), counts["consistent"], counts["divergent"], counts["missing"], counts["divergent"] + counts["missing"], FEDERATION_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation(provisional.federation_id, provisional.version, provisional.boundary, provisional.peers, provisional.observations, provisional.peer_count, provisional.observation_count, provisional.consistent_count, provisional.divergent_count, provisional.missing_count, provisional.conflict_count, address_federation(provisional))


def _default_peer_ids(values: Sequence[registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry]) -> tuple[str, ...]:
    """Derive order-independent peer labels, including deterministic duplicates."""

    positions = sorted(range(len(values)), key=lambda index: (values[index].registry_id, values[index].content_address))
    totals: dict[str, int] = {}
    for index in positions:
        totals[values[index].registry_id] = totals.get(values[index].registry_id, 0) + 1
    seen: dict[str, int] = {}
    result = [""] * len(values)
    for index in positions:
        registry_id = values[index].registry_id
        seen[registry_id] = seen.get(registry_id, 0) + 1
        result[index] = registry_id if totals[registry_id] == 1 else f"{registry_id}-{seen[registry_id]}"
    return tuple(_label(item, "federation peer ID") for item in result)


def federation_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation:
    return verify_federation(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation.from_mapping(value))


def verify_federation(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation):
        raise ValidationError("federation verification requires a typed federation")
    value._validate()
    if not value.content_address.endswith(":pending") and address_federation(value) != value.content_address:
        raise ValidationError("federation address verification failed")
    return value


def federation_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation) -> str:
    return canonical_json(verify_federation(value).to_dict())


def federation_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation) -> str:
    value = verify_federation(value)
    stream = io.StringIO()
    fields = ("entry_id", "package_id", "state", "presence_count", "peer_count", "peer_ids", "observed_archive_addresses", "observed_package_addresses", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.observations:
        row = item.to_dict()
        writer.writerow({field: ",".join(row[field]) if isinstance(row[field], tuple) else row[field] for field in fields})
    return stream.getvalue()


def render_federation_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation) -> str:
    value = verify_federation(value)
    lines = ["# Certificate Observatory Archive Registry Federation", "", f"- Federation: `{value.federation_id}`", f"- Peers: `{value.peer_count}`", f"- Entries compared: `{value.observation_count}`", f"- Consistent: `{value.consistent_count}`", f"- Divergent: `{value.divergent_count}`", f"- Missing: `{value.missing_count}`", f"- Content address: `{value.content_address}`", "", "| entry | package | state | present / peers | evidence addresses |", "| --- | --- | --- | ---: | --- |"]
    lines.extend(f"| `{item.entry_id}` | `{item.package_id}` | `{item.state}` | `{item.presence_count} / {item.peer_count}` | `{', '.join(item.observed_archive_addresses)}` |" for item in value.observations)
    return "\n".join(lines) + "\n"


def peer_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer.FIELDS), "properties": {"peer_id": {"type": "string"}, "registry_id": {"type": "string"}, "registry_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 1}, "accepted_count": {"type": "integer", "minimum": 0}, "held_count": {"type": "integer", "minimum": 0}, "package_count": {"type": "integer", "minimum": 1}, "content_address": {"type": "string"}}}


def observation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation.FIELDS), "properties": {"entry_id": {"type": "string"}, "package_id": {"type": "string"}, "peer_ids": {"type": "array", "items": {"type": "string"}}, "observed_archive_addresses": {"type": "array", "items": {"type": "string"}}, "observed_package_addresses": {"type": "array", "items": {"type": "string"}}, "presence_count": {"type": "integer", "minimum": 0}, "peer_count": {"type": "integer", "minimum": 1}, "state": {"enum": list(STATES)}, "content_address": {"type": "string"}}}


def federation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation.FIELDS), "properties": {"federation_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "peers": {"type": "array", "items": peer_schema()}, "observations": {"type": "array", "items": observation_schema()}, "peer_count": {"type": "integer", "minimum": 1}, "observation_count": {"type": "integer", "minimum": 1}, "consistent_count": {"type": "integer", "minimum": 0}, "divergent_count": {"type": "integer", "minimum": 0}, "missing_count": {"type": "integer", "minimum": 0}, "conflict_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "operations": ("build_federation", "federation_from_mapping", "federation_json", "federation_csv", "render_federation_markdown", "verify_federation"), "states": STATES, "limits": {"max_peers": MAX_PEERS, "max_entries_per_peer": registry_model.MAX_ENTRIES}}


__all__ = ["BOUNDARY", "DEFAULT_FEDERATION_ID", "FEDERATION_PREFIX", "MAX_ENTRIES", "MAX_PEERS", "OBSERVATION_PREFIX", "PEER_PREFIX", "STATES", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationPeer", "address_federation", "address_observation", "address_peer", "build_federation", "capabilities", "federation_csv", "federation_from_mapping", "federation_json", "federation_schema", "observation_schema", "peer_schema", "render_federation_markdown", "verify_federation"]
