"""Cross-history observatory projections for federation release receipts."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_history as history_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-observatory-v1"
BOUNDARY = history_model.BOUNDARY + "_observatory"
OBSERVATORY_PREFIX = federation_model.FEDERATION_PREFIX + "-observatory"
OBSERVATION_PREFIX = federation_model.FEDERATION_PREFIX + "-observation"
MAX_OBSERVATIONS = history_model.MAX_ENTRIES * 4
CHECK_IDS = ("exact-fields", "public-boundary", "history-conservation", "observation-conservation", "ordinal-conservation", "counter-conservation", "latest-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field)
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
        return "agent" not in value.lower() and "/" not in value and "\\" not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationObservation:
    FIELDS = ("ordinal", "history_id", "federation_id", "federation_address", "state", "decision", "accepted", "audit_address", "gate_address", "content_address")

    def __init__(self, ordinal: int, history_id: str, federation_id: str, federation_address: str, state: str, decision: str, accepted: bool, audit_address: str, gate_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observation ordinal", MAX_OBSERVATIONS, positive=True)
        self.history_id = _label(history_id, "observation history ID")
        self.federation_id = _label(federation_id, "observation federation ID")
        self.federation_address = _address(federation_address, "observation federation address", federation_model.FEDERATION_PREFIX)
        if state not in federation_model.STATES or decision not in federation_model.DECISIONS:
            raise ValidationError("observation disposition is unsupported")
        self.state = state
        self.decision = decision
        self.accepted = _bool(accepted, "observation acceptance")
        self.audit_address = _address(audit_address, "observation audit address", federation_model.FEDERATION_PREFIX + "-audit")
        self.gate_address = _address(gate_address, "observation gate address", federation_model.FEDERATION_PREFIX + "-gate")
        self.content_address = _address(content_address, "observation content address", OBSERVATION_PREFIX)
        if not self.content_address.endswith(":pending") and address_observation(self) != self.content_address:
            raise ValidationError("observation content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "history_id": self.history_id, "federation_id": self.federation_id, "federation_address": self.federation_address, "state": self.state, "decision": self.decision, "accepted": self.accepted, "audit_address": self.audit_address, "gate_address": self.gate_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationObservation:
        value = _mapping(value, "federation observation")
        _strict(value, set(cls.FIELDS), "federation observation")
        return cls(value["ordinal"], value["history_id"], value["federation_id"], value["federation_address"], value["state"], value["decision"], value["accepted"], value["audit_address"], value["gate_address"], value["content_address"])


def address_observation(value: RegistryFederationObservation) -> str:
    if not isinstance(value, RegistryFederationObservation):
        raise ValidationError("observation address requires a typed observation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATION_PREFIX)


class RegistryFederationObservatory:
    FIELDS = ("observatory_id", "histories", "observations", "history_count", "observation_count", "accepted_count", "rejected_count", "review_count", "latest_federation_address", "content_address")

    def __init__(self, observatory_id: str, histories: Sequence[str], observations: Sequence[RegistryFederationObservation], history_count: int, observation_count: int, accepted_count: int, rejected_count: int, review_count: int, latest_federation_address: str, content_address: str) -> None:
        self.observatory_id = _label(observatory_id, "observatory ID")
        self.histories = tuple(sorted(_label(item, "observatory history ID") for item in histories))
        self.observations = tuple(observations)
        self.history_count = _count(history_count, "observatory history count", history_model.MAX_ENTRIES, positive=True)
        self.observation_count = _count(observation_count, "observatory observation count", MAX_OBSERVATIONS, positive=True)
        self.accepted_count = _count(accepted_count, "observatory accepted count", self.observation_count)
        self.rejected_count = _count(rejected_count, "observatory rejected count", self.observation_count)
        self.review_count = _count(review_count, "observatory review count", self.observation_count)
        self.latest_federation_address = _address(latest_federation_address, "observatory latest address", federation_model.FEDERATION_PREFIX)
        self.content_address = _address(content_address, "observatory content address", OBSERVATORY_PREFIX)
        if len(self.histories) != self.history_count or len(self.observations) != self.observation_count or tuple(item.ordinal for item in self.observations) != tuple(range(1, self.observation_count + 1)) or self.accepted_count != sum(item.accepted for item in self.observations) or self.rejected_count != sum(item.decision == "reject" for item in self.observations) or self.review_count != sum(item.decision == "review" for item in self.observations) or self.observations[-1].federation_address != self.latest_federation_address:
            raise ValidationError("observatory counters or ordering are not conserved")
        if not self.content_address.endswith(":pending") and address_observatory(self) != self.content_address:
            raise ValidationError("observatory content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"observatory_id": self.observatory_id, "histories": self.histories, "observations": tuple(item.to_dict() for item in self.observations), "history_count": self.history_count, "observation_count": self.observation_count, "accepted_count": self.accepted_count, "rejected_count": self.rejected_count, "review_count": self.review_count, "latest_federation_address": self.latest_federation_address, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"histories", "observations"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationObservatory:
        value = _mapping(value, "federation observatory")
        _strict(value, set(cls.FIELDS), "federation observatory")
        histories = tuple(value["histories"]) if isinstance(value["histories"], list) else value["histories"]
        observations = tuple(value["observations"]) if isinstance(value["observations"], list) else value["observations"]
        return cls(value["observatory_id"], histories, tuple(RegistryFederationObservation.from_mapping(item) for item in observations), value["history_count"], value["observation_count"], value["accepted_count"], value["rejected_count"], value["review_count"], value["latest_federation_address"], value["content_address"])


def address_observatory(value: RegistryFederationObservatory) -> str:
    if not isinstance(value, RegistryFederationObservatory):
        raise ValidationError("observatory address requires a typed observatory")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATORY_PREFIX)


def build_observatory(histories: Sequence[history_model.RegistryFederationHistory], *, observatory_id: str = "federation-observatory") -> RegistryFederationObservatory:
    histories = _sequence(histories, "observatory histories", history_model.MAX_ENTRIES)
    if not histories:
        raise ValidationError("observatory requires at least one history")
    typed_histories = tuple(history_model.verify_history(value) for value in histories)
    observations = []
    for history in typed_histories:
        for entry in history.entries:
            provisional = RegistryFederationObservation(len(observations) + 1, history.history_id, entry.federation_id, entry.federation_address, entry.state, entry.decision, entry.accepted, entry.audit_address, entry.gate_address, OBSERVATION_PREFIX + ":pending")
            observations.append(RegistryFederationObservation(provisional.ordinal, provisional.history_id, provisional.federation_id, provisional.federation_address, provisional.state, provisional.decision, provisional.accepted, provisional.audit_address, provisional.gate_address, address_observation(provisional)))
    provisional = RegistryFederationObservatory(observatory_id, tuple(history.history_id for history in typed_histories), tuple(observations), len(typed_histories), len(observations), sum(item.accepted for item in observations), sum(item.decision == "reject" for item in observations), sum(item.decision == "review" for item in observations), observations[-1].federation_address, OBSERVATORY_PREFIX + ":pending")
    return RegistryFederationObservatory(provisional.observatory_id, provisional.histories, provisional.observations, provisional.history_count, provisional.observation_count, provisional.accepted_count, provisional.rejected_count, provisional.review_count, provisional.latest_federation_address, address_observatory(provisional))


def query_observatory(value: RegistryFederationObservatory, *, state: str | None = None, decision: str | None = None, accepted: bool | None = None, offset: int = 0, limit: int = 100) -> tuple[RegistryFederationObservation, ...]:
    value = verify_observatory(value)
    if state is not None and state not in federation_model.STATES or decision is not None and decision not in federation_model.DECISIONS:
        raise ValidationError("observatory query disposition is unsupported")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValidationError("observatory query pagination is invalid")
    matched = tuple(item for item in value.observations if (state is None or item.state == state) and (decision is None or item.decision == decision) and (accepted is None or item.accepted == accepted))
    return matched[offset:offset + limit]


def verify_observatory(value: RegistryFederationObservatory) -> RegistryFederationObservatory:
    if not isinstance(value, RegistryFederationObservatory) or (not value.content_address.endswith(":pending") and address_observatory(value) != value.content_address):
        raise ValidationError("federation observatory is not valid")
    return value


def observatory_json(value: RegistryFederationObservatory) -> str:
    return canonical_json(verify_observatory(value).to_dict())


def observatory_csv(value: RegistryFederationObservatory) -> str:
    value = verify_observatory(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "history_id", "federation_id", "federation_address", "state", "decision", "accepted", "audit_address", "gate_address", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in value.observations:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def observatory_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationObservatory.FIELDS), "properties": {"observatory_id": {"type": "string"}, "histories": {"type": "array"}, "observations": {"type": "array"}, "history_count": {"type": "integer"}, "observation_count": {"type": "integer"}, "accepted_count": {"type": "integer"}, "rejected_count": {"type": "integer"}, "review_count": {"type": "integer"}, "latest_federation_address": {"type": "string"}, "content_address": {"type": "string"}}}


def observation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationObservation.FIELDS), "properties": {"ordinal": {"type": "integer"}, "history_id": {"type": "string"}, "federation_id": {"type": "string"}, "federation_address": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": "boolean"}, "audit_address": {"type": "string"}, "gate_address": {"type": "string"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "observatory_prefix": OBSERVATORY_PREFIX, "observation_prefix": OBSERVATION_PREFIX, "check_ids": CHECK_IDS, "features": ("multi-history federation timeline", "accepted/rejected/review counts", "latest federation pointer", "state and decision filters", "bounded pagination", "JSON and CSV exports"), "schemas": ("observation", "observatory")}


__all__ = ["BOUNDARY", "CHECK_IDS", "MAX_OBSERVATIONS", "OBSERVATION_PREFIX", "OBSERVATORY_PREFIX", "RegistryFederationObservation", "RegistryFederationObservatory", "VERSION", "address_observation", "address_observatory", "build_observatory", "capabilities", "observation_schema", "observatory_csv", "observatory_json", "observatory_schema", "query_observatory", "verify_observatory"]
