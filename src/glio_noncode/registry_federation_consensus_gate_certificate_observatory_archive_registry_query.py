"""Bounded inspection queries for certificate-observatory archive registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from . import registry_federation_consensus_gate_certificate_observatory_package as package_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-query-v1"
BOUNDARY = registry_model.BOUNDARY + "_query"
QUERY_PREFIX = registry_model.REGISTRY_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
RESOURCES = ("summary", "entries", "accepted", "held", "packages")
DEFAULT_RESOURCES = RESOURCES
DEFAULT_LIMIT = registry_model.DEFAULT_LIMIT
MAX_LIMIT = registry_model.MAX_QUERY_ITEMS
MAX_TEXT = 256


def _text(value: Any, field: str, maximum: int = 512, *, required: bool = True) -> str:
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
        raise ValidationError(f"{field} must be a public address")
    if value and prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
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
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery:
    """An immutable bounded filter over a registry."""

    FIELDS = ("query_id", "registry_address", "resources", "package_id", "archive_id", "accepted", "text", "offset", "limit", "content_address")

    def __init__(self, query_id: str, registry_address: str, resources: Sequence[str], package_id: str, archive_id: str, accepted: bool | None, text: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "registry query ID")
        self.registry_address = _address(registry_address, "registry query registry address", registry_model.REGISTRY_PREFIX)
        self.resources = tuple(_label(item, "registry query resource") for item in _sequence(resources, "registry query resources", len(RESOURCES)))
        self.package_id = _label(package_id, "registry query package ID", required=False)
        self.archive_id = _label(archive_id, "registry query archive ID", required=False)
        self.accepted = _optional_bool(accepted, "registry query accepted filter")
        self.text = _text(text, "registry query text", MAX_TEXT, required=False)
        self.offset = _count(offset, "registry query offset", registry_model.MAX_QUERY_ITEMS)
        self.limit = _count(limit, "registry query limit", MAX_LIMIT, positive=True)
        self.content_address = _address(content_address, "registry query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry query address")
        self._validate()

    def _validate(self) -> None:
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources):
            raise ValidationError("registry query resources are invalid")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("registry query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery":
        value = _mapping(value, "registry query")
        _strict(value, set(cls.FIELDS), "registry query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery):
        raise ValidationError("registry query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow:
    """One bounded row with explicit evidence links."""

    FIELDS = ("ordinal", "resource", "row_id", "entry_id", "archive_id", "archive_address", "package_id", "package_address", "archive_size", "accepted", "observation_count", "total_check_count", "total_failed_count", "alert_count", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, entry_id: str, archive_id: str, archive_address: str, package_id: str, package_address: str, archive_size: int, accepted: bool, observation_count: int, total_check_count: int, total_failed_count: int, alert_count: int, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "registry query row ordinal", registry_model.MAX_QUERY_ITEMS, positive=True)
        self.resource = _label(resource, "registry query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("registry query row resource is unsupported")
        self.row_id = _label(row_id, "registry query row ID")
        self.entry_id = _label(entry_id, "registry query row entry ID", required=False)
        self.archive_id = _label(archive_id, "registry query row archive ID", required=False)
        self.archive_address = _address(archive_address, "registry query row archive address", registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.package_id = _label(package_id, "registry query row package ID", required=False)
        self.package_address = _address(package_address, "registry query row package address", package_model.PACKAGE_PREFIX, required=False)
        self.archive_size = _count(archive_size, "registry query row archive size", registry_model.MAX_TOTAL_ARCHIVE_BYTES)
        self.accepted = _bool(accepted, "registry query row accepted")
        self.observation_count = _count(observation_count, "registry query row observations", 65536)
        self.total_check_count = _count(total_check_count, "registry query row checks", 2_000_000_000)
        self.total_failed_count = _count(total_failed_count, "registry query row failed checks", self.total_check_count)
        self.alert_count = _count(alert_count, "registry query row alerts", 4096)
        self.evidence_addresses = tuple(_address(item, "registry query row evidence address") for item in _sequence(evidence_addresses, "registry query row evidence", 512))
        self.content_address = _address(content_address, "registry query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry query row address")
        self._validate()

    def _validate(self) -> None:
        if self.total_failed_count > self.total_check_count or not self.evidence_addresses:
            raise ValidationError("registry query row counters or evidence are invalid")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("registry query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow":
        value = _mapping(value, "registry query row")
        _strict(value, set(cls.FIELDS), "registry query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow):
        raise ValidationError("registry query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult:
    """Addressed page returned by a registry query."""

    FIELDS = ("query", "registry_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery, registry_id: str, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        self.query = query if isinstance(query, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery.from_mapping(query)
        self.registry_id = _label(registry_id, "registry query result registry ID")
        self.rows = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow.from_mapping(item) for item in _sequence(rows, "registry query result rows", registry_model.MAX_QUERY_ITEMS))
        self.total_count = _count(total_count, "registry query total count", registry_model.MAX_QUERY_ITEMS)
        self.matched_count = _count(matched_count, "registry query matched count", registry_model.MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "registry query returned count", registry_model.MAX_QUERY_ITEMS)
        self.next_offset = _count(next_offset, "registry query next offset", registry_model.MAX_QUERY_ITEMS)
        self.truncated = _bool(truncated, "registry query truncation")
        self.content_address = _address(content_address, "registry query result address", RESULT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry query result address")
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.matched_count:
            raise ValidationError("registry query result counters are not conserved")
        if self.rows and tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)):
            raise ValidationError("registry query result row ordinals are not conserved")
        if self.truncated != (self.next_offset < self.query.offset + self.matched_count):
            raise ValidationError("registry query truncation does not replay")
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("registry query result address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry query result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "registry_id": self.registry_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("registry_id", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult":
        value = _mapping(value, "registry query result")
        _strict(value, set(cls.FIELDS), "registry query result")
        query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery.from_mapping(value["query"])
        rows = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow.from_mapping(item) for item in _sequence(value["rows"], "registry query result rows", registry_model.MAX_QUERY_ITEMS))
        return cls(query, value["registry_id"], rows, value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult):
        raise ValidationError("registry query result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, row_id: str, *, entry_id: str = "", archive_id: str = "", archive_address: str = "", package_id: str = "", package_address: str = "", archive_size: int = 0, accepted: bool = False, observation_count: int = 0, total_check_count: int = 0, total_failed_count: int = 0, alert_count: int = 0, evidence_addresses: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "row_id": row_id, "entry_id": entry_id, "archive_id": archive_id, "archive_address": archive_address, "package_id": package_id, "package_address": package_address, "archive_size": archive_size, "accepted": accepted, "observation_count": observation_count, "total_check_count": total_check_count, "total_failed_count": total_failed_count, "alert_count": alert_count, "evidence_addresses": tuple(evidence_addresses)}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow(**body, content_address=address_row(provisional))


def _all_rows(value: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow, ...]:
    rows: list[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow] = []
    ordinal = 1
    selected = tuple(resources)
    if "summary" in selected:
        metrics = value.metrics
        rows.append(_row(ordinal, "summary", value.registry_id, archive_size=metrics.archive_bytes, accepted=metrics.held_count == 0, observation_count=metrics.observation_count, total_check_count=metrics.total_check_count, total_failed_count=metrics.total_failed_count, alert_count=metrics.alert_count, evidence_addresses=(value.content_address, value.index.content_address)))
        ordinal += 1
    if any(item in selected for item in ("entries", "accepted", "held")):
        for entry in value.entries:
            if "entries" in selected:
                resource = "entries"
            elif entry.accepted and "accepted" in selected:
                resource = "accepted"
            elif not entry.accepted and "held" in selected:
                resource = "held"
            else:
                continue
            rows.append(_row(ordinal, resource, entry.entry_id, entry_id=entry.entry_id, archive_id=entry.archive_id, archive_address=entry.archive_address, package_id=entry.package_id, package_address=entry.package_address, archive_size=entry.archive_size, accepted=entry.accepted, observation_count=entry.observation_count, total_check_count=entry.total_check_count, total_failed_count=entry.total_failed_count, alert_count=entry.alert_count, evidence_addresses=(entry.content_address, entry.archive_address, entry.package_address)))
            ordinal += 1
    if "packages" in selected:
        entries_by_package = {group.package_id: tuple(value.entry(entry_id) for entry_id in group.entry_ids) for group in value.index.groups}
        for package_id in sorted(entries_by_package):
            entries = entries_by_package[package_id]
            first = entries[0]
            rows.append(_row(ordinal, "packages", package_id, package_id=package_id, package_address=first.package_address, archive_size=sum(item.archive_size for item in entries), accepted=all(item.accepted for item in entries), observation_count=sum(item.observation_count for item in entries), total_check_count=sum(item.total_check_count for item in entries), total_failed_count=sum(item.total_failed_count for item in entries), alert_count=sum(item.alert_count for item in entries), evidence_addresses=tuple(item.content_address for item in entries) + (value.index.content_address,)))
            ordinal += 1
    return tuple(rows)


def _matches(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery) -> bool:
    if query.package_id and row.package_id != query.package_id:
        return False
    if query.archive_id and row.archive_id != query.archive_id:
        return False
    if query.accepted is not None and row.accepted != query.accepted:
        return False
    if query.text:
        haystack = " ".join((row.row_id, row.entry_id, row.archive_id, row.package_id, row.archive_address, row.package_address)).lower()
        if query.text.lower() not in haystack:
            return False
    return True


def _reordinal(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow, ordinal: int) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow:
    """Re-address a filtered row against its deterministic result position."""

    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow.from_mapping(body)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow.from_mapping(provisional.to_dict() | {"content_address": address_row(provisional)})


def query_registry(value: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry, *, query_id: str = "consensus-certificate-observatory-archive-registry-query", resources: Sequence[str] = DEFAULT_RESOURCES, package_id: str = "", archive_id: str = "", accepted: bool | None = None, text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult:
    value = registry_model.verify_registry(value)
    selected_resources = tuple(resources)
    provisional_query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery(query_id, value.content_address, selected_resources, package_id, archive_id, accepted, text, offset, limit, QUERY_PREFIX + ":pending")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery(provisional_query.query_id, provisional_query.registry_address, provisional_query.resources, provisional_query.package_id, provisional_query.archive_id, provisional_query.accepted, provisional_query.text, provisional_query.offset, provisional_query.limit, address_query(provisional_query))
    rows = _all_rows(value, query.resources)
    matched = tuple(row for row in rows if _matches(row, query))
    page = tuple(_reordinal(row, query.offset + index + 1) for index, row in enumerate(matched[query.offset:query.offset + query.limit]))
    next_offset = query.offset + len(page)
    truncated = next_offset < query.offset + len(matched)
    provisional_result = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult(query, value.registry_id, page, len(rows), len(matched), len(page), next_offset, truncated, RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult(query, provisional_result.registry_id, provisional_result.rows, provisional_result.total_count, provisional_result.matched_count, provisional_result.returned_count, provisional_result.next_offset, provisional_result.truncated, address_result(provisional_result))


def query_registry_from_mapping(value: Mapping[str, Any], **kwargs: Any) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult:
    return query_registry(registry_model.registry_from_mapping(value), **kwargs)


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult:
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult.from_mapping(value)


def verify_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("registry query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("registry query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    fields = ("ordinal", "resource", "row_id", "entry_id", "archive_id", "archive_address", "package_id", "package_address", "archive_size", "accepted", "observation_count", "total_check_count", "total_failed_count", "alert_count", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        writer.writerow({field: item.to_dict()[field] for field in fields})
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Certificate Observatory Archive Registry Query", "", f"- Registry: `{value.registry_id}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Next offset: `{value.next_offset}`", f"- Truncated: `{value.truncated}`", "", "| # | resource | row | package | accepted | bytes |", "| ---: | --- | --- | --- | ---: | ---: |"]
    lines.extend(f"| `{item.ordinal}` | `{item.resource}` | `{item.row_id}` | `{item.package_id}` | `{str(item.accepted).lower()}` | `{item.archive_size}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "registry_address": {"type": "string"}, "resources": {"type": "array", "items": {"type": "string", "enum": list(RESOURCES)}}, "package_id": {"type": "string"}, "archive_id": {"type": "string"}, "accepted": {"type": ["boolean", "null"]}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"type": "string", "enum": list(RESOURCES)}, "row_id": {"type": "string"}, "entry_id": {"type": "string"}, "archive_id": {"type": "string"}, "archive_address": {"type": "string"}, "package_id": {"type": "string"}, "package_address": {"type": "string"}, "archive_size": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "observation_count": {"type": "integer", "minimum": 0}, "total_check_count": {"type": "integer", "minimum": 0}, "total_failed_count": {"type": "integer", "minimum": 0}, "alert_count": {"type": "integer", "minimum": 0}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult.FIELDS), "properties": {"query": query_schema(), "registry_id": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RESULT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "result_prefix": RESULT_PREFIX, "resources": RESOURCES, "limits": {"max_limit": MAX_LIMIT, "max_query_items": registry_model.MAX_QUERY_ITEMS}, "filters": ("package_id", "archive_id", "accepted", "text", "offset", "limit"), "features": ("summary rows", "archive entry rows", "accepted and held views", "package-group rows", "bounded pagination", "evidence-linked rows", "JSON CSV and Markdown exports"), "schemas": ("query", "row", "result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "DEFAULT_RESOURCES",
    "MAX_LIMIT",
    "QUERY_PREFIX",
    "RESOURCES",
    "RESULT_PREFIX",
    "ROW_PREFIX",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQuery",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryResult",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryQueryRow",
    "VERSION",
    "address_query",
    "address_result",
    "address_row",
    "capabilities",
    "query_csv",
    "query_from_mapping",
    "query_json",
    "query_registry",
    "query_registry_from_mapping",
    "query_schema",
    "render_query_markdown",
    "result_schema",
    "row_schema",
    "verify_query",
    "verify_query_result",
]
