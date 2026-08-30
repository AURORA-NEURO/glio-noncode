"""Cross-history observatory and bounded queries for release certificates."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate as certificate_model
from . import registry_federation_consensus_gate_certificate_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-observatory-v1"
BOUNDARY = history_model.BOUNDARY + "_observatory"
OBSERVATORY_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-observatory"
OBSERVATION_PREFIX = OBSERVATORY_PREFIX + "-observation"
QUERY_PREFIX = OBSERVATORY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
MAX_TEXT = certificate_model.MAX_TEXT
MAX_HISTORIES = 64
MAX_OBSERVATIONS = history_model.MAX_ENTRIES * MAX_HISTORIES
MAX_ROWS = MAX_OBSERVATIONS * 5 + 1
RESOURCES = ("summary", "observations", "issued", "withheld", "accepted", "held", "evidence")
DEFAULT_RESOURCES = RESOURCES
STATES = certificate_model.CERTIFICATE_STATES
DECISIONS = certificate_model.CERTIFICATE_DECISIONS


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
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(values) != len(set(values)):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(values))


def _resources(value: Any, field: str) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, len(RESOURCES)))
    if not values or len(values) != len(set(values)) or any(item not in RESOURCES for item in values):
        raise ValidationError(f"{field} contains unsupported resources")
    return tuple(item for item in RESOURCES if item in values)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateCertificateObservation:
    """One immutable observation projected from one certificate history entry."""

    FIELDS = ("ordinal", "history_id", "history_address", "entry_ordinal", "entry_address", "certificate_id", "runtime_id", "certificate_address", "audit_address", "state", "decision", "accepted", "check_count", "failed_count", "evidence_count", "content_address")

    def __init__(self, ordinal: int, history_id: str, history_address: str, entry_ordinal: int, entry_address: str, certificate_id: str, runtime_id: str, certificate_address: str, audit_address: str, state: str, decision: str, accepted: bool, check_count: int, failed_count: int, evidence_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate observation ordinal", MAX_OBSERVATIONS, positive=True)
        self.history_id = _label(history_id, "certificate observation history ID")
        self.history_address = _address(history_address, "certificate observation history address", history_model.HISTORY_PREFIX)
        self.entry_ordinal = _count(entry_ordinal, "certificate observation entry ordinal", history_model.MAX_ENTRIES, positive=True)
        self.entry_address = _address(entry_address, "certificate observation entry address", history_model.ENTRY_PREFIX)
        self.certificate_id = _label(certificate_id, "certificate observation certificate ID")
        self.runtime_id = _label(runtime_id, "certificate observation runtime ID")
        self.certificate_address = _address(certificate_address, "certificate observation certificate address", certificate_model.CERTIFICATE_PREFIX)
        audit_prefix = certificate_model.CERTIFICATE_PREFIX + "-audit"
        self.audit_address = _address(audit_address, "certificate observation audit address", audit_prefix)
        if state not in STATES or decision not in DECISIONS:
            raise ValidationError("certificate observation disposition is unsupported")
        self.state, self.decision = state, decision
        self.accepted = _bool(accepted, "certificate observation acceptance")
        self.check_count = _count(check_count, "certificate observation check count", certificate_model.MAX_CHECKS, positive=True)
        self.failed_count = _count(failed_count, "certificate observation failed count", self.check_count)
        self.evidence_count = _count(evidence_count, "certificate observation evidence count", certificate_model.MAX_EVIDENCE, positive=True)
        self.content_address = _address(content_address, "certificate observation content address", OBSERVATION_PREFIX)
        if not self.content_address.endswith(":pending") and address_observation(self) != self.content_address:
            raise ValidationError("certificate observation content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservation:
        value = _mapping(value, "certificate observation")
        _strict(value, set(cls.FIELDS), "certificate observation")
        return cls(*(value[field] for field in cls.FIELDS))


def address_observation(value: RegistryFederationConsensusGateCertificateObservation) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservation):
        raise ValidationError("certificate observation address requires a typed observation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATION_PREFIX)


class RegistryFederationConsensusGateCertificateObservatory:
    """Addressed aggregate of one or more append-only certificate histories."""

    FIELDS = ("observatory_id", "history_addresses", "observations", "history_count", "observation_count", "issued_count", "withheld_count", "accepted_count", "held_count", "total_check_count", "total_failed_count", "content_address")

    def __init__(self, observatory_id: str, history_addresses: Sequence[str], observations: Sequence[RegistryFederationConsensusGateCertificateObservation], history_count: int, observation_count: int, issued_count: int, withheld_count: int, accepted_count: int, held_count: int, total_check_count: int, total_failed_count: int, content_address: str) -> None:
        self.observatory_id = _label(observatory_id, "certificate observatory ID")
        self.history_addresses = _addresses(history_addresses, "certificate observatory history addresses", MAX_HISTORIES)
        self.observations = tuple(observations)
        if len(self.observations) > MAX_OBSERVATIONS or any(not isinstance(item, RegistryFederationConsensusGateCertificateObservation) for item in self.observations):
            raise ValidationError("certificate observatory observations are outside the bound")
        self.history_count = _count(history_count, "certificate observatory history count", MAX_HISTORIES, positive=True)
        self.observation_count = _count(observation_count, "certificate observatory observation count", MAX_OBSERVATIONS, positive=True)
        self.issued_count = _count(issued_count, "certificate observatory issued count", self.observation_count)
        self.withheld_count = _count(withheld_count, "certificate observatory withheld count", self.observation_count)
        self.accepted_count = _count(accepted_count, "certificate observatory accepted count", self.observation_count)
        self.held_count = _count(held_count, "certificate observatory held count", self.observation_count)
        self.total_check_count = _count(total_check_count, "certificate observatory total check count", MAX_OBSERVATIONS * certificate_model.MAX_CHECKS)
        self.total_failed_count = _count(total_failed_count, "certificate observatory total failed count", self.total_check_count)
        if len(self.history_addresses) != self.history_count or len(self.observations) != self.observation_count or tuple(item.ordinal for item in self.observations) != tuple(range(1, self.observation_count + 1)):
            raise ValidationError("certificate observatory membership or ordinals are not conserved")
        if self.issued_count != sum(item.state == "issued" for item in self.observations) or self.withheld_count != sum(item.state == "withheld" for item in self.observations) or self.accepted_count != sum(item.accepted for item in self.observations) or self.held_count != sum(not item.accepted for item in self.observations) or self.total_check_count != sum(item.check_count for item in self.observations) or self.total_failed_count != sum(item.failed_count for item in self.observations):
            raise ValidationError("certificate observatory counters are not conserved")
        if any(item.history_address not in self.history_addresses for item in self.observations):
            raise ValidationError("certificate observatory observation history links are not conserved")
        self.content_address = _address(content_address, "certificate observatory content address", OBSERVATORY_PREFIX)
        if not self.content_address.endswith(":pending") and address_observatory(self) != self.content_address:
            raise ValidationError("certificate observatory content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"observatory_id": self.observatory_id, "history_addresses": self.history_addresses, "observations": tuple(item.to_dict() for item in self.observations), "history_count": self.history_count, "observation_count": self.observation_count, "issued_count": self.issued_count, "withheld_count": self.withheld_count, "accepted_count": self.accepted_count, "held_count": self.held_count, "total_check_count": self.total_check_count, "total_failed_count": self.total_failed_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "observations"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatory:
        value = _mapping(value, "certificate observatory")
        _strict(value, set(cls.FIELDS), "certificate observatory")
        return cls(value["observatory_id"], value["history_addresses"], tuple(RegistryFederationConsensusGateCertificateObservation.from_mapping(item) for item in value["observations"]), value["history_count"], value["observation_count"], value["issued_count"], value["withheld_count"], value["accepted_count"], value["held_count"], value["total_check_count"], value["total_failed_count"], value["content_address"])


def address_observatory(value: RegistryFederationConsensusGateCertificateObservatory) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatory):
        raise ValidationError("certificate observatory address requires a typed observatory")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATORY_PREFIX)


def _observation(ordinal: int, history: history_model.RegistryFederationConsensusGateCertificateHistory, entry: history_model.RegistryFederationConsensusGateCertificateHistoryEntry) -> RegistryFederationConsensusGateCertificateObservation:
    provisional = RegistryFederationConsensusGateCertificateObservation(ordinal, history.history_id, history.content_address, entry.ordinal, entry.content_address, entry.certificate_id, entry.runtime_id, entry.certificate_address, entry.audit_address, entry.state, entry.decision, entry.accepted, entry.check_count, entry.failed_count, len(entry.evidence_addresses), OBSERVATION_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservation(provisional.ordinal, provisional.history_id, provisional.history_address, provisional.entry_ordinal, provisional.entry_address, provisional.certificate_id, provisional.runtime_id, provisional.certificate_address, provisional.audit_address, provisional.state, provisional.decision, provisional.accepted, provisional.check_count, provisional.failed_count, provisional.evidence_count, address_observation(provisional))


def build_observatory(values: Sequence[history_model.RegistryFederationConsensusGateCertificateHistory], *, observatory_id: str = "consensus-certificate-observatory") -> RegistryFederationConsensusGateCertificateObservatory:
    values = _sequence(values, "certificate observatory histories", MAX_HISTORIES)
    histories = tuple(history_model.verify_history(item) for item in values)
    if not histories:
        raise ValidationError("certificate observatory requires at least one history")
    if len({item.content_address for item in histories}) != len(histories):
        raise ValidationError("certificate observatory histories must have unique addresses")
    observations = tuple(_observation(ordinal, history, entry) for ordinal, (history, entry) in enumerate(((history, entry) for history in histories for entry in history.entries), start=1))
    provisional = RegistryFederationConsensusGateCertificateObservatory(observatory_id, tuple(item.content_address for item in histories), observations, len(histories), len(observations), sum(item.state == "issued" for item in observations), sum(item.state == "withheld" for item in observations), sum(item.accepted for item in observations), sum(not item.accepted for item in observations), sum(item.check_count for item in observations), sum(item.failed_count for item in observations), OBSERVATORY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatory(provisional.observatory_id, provisional.history_addresses, provisional.observations, provisional.history_count, provisional.observation_count, provisional.issued_count, provisional.withheld_count, provisional.accepted_count, provisional.held_count, provisional.total_check_count, provisional.total_failed_count, address_observatory(provisional))


class RegistryFederationConsensusGateCertificateObservatoryQuery:
    """Immutable resource, disposition, and page filter for an observatory."""

    FIELDS = ("query_id", "observatory_address", "resources", "history_id", "certificate_id", "state", "decision", "accepted", "offset", "limit", "content_address")

    def __init__(self, query_id: str, observatory_address: str, resources: Sequence[str], history_id: str, certificate_id: str, state: str, decision: str, accepted: bool | None, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "certificate observatory query ID")
        self.observatory_address = _address(observatory_address, "queried certificate observatory address", OBSERVATORY_PREFIX)
        self.resources = _resources(resources, "certificate observatory query resources")
        self.history_id = _label(history_id, "certificate observatory query history ID", required=False)
        self.certificate_id = _label(certificate_id, "certificate observatory query certificate ID", required=False)
        self.state = _label(state, "certificate observatory query state", required=False)
        self.decision = _label(decision, "certificate observatory query decision", required=False)
        if self.state and self.state not in STATES or self.decision and self.decision not in DECISIONS:
            raise ValidationError("certificate observatory query disposition is unsupported")
        self.accepted = _optional_bool(accepted, "certificate observatory query acceptance filter")
        self.offset = _count(offset, "certificate observatory query offset", MAX_ROWS)
        self.limit = _count(limit, "certificate observatory query limit", MAX_ROWS, positive=True)
        self.content_address = _address(content_address, "certificate observatory query address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("certificate observatory query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryQuery:
        value = _mapping(value, "certificate observatory query")
        _strict(value, set(cls.FIELDS), "certificate observatory query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryQuery) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryQuery):
        raise ValidationError("certificate observatory query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryQueryRow:
    """One bounded row from a filtered observatory projection."""

    FIELDS = ("ordinal", "resource", "row_id", "observation_ordinal", "history_id", "history_address", "entry_ordinal", "certificate_id", "runtime_id", "certificate_address", "audit_address", "state", "decision", "accepted", "check_count", "failed_count", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, observation_ordinal: int, history_id: str, history_address: str, entry_ordinal: int, certificate_id: str, runtime_id: str, certificate_address: str, audit_address: str, state: str, decision: str, accepted: bool, check_count: int, failed_count: int, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate observatory query row ordinal", MAX_ROWS, positive=True)
        self.resource = _label(resource, "certificate observatory query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("certificate observatory query row resource is unsupported")
        self.row_id = _label(row_id, "certificate observatory query row ID")
        self.observation_ordinal = _count(observation_ordinal, "certificate observatory query observation ordinal", MAX_OBSERVATIONS, positive=True)
        self.history_id = _label(history_id, "certificate observatory query row history ID")
        self.history_address = _address(history_address, "certificate observatory query row history address", history_model.HISTORY_PREFIX)
        self.entry_ordinal = _count(entry_ordinal, "certificate observatory query row entry ordinal", history_model.MAX_ENTRIES, positive=True)
        self.certificate_id = _label(certificate_id, "certificate observatory query row certificate ID")
        self.runtime_id = _label(runtime_id, "certificate observatory query row runtime ID")
        self.certificate_address = _address(certificate_address, "certificate observatory query row certificate address", certificate_model.CERTIFICATE_PREFIX)
        self.audit_address = _address(audit_address, "certificate observatory query row audit address", certificate_model.CERTIFICATE_PREFIX + "-audit")
        if state not in STATES or decision not in DECISIONS:
            raise ValidationError("certificate observatory query row disposition is unsupported")
        self.state, self.decision = state, decision
        self.accepted = _bool(accepted, "certificate observatory query row acceptance")
        self.check_count = _count(check_count, "certificate observatory query row check count", certificate_model.MAX_CHECKS, positive=True)
        self.failed_count = _count(failed_count, "certificate observatory query row failed count", self.check_count)
        self.evidence_addresses = tuple(_address(item, "certificate observatory query evidence address") for item in _sequence(evidence_addresses, "certificate observatory query evidence addresses", certificate_model.MAX_EVIDENCE))
        if not self.evidence_addresses:
            raise ValidationError("certificate observatory query rows require evidence")
        self.content_address = _address(content_address, "certificate observatory query row address", ROW_PREFIX)
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("certificate observatory query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryQueryRow:
        value = _mapping(value, "certificate observatory query row")
        _strict(value, set(cls.FIELDS), "certificate observatory query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryQueryRow) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryQueryRow):
        raise ValidationError("certificate observatory query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryQueryResult:
    FIELDS = ("query", "observatory_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryQuery, observatory_id: str, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        if not isinstance(query, RegistryFederationConsensusGateCertificateObservatoryQuery):
            raise ValidationError("certificate observatory query result query must be typed")
        self.query = query
        self.observatory_id = _label(observatory_id, "certificate observatory query result ID")
        self.rows = tuple(rows)
        if len(self.rows) > MAX_ROWS or any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryQueryRow) for item in self.rows):
            raise ValidationError("certificate observatory query result rows are outside the bound")
        self.total_count = _count(total_count, "certificate observatory query total count", MAX_ROWS)
        self.matched_count = _count(matched_count, "certificate observatory query matched count", self.total_count)
        self.returned_count = _count(returned_count, "certificate observatory query returned count", self.matched_count)
        self.next_offset = _count(next_offset, "certificate observatory query next offset", MAX_ROWS)
        self.truncated = _bool(truncated, "certificate observatory query truncated flag")
        if len(self.rows) != self.returned_count or tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)) or self.truncated != (self.next_offset > 0) or (not self.truncated and self.next_offset != 0) or (self.truncated and self.next_offset <= self.query.offset):
            raise ValidationError("certificate observatory query pagination is not conserved")
        self.content_address = _address(content_address, "certificate observatory query result address", RESULT_PREFIX)
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("certificate observatory query result address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory query result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "observatory_id": self.observatory_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"query", "rows"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryQueryResult:
        value = _mapping(value, "certificate observatory query result")
        _strict(value, set(cls.FIELDS), "certificate observatory query result")
        return cls(RegistryFederationConsensusGateCertificateObservatoryQuery.from_mapping(value["query"]), value["observatory_id"], tuple(RegistryFederationConsensusGateCertificateObservatoryQueryRow.from_mapping(item) for item in value["rows"]), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryQueryResult) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryQueryResult):
        raise ValidationError("certificate observatory query result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, row_id: str, item: RegistryFederationConsensusGateCertificateObservation, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryQueryRow:
    provisional = RegistryFederationConsensusGateCertificateObservatoryQueryRow(ordinal, resource, row_id, item.ordinal, item.history_id, item.history_address, item.entry_ordinal, item.certificate_id, item.runtime_id, item.certificate_address, item.audit_address, item.state, item.decision, item.accepted, item.check_count, item.failed_count, evidence, ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryQueryRow(provisional.ordinal, provisional.resource, provisional.row_id, provisional.observation_ordinal, provisional.history_id, provisional.history_address, provisional.entry_ordinal, provisional.certificate_id, provisional.runtime_id, provisional.certificate_address, provisional.audit_address, provisional.state, provisional.decision, provisional.accepted, provisional.check_count, provisional.failed_count, provisional.evidence_addresses, address_row(provisional))


def build_query(value: RegistryFederationConsensusGateCertificateObservatory, *, query_id: str = "consensus-certificate-observatory-query", resources: Sequence[str] = DEFAULT_RESOURCES, history_id: str = "", certificate_id: str = "", state: str = "", decision: str = "", accepted: bool | None = None, offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateCertificateObservatoryQuery:
    value = verify_observatory(value)
    provisional = RegistryFederationConsensusGateCertificateObservatoryQuery(query_id, value.content_address, resources, history_id, certificate_id, state, decision, accepted, offset, limit, QUERY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryQuery(provisional.query_id, provisional.observatory_address, provisional.resources, provisional.history_id, provisional.certificate_id, provisional.state, provisional.decision, provisional.accepted, provisional.offset, provisional.limit, address_query(provisional))


def _all_rows(value: RegistryFederationConsensusGateCertificateObservatory, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateCertificateObservatoryQueryRow, ...]:
    rows: list[RegistryFederationConsensusGateCertificateObservatoryQueryRow] = []
    observations = value.observations
    if "summary" in resources:
        first = observations[0]
        rows.append(_row(len(rows) + 1, "summary", "summary", first, (value.content_address,)))
    for resource, selected in (("observations", observations), ("issued", tuple(item for item in observations if item.state == "issued")), ("withheld", tuple(item for item in observations if item.state == "withheld")), ("accepted", tuple(item for item in observations if item.accepted)), ("held", tuple(item for item in observations if not item.accepted))):
        if resource in resources:
            rows.extend(_row(len(rows) + 1, resource, f"{resource}-{item.ordinal}", item, (item.content_address, item.certificate_address, item.audit_address)) for item in selected)
    if "evidence" in resources:
        for item in observations:
            rows.append(_row(len(rows) + 1, "evidence", f"evidence-{item.ordinal}", item, (item.certificate_address, item.audit_address)))
    return tuple(rows)


def query_observatory(value: RegistryFederationConsensusGateCertificateObservatory, *, query_id: str = "consensus-certificate-observatory-query", resources: Sequence[str] = DEFAULT_RESOURCES, history_id: str = "", certificate_id: str = "", state: str = "", decision: str = "", accepted: bool | None = None, offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateCertificateObservatoryQueryResult:
    value = verify_observatory(value)
    query = build_query(value, query_id=query_id, resources=resources, history_id=history_id, certificate_id=certificate_id, state=state, decision=decision, accepted=accepted, offset=offset, limit=limit)
    rows = _all_rows(value, query.resources)
    matched = tuple(item for item in rows if (not query.history_id or item.history_id == query.history_id) and (not query.certificate_id or item.certificate_id == query.certificate_id) and (not query.state or item.state == query.state) and (not query.decision or item.decision == query.decision) and (query.accepted is None or item.accepted == query.accepted))
    page = matched[query.offset:query.offset + query.limit]
    truncated = query.offset + len(page) < len(matched)
    next_offset = query.offset + len(page) if truncated else 0
    typed_rows = tuple(_row(query.offset + ordinal, item.resource, item.row_id, next((observation for observation in value.observations if observation.ordinal == item.observation_ordinal), value.observations[0]), item.evidence_addresses) for ordinal, item in enumerate(page, start=1))
    provisional = RegistryFederationConsensusGateCertificateObservatoryQueryResult(query, value.observatory_id, typed_rows, len(rows), len(matched), len(typed_rows), next_offset, truncated, RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryQueryResult(provisional.query, provisional.observatory_id, provisional.rows, provisional.total_count, provisional.matched_count, provisional.returned_count, provisional.next_offset, provisional.truncated, address_result(provisional))


def observatory_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatory:
    return verify_observatory(RegistryFederationConsensusGateCertificateObservatory.from_mapping(value))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryQueryResult:
    return verify_query_result(RegistryFederationConsensusGateCertificateObservatoryQueryResult.from_mapping(value))


def verify_observatory(value: RegistryFederationConsensusGateCertificateObservatory) -> RegistryFederationConsensusGateCertificateObservatory:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatory) or (not value.content_address.endswith(":pending") and address_observatory(value) != value.content_address):
        raise ValidationError("certificate observatory is not valid")
    return value


def verify_query(value: RegistryFederationConsensusGateCertificateObservatoryQuery) -> RegistryFederationConsensusGateCertificateObservatoryQuery:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("certificate observatory query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("certificate observatory query result is not valid")
    return value


def observatory_json(value: RegistryFederationConsensusGateCertificateObservatory) -> str:
    return canonical_json(verify_observatory(value).to_dict())


def observatory_csv(value: RegistryFederationConsensusGateCertificateObservatory) -> str:
    value = verify_observatory(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservation.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.observations:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_observatory_markdown(value: RegistryFederationConsensusGateCertificateObservatory) -> str:
    value = verify_observatory(value)
    lines = ["# Consensus Release Certificate Observatory", "", f"- Observatory: `{value.observatory_id}`", f"- Histories: `{value.history_count}`", f"- Observations: `{value.observation_count}`", f"- Issued: `{value.issued_count}`", f"- Withheld: `{value.withheld_count}`", f"- Accepted: `{value.accepted_count}`", f"- Held: `{value.held_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | history | certificate | state | decision | accepted | failed |", "| --- | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.history_id}` | `{item.certificate_id}` | `{item.state}` | `{item.decision}` | `{item.accepted}` | `{item.failed_count}` |" for item in value.observations)
    return "\n".join(lines) + "\n"


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryQueryRow.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        row = item.to_dict()
        row["evidence_addresses"] = "|".join(item.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Consensus Release Certificate Observatory Query", "", f"- Observatory: `{value.observatory_id}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Result: `{value.content_address}`", "", "| resource | row | history | certificate | state | accepted |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.resource}` | `{item.row_id}` | `{item.history_id}` | `{item.certificate_id}` | `{item.state}` | `{item.accepted}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "observatory_address": {"type": "string", "pattern": "^" + OBSERVATORY_PREFIX + ":"}, "resources": {"type": "array", "items": {"type": "string"}}, "history_id": {"type": "string"}, "certificate_id": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": ["boolean", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"type": "string"}, "row_id": {"type": "string"}, "observation_ordinal": {"type": "integer"}, "history_id": {"type": "string"}, "history_address": {"type": "string"}, "entry_ordinal": {"type": "integer"}, "certificate_id": {"type": "string"}, "runtime_id": {"type": "string"}, "certificate_address": {"type": "string"}, "audit_address": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryQueryResult.FIELDS), "properties": {"query": query_schema(), "observatory_id": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer"}, "matched_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "next_offset": {"type": "integer"}, "truncated": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RESULT_PREFIX + ":"}}}


def observatory_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatory.FIELDS), "properties": {"observatory_id": {"type": "string"}, "history_addresses": {"type": "array", "items": {"type": "string"}}, "observations": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservation.FIELDS), "properties": {field: {"type": "array"} if field == "evidence_addresses" else {"type": "integer"} if field.endswith("count") or field.endswith("ordinal") else {"type": "boolean"} if field == "accepted" else {"type": "string"} for field in RegistryFederationConsensusGateCertificateObservation.FIELDS}}}, "history_count": {"type": "integer"}, "observation_count": {"type": "integer"}, "issued_count": {"type": "integer"}, "withheld_count": {"type": "integer"}, "accepted_count": {"type": "integer"}, "held_count": {"type": "integer"}, "total_check_count": {"type": "integer"}, "total_failed_count": {"type": "integer"}, "content_address": {"type": "string", "pattern": "^" + OBSERVATORY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "observatory_prefix": OBSERVATORY_PREFIX, "observation_prefix": OBSERVATION_PREFIX, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "result_prefix": RESULT_PREFIX, "resources": RESOURCES, "default_resources": DEFAULT_RESOURCES, "states": STATES, "decisions": DECISIONS, "limits": {"max_histories": MAX_HISTORIES, "max_observations": MAX_OBSERVATIONS, "max_rows": MAX_ROWS}, "features": ("cross-history certificate aggregation", "issued and withheld counters", "acceptance and failure density metrics", "bounded history and certificate filters", "deterministic pagination", "content-addressed observations and rows", "JSON CSV and Markdown exports"), "schemas": ("observatory", "query", "row", "result")}


__all__ = ["BOUNDARY", "DEFAULT_RESOURCES", "DECISIONS", "MAX_HISTORIES", "MAX_OBSERVATIONS", "MAX_ROWS", "OBSERVATION_PREFIX", "OBSERVATORY_PREFIX", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "STATES", "RegistryFederationConsensusGateCertificateObservation", "RegistryFederationConsensusGateCertificateObservatory", "RegistryFederationConsensusGateCertificateObservatoryQuery", "RegistryFederationConsensusGateCertificateObservatoryQueryResult", "RegistryFederationConsensusGateCertificateObservatoryQueryRow", "VERSION", "address_observation", "address_observatory", "address_query", "address_result", "address_row", "build_observatory", "build_query", "capabilities", "observatory_from_mapping", "observatory_json", "observatory_csv", "observatory_schema", "query_from_mapping", "query_json", "query_csv", "query_observatory", "query_schema", "render_observatory_markdown", "render_query_markdown", "result_schema", "row_schema", "verify_observatory", "verify_query", "verify_query_result"]
