"""Explainable, evidence-preserving resolution of registry federation rows.

The federation boundary deliberately stops at observation and quorum.  This
module is the next decision boundary: it turns each observation into a
replayable disposition without rewriting any source registry.  A quorum
selection is retained as a resolved row, an incomplete observation becomes a
blocked request for missing evidence, and a non-quorate disagreement remains
an explicit review item.  The public object keeps the candidate and peer
addresses needed to explain the result while excluding filesystem, network,
credential, and runtime-only metadata.

The contract is deterministic for a fixed federation and consensus object.
Every collection is sorted, every object has a content address, and the
aggregate counters are conserved.  Resolution is analysis-only; execution of
the resulting reconciliation plan belongs to a separate, non-mutating plan
boundary.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus as consensus_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-resolution-v1"
BOUNDARY = federation_model.BOUNDARY + "_resolution"
RESOLUTION_PREFIX = federation_model.FEDERATION_PREFIX + "-resolution"
ITEM_PREFIX = RESOLUTION_PREFIX + "-item"
DEFAULT_RESOLUTION_ID = "consensus-certificate-observatory-archive-registry-federation-resolution"
MAX_ITEMS = federation_model.MAX_ENTRIES
MAX_PEERS = federation_model.MAX_PEERS

STATES = ("resolved", "review", "blocked")
ACTIONS = ("retain-consensus", "review-divergence", "request-missing")
RATIONALES = ("quorum-selected", "quorum-unmet-divergence", "quorum-unmet-missing")


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


def _unique_sorted_labels(values: Sequence[str], field: str) -> tuple[str, ...]:
    result = tuple(_label(item, field) for item in _sequence(values, field, MAX_PEERS))
    if len(set(result)) != len(result) or result != tuple(sorted(result)):
        raise ValidationError(f"{field} must be unique and sorted")
    return result


def _unique_sorted_addresses(values: Sequence[str], field: str) -> tuple[str, ...]:
    result = tuple(_address(item, field, federation_model.registry_model.archive_model.ARCHIVE_PREFIX) for item in _sequence(values, field, MAX_PEERS))
    if len(set(result)) != len(result) or result != tuple(sorted(result)):
        raise ValidationError(f"{field} must be unique and sorted")
    return result


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem:
    """One deterministic disposition for one federated entry observation."""

    FIELDS = (
        "ordinal",
        "entry_id",
        "package_id",
        "state",
        "action",
        "selected_archive_address",
        "candidate_addresses",
        "supporting_peer_ids",
        "missing_peer_ids",
        "dissenting_peer_ids",
        "required_quorum",
        "observed_peer_count",
        "presence_count",
        "evidence_addresses",
        "rationale",
        "content_address",
    )

    def __init__(
        self,
        ordinal: int,
        entry_id: str,
        package_id: str,
        state: str,
        action: str,
        selected_archive_address: str,
        candidate_addresses: Sequence[str],
        supporting_peer_ids: Sequence[str],
        missing_peer_ids: Sequence[str],
        dissenting_peer_ids: Sequence[str],
        required_quorum: int,
        observed_peer_count: int,
        presence_count: int,
        evidence_addresses: Sequence[str],
        rationale: str,
        content_address: str,
    ) -> None:
        self.ordinal = _count(ordinal, "resolution item ordinal", MAX_ITEMS, positive=True)
        self.entry_id = _label(entry_id, "resolution item entry ID")
        self.package_id = _label(package_id, "resolution item package ID", required=False)
        self.state = _label(state, "resolution item state")
        self.action = _label(action, "resolution item action")
        self.selected_archive_address = _address(selected_archive_address, "resolution selected archive address", federation_model.registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.candidate_addresses = _unique_sorted_addresses(candidate_addresses, "resolution candidate addresses")
        self.supporting_peer_ids = _unique_sorted_labels(supporting_peer_ids, "resolution supporting peers")
        self.missing_peer_ids = _unique_sorted_labels(missing_peer_ids, "resolution missing peers")
        self.dissenting_peer_ids = _unique_sorted_labels(dissenting_peer_ids, "resolution dissenting peers")
        self.required_quorum = _count(required_quorum, "resolution required quorum", MAX_PEERS, positive=True)
        self.observed_peer_count = _count(observed_peer_count, "resolution observed peer count", MAX_PEERS, positive=True)
        self.presence_count = _count(presence_count, "resolution presence count", self.observed_peer_count)
        self.evidence_addresses = tuple(_text(item, "resolution evidence address", 2048) for item in _sequence(evidence_addresses, "resolution evidence addresses", MAX_PEERS * 2 + 2))
        self.rationale = _label(rationale, "resolution rationale")
        self.content_address = _address(content_address, "resolution item content address", ITEM_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "resolution item content address")
        self._validate()

    def _validate(self) -> None:
        if self.state not in STATES or self.action not in ACTIONS or self.rationale not in RATIONALES:
            raise ValidationError("resolution item vocabulary is unsupported")
        if self.required_quorum > self.observed_peer_count or self.presence_count > self.observed_peer_count:
            raise ValidationError("resolution item peer bounds are invalid")
        peer_sets = set(self.supporting_peer_ids) | set(self.missing_peer_ids) | set(self.dissenting_peer_ids)
        if len(peer_sets) > self.observed_peer_count:
            raise ValidationError("resolution item peer evidence exceeds the observed peer count")
        if not self.evidence_addresses:
            raise ValidationError("resolution item requires evidence addresses")
        if self.state == "resolved":
            if self.action != "retain-consensus" or not self.selected_archive_address or len(self.supporting_peer_ids) < self.required_quorum or self.rationale != "quorum-selected":
                raise ValidationError("resolved item does not retain a quorate selection")
        elif self.state == "blocked":
            if self.action != "request-missing" or self.selected_archive_address or not self.missing_peer_ids or self.rationale != "quorum-unmet-missing":
                raise ValidationError("blocked item does not request missing evidence")
        elif self.action != "review-divergence" or self.selected_archive_address or self.rationale != "quorum-unmet-divergence":
            raise ValidationError("review item does not preserve a non-quorate divergence")
        if self.selected_archive_address and self.selected_archive_address not in self.candidate_addresses:
            raise ValidationError("selected resolution address is absent from candidates")
        if not _public(self.to_dict()):
            raise ValidationError("resolution item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("resolution item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"candidate_addresses", "evidence_addresses"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem":
        value = _mapping(value, "resolution item")
        _strict(value, set(cls.FIELDS), "resolution item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem):
        raise ValidationError("resolution item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution:
    """The conserved, addressed resolution of one federation and quorum run."""

    FIELDS = (
        "resolution_id",
        "version",
        "boundary",
        "federation_id",
        "federation_address",
        "consensus_id",
        "consensus_address",
        "items",
        "peer_count",
        "entry_count",
        "resolved_count",
        "review_count",
        "blocked_count",
        "accepted",
        "release_ready",
        "state",
        "content_address",
    )

    def __init__(
        self,
        resolution_id: str,
        version: str,
        boundary: str,
        federation_id: str,
        federation_address: str,
        consensus_id: str,
        consensus_address: str,
        items: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem],
        peer_count: int,
        entry_count: int,
        resolved_count: int,
        review_count: int,
        blocked_count: int,
        accepted: bool,
        release_ready: bool,
        state: str,
        content_address: str,
    ) -> None:
        self.resolution_id = _label(resolution_id, "federation resolution ID")
        self.version = _text(version, "federation resolution version")
        self.boundary = _text(boundary, "federation resolution boundary", 512)
        self.federation_id = _label(federation_id, "resolution federation ID")
        self.federation_address = _address(federation_address, "resolution federation address", federation_model.FEDERATION_PREFIX)
        self.consensus_id = _label(consensus_id, "resolution consensus ID")
        self.consensus_address = _address(consensus_address, "resolution consensus address", consensus_model.CONSENSUS_PREFIX)
        self.items = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem.from_mapping(item) for item in _sequence(items, "resolution items", MAX_ITEMS))
        self.peer_count = _count(peer_count, "resolution peer count", MAX_PEERS, positive=True)
        self.entry_count = _count(entry_count, "resolution entry count", MAX_ITEMS, positive=True)
        self.resolved_count = _count(resolved_count, "resolution resolved count", self.entry_count)
        self.review_count = _count(review_count, "resolution review count", self.entry_count)
        self.blocked_count = _count(blocked_count, "resolution blocked count", self.entry_count)
        self.accepted = _bool(accepted, "resolution acceptance")
        self.release_ready = _bool(release_ready, "resolution release readiness")
        self.state = _label(state, "resolution state")
        self.content_address = _address(content_address, "resolution content address", RESOLUTION_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "resolution content address")
        self._validate()

    def _validate(self) -> None:
        if self.entry_count != len(self.items) or not self.items:
            raise ValidationError("resolution entry count does not match items")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, self.entry_count + 1)) or tuple(item.entry_id for item in self.items) != tuple(sorted(item.entry_id for item in self.items)) or len({item.entry_id for item in self.items}) != self.entry_count:
            raise ValidationError("resolution items are not canonical")
        if self.resolved_count + self.review_count + self.blocked_count != self.entry_count:
            raise ValidationError("resolution state counts are not conserved")
        if self.resolved_count != sum(item.state == "resolved" for item in self.items) or self.review_count != sum(item.state == "review" for item in self.items) or self.blocked_count != sum(item.state == "blocked" for item in self.items):
            raise ValidationError("resolution state projections do not replay")
        expected_state = "blocked" if self.blocked_count else "review" if self.review_count else "ready"
        if self.state != expected_state or self.accepted != (self.blocked_count == 0) or self.release_ready != (self.state == "ready"):
            raise ValidationError("resolution outcome does not replay")
        if any(item.observed_peer_count != self.peer_count for item in self.items):
            raise ValidationError("resolution item peer links do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("resolution crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_resolution(self) != self.content_address:
            raise ValidationError("resolution address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"resolution_id": self.resolution_id, "version": self.version, "boundary": self.boundary, "federation_id": self.federation_id, "federation_address": self.federation_address, "consensus_id": self.consensus_id, "consensus_address": self.consensus_address, "items": tuple(item.to_dict() for item in self.items), "peer_count": self.peer_count, "entry_count": self.entry_count, "resolved_count": self.resolved_count, "review_count": self.review_count, "blocked_count": self.blocked_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("resolution_id", "version", "boundary", "federation_id", "federation_address", "consensus_id", "consensus_address", "peer_count", "entry_count", "resolved_count", "review_count", "blocked_count", "accepted", "release_ready", "state", "content_address")}

    def item(self, entry_id: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem:
        entry_id = _label(entry_id, "resolution item entry ID")
        for item in self.items:
            if item.entry_id == entry_id:
                return item
        raise ValidationError("resolution item was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution":
        value = _mapping(value, "federation resolution")
        _strict(value, set(cls.FIELDS), "federation resolution")
        items = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem.from_mapping(item) for item in _sequence(value["items"], "resolution items", MAX_ITEMS))
        return cls(value["resolution_id"], value["version"], value["boundary"], value["federation_id"], value["federation_address"], value["consensus_id"], value["consensus_address"], items, value["peer_count"], value["entry_count"], value["resolved_count"], value["review_count"], value["blocked_count"], value["accepted"], value["release_ready"], value["state"], value["content_address"])


def address_resolution(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution):
        raise ValidationError("resolution address requires a typed resolution")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESOLUTION_PREFIX)


def _item_from_evidence(
    ordinal: int,
    observation: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation,
    decision: consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusDecision,
    candidates: Mapping[str, consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate],
) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem:
    candidate_addresses = tuple(sorted(decision.candidate_addresses))
    present_peer_ids = tuple(sorted({peer_id for candidate in candidates.values() for peer_id in candidate.peer_ids}))
    missing_peer_ids = tuple(sorted(set(observation.peer_ids) - set(present_peer_ids)))
    selected_candidates = tuple(candidate for candidate in candidates.values() if candidate.selected)
    selected = selected_candidates[0] if len(selected_candidates) == 1 else None
    supporting = tuple(sorted(selected.peer_ids)) if selected is not None else ()
    dissenting = tuple(sorted(set(present_peer_ids) - set(supporting)))
    if selected is not None:
        state, action, rationale, selected_address = "resolved", "retain-consensus", "quorum-selected", selected.archive_address
    elif missing_peer_ids:
        state, action, rationale, selected_address = "blocked", "request-missing", "quorum-unmet-missing", ""
    else:
        state, action, rationale, selected_address = "review", "review-divergence", "quorum-unmet-divergence", ""
    evidence = (observation.content_address, decision.content_address) + tuple(candidate.content_address for candidate in sorted(candidates.values(), key=lambda item: item.archive_address))
    body = dict(
        ordinal=ordinal,
        entry_id=observation.entry_id,
        package_id=observation.package_id,
        state=state,
        action=action,
        selected_archive_address=selected_address,
        candidate_addresses=candidate_addresses,
        supporting_peer_ids=supporting,
        missing_peer_ids=missing_peer_ids,
        dissenting_peer_ids=dissenting,
        required_quorum=decision.quorum,
        observed_peer_count=observation.peer_count,
        presence_count=observation.presence_count,
        evidence_addresses=evidence,
        rationale=rationale,
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem(**body, content_address=ITEM_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem(**body, content_address=address_item(provisional))


def build_resolution(
    federation: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation,
    *,
    consensus: consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensus | None = None,
    resolution_id: str = DEFAULT_RESOLUTION_ID,
) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution:
    federation = federation_model.verify_federation(federation)
    selected_consensus = consensus_model.build_consensus(federation) if consensus is None else consensus_model.verify_consensus(consensus)
    if selected_consensus.federation_address != federation.content_address or selected_consensus.federation_id != federation.federation_id:
        raise ValidationError("resolution consensus does not link to the federation")
    candidates_by_entry: dict[str, dict[str, consensus_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationConsensusCandidate]] = {}
    for candidate in selected_consensus.candidates:
        candidates_by_entry.setdefault(candidate.entry_id, {})[candidate.archive_address] = candidate
    decisions = {decision.entry_id: decision for decision in selected_consensus.decisions}
    items = tuple(_item_from_evidence(index, observation, decisions[observation.entry_id], candidates_by_entry.get(observation.entry_id, {})) for index, observation in enumerate(federation.observations, 1))
    counts = {state: sum(item.state == state for item in items) for state in STATES}
    body = dict(
        resolution_id=resolution_id,
        version=VERSION,
        boundary=BOUNDARY,
        federation_id=federation.federation_id,
        federation_address=federation.content_address,
        consensus_id=selected_consensus.consensus_id,
        consensus_address=selected_consensus.content_address,
        items=items,
        peer_count=federation.peer_count,
        entry_count=len(items),
        resolved_count=counts["resolved"],
        review_count=counts["review"],
        blocked_count=counts["blocked"],
        accepted=counts["blocked"] == 0,
        release_ready=counts["review"] == 0 and counts["blocked"] == 0,
        state="blocked" if counts["blocked"] else "review" if counts["review"] else "ready",
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution(**body, content_address=RESOLUTION_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution(**body, content_address=address_resolution(provisional))


def resolution_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution:
    return verify_resolution(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution.from_mapping(value))


def verify_resolution(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution):
        raise ValidationError("resolution verification requires a typed resolution")
    value._validate()
    if not value.content_address.endswith(":pending") and address_resolution(value) != value.content_address:
        raise ValidationError("resolution address verification failed")
    return value


def resolution_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution) -> str:
    return canonical_json(verify_resolution(value).to_dict())


def resolution_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution) -> str:
    value = verify_resolution(value)
    fields = ("ordinal", "entry_id", "package_id", "state", "action", "selected_archive_address", "candidate_addresses", "supporting_peer_ids", "missing_peer_ids", "dissenting_peer_ids", "required_quorum", "observed_peer_count", "presence_count", "evidence_addresses", "rationale", "content_address")
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        for field in fields:
            if isinstance(row[field], tuple):
                row[field] = ",".join(row[field])
        writer.writerow(row)
    return stream.getvalue()


def render_resolution_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution) -> str:
    value = verify_resolution(value)
    lines = ["# Archive Registry Federation Resolution", "", f"- State: `{value.state}`", f"- Release ready: `{value.release_ready}`", f"- Resolved: `{value.resolved_count}`", f"- Review: `{value.review_count}`", f"- Blocked: `{value.blocked_count}`", "", "| # | entry | state | action | selected archive | evidence peers |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.entry_id}` | `{item.state}` | `{item.action}` | `{item.selected_archive_address}` | {len(item.supporting_peer_ids)} support / {len(item.missing_peer_ids)} missing / {len(item.dissenting_peer_ids)} dissent |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "state": {"enum": list(STATES)}, "action": {"enum": list(ACTIONS)}, "selected_archive_address": {"type": "string"}, "candidate_addresses": {"type": "array", "items": {"type": "string"}}, "supporting_peer_ids": {"type": "array", "items": {"type": "string"}}, "missing_peer_ids": {"type": "array", "items": {"type": "string"}}, "dissenting_peer_ids": {"type": "array", "items": {"type": "string"}}, "required_quorum": {"type": "integer", "minimum": 1}, "observed_peer_count": {"type": "integer", "minimum": 1}, "presence_count": {"type": "integer", "minimum": 0}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "rationale": {"enum": list(RATIONALES)}, "content_address": {"type": "string"}}}


def resolution_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution.FIELDS), "properties": {"resolution_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "federation_id": {"type": "string"}, "federation_address": {"type": "string"}, "consensus_id": {"type": "string"}, "consensus_address": {"type": "string"}, "items": {"type": "array", "items": item_schema()}, "peer_count": {"type": "integer", "minimum": 1}, "entry_count": {"type": "integer", "minimum": 1}, "resolved_count": {"type": "integer", "minimum": 0}, "review_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": ["ready", "review", "blocked"]}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "analysis_only": True, "operations": ("build_resolution", "resolution_from_mapping", "resolution_json", "resolution_csv", "render_resolution_markdown", "verify_resolution"), "states": STATES, "actions": ACTIONS, "rationales": RATIONALES, "max_items": MAX_ITEMS}


__all__ = ["ACTIONS", "BOUNDARY", "DEFAULT_RESOLUTION_ID", "ITEM_PREFIX", "MAX_ITEMS", "MAX_PEERS", "RATIONALES", "RESOLUTION_PREFIX", "STATES", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem", "address_item", "address_resolution", "build_resolution", "capabilities", "item_schema", "render_resolution_markdown", "resolution_csv", "resolution_from_mapping", "resolution_json", "resolution_schema", "verify_resolution"]
