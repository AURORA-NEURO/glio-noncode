"""Bounded, deterministic inspection of federated resolution evidence."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution as resolution_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = resolution_model.VERSION + "-query-v1"
BOUNDARY = resolution_model.BOUNDARY + "_query"
QUERY_PREFIX = resolution_model.RESOLUTION_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
DEFAULT_LIMIT = 50
MAX_QUERY_ITEMS = resolution_model.MAX_ITEMS * 2
RESOURCES = ("summary", "items", "resolved", "review", "blocked", "supporting", "missing", "dissenting")


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
    return resolution_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery:
    """A stable query specification over resolution rows."""

    FIELDS = ("query_id", "resolution_address", "resources", "entry_id", "state", "action", "peer_id", "package_id", "text", "offset", "limit", "content_address")

    def __init__(self, query_id: str, resolution_address: str, resources: Sequence[str], entry_id: str, state: str, action: str, peer_id: str, package_id: str, text: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "resolution query ID")
        self.resolution_address = _address(resolution_address, "resolution query address", resolution_model.RESOLUTION_PREFIX)
        self.resources = tuple(_label(item, "resolution query resource") for item in _sequence(resources, "resolution query resources", len(RESOURCES)))
        self.entry_id = _label(entry_id, "resolution query entry ID", required=False)
        self.state = _label(state, "resolution query state", required=False)
        self.action = _label(action, "resolution query action", required=False)
        self.peer_id = _label(peer_id, "resolution query peer ID", required=False)
        self.package_id = _label(package_id, "resolution query package ID", required=False)
        self.text = _text(text, "resolution query text", 512, required=False)
        self.offset = _count(offset, "resolution query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "resolution query limit", MAX_QUERY_ITEMS)
        self.content_address = _address(content_address, "resolution query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "resolution query address")
        self._validate()

    def _validate(self) -> None:
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.limit < 1:
            raise ValidationError("resolution query resources or limit are invalid")
        if self.state and self.state not in resolution_model.STATES or self.action and self.action not in resolution_model.ACTIONS:
            raise ValidationError("resolution query filter vocabulary is unsupported")
        if not _public(self.to_dict()):
            raise ValidationError("resolution query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("resolution query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery":
        value = _mapping(value, "resolution query")
        _strict(value, set(cls.FIELDS), "resolution query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow:
    """A path-free row returned by a resolution query."""

    FIELDS = ("ordinal", "resource", "row_id", "entry_id", "package_id", "state", "action", "selected_archive_address", "supporting_peer_ids", "missing_peer_ids", "dissenting_peer_ids", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, entry_id: str, package_id: str, state: str, action: str, selected_archive_address: str, supporting_peer_ids: Sequence[str], missing_peer_ids: Sequence[str], dissenting_peer_ids: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "resolution query row ordinal", MAX_QUERY_ITEMS)
        self.resource = _label(resource, "resolution query row resource")
        self.row_id = _label(row_id, "resolution query row ID")
        self.entry_id = _label(entry_id, "resolution query row entry ID", required=False)
        self.package_id = _label(package_id, "resolution query row package ID", required=False)
        self.state = _label(state, "resolution query row state")
        self.action = _label(action, "resolution query row action", required=False)
        self.selected_archive_address = _address(selected_archive_address, "resolution query row selected address", resolution_model.federation_model.registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.supporting_peer_ids = tuple(_label(item, "resolution query row supporting peer") for item in _sequence(supporting_peer_ids, "resolution query row supporting peers", resolution_model.MAX_PEERS))
        self.missing_peer_ids = tuple(_label(item, "resolution query row missing peer") for item in _sequence(missing_peer_ids, "resolution query row missing peers", resolution_model.MAX_PEERS))
        self.dissenting_peer_ids = tuple(_label(item, "resolution query row dissenting peer") for item in _sequence(dissenting_peer_ids, "resolution query row dissenting peers", resolution_model.MAX_PEERS))
        self.evidence_addresses = tuple(_text(item, "resolution query row evidence address", 2048) for item in _sequence(evidence_addresses, "resolution query row evidence", resolution_model.MAX_PEERS * 2 + 2))
        self.content_address = _address(content_address, "resolution query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "resolution query row address")
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES or self.state not in resolution_model.STATES + ("ready",) or self.action and self.action not in resolution_model.ACTIONS or not _public(self.to_dict()):
            raise ValidationError("resolution query row vocabulary is invalid")
        if not self.evidence_addresses:
            raise ValidationError("resolution query row requires evidence")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("resolution query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow":
        value = _mapping(value, "resolution query row")
        _strict(value, set(cls.FIELDS), "resolution query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult:
    FIELDS = ("query", "resolution_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery, resolution_id: str, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        self.query = query if isinstance(query, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery.from_mapping(query)
        self.resolution_id = _label(resolution_id, "resolution query result resolution ID")
        self.rows = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow.from_mapping(item) for item in _sequence(rows, "resolution query result rows", MAX_QUERY_ITEMS))
        self.total_count = _count(total_count, "resolution query total count", MAX_QUERY_ITEMS)
        self.matched_count = _count(matched_count, "resolution query matched count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "resolution query returned count", MAX_QUERY_ITEMS)
        self.next_offset = _count(next_offset, "resolution query next offset", MAX_QUERY_ITEMS)
        self.truncated = _bool(truncated, "resolution query truncation")
        self.content_address = _address(content_address, "resolution query result address", RESULT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "resolution query result address")
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.matched_count or self.next_offset != self.query.offset + self.returned_count:
            raise ValidationError("resolution query result counters are not conserved")
        if self.rows and tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)):
            raise ValidationError("resolution query result ordinals do not replay")
        if self.truncated != (self.next_offset < self.query.offset + self.matched_count):
            raise ValidationError("resolution query truncation does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("resolution query result crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("resolution query result address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "resolution_id": self.resolution_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("resolution_id", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult":
        value = _mapping(value, "resolution query result")
        _strict(value, set(cls.FIELDS), "resolution query result")
        return cls(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery.from_mapping(value["query"]), value["resolution_id"], tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow.from_mapping(item) for item in _sequence(value["rows"], "resolution query result rows", MAX_QUERY_ITEMS)), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, row_id: str, item: resolution_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionItem | None, value: resolution_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow:
    if item is None:
        body = {"ordinal": ordinal, "resource": resource, "row_id": row_id, "entry_id": "", "package_id": "", "state": "ready", "action": "", "selected_archive_address": "", "supporting_peer_ids": (), "missing_peer_ids": (), "dissenting_peer_ids": (), "evidence_addresses": (value.content_address,)}
    else:
        body = {"ordinal": ordinal, "resource": resource, "row_id": row_id, "entry_id": item.entry_id, "package_id": item.package_id, "state": item.state, "action": item.action, "selected_archive_address": item.selected_archive_address, "supporting_peer_ids": item.supporting_peer_ids, "missing_peer_ids": item.missing_peer_ids, "dissenting_peer_ids": item.dissenting_peer_ids, "evidence_addresses": item.evidence_addresses}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow(**body, content_address=address_row(provisional))


def _all_rows(value: resolution_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow, ...]:
    rows: list[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow] = []
    ordinal = 1
    selected = tuple(resources)
    if "summary" in selected:
        rows.append(_row(ordinal, "summary", value.resolution_id, None, value))
        ordinal += 1
    for item in value.items:
        item_resources = ("items", item.state)
        if any(resource in selected for resource in item_resources):
            resource = "items" if "items" in selected else item.state
            rows.append(_row(ordinal, resource, item.entry_id, item, value))
            ordinal += 1
        for resource, peer_ids in (("supporting", item.supporting_peer_ids), ("missing", item.missing_peer_ids), ("dissenting", item.dissenting_peer_ids)):
            if resource in selected:
                rows.append(_row(ordinal, resource, f"{item.entry_id}-{resource}", item, value))
                ordinal += 1
    return tuple(rows)


def _matches(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery) -> bool:
    if query.entry_id and row.entry_id != query.entry_id or query.state and row.state != query.state or query.action and row.action != query.action or query.package_id and row.package_id != query.package_id:
        return False
    if query.peer_id and query.peer_id not in row.supporting_peer_ids + row.missing_peer_ids + row.dissenting_peer_ids:
        return False
    if query.text:
        haystack = " ".join((row.row_id, row.entry_id, row.package_id, row.state, row.action, row.selected_archive_address, *row.supporting_peer_ids, *row.missing_peer_ids, *row.dissenting_peer_ids)).lower()
        if query.text.lower() not in haystack:
            return False
    return True


def _reordinal(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow, ordinal: int) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow.from_mapping(body)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow.from_mapping(provisional.to_dict() | {"content_address": address_row(provisional)})


def query_resolution(value: resolution_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolution, *, query_id: str = "consensus-certificate-observatory-archive-registry-federation-resolution-query", resources: Sequence[str] = ("summary", "items"), entry_id: str = "", state: str = "", action: str = "", peer_id: str = "", package_id: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult:
    value = resolution_model.verify_resolution(value)
    provisional_query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery(query_id, value.content_address, resources, entry_id, state, action, peer_id, package_id, text, offset, limit, QUERY_PREFIX + ":pending")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery(provisional_query.query_id, provisional_query.resolution_address, provisional_query.resources, provisional_query.entry_id, provisional_query.state, provisional_query.action, provisional_query.peer_id, provisional_query.package_id, provisional_query.text, provisional_query.offset, provisional_query.limit, address_query(provisional_query))
    rows = _all_rows(value, query.resources)
    matched = tuple(row for row in rows if _matches(row, query))
    page = tuple(_reordinal(row, query.offset + index + 1) for index, row in enumerate(matched[query.offset:query.offset + query.limit]))
    next_offset = query.offset + len(page)
    provisional_result = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult(query, value.resolution_id, page, len(rows), len(matched), len(page), next_offset, next_offset < query.offset + len(matched), RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult(query, provisional_result.resolution_id, provisional_result.rows, provisional_result.total_count, provisional_result.matched_count, provisional_result.returned_count, provisional_result.next_offset, provisional_result.truncated, address_result(provisional_result))


def query_resolution_from_mapping(value: Mapping[str, Any], **kwargs: Any) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult:
    return query_resolution(resolution_model.resolution_from_mapping(value), **kwargs)


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult:
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult.from_mapping(value)


def verify_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("resolution query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("resolution query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    fields = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow.FIELDS
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        row = item.to_dict()
        for field in fields:
            if isinstance(row[field], tuple):
                row[field] = ",".join(row[field])
        writer.writerow(row)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Archive Registry Federation Resolution Query", "", f"- Resolution: `{value.resolution_id}`", f"- Returned: `{value.returned_count}/{value.matched_count}`", f"- Next offset: `{value.next_offset}`", "", "| # | resource | row | state | action | selected |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.row_id}` | `{item.state}` | `{item.action}` | `{item.selected_archive_address}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "resolution_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "entry_id": {"type": "string"}, "state": {"enum": [""] + list(resolution_model.STATES)}, "action": {"enum": [""] + list(resolution_model.ACTIONS)}, "peer_id": {"type": "string"}, "package_id": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "row_id": {"type": "string"}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "state": {"enum": list(resolution_model.STATES) + ["ready"]}, "action": {"type": "string"}, "selected_archive_address": {"type": "string"}, "supporting_peer_ids": {"type": "array", "items": {"type": "string"}}, "missing_peer_ids": {"type": "array", "items": {"type": "string"}}, "dissenting_peer_ids": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult.FIELDS), "properties": {"query": query_schema(), "resolution_id": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "operations": ("query_resolution", "query_resolution_from_mapping", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "verify_query_result"), "resources": RESOURCES, "max_items": MAX_QUERY_ITEMS}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQuery", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryResult", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationResolutionQueryRow", "address_query", "address_result", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_resolution", "query_resolution_from_mapping", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_query", "verify_query_result"]
