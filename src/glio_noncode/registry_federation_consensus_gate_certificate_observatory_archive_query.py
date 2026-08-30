"""Bounded inspection queries for certificate-observatory archives.

Archive bytes are the source of truth for transport.  Queries are derived
views for operators: they expose the manifest, package identity, artifact
receipts, and nested evidence without opening the ZIP again.  Every row and
page is content-addressed, resources are selected before pagination, and all
filters are bounded so a public endpoint cannot accidentally become an
unbounded file browser.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = archive_model.VERSION + "-query-v1"
BOUNDARY = archive_model.BOUNDARY + "_query"
QUERY_PREFIX = archive_model.ARCHIVE_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
RESOURCE_NAMES = ("summary", "artifacts", "files", "package", "evidence")
DEFAULT_RESOURCES = RESOURCE_NAMES
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_OFFSET = 100000
MAX_TEXT = 512
MAX_QUERY_ITEMS = 4096


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048, required=True)
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
    return value


def _public(value: Any) -> bool:
    return archive_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveQuery:
    """A bounded, addressed archive query request."""

    FIELDS = ("resources", "name", "text", "offset", "limit", "content_address")

    def __init__(self, resources: Sequence[str], name: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, content_address: str = QUERY_PREFIX + ":pending") -> None:
        self.resources = tuple(_text(item, "query resource", 64, required=True) for item in _sequence(resources, "query resources", len(RESOURCE_NAMES)))
        if not self.resources or any(item not in RESOURCE_NAMES for item in self.resources) or len(set(self.resources)) != len(self.resources):
            raise ValidationError("query resources are not declared or are duplicated")
        self.name = _text(name, "query name")
        self.text = _text(text, "query text")
        self.offset = _count(offset, "query offset", MAX_OFFSET)
        self.limit = _count(limit, "query limit", MAX_LIMIT)
        if self.limit == 0:
            raise ValidationError("query limit must be positive")
        self.content_address = _address(content_address, "query address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}


class RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow:
    """One public row returned by an archive query."""

    FIELDS = ("resource", "ordinal", "payload", "content_address")

    def __init__(self, resource: str, ordinal: int, payload: Mapping[str, Any], content_address: str = ROW_PREFIX + ":pending") -> None:
        self.resource = _text(resource, "query row resource", 64, required=True)
        if self.resource not in RESOURCE_NAMES:
            raise ValidationError("query row resource is not declared")
        self.ordinal = _count(ordinal, "query row ordinal", MAX_OFFSET + MAX_LIMIT)
        self.payload = dict(_mapping(payload, "query row payload"))
        if not _public(self.payload):
            raise ValidationError("query row crosses the public boundary")
        self.content_address = _address(content_address, "query row address", ROW_PREFIX)
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "ordinal": self.ordinal, "payload": self.payload, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow":
        value = _mapping(value, "query row")
        _strict(value, set(cls.FIELDS), "query row")
        return cls(value["resource"], value["ordinal"], value["payload"], value["content_address"])


class RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult:
    """An addressed page with conservation counters."""

    FIELDS = ("query", "rows", "total", "matched", "returned", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveQuery, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow], total: int, matched: int, returned: int, next_offset: int | None, truncated: bool, content_address: str = RESULT_PREFIX + ":pending") -> None:
        if not isinstance(query, RegistryFederationConsensusGateCertificateObservatoryArchiveQuery):
            raise ValidationError("query result requires a typed query")
        self.query = query
        self.rows = tuple(rows)
        self.total = _count(total, "query total", MAX_QUERY_ITEMS)
        self.matched = _count(matched, "query matched", MAX_QUERY_ITEMS)
        self.returned = _count(returned, "query returned", MAX_LIMIT)
        self.next_offset = None if next_offset is None else _count(next_offset, "query next offset", MAX_OFFSET)
        if self.returned != len(self.rows) or self.matched > self.total or self.returned > self.matched or self.returned > self.query.limit or self.next_offset != (self.query.offset + self.returned if self.query.offset + self.returned < self.query.offset + self.matched else None) or truncated != (self.next_offset is not None):
            raise ValidationError("query result counters are not conserved")
        self.truncated = bool(truncated) if isinstance(truncated, bool) else (_ for _ in ()).throw(ValidationError("query truncation state must be boolean"))
        self.content_address = _address(content_address, "query result address", RESULT_PREFIX)
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("query result address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "rows": tuple(row.to_dict() for row in self.rows), "total": self.total, "matched": self.matched, "returned": self.returned, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("total", "matched", "returned", "next_offset", "truncated", "content_address")}


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQuery) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveQuery):
        raise ValidationError("query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow):
        raise ValidationError("row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult):
        raise ValidationError("result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(resource: str, ordinal: int, payload: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow(resource, ordinal, payload)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow(resource, ordinal, payload, address_row(provisional))


def _records(value: archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive, resource: str) -> tuple[Mapping[str, Any], ...]:
    if resource == "summary":
        return (value.summary() | {"archive_address": value.content_address},)
    if resource in ("artifacts", "files"):
        return tuple(item.to_dict() | {"archive_address": value.content_address, "resource": resource} for item in value.artifacts)
    if resource == "package":
        package_summary = value.package.summary() if value.package is not None else {"package_id": value.package_id, "content_address": value.package_address}
        return (dict(package_summary) | {"archive_address": value.content_address, "resource": resource},)
    evidence = [{"archive_address": value.content_address, "package_address": value.package_address, "member": item.name, "evidence_address": item.hash} for item in value.artifacts]
    return tuple(evidence)


def query_archive(value: archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive, *, resources: Sequence[str] = DEFAULT_RESOURCES, name: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult:
    archive_model.verify_archive(value)
    pending = RegistryFederationConsensusGateCertificateObservatoryArchiveQuery(resources, name, text, offset, limit)
    request = RegistryFederationConsensusGateCertificateObservatoryArchiveQuery(resources, name, text, offset, limit, address_query(pending))
    selected: list[tuple[str, Mapping[str, Any]]] = []
    for resource in request.resources:
        selected.extend((resource, record) for record in _records(value, resource))
    if len(selected) > MAX_QUERY_ITEMS:
        raise ValidationError("query source exceeds its bounded item limit")
    filtered = [(resource, record) for resource, record in selected if (not request.name or str(record.get("name", "")) == request.name) and (not request.text or request.text.lower() in canonical_json(record).lower())]
    page = filtered[request.offset:request.offset + request.limit]
    rows = tuple(_row(resource, request.offset + ordinal, record) for ordinal, (resource, record) in enumerate(page))
    next_offset = request.offset + len(page) if request.offset + len(page) < request.offset + len(filtered) else None
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult(request, rows, len(selected), len(filtered), len(rows), next_offset, next_offset is not None)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult(request, rows, len(selected), len(filtered), len(rows), next_offset, next_offset is not None, address_result(provisional))


def query_archive_from_mapping(value: Mapping[str, Any], **kwargs: Any) -> RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult:
    return query_archive(archive_model.archive_from_mapping(value), **kwargs)


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult:
    value = _mapping(value, "archive query result")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult.FIELDS), "archive query result")
    query_value = _mapping(value["query"], "archive query")
    _strict(query_value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveQuery.FIELDS), "archive query")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveQuery(query_value["resources"], query_value["name"], query_value["text"], query_value["offset"], query_value["limit"], query_value["content_address"])
    rows = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow.from_mapping(item) for item in _sequence(value["rows"], "archive query rows", MAX_LIMIT))
    return verify_result(RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult(query, rows, value["total"], value["matched"], value["returned"], value["next_offset"], value["truncated"], value["content_address"]))


def verify_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("archive query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult) -> str:
    return canonical_json(verify_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult) -> str:
    value = verify_result(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("resource", "ordinal", "payload", "content_address"), lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow({"resource": row.resource, "ordinal": row.ordinal, "payload": canonical_json(row.payload), "content_address": row.content_address})
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult) -> str:
    value = verify_result(value)
    lines = ["# Certificate Observatory Archive Query", "", f"- Resources: `{', '.join(value.query.resources)}`", f"- Matched: `{value.matched}`", f"- Returned: `{value.returned}`", f"- Next offset: `{value.next_offset}`", f"- Address: `{value.content_address}`", "", "| resource | ordinal | row address | payload |", "| --- | ---: | --- | --- |"]
    lines.extend(f"| `{row.resource}` | `{row.ordinal}` | `{row.content_address}` | `{canonical_json(row.payload)}` |" for row in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveQuery.FIELDS), "properties": {"resources": {"type": "array", "items": {"type": "string", "enum": list(RESOURCE_NAMES)}}, "name": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow.FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCE_NAMES)}, "ordinal": {"type": "integer", "minimum": 0}, "payload": {"type": "object"}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult.FIELDS), "properties": {"query": query_schema(), "rows": {"type": "array", "items": row_schema()}, "total": {"type": "integer"}, "matched": {"type": "integer"}, "returned": {"type": "integer"}, "next_offset": {"type": ["integer", "null"]}, "truncated": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RESULT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "result_prefix": RESULT_PREFIX, "resources": RESOURCE_NAMES, "features": ("bounded resource selection", "exact name and text filtering", "stable row addresses", "conserved pagination counters", "JSON CSV and Markdown exports", "path-free public rows"), "schemas": ("query", "row", "result")}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RESOURCES", "MAX_LIMIT", "QUERY_PREFIX", "RESOURCE_NAMES", "RESULT_PREFIX", "ROW_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchiveQuery", "RegistryFederationConsensusGateCertificateObservatoryArchiveQueryResult", "RegistryFederationConsensusGateCertificateObservatoryArchiveQueryRow", "VERSION", "address_query", "address_result", "address_row", "capabilities", "query_archive", "query_archive_from_mapping", "query_csv", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_result"]
