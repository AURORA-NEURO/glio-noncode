"""Cross-history observatory and bounded queries for consensus gates."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from . import registry_federation_consensus_gate_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-observatory-v1"
BOUNDARY = history_model.BOUNDARY + "_observatory"
OBSERVATORY_PREFIX = gate_model.GATE_PREFIX + "-observatory"
OBSERVATION_PREFIX = gate_model.GATE_PREFIX + "-observation"
QUERY_PREFIX = gate_model.GATE_PREFIX + "-observatory-query"
ROW_PREFIX = gate_model.GATE_PREFIX + "-observatory-query-row"
RESULT_PREFIX = gate_model.GATE_PREFIX + "-observatory-query-result"
MAX_TEXT = gate_model.MAX_TEXT
MAX_HISTORIES = 64
MAX_OBSERVATIONS = history_model.MAX_ENTRIES * MAX_HISTORIES
MAX_ROWS = MAX_OBSERVATIONS
STATES = gate_model.GATE_STATES
DECISIONS = gate_model.GATE_DECISIONS


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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


def _optional_bool(value: Any, field: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean or null")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    items = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(set(items)) != len(items):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(items))


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


class RegistryFederationConsensusGateObservation:
    FIELDS = ("ordinal", "history_id", "history_address", "entry_ordinal", "gate_id", "gate_address", "state", "decision", "accepted", "failed_count", "content_address")

    def __init__(self, ordinal: int, history_id: str, history_address: str, entry_ordinal: int, gate_id: str, gate_address: str, state: str, decision: str, accepted: bool, failed_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory observation ordinal", MAX_OBSERVATIONS, positive=True)
        self.history_id = _label(history_id, "observation history ID")
        self.history_address = _address(history_address, "observation history address", history_model.HISTORY_PREFIX)
        self.entry_ordinal = _count(entry_ordinal, "observation entry ordinal", history_model.MAX_ENTRIES, positive=True)
        self.gate_id = _label(gate_id, "observation gate ID")
        self.gate_address = _address(gate_address, "observation gate address", gate_model.GATE_PREFIX)
        if state not in STATES or decision not in DECISIONS:
            raise ValidationError("observation disposition is unsupported")
        self.state, self.decision = state, decision
        self.accepted = _bool(accepted, "observation acceptance")
        self.failed_count = _count(failed_count, "observation failed count", gate_model.MAX_CHECKS)
        self.content_address = _address(content_address, "observation content address", OBSERVATION_PREFIX)
        if not self.content_address.endswith(":pending") and address_observation(self) != self.content_address:
            raise ValidationError("observation content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateObservation:
        value = _mapping(value, "gate observation")
        _strict(value, set(cls.FIELDS), "gate observation")
        return cls(*(value[field] for field in cls.FIELDS))


def address_observation(value: RegistryFederationConsensusGateObservation) -> str:
    if not isinstance(value, RegistryFederationConsensusGateObservation):
        raise ValidationError("observation address requires a typed observation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATION_PREFIX)


class RegistryFederationConsensusGateObservatory:
    FIELDS = ("observatory_id", "history_addresses", "observations", "history_count", "observation_count", "accepted_count", "review_count", "blocked_count", "content_address")

    def __init__(self, observatory_id: str, history_addresses: Sequence[str], observations: Sequence[RegistryFederationConsensusGateObservation], history_count: int, observation_count: int, accepted_count: int, review_count: int, blocked_count: int, content_address: str) -> None:
        self.observatory_id = _label(observatory_id, "observatory ID")
        self.history_addresses = _addresses(history_addresses, "observatory history addresses", MAX_HISTORIES)
        self.observations = tuple(observations)
        if len(self.observations) > MAX_OBSERVATIONS or any(not isinstance(item, RegistryFederationConsensusGateObservation) for item in self.observations):
            raise ValidationError("observatory observations are outside the bound")
        self.history_count = _count(history_count, "observatory history count", MAX_HISTORIES, positive=True)
        self.observation_count = _count(observation_count, "observatory observation count", MAX_OBSERVATIONS, positive=True)
        self.accepted_count = _count(accepted_count, "observatory accepted count", self.observation_count)
        self.review_count = _count(review_count, "observatory review count", self.observation_count)
        self.blocked_count = _count(blocked_count, "observatory blocked count", self.observation_count)
        if len(self.history_addresses) != self.history_count or len(self.observations) != self.observation_count or tuple(item.ordinal for item in self.observations) != tuple(range(1, self.observation_count + 1)) or self.accepted_count != sum(item.accepted for item in self.observations) or self.review_count != sum(item.state == "review" for item in self.observations) or self.blocked_count != sum(item.state == "blocked" for item in self.observations):
            raise ValidationError("observatory counters are not conserved")
        self.content_address = _address(content_address, "observatory content address", OBSERVATORY_PREFIX)
        if not self.content_address.endswith(":pending") and address_observatory(self) != self.content_address:
            raise ValidationError("observatory content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"observatory_id": self.observatory_id, "history_addresses": self.history_addresses, "observations": tuple(item.to_dict() for item in self.observations), "history_count": self.history_count, "observation_count": self.observation_count, "accepted_count": self.accepted_count, "review_count": self.review_count, "blocked_count": self.blocked_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "observations"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateObservatory:
        value = _mapping(value, "consensus gate observatory")
        _strict(value, set(cls.FIELDS), "consensus gate observatory")
        return cls(value["observatory_id"], value["history_addresses"], tuple(RegistryFederationConsensusGateObservation.from_mapping(item) for item in value["observations"]), value["history_count"], value["observation_count"], value["accepted_count"], value["review_count"], value["blocked_count"], value["content_address"])


def address_observatory(value: RegistryFederationConsensusGateObservatory) -> str:
    if not isinstance(value, RegistryFederationConsensusGateObservatory):
        raise ValidationError("observatory address requires a typed observatory")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATORY_PREFIX)


def _observation(ordinal: int, history: history_model.RegistryFederationConsensusGateHistory, entry: history_model.RegistryFederationConsensusGateHistoryEntry) -> RegistryFederationConsensusGateObservation:
    provisional = RegistryFederationConsensusGateObservation(ordinal, history.history_id, history.content_address, entry.ordinal, entry.gate_id, entry.gate_address, entry.state, entry.decision, entry.accepted, entry.failed_count, OBSERVATION_PREFIX + ":pending")
    return RegistryFederationConsensusGateObservation(provisional.ordinal, provisional.history_id, provisional.history_address, provisional.entry_ordinal, provisional.gate_id, provisional.gate_address, provisional.state, provisional.decision, provisional.accepted, provisional.failed_count, address_observation(provisional))


def build_observatory(values: Sequence[history_model.RegistryFederationConsensusGateHistory], *, observatory_id: str = "consensus-gate-observatory") -> RegistryFederationConsensusGateObservatory:
    values = _sequence(values, "observatory histories", MAX_HISTORIES)
    histories = tuple(history_model.verify_history(item) for item in values)
    if not histories:
        raise ValidationError("observatory requires at least one history")
    if len({item.content_address for item in histories}) != len(histories):
        raise ValidationError("observatory histories must have unique addresses")
    observations = tuple(_observation(ordinal, history, entry) for ordinal, (history, entry) in enumerate(((history, entry) for history in histories for entry in history.entries), start=1))
    provisional = RegistryFederationConsensusGateObservatory(observatory_id, tuple(item.content_address for item in histories), observations, len(histories), len(observations), sum(item.accepted for item in observations), sum(item.state == "review" for item in observations), sum(item.state == "blocked" for item in observations), OBSERVATORY_PREFIX + ":pending")
    return RegistryFederationConsensusGateObservatory(provisional.observatory_id, provisional.history_addresses, provisional.observations, provisional.history_count, provisional.observation_count, provisional.accepted_count, provisional.review_count, provisional.blocked_count, address_observatory(provisional))


class RegistryFederationConsensusGateObservatoryQuery:
    FIELDS = ("query_id", "observatory_address", "state", "decision", "accepted", "offset", "limit", "content_address")

    def __init__(self, query_id: str, observatory_address: str, state: str, decision: str, accepted: bool | None, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "observatory query ID")
        self.observatory_address = _address(observatory_address, "queried observatory address", OBSERVATORY_PREFIX)
        self.state = _label(state, "observatory query state", required=False)
        self.decision = _label(decision, "observatory query decision", required=False)
        self.accepted = _optional_bool(accepted, "observatory query acceptance filter")
        if self.state and self.state not in STATES or self.decision and self.decision not in DECISIONS:
            raise ValidationError("observatory query disposition is unsupported")
        self.offset = _count(offset, "observatory query offset", MAX_ROWS)
        self.limit = _count(limit, "observatory query limit", MAX_ROWS, positive=True)
        self.content_address = _address(content_address, "observatory query content address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("observatory query content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateObservatoryQuery:
        value = _mapping(value, "observatory query")
        _strict(value, set(cls.FIELDS), "observatory query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateObservatoryQuery) -> str:
    if not isinstance(value, RegistryFederationConsensusGateObservatoryQuery):
        raise ValidationError("observatory query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateObservatoryQueryRow:
    FIELDS = ("ordinal", "history_id", "history_address", "entry_ordinal", "gate_id", "gate_address", "state", "decision", "accepted", "failed_count", "content_address")

    def __init__(self, ordinal: int, history_id: str, history_address: str, entry_ordinal: int, gate_id: str, gate_address: str, state: str, decision: str, accepted: bool, failed_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory query row ordinal", MAX_ROWS, positive=True)
        self.history_id = _label(history_id, "observatory query row history ID")
        self.history_address = _address(history_address, "observatory query row history address", history_model.HISTORY_PREFIX)
        self.entry_ordinal = _count(entry_ordinal, "observatory query row entry ordinal", history_model.MAX_ENTRIES, positive=True)
        self.gate_id = _label(gate_id, "observatory query row gate ID")
        self.gate_address = _address(gate_address, "observatory query row gate address", gate_model.GATE_PREFIX)
        if state not in STATES or decision not in DECISIONS:
            raise ValidationError("observatory query row disposition is unsupported")
        self.state, self.decision = state, decision
        self.accepted = _bool(accepted, "observatory query row acceptance")
        self.failed_count = _count(failed_count, "observatory query row failed count", gate_model.MAX_CHECKS)
        self.content_address = _address(content_address, "observatory query row content address", ROW_PREFIX)
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("observatory query row content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateObservatoryQueryRow:
        value = _mapping(value, "observatory query row")
        _strict(value, set(cls.FIELDS), "observatory query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateObservatoryQueryRow) -> str:
    if not isinstance(value, RegistryFederationConsensusGateObservatoryQueryRow):
        raise ValidationError("observatory query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateObservatoryQueryResult:
    FIELDS = ("query", "observatory_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateObservatoryQuery, observatory_id: str, rows: Sequence[RegistryFederationConsensusGateObservatoryQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        if not isinstance(query, RegistryFederationConsensusGateObservatoryQuery):
            raise ValidationError("observatory query result query must be typed")
        self.query = query
        self.observatory_id = _label(observatory_id, "observatory query result ID")
        self.rows = tuple(rows)
        if len(self.rows) > MAX_ROWS or any(not isinstance(item, RegistryFederationConsensusGateObservatoryQueryRow) for item in self.rows):
            raise ValidationError("observatory query result rows are outside the bound")
        self.total_count = _count(total_count, "observatory query total count", MAX_ROWS)
        self.matched_count = _count(matched_count, "observatory query matched count", self.total_count)
        self.returned_count = _count(returned_count, "observatory query returned count", self.matched_count)
        self.next_offset = _count(next_offset, "observatory query next offset", MAX_ROWS)
        self.truncated = _bool(truncated, "observatory query truncated flag")
        if len(self.rows) != self.returned_count or tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)) or self.truncated != (self.next_offset > 0) or (not self.truncated and self.next_offset != 0) or (self.truncated and self.next_offset <= self.query.offset):
            raise ValidationError("observatory query pagination is not conserved")
        self.content_address = _address(content_address, "observatory query result content address", RESULT_PREFIX)
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("observatory query result content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory query result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "observatory_id": self.observatory_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"query", "rows"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateObservatoryQueryResult:
        value = _mapping(value, "observatory query result")
        _strict(value, set(cls.FIELDS), "observatory query result")
        return cls(RegistryFederationConsensusGateObservatoryQuery.from_mapping(value["query"]), value["observatory_id"], tuple(RegistryFederationConsensusGateObservatoryQueryRow.from_mapping(item) for item in value["rows"]), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateObservatoryQueryResult) -> str:
    if not isinstance(value, RegistryFederationConsensusGateObservatoryQueryResult):
        raise ValidationError("observatory query result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _query_row(ordinal: int, item: RegistryFederationConsensusGateObservation) -> RegistryFederationConsensusGateObservatoryQueryRow:
    provisional = RegistryFederationConsensusGateObservatoryQueryRow(ordinal, item.history_id, item.history_address, item.entry_ordinal, item.gate_id, item.gate_address, item.state, item.decision, item.accepted, item.failed_count, ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateObservatoryQueryRow(provisional.ordinal, provisional.history_id, provisional.history_address, provisional.entry_ordinal, provisional.gate_id, provisional.gate_address, provisional.state, provisional.decision, provisional.accepted, provisional.failed_count, address_row(provisional))


def query_observatory(value: RegistryFederationConsensusGateObservatory, *, query_id: str = "consensus-gate-observatory-query", state: str = "", decision: str = "", accepted: bool | None = None, offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateObservatoryQueryResult:
    value = verify_observatory(value)
    query = RegistryFederationConsensusGateObservatoryQuery(query_id, value.content_address, state, decision, accepted, offset, limit, QUERY_PREFIX + ":pending")
    query = RegistryFederationConsensusGateObservatoryQuery(query.query_id, query.observatory_address, query.state, query.decision, query.accepted, query.offset, query.limit, address_query(query))
    matched = tuple(item for item in value.observations if (not query.state or item.state == query.state) and (not query.decision or item.decision == query.decision) and (query.accepted is None or item.accepted == query.accepted))
    page = matched[query.offset:query.offset + query.limit]
    truncated = query.offset + len(page) < len(matched)
    next_offset = query.offset + len(page) if truncated else 0
    rows = tuple(_query_row(query.offset + ordinal, item) for ordinal, item in enumerate(page, start=1))
    provisional = RegistryFederationConsensusGateObservatoryQueryResult(query, value.observatory_id, rows, len(value.observations), len(matched), len(rows), next_offset, truncated, RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateObservatoryQueryResult(provisional.query, provisional.observatory_id, provisional.rows, provisional.total_count, provisional.matched_count, provisional.returned_count, provisional.next_offset, provisional.truncated, address_result(provisional))


def observatory_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateObservatory:
    return verify_observatory(RegistryFederationConsensusGateObservatory.from_mapping(value))


def verify_observatory(value: RegistryFederationConsensusGateObservatory) -> RegistryFederationConsensusGateObservatory:
    if not isinstance(value, RegistryFederationConsensusGateObservatory) or (not value.content_address.endswith(":pending") and address_observatory(value) != value.content_address):
        raise ValidationError("consensus gate observatory is not valid")
    return value


def verify_query(value: RegistryFederationConsensusGateObservatoryQuery) -> RegistryFederationConsensusGateObservatoryQuery:
    if not isinstance(value, RegistryFederationConsensusGateObservatoryQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("observatory query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusGateObservatoryQueryResult) -> RegistryFederationConsensusGateObservatoryQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateObservatoryQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("observatory query result is not valid")
    return value


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateObservatoryQueryResult:
    """Decode and verify one serialized observatory query result."""

    return verify_query_result(RegistryFederationConsensusGateObservatoryQueryResult.from_mapping(value))


def observatory_json(value: RegistryFederationConsensusGateObservatory) -> str:
    return canonical_json(verify_observatory(value).to_dict())


def observatory_csv(value: RegistryFederationConsensusGateObservatory) -> str:
    value = verify_observatory(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateObservation.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.observations:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_observatory_markdown(value: RegistryFederationConsensusGateObservatory) -> str:
    value = verify_observatory(value)
    lines = ["# Consensus Release Gate Observatory", "", f"- Observatory: `{value.observatory_id}`", f"- Histories: `{value.history_count}`", f"- Observations: `{value.observation_count}`", f"- Accepted: `{value.accepted_count}`", f"- Review: `{value.review_count}`", f"- Blocked: `{value.blocked_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | history | gate | state | decision | accepted |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.history_id}` | `{item.gate_id}` | `{item.state}` | `{item.decision}` | `{item.accepted}` |" for item in value.observations)
    return "\n".join(lines) + "\n"


def query_json(value: RegistryFederationConsensusGateObservatoryQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateObservatoryQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateObservatoryQueryRow.FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow(row.to_dict())
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateObservatoryQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Consensus Gate Observatory Query", "", f"- Observatory: `{value.observatory_id}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Address: `{value.content_address}`", "", "| history | gate | state | decision | accepted |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{row.history_id}` | `{row.gate_id}` | `{row.state}` | `{row.decision}` | `{row.accepted}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def observation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateObservation.FIELDS), "properties": {"ordinal": {"type": "integer"}, "history_id": {"type": "string"}, "history_address": {"type": "string"}, "entry_ordinal": {"type": "integer"}, "gate_id": {"type": "string"}, "gate_address": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": "boolean"}, "failed_count": {"type": "integer"}, "content_address": {"type": "string"}}}


def observatory_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateObservatory.FIELDS), "properties": {"observatory_id": {"type": "string"}, "history_addresses": {"type": "array"}, "observations": {"type": "array", "items": observation_schema()}, "history_count": {"type": "integer"}, "observation_count": {"type": "integer"}, "accepted_count": {"type": "integer"}, "review_count": {"type": "integer"}, "blocked_count": {"type": "integer"}, "content_address": {"type": "string", "pattern": "^" + OBSERVATORY_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateObservatoryQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "observatory_address": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": ["boolean", "null"]}, "offset": {"type": "integer"}, "limit": {"type": "integer"}, "content_address": {"type": "string"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateObservatoryQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer"}, "history_id": {"type": "string"}, "history_address": {"type": "string"}, "entry_ordinal": {"type": "integer"}, "gate_id": {"type": "string"}, "gate_address": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": "boolean"}, "failed_count": {"type": "integer"}, "content_address": {"type": "string"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateObservatoryQueryResult.FIELDS), "properties": {"query": query_schema(), "observatory_id": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer"}, "matched_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "next_offset": {"type": "integer"}, "truncated": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "observatory_prefix": OBSERVATORY_PREFIX, "observation_prefix": OBSERVATION_PREFIX, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "result_prefix": RESULT_PREFIX, "states": STATES, "decisions": DECISIONS, "features": ("cross-history aggregation", "accepted review and blocked counters", "state decision and acceptance filters", "bounded deterministic pagination", "JSON CSV and Markdown exports"), "limits": {"max_histories": MAX_HISTORIES, "max_observations": MAX_OBSERVATIONS}, "schemas": ("observation", "observatory", "query", "row", "result")}


__all__ = ["BOUNDARY", "DECISIONS", "MAX_HISTORIES", "MAX_OBSERVATIONS", "MAX_ROWS", "OBSERVATION_PREFIX", "OBSERVATORY_PREFIX", "QUERY_PREFIX", "RESULT_PREFIX", "ROW_PREFIX", "STATES", "RegistryFederationConsensusGateObservation", "RegistryFederationConsensusGateObservatory", "RegistryFederationConsensusGateObservatoryQuery", "RegistryFederationConsensusGateObservatoryQueryResult", "RegistryFederationConsensusGateObservatoryQueryRow", "VERSION", "address_observation", "address_observatory", "address_query", "address_result", "address_row", "build_observatory", "capabilities", "observatory_csv", "observatory_from_mapping", "observatory_json", "observatory_schema", "observation_schema", "query_csv", "query_from_mapping", "query_json", "query_observatory", "query_schema", "render_observatory_markdown", "render_query_markdown", "result_schema", "row_schema", "verify_observatory", "verify_query", "verify_query_result"]
