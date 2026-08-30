"""Quorum decisions for archive-registry federation observations."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-consensus-v1"
BOUNDARY = federation_model.BOUNDARY + "_consensus"
CONSENSUS_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus"
CANDIDATE_PREFIX = CONSENSUS_PREFIX + "-candidate"
DECISION_PREFIX = CONSENSUS_PREFIX + "-decision"
DEFAULT_CONSENSUS_ID = "consensus-certificate-observatory-archive-registry-federation-consensus"
MAX_DECISIONS = federation_model.MAX_ENTRIES
STATES = ("selected", "held")
DECISIONS = ("accept", "hold")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
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
    return federation_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate:
    FIELDS = ("ordinal", "entry_id", "package_id", "archive_address", "peer_ids", "support_count", "expected_peer_count", "quorum", "selected", "content_address")

    def __init__(self, ordinal: int, entry_id: str, package_id: str, archive_address: str, peer_ids: Sequence[str], support_count: int, expected_peer_count: int, quorum: int, selected: bool, content_address: str) -> None:
        self.ordinal = _count(ordinal, "consensus candidate ordinal", MAX_DECISIONS * federation_model.MAX_PEERS, positive=True)
        self.entry_id = _label(entry_id, "consensus candidate entry ID")
        self.package_id = _label(package_id, "consensus candidate package ID", required=False)
        self.archive_address = _address(archive_address, "consensus candidate archive address", federation_model.registry_model.archive_model.ARCHIVE_PREFIX)
        self.peer_ids = tuple(_label(item, "consensus candidate peer ID") for item in _sequence(peer_ids, "consensus candidate peers", federation_model.MAX_PEERS))
        self.support_count = _count(support_count, "consensus candidate support count", federation_model.MAX_PEERS)
        self.expected_peer_count = _count(expected_peer_count, "consensus candidate expected peer count", federation_model.MAX_PEERS, positive=True)
        self.quorum = _count(quorum, "consensus candidate quorum", self.expected_peer_count, positive=True)
        self.selected = _bool(selected, "consensus candidate selection")
        self.content_address = _address(content_address, "consensus candidate address", CANDIDATE_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "consensus candidate address")
        self._validate()

    def _validate(self) -> None:
        if len(self.peer_ids) != self.support_count or len(set(self.peer_ids)) != self.support_count or tuple(sorted(self.peer_ids)) != self.peer_ids or self.support_count > self.expected_peer_count or self.selected != (self.support_count >= self.quorum):
            raise ValidationError("consensus candidate support is not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("consensus candidate crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_candidate(self) != self.content_address:
            raise ValidationError("consensus candidate address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate":
        value = _mapping(value, "consensus candidate")
        _strict(value, set(cls.FIELDS), "consensus candidate")
        return cls(*(value[field] for field in cls.FIELDS))


def address_candidate(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CANDIDATE_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision:
    FIELDS = ("ordinal", "entry_id", "package_id", "state", "candidate_count", "selected_address", "support_count", "expected_peer_count", "quorum", "dissent_count", "candidate_addresses", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, entry_id: str, package_id: str, state: str, candidate_count: int, selected_address: str, support_count: int, expected_peer_count: int, quorum: int, dissent_count: int, candidate_addresses: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "consensus decision ordinal", MAX_DECISIONS, positive=True)
        self.entry_id = _label(entry_id, "consensus decision entry ID")
        self.package_id = _label(package_id, "consensus decision package ID", required=False)
        self.state = _label(state, "consensus decision state")
        self.candidate_count = _count(candidate_count, "consensus decision candidate count", federation_model.MAX_PEERS)
        self.selected_address = _address(selected_address, "consensus selected address", federation_model.registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.support_count = _count(support_count, "consensus decision support count", expected_peer_count)
        self.expected_peer_count = _count(expected_peer_count, "consensus decision expected peer count", federation_model.MAX_PEERS, positive=True)
        self.quorum = _count(quorum, "consensus decision quorum", self.expected_peer_count, positive=True)
        self.dissent_count = _count(dissent_count, "consensus decision dissent count", federation_model.MAX_PEERS)
        self.candidate_addresses = tuple(_address(item, "consensus candidate address", federation_model.registry_model.archive_model.ARCHIVE_PREFIX) for item in _sequence(candidate_addresses, "consensus candidate addresses", federation_model.MAX_PEERS))
        self.evidence_addresses = tuple(_text(item, "consensus decision evidence address", 2048) for item in _sequence(evidence_addresses, "consensus decision evidence", federation_model.MAX_PEERS + 1))
        self.content_address = _address(content_address, "consensus decision address", DECISION_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "consensus decision address")
        self._validate()

    def _validate(self) -> None:
        if self.state not in STATES or self.candidate_count != len(self.candidate_addresses) or self.support_count > self.expected_peer_count or self.dissent_count > self.expected_peer_count or not self.evidence_addresses:
            raise ValidationError("consensus decision is not conserved")
        if self.state == "selected" and (not self.selected_address or self.support_count < self.quorum):
            raise ValidationError("selected consensus decision lacks quorum")
        if self.state == "held" and self.selected_address:
            raise ValidationError("held consensus decision cannot expose a selected address")
        if not _public(self.to_dict()):
            raise ValidationError("consensus decision crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_decision(self) != self.content_address:
            raise ValidationError("consensus decision address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision":
        value = _mapping(value, "consensus decision")
        _strict(value, set(cls.FIELDS), "consensus decision")
        return cls(*(value[field] for field in cls.FIELDS))


def address_decision(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DECISION_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus:
    FIELDS = ("consensus_id", "federation_id", "federation_address", "quorum", "candidates", "decisions", "peer_count", "entry_count", "selected_count", "held_count", "accepted", "state", "decision", "content_address")

    def __init__(self, consensus_id: str, federation_id: str, federation_address: str, quorum: int, candidates: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate], decisions: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision], peer_count: int, entry_count: int, selected_count: int, held_count: int, accepted: bool, state: str, decision: str, content_address: str) -> None:
        self.consensus_id = _label(consensus_id, "federation consensus ID")
        self.federation_id = _label(federation_id, "federation consensus federation ID")
        self.federation_address = _address(federation_address, "federation consensus federation address", federation_model.FEDERATION_PREFIX)
        self.quorum = _count(quorum, "federation consensus quorum", federation_model.MAX_PEERS, positive=True)
        self.candidates = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate.from_mapping(item) for item in _sequence(candidates, "federation consensus candidates", MAX_DECISIONS * federation_model.MAX_PEERS))
        self.decisions = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision.from_mapping(item) for item in _sequence(decisions, "federation consensus decisions", MAX_DECISIONS))
        self.peer_count = _count(peer_count, "federation consensus peer count", federation_model.MAX_PEERS, positive=True)
        self.entry_count = _count(entry_count, "federation consensus entry count", MAX_DECISIONS, positive=True)
        self.selected_count = _count(selected_count, "federation consensus selected count", self.entry_count)
        self.held_count = _count(held_count, "federation consensus held count", self.entry_count)
        self.accepted = _bool(accepted, "federation consensus acceptance")
        self.state = _label(state, "federation consensus state")
        self.decision = _label(decision, "federation consensus decision")
        self.content_address = _address(content_address, "federation consensus address", CONSENSUS_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation consensus address")
        self._validate()

    def _validate(self) -> None:
        if self.quorum > self.peer_count or self.entry_count != len(self.decisions) or self.selected_count + self.held_count != self.entry_count or self.selected_count != sum(item.state == "selected" for item in self.decisions) or self.held_count != sum(item.state == "held" for item in self.decisions):
            raise ValidationError("federation consensus counters are not conserved")
        if tuple(item.ordinal for item in self.decisions) != tuple(range(1, self.entry_count + 1)) or tuple(item.entry_id for item in self.decisions) != tuple(sorted(item.entry_id for item in self.decisions)):
            raise ValidationError("federation consensus decisions are not canonical")
        if self.accepted != (self.held_count == 0) or self.state != ("ready" if self.accepted else "blocked") or self.decision != ("accept" if self.accepted else "hold"):
            raise ValidationError("federation consensus outcome does not replay")
        if any(item.expected_peer_count != self.peer_count or item.quorum != self.quorum for item in self.decisions):
            raise ValidationError("federation consensus decision peer links do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("federation consensus crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_consensus(self) != self.content_address:
            raise ValidationError("federation consensus address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"consensus_id": self.consensus_id, "federation_id": self.federation_id, "federation_address": self.federation_address, "quorum": self.quorum, "candidates": tuple(item.to_dict() for item in self.candidates), "decisions": tuple(item.to_dict() for item in self.decisions), "peer_count": self.peer_count, "entry_count": self.entry_count, "selected_count": self.selected_count, "held_count": self.held_count, "accepted": self.accepted, "state": self.state, "decision": self.decision, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("consensus_id", "federation_id", "federation_address", "quorum", "peer_count", "entry_count", "selected_count", "held_count", "accepted", "state", "decision", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus":
        value = _mapping(value, "federation consensus")
        _strict(value, set(cls.FIELDS), "federation consensus")
        candidates = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate.from_mapping(item) for item in _sequence(value["candidates"], "federation consensus candidates", MAX_DECISIONS * federation_model.MAX_PEERS))
        decisions = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision.from_mapping(item) for item in _sequence(value["decisions"], "federation consensus decisions", MAX_DECISIONS))
        return cls(value["consensus_id"], value["federation_id"], value["federation_address"], value["quorum"], candidates, decisions, value["peer_count"], value["entry_count"], value["selected_count"], value["held_count"], value["accepted"], value["state"], value["decision"], value["content_address"])


def address_consensus(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CONSENSUS_PREFIX)


def _candidate_rows(observation: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation, quorum: int) -> tuple[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate, ...]:
    peer_by_address: dict[str, list[str]] = defaultdict(list)
    for peer_id, archive_address in zip(observation.peer_ids, observation.observed_archive_addresses):
        peer_by_address[archive_address].append(peer_id)
    candidates = []
    for ordinal, archive_address in enumerate(sorted(peer_by_address), 1):
        peer_ids = tuple(sorted(peer_by_address[archive_address]))
        provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate(ordinal, observation.entry_id, observation.package_id, archive_address, peer_ids, len(peer_ids), observation.peer_count, quorum, len(peer_ids) >= quorum, CANDIDATE_PREFIX + ":pending")
        candidates.append(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate(provisional.ordinal, provisional.entry_id, provisional.package_id, provisional.archive_address, provisional.peer_ids, provisional.support_count, provisional.expected_peer_count, provisional.quorum, provisional.selected, address_candidate(provisional)))
    return tuple(candidates)


def _decision(ordinal: int, observation: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation, candidates: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate], quorum: int) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision:
    selected = tuple(item for item in candidates if item.selected)
    selected_address = selected[0].archive_address if len(selected) == 1 else ""
    support = selected[0].support_count if len(selected) == 1 else 0
    state = "selected" if selected_address else "held"
    dissent = observation.presence_count - support
    evidence = (observation.content_address,) + tuple(item.content_address for item in candidates)
    body = {"ordinal": ordinal, "entry_id": observation.entry_id, "package_id": observation.package_id, "state": state, "candidate_count": len(candidates), "selected_address": selected_address, "support_count": support, "expected_peer_count": observation.peer_count, "quorum": quorum, "dissent_count": dissent, "candidate_addresses": tuple(item.archive_address for item in candidates), "evidence_addresses": evidence}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision(**body, content_address=DECISION_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision(**body, content_address=address_decision(provisional))


def build_consensus(value: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation, *, consensus_id: str = DEFAULT_CONSENSUS_ID, quorum: int | None = None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus:
    value = federation_model.verify_federation(value)
    selected_quorum = max(1, value.peer_count // 2 + 1) if quorum is None else _count(quorum, "federation consensus quorum", value.peer_count, positive=True)
    candidates = tuple(candidate for observation in value.observations for candidate in _candidate_rows(observation, selected_quorum))
    decisions = tuple(_decision(index, observation, _candidate_rows(observation, selected_quorum), selected_quorum) for index, observation in enumerate(value.observations, 1))
    accepted = all(item.state == "selected" for item in decisions)
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus(consensus_id, value.federation_id, value.content_address, selected_quorum, candidates, decisions, value.peer_count, len(decisions), sum(item.state == "selected" for item in decisions), sum(item.state == "held" for item in decisions), accepted, "ready" if accepted else "blocked", "accept" if accepted else "hold", CONSENSUS_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus(provisional.consensus_id, provisional.federation_id, provisional.federation_address, provisional.quorum, provisional.candidates, provisional.decisions, provisional.peer_count, provisional.entry_count, provisional.selected_count, provisional.held_count, provisional.accepted, provisional.state, provisional.decision, address_consensus(provisional))


def consensus_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus:
    return verify_consensus(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus.from_mapping(value))


def verify_consensus(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus):
        raise ValidationError("federation consensus verification requires a typed consensus")
    value._validate()
    if not value.content_address.endswith(":pending") and address_consensus(value) != value.content_address:
        raise ValidationError("federation consensus address verification failed")
    return value


def consensus_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus) -> str:
    return canonical_json(verify_consensus(value).to_dict())


def consensus_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus) -> str:
    value = verify_consensus(value)
    stream = io.StringIO()
    fields = ("ordinal", "entry_id", "package_id", "state", "candidate_count", "selected_address", "support_count", "expected_peer_count", "quorum", "dissent_count", "candidate_addresses", "evidence_addresses", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.decisions:
        row = item.to_dict()
        row["candidate_addresses"] = ",".join(row["candidate_addresses"])
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_consensus_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus) -> str:
    value = verify_consensus(value)
    lines = ["# Archive Registry Federation Consensus", "", f"- Decision: `{value.decision}`", f"- Quorum: `{value.quorum}/{value.peer_count}`", f"- Selected: `{value.selected_count}`", f"- Held: `{value.held_count}`", "", "| # | entry | state | selected archive | support / quorum |", "| ---: | --- | --- | --- | ---: |"]
    lines.extend(f"| {item.ordinal} | `{item.entry_id}` | `{item.state}` | `{item.selected_address}` | `{item.support_count} / {item.quorum}` |" for item in value.decisions)
    return "\n".join(lines) + "\n"


def candidate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "archive_address": {"type": "string"}, "peer_ids": {"type": "array", "items": {"type": "string"}}, "support_count": {"type": "integer", "minimum": 0}, "expected_peer_count": {"type": "integer", "minimum": 1}, "quorum": {"type": "integer", "minimum": 1}, "selected": {"type": "boolean"}, "content_address": {"type": "string"}}}


def decision_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "state": {"enum": list(STATES)}, "candidate_count": {"type": "integer", "minimum": 0}, "selected_address": {"type": "string"}, "support_count": {"type": "integer", "minimum": 0}, "expected_peer_count": {"type": "integer", "minimum": 1}, "quorum": {"type": "integer", "minimum": 1}, "dissent_count": {"type": "integer", "minimum": 0}, "candidate_addresses": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def consensus_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus.FIELDS), "properties": {"consensus_id": {"type": "string"}, "federation_id": {"type": "string"}, "federation_address": {"type": "string"}, "quorum": {"type": "integer", "minimum": 1}, "candidates": {"type": "array", "items": candidate_schema()}, "decisions": {"type": "array", "items": decision_schema()}, "peer_count": {"type": "integer", "minimum": 1}, "entry_count": {"type": "integer", "minimum": 1}, "selected_count": {"type": "integer", "minimum": 0}, "held_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "state": {"enum": ["ready", "blocked"]}, "decision": {"enum": list(DECISIONS)}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "operations": ("build_consensus", "consensus_from_mapping", "consensus_json", "consensus_csv", "render_consensus_markdown", "verify_consensus"), "states": STATES, "decisions": DECISIONS, "max_entries": MAX_DECISIONS}


__all__ = ["BOUNDARY", "CANDIDATE_PREFIX", "CONSENSUS_PREFIX", "DECISION_PREFIX", "DEFAULT_CONSENSUS_ID", "DECISIONS", "STATES", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision", "address_candidate", "address_consensus", "address_decision", "build_consensus", "candidate_schema", "capabilities", "consensus_csv", "consensus_from_mapping", "consensus_json", "consensus_schema", "decision_schema", "render_consensus_markdown", "verify_consensus"]
