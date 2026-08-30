"""Bounded, addressed queries over archive-registry federation evidence."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-query-v1"
BOUNDARY = federation_model.BOUNDARY + "_query"
QUERY_PREFIX = federation_model.FEDERATION_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
DEFAULT_LIMIT = 50
MAX_QUERY_ITEMS = federation_model.MAX_ENTRIES + federation_model.MAX_PEERS
RESOURCES = ("summary", "peers", "observations", "consistent", "divergent", "missing")


def _text(value: Any, field: str, maximum: int = 2048, *, required: bool = True) -> str:
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


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery:
    FIELDS = ("query_id", "federation_address", "resources", "peer_id", "entry_id", "state", "package_id", "text", "offset", "limit", "content_address")

    def __init__(self, query_id: str, federation_address: str, resources: Sequence[str], peer_id: str, entry_id: str, state: str, package_id: str, text: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "federation query ID")
        self.federation_address = _address(federation_address, "federation query address", federation_model.FEDERATION_PREFIX)
        self.resources = tuple(_label(item, "federation query resource") for item in _sequence(resources, "federation query resources", len(RESOURCES)))
        self.peer_id = _label(peer_id, "federation query peer ID", required=False)
        self.entry_id = _label(entry_id, "federation query entry ID", required=False)
        self.state = _label(state, "federation query state", required=False)
        self.package_id = _label(package_id, "federation query package ID", required=False)
        self.text = _text(text, "federation query text", 512, required=False)
        self.offset = _count(offset, "federation query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "federation query limit", MAX_QUERY_ITEMS)
        self.content_address = _address(content_address, "federation query content address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation query content address")
        self._validate()

    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources) or self.limit < 1:
            raise ValidationError("federation query resources or limit are invalid")
        if self.state and self.state not in federation_model.STATES:
            raise ValidationError("federation query state is unsupported")
        if not _public(self.to_dict()):
            raise ValidationError("federation query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("federation query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery":
        value = _mapping(value, "federation query")
        _strict(value, set(cls.FIELDS), "federation query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow:
    FIELDS = ("ordinal", "resource", "row_id", "peer_id", "registry_id", "entry_id", "package_id", "state", "peer_count", "presence_count", "observed_archive_addresses", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, peer_id: str, registry_id: str, entry_id: str, package_id: str, state: str, peer_count: int, presence_count: int, observed_archive_addresses: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation query row ordinal", MAX_QUERY_ITEMS)
        self.resource = _label(resource, "federation query row resource")
        self.row_id = _label(row_id, "federation query row ID")
        self.peer_id = _label(peer_id, "federation query row peer ID", required=False)
        self.registry_id = _label(registry_id, "federation query row registry ID", required=False)
        self.entry_id = _label(entry_id, "federation query row entry ID", required=False)
        self.package_id = _label(package_id, "federation query row package ID", required=False)
        self.state = _label(state, "federation query row state")
        self.peer_count = _count(peer_count, "federation query row peer count", federation_model.MAX_PEERS)
        self.presence_count = _count(presence_count, "federation query row presence count", federation_model.MAX_PEERS)
        self.observed_archive_addresses = tuple(_address(item, "federation query archive address", registry_model.archive_model.ARCHIVE_PREFIX) for item in _sequence(observed_archive_addresses, "federation query archive addresses", federation_model.MAX_PEERS))
        self.evidence_addresses = tuple(_text(item, "federation query evidence address", 2048) for item in _sequence(evidence_addresses, "federation query evidence", federation_model.MAX_ENTRIES + federation_model.MAX_PEERS))
        self.content_address = _address(content_address, "federation query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation query row address")
        self._validate()

    def _validate(self) -> None:
        if self.state not in federation_model.STATES or self.presence_count != len(self.observed_archive_addresses) or self.presence_count > self.peer_count or not self.evidence_addresses:
            raise ValidationError("federation query row is not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("federation query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("federation query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow":
        value = _mapping(value, "federation query row")
        _strict(value, set(cls.FIELDS), "federation query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult:
    FIELDS = ("query", "federation_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery, federation_id: str, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        self.query = query if isinstance(query, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery.from_mapping(query)
        self.federation_id = _label(federation_id, "federation query result federation ID")
        self.rows = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow.from_mapping(item) for item in _sequence(rows, "federation query result rows", MAX_QUERY_ITEMS))
        self.total_count = _count(total_count, "federation query total count", MAX_QUERY_ITEMS)
        self.matched_count = _count(matched_count, "federation query matched count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "federation query returned count", MAX_QUERY_ITEMS)
        self.next_offset = _count(next_offset, "federation query next offset", MAX_QUERY_ITEMS)
        self.truncated = _bool(truncated, "federation query truncation")
        self.content_address = _address(content_address, "federation query result address", RESULT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation query result address")
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.matched_count or self.next_offset != self.query.offset + self.returned_count:
            raise ValidationError("federation query result counters are not conserved")
        if self.rows and tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)):
            raise ValidationError("federation query result ordinals are not conserved")
        if self.truncated != (self.next_offset < self.query.offset + self.matched_count):
            raise ValidationError("federation query truncation does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("federation query result crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("federation query result address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "federation_id": self.federation_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("federation_id", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult":
        value = _mapping(value, "federation query result")
        _strict(value, set(cls.FIELDS), "federation query result")
        return cls(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery.from_mapping(value["query"]), value["federation_id"], tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow.from_mapping(item) for item in _sequence(value["rows"], "federation query result rows", MAX_QUERY_ITEMS)), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, row_id: str, *, peer_id: str = "", registry_id: str = "", entry_id: str = "", package_id: str = "", state: str = "consistent", peer_count: int = 0, presence_count: int = 0, observed_archive_addresses: Sequence[str] = (), evidence_addresses: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "row_id": row_id, "peer_id": peer_id, "registry_id": registry_id, "entry_id": entry_id, "package_id": package_id, "state": state, "peer_count": peer_count, "presence_count": presence_count, "observed_archive_addresses": tuple(observed_archive_addresses), "evidence_addresses": tuple(evidence_addresses)}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow(**body, content_address=address_row(provisional))


def _all_rows(value: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow, ...]:
    rows: list[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow] = []
    ordinal = 1
    selected = tuple(resources)
    if "summary" in selected:
        rows.append(_row(ordinal, "summary", value.federation_id, state="divergent" if value.conflict_count else "consistent", peer_count=value.peer_count, presence_count=0, evidence_addresses=(value.content_address,)))
        ordinal += 1
    if "peers" in selected:
        for peer in value.peers:
            rows.append(_row(ordinal, "peers", peer.peer_id, peer_id=peer.peer_id, registry_id=peer.registry_id, peer_count=value.peer_count, presence_count=0, evidence_addresses=(peer.content_address, peer.registry_address)))
            ordinal += 1
    if any(item in selected for item in ("observations", "consistent", "divergent", "missing")):
        for observation in value.observations:
            resource = "observations" if "observations" in selected else observation.state
            if resource not in selected:
                continue
            rows.append(_row(ordinal, resource, observation.entry_id, entry_id=observation.entry_id, package_id=observation.package_id, state=observation.state, peer_count=observation.peer_count, presence_count=observation.presence_count, observed_archive_addresses=observation.observed_archive_addresses, evidence_addresses=(observation.content_address,) + observation.observed_archive_addresses))
            ordinal += 1
    return tuple(rows)


def _matches(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery) -> bool:
    if query.peer_id and row.peer_id != query.peer_id:
        return False
    if query.entry_id and row.entry_id != query.entry_id:
        return False
    if query.state and row.state != query.state:
        return False
    if query.package_id and row.package_id != query.package_id:
        return False
    if query.text:
        haystack = " ".join((row.row_id, row.peer_id, row.registry_id, row.entry_id, row.package_id, row.state, *row.observed_archive_addresses)).lower()
        if query.text.lower() not in haystack:
            return False
    return True


def _reordinal(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow, ordinal: int) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow.from_mapping(body)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow.from_mapping(provisional.to_dict() | {"content_address": address_row(provisional)})


def query_federation(value: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation, *, query_id: str = "consensus-certificate-observatory-archive-registry-federation-query", resources: Sequence[str] = ("summary", "peers", "observations"), peer_id: str = "", entry_id: str = "", state: str = "", package_id: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult:
    value = federation_model.verify_federation(value)
    provisional_query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery(query_id, value.content_address, resources, peer_id, entry_id, state, package_id, text, offset, limit, QUERY_PREFIX + ":pending")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery(provisional_query.query_id, provisional_query.federation_address, provisional_query.resources, provisional_query.peer_id, provisional_query.entry_id, provisional_query.state, provisional_query.package_id, provisional_query.text, provisional_query.offset, provisional_query.limit, address_query(provisional_query))
    rows = _all_rows(value, query.resources)
    matched = tuple(row for row in rows if _matches(row, query))
    page = tuple(_reordinal(row, query.offset + index + 1) for index, row in enumerate(matched[query.offset:query.offset + query.limit]))
    next_offset = query.offset + len(page)
    provisional_result = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult(query, value.federation_id, page, len(rows), len(matched), len(page), next_offset, next_offset < query.offset + len(matched), RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult(query, provisional_result.federation_id, provisional_result.rows, provisional_result.total_count, provisional_result.matched_count, provisional_result.returned_count, provisional_result.next_offset, provisional_result.truncated, address_result(provisional_result))


def query_federation_from_mapping(value: Mapping[str, Any], **kwargs: Any) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult:
    return query_federation(federation_model.federation_from_mapping(value), **kwargs)


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult:
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult.from_mapping(value)


def verify_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("federation query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("federation query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult) -> str:
    value = verify_query_result(value)
    fields = ("ordinal", "resource", "row_id", "peer_id", "registry_id", "entry_id", "package_id", "state", "peer_count", "presence_count", "observed_archive_addresses", "evidence_addresses", "content_address")
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        row = item.to_dict()
        for field in ("observed_archive_addresses", "evidence_addresses"):
            row[field] = ",".join(row[field])
        writer.writerow(row)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Archive Registry Federation Query", "", f"- Federation: `{value.federation_id}`", f"- Returned: `{value.returned_count}/{value.matched_count}`", f"- Next offset: `{value.next_offset}`", "", "| # | resource | row | state | evidence |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.row_id}` | `{item.state}` | `{', '.join(item.evidence_addresses)}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "federation_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "peer_id": {"type": "string"}, "entry_id": {"type": "string"}, "state": {"enum": [""] + list(federation_model.STATES)}, "package_id": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"type": "string"}, "row_id": {"type": "string"}, "peer_id": {"type": "string"}, "registry_id": {"type": "string"}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "state": {"enum": list(federation_model.STATES)}, "peer_count": {"type": "integer", "minimum": 0}, "presence_count": {"type": "integer", "minimum": 0}, "observed_archive_addresses": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult.FIELDS), "properties": {"query": query_schema(), "federation_id": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "operations": ("query_federation", "query_federation_from_mapping", "query_json", "query_csv", "render_query_markdown", "verify_query_result"), "resources": RESOURCES, "max_items": MAX_QUERY_ITEMS}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQuery", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryResult", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationQueryRow", "address_query", "address_result", "address_row", "capabilities", "query_csv", "query_federation", "query_federation_from_mapping", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_query", "verify_query_result"]
