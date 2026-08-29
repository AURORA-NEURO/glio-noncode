"""Cross-history observatory for consensus health over time."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_history as history_model
from . import registry_federation_consensus as consensus_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-observatory-v1"
BOUNDARY = history_model.BOUNDARY + "_observatory"
OBSERVATORY_PREFIX = registry_model.REGISTRY_PREFIX + "-consensus-observatory"
OBSERVATION_PREFIX = registry_model.REGISTRY_PREFIX + "-consensus-observation"
MAX_HISTORIES = 16
MAX_OBSERVATIONS = history_model.MAX_ENTRIES * MAX_HISTORIES
CHECK_IDS = ("exact-fields", "public-boundary", "history-conservation", "observation-conservation", "ordinal-conservation", "counter-conservation", "latest-conservation", "address-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 512, *, required: bool = False) -> str:
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


class RegistryFederationConsensusObservation:
    FIELDS = ("ordinal", "history_id", "consensus_id", "consensus_address", "federation_id", "state", "decision", "accepted", "selected_count", "action_count", "audit_address", "content_address")

    def __init__(self, ordinal: int, history_id: str, consensus_id: str, consensus_address: str, federation_id: str, state: str, decision: str, accepted: bool, selected_count: int, action_count: int, audit_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observation ordinal", MAX_OBSERVATIONS, positive=True)
        self.history_id = _label(history_id, "observation history ID")
        self.consensus_id = _label(consensus_id, "observation consensus ID")
        self.consensus_address = _address(consensus_address, "observation consensus address", consensus_model.CONSENSUS_PREFIX)
        self.federation_id = _label(federation_id, "observation federation ID")
        if state not in consensus_model.STATES or decision not in consensus_model.DECISIONS:
            raise ValidationError("observation disposition is unsupported")
        self.state, self.decision = state, decision
        self.accepted = _bool(accepted, "observation acceptance")
        self.selected_count = _count(selected_count, "observation selected count", consensus_model.MAX_PACKAGES)
        self.action_count = _count(action_count, "observation action count", consensus_model.MAX_ACTIONS)
        self.audit_address = _address(audit_address, "observation audit address", history_model.audit_model.AUDIT_PREFIX)
        self.content_address = _address(content_address, "observation content address", OBSERVATION_PREFIX)
        if not self.content_address.endswith(":pending") and address_observation(self) != self.content_address:
            raise ValidationError("observation content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "history_id": self.history_id, "consensus_id": self.consensus_id, "consensus_address": self.consensus_address, "federation_id": self.federation_id, "state": self.state, "decision": self.decision, "accepted": self.accepted, "selected_count": self.selected_count, "action_count": self.action_count, "audit_address": self.audit_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusObservation:
        value = _mapping(value, "consensus observation")
        _strict(value, set(cls.FIELDS), "consensus observation")
        return cls(value["ordinal"], value["history_id"], value["consensus_id"], value["consensus_address"], value["federation_id"], value["state"], value["decision"], value["accepted"], value["selected_count"], value["action_count"], value["audit_address"], value["content_address"])


def address_observation(value: RegistryFederationConsensusObservation) -> str:
    if not isinstance(value, RegistryFederationConsensusObservation):
        raise ValidationError("observation address requires a typed observation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATION_PREFIX)


class RegistryFederationConsensusObservatory:
    FIELDS = ("observatory_id", "histories", "observations", "history_count", "observation_count", "accepted_count", "rejected_count", "review_count", "latest_consensus_address", "content_address")

    def __init__(self, observatory_id: str, histories: Sequence[str], observations: Sequence[RegistryFederationConsensusObservation], history_count: int, observation_count: int, accepted_count: int, rejected_count: int, review_count: int, latest_consensus_address: str, content_address: str) -> None:
        self.observatory_id = _label(observatory_id, "observatory ID")
        self.histories = tuple(sorted(_label(item, "observatory history ID") for item in histories))
        self.observations = tuple(observations)
        self.history_count = _count(history_count, "observatory history count", MAX_HISTORIES, positive=True)
        self.observation_count = _count(observation_count, "observatory observation count", MAX_OBSERVATIONS, positive=True)
        self.accepted_count = _count(accepted_count, "observatory accepted count", self.observation_count)
        self.rejected_count = _count(rejected_count, "observatory rejected count", self.observation_count)
        self.review_count = _count(review_count, "observatory review count", self.observation_count)
        self.latest_consensus_address = _address(latest_consensus_address, "observatory latest consensus address", consensus_model.CONSENSUS_PREFIX)
        self.content_address = _address(content_address, "observatory content address", OBSERVATORY_PREFIX)
        if len(self.histories) != self.history_count or len(self.observations) != self.observation_count or tuple(item.ordinal for item in self.observations) != tuple(range(1, self.observation_count + 1)) or self.accepted_count != sum(item.accepted for item in self.observations) or self.rejected_count != sum(item.decision == "reject" for item in self.observations) or self.review_count != sum(item.decision == "review" for item in self.observations) or self.observations[-1].consensus_address != self.latest_consensus_address:
            raise ValidationError("observatory counters or ordering are not conserved")
        if not self.content_address.endswith(":pending") and address_observatory(self) != self.content_address:
            raise ValidationError("observatory content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"observatory_id": self.observatory_id, "histories": self.histories, "observations": tuple(item.to_dict() for item in self.observations), "history_count": self.history_count, "observation_count": self.observation_count, "accepted_count": self.accepted_count, "rejected_count": self.rejected_count, "review_count": self.review_count, "latest_consensus_address": self.latest_consensus_address, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"histories", "observations"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusObservatory:
        value = _mapping(value, "consensus observatory")
        _strict(value, set(cls.FIELDS), "consensus observatory")
        return cls(value["observatory_id"], value["histories"], tuple(RegistryFederationConsensusObservation.from_mapping(item) for item in value["observations"]), value["history_count"], value["observation_count"], value["accepted_count"], value["rejected_count"], value["review_count"], value["latest_consensus_address"], value["content_address"])


def address_observatory(value: RegistryFederationConsensusObservatory) -> str:
    if not isinstance(value, RegistryFederationConsensusObservatory):
        raise ValidationError("observatory address requires a typed observatory")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATORY_PREFIX)


def build_observatory(histories: Sequence[history_model.RegistryFederationConsensusHistory], *, observatory_id: str = "consensus-observatory") -> RegistryFederationConsensusObservatory:
    histories = _sequence(histories, "observatory histories", MAX_HISTORIES)
    if not histories:
        raise ValidationError("observatory requires at least one history")
    typed = tuple(history_model.verify_history(item) for item in histories)
    observations: list[RegistryFederationConsensusObservation] = []
    for history in typed:
        for entry in history.entries:
            provisional = RegistryFederationConsensusObservation(len(observations) + 1, history.history_id, entry.consensus_id, entry.consensus_address, entry.federation_id, entry.state, entry.decision, entry.accepted, entry.selected_count, entry.action_count, entry.audit_address, OBSERVATION_PREFIX + ":pending")
            observations.append(RegistryFederationConsensusObservation(provisional.ordinal, provisional.history_id, provisional.consensus_id, provisional.consensus_address, provisional.federation_id, provisional.state, provisional.decision, provisional.accepted, provisional.selected_count, provisional.action_count, provisional.audit_address, address_observation(provisional)))
    provisional = RegistryFederationConsensusObservatory(observatory_id, tuple(history.history_id for history in typed), tuple(observations), len(typed), len(observations), sum(item.accepted for item in observations), sum(item.decision == "reject" for item in observations), sum(item.decision == "review" for item in observations), observations[-1].consensus_address, OBSERVATORY_PREFIX + ":pending")
    return RegistryFederationConsensusObservatory(provisional.observatory_id, provisional.histories, provisional.observations, provisional.history_count, provisional.observation_count, provisional.accepted_count, provisional.rejected_count, provisional.review_count, provisional.latest_consensus_address, address_observatory(provisional))


def observatory_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusObservatory:
    return verify_observatory(RegistryFederationConsensusObservatory.from_mapping(value))


def verify_observatory(value: RegistryFederationConsensusObservatory) -> RegistryFederationConsensusObservatory:
    if not isinstance(value, RegistryFederationConsensusObservatory) or (not value.content_address.endswith(":pending") and address_observatory(value) != value.content_address):
        raise ValidationError("consensus observatory is not valid")
    return value


def query_observatory(value: RegistryFederationConsensusObservatory, *, state: str = "", decision: str = "", accepted: bool | None = None, offset: int = 0, limit: int = 100) -> tuple[RegistryFederationConsensusObservation, ...]:
    value = verify_observatory(value)
    if state and state not in consensus_model.STATES or decision and decision not in consensus_model.DECISIONS:
        raise ValidationError("observatory query disposition is unsupported")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValidationError("observatory query pagination is invalid")
    matched = tuple(item for item in value.observations if (not state or item.state == state) and (not decision or item.decision == decision) and (accepted is None or item.accepted == accepted))
    return matched[offset:offset + limit]


def observatory_json(value: RegistryFederationConsensusObservatory) -> str:
    return canonical_json(verify_observatory(value).to_dict())


def observatory_csv(value: RegistryFederationConsensusObservatory) -> str:
    value = verify_observatory(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusObservation.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.observations:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_observatory_markdown(value: RegistryFederationConsensusObservatory) -> str:
    value = verify_observatory(value)
    lines = ["# Consensus Observatory", "", f"- Observatory: `{value.observatory_id}`", f"- Histories: `{value.history_count}`", f"- Observations: `{value.observation_count}`", f"- Accepted: `{value.accepted_count}`", f"- Rejected: `{value.rejected_count}`", f"- Review: `{value.review_count}`", "", "| ordinal | history | consensus | state | decision | accepted | actions |", "| ---: | --- | --- | --- | --- | --- | ---: |"]
    lines.extend(f"| {item.ordinal} | `{item.history_id}` | `{item.consensus_id}` | `{item.state}` | `{item.decision}` | `{item.accepted}` | {item.action_count} |" for item in value.observations)
    return "\n".join(lines) + "\n"


def observation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusObservation.FIELDS), "properties": {"ordinal": {"type": "integer"}, "history_id": {"type": "string"}, "consensus_id": {"type": "string"}, "consensus_address": {"type": "string"}, "federation_id": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": "boolean"}, "selected_count": {"type": "integer"}, "action_count": {"type": "integer"}, "audit_address": {"type": "string"}, "content_address": {"type": "string"}}}


def observatory_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusObservatory.FIELDS), "properties": {"observatory_id": {"type": "string"}, "histories": {"type": "array"}, "observations": {"type": "array", "items": observation_schema()}, "history_count": {"type": "integer"}, "observation_count": {"type": "integer"}, "accepted_count": {"type": "integer"}, "rejected_count": {"type": "integer"}, "review_count": {"type": "integer"}, "latest_consensus_address": {"type": "string"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "observatory_prefix": OBSERVATORY_PREFIX, "observation_prefix": OBSERVATION_PREFIX, "check_ids": CHECK_IDS, "features": ("multi-history consensus timeline", "accepted rejected and review counts", "latest consensus pointer", "state decision and acceptance filters", "bounded pagination", "JSON CSV and Markdown exports"), "schemas": ("observation", "observatory")}


__all__ = ["BOUNDARY", "CHECK_IDS", "MAX_OBSERVATIONS", "OBSERVATION_PREFIX", "OBSERVATORY_PREFIX", "RegistryFederationConsensusObservation", "RegistryFederationConsensusObservatory", "VERSION", "address_observation", "address_observatory", "build_observatory", "capabilities", "observation_schema", "observatory_csv", "observatory_from_mapping", "observatory_json", "observatory_schema", "query_observatory", "render_observatory_markdown", "verify_observatory"]
