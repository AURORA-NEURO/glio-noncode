"""Bounded inspection queries for archive-registry diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
RESOURCES = ("summary", "items", "added", "removed", "changed")
DEFAULT_RESOURCES = RESOURCES
DEFAULT_LIMIT = 50
MAX_LIMIT = 4096


def _text(value: Any, field: str, maximum: int = 2048, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
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


def _public(value: Any) -> bool:
    return diff_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery:
    FIELDS = ("query_id", "diff_address", "resources", "change_type", "text", "offset", "limit", "content_address")

    def __init__(self, query_id: str, diff_address: str, resources: Sequence[str], change_type: str, text: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "diff query ID")
        self.diff_address = _address(diff_address, "diff query diff address", diff_model.DIFF_PREFIX)
        self.resources = tuple(_label(item, "diff query resource") for item in _sequence(resources, "diff query resources", len(RESOURCES)))
        self.change_type = _label(change_type, "diff query change type", required=False)
        self.text = _text(text, "diff query text", 256, required=False)
        self.offset = _count(offset, "diff query offset", MAX_LIMIT)
        self.limit = _count(limit, "diff query limit", MAX_LIMIT, positive=True)
        self.content_address = _address(content_address, "diff query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff query address")
        self._validate()

    def _validate(self) -> None:
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources):
            raise ValidationError("diff query resources are invalid")
        if self.change_type and self.change_type not in diff_model.CHANGE_TYPES:
            raise ValidationError("diff query change type is invalid")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("diff query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery":
        value = _mapping(value, "diff query")
        _strict(value, set(cls.FIELDS), "diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery):
        raise ValidationError("diff query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow:
    FIELDS = ("ordinal", "resource", "item_id", "change_type", "entry_id", "archive_id", "left_address", "right_address", "changed_fields", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, item_id: str, change_type: str, entry_id: str, archive_id: str, left_address: str, right_address: str, changed_fields: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff query row ordinal", MAX_LIMIT, positive=True)
        self.resource = _label(resource, "diff query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("diff query row resource is invalid")
        self.item_id = _address(item_id, "diff query row ID")
        if change_type not in diff_model.CHANGE_TYPES:
            raise ValidationError("diff query row change type is invalid")
        self.change_type = change_type
        self.entry_id = _label(entry_id, "diff query row entry ID")
        self.archive_id = _label(archive_id, "diff query row archive ID")
        self.left_address = _address(left_address, "diff query row left address", diff_model.registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.right_address = _address(right_address, "diff query row right address", diff_model.registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.changed_fields = tuple(_label(item, "diff query row changed field") for item in _sequence(changed_fields, "diff query row changed fields", 64))
        self.evidence_addresses = tuple(_address(item, "diff query row evidence address") for item in _sequence(evidence_addresses, "diff query row evidence", 8))
        self.content_address = _address(content_address, "diff query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff query row address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or len(set(self.changed_fields)) != len(self.changed_fields):
            raise ValidationError("diff query row evidence or fields are invalid")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("diff query row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow":
        value = _mapping(value, "diff query row")
        _strict(value, set(cls.FIELDS), "diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow):
        raise ValidationError("diff query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult:
    FIELDS = ("query", "diff_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery, diff_id: str, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        self.query = query if isinstance(query, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery.from_mapping(query)
        self.diff_id = _label(diff_id, "diff query result diff ID")
        self.rows = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow.from_mapping(item) for item in _sequence(rows, "diff query result rows", MAX_LIMIT))
        self.total_count = _count(total_count, "diff query total count", MAX_LIMIT)
        self.matched_count = _count(matched_count, "diff query matched count", MAX_LIMIT)
        self.returned_count = _count(returned_count, "diff query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "diff query next offset", MAX_LIMIT)
        if not isinstance(truncated, bool):
            raise ValidationError("diff query truncation must be boolean")
        self.truncated = truncated
        self.content_address = _address(content_address, "diff query result address", RESULT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff query result address")
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.matched_count or self.next_offset != self.query.offset + self.returned_count or self.truncated != (self.next_offset < self.query.offset + self.matched_count):
            raise ValidationError("diff query result counters are not conserved")
        if self.rows and tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)):
            raise ValidationError("diff query result ordinals are not exact")
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("diff query result address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff query result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "diff_id": self.diff_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("diff_id", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult":
        value = _mapping(value, "diff query result")
        _strict(value, set(cls.FIELDS), "diff query result")
        query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery.from_mapping(value["query"])
        rows = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow.from_mapping(item) for item in _sequence(value["rows"], "diff query result rows", MAX_LIMIT))
        return cls(query, value["diff_id"], rows, value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult):
        raise ValidationError("diff query result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, item: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffItem) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "item_id": item.content_address, "change_type": item.change_type, "entry_id": item.entry_id, "archive_id": item.archive_id, "left_address": item.left_address, "right_address": item.right_address, "changed_fields": item.changed_fields, "evidence_addresses": tuple(address for address in (item.left_address, item.right_address, item.left_entry_address, item.right_entry_address) if address)}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow(**body, content_address=address_row(provisional))


def _summary_row(ordinal: int, value: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow:
    body = {"ordinal": ordinal, "resource": "summary", "item_id": value.content_address, "change_type": "changed", "entry_id": "summary", "archive_id": "summary", "left_address": "", "right_address": "", "changed_fields": ("added_count", "removed_count", "changed_count", "unchanged_count"), "evidence_addresses": (value.left_registry_address, value.right_registry_address)}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow(**body, content_address=address_row(provisional))


def _matches(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery) -> bool:
    if query.change_type and row.change_type != query.change_type:
        return False
    if query.text and query.text.lower() not in " ".join((row.item_id, row.entry_id, row.archive_id, row.change_type, *row.changed_fields)).lower():
        return False
    return True


def query_diff(value: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiff, *, query_id: str = "consensus-certificate-observatory-archive-registry-diff-query", resources: Sequence[str] = DEFAULT_RESOURCES, change_type: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult:
    value = diff_model.verify_diff(value)
    provisional_query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery(query_id, value.content_address, resources, change_type, text, offset, limit, QUERY_PREFIX + ":pending")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery(provisional_query.query_id, provisional_query.diff_address, provisional_query.resources, provisional_query.change_type, provisional_query.text, provisional_query.offset, provisional_query.limit, address_query(provisional_query))
    all_items = tuple(value.items)
    rows = []
    if "summary" in query.resources:
        rows.append(_summary_row(1, value))
    for item in all_items:
        selected_resource = "items" if "items" in query.resources else item.change_type if item.change_type in query.resources else ""
        if selected_resource:
            rows.append(_row(len(rows) + 1, selected_resource, item))
    matched = tuple(row for row in rows if _matches(row, query))
    page = matched[query.offset:query.offset + query.limit]
    provisional_result = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult(query, value.diff_id, page, len(rows), len(matched), len(page), query.offset + len(page), query.offset + len(page) < query.offset + len(matched), RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult(provisional_result.query, provisional_result.diff_id, provisional_result.rows, provisional_result.total_count, provisional_result.matched_count, provisional_result.returned_count, provisional_result.next_offset, provisional_result.truncated, address_result(provisional_result))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult:
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult.from_mapping(value)


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("diff query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    fields = ("ordinal", "resource", "item_id", "change_type", "entry_id", "archive_id", "left_address", "right_address", "changed_fields", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        row = item.to_dict()
        row["changed_fields"] = ",".join(row["changed_fields"])
        writer.writerow({field: row[field] for field in fields})
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Certificate Observatory Archive Registry Diff Query", "", f"- Diff: `{value.diff_id}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Truncated: `{value.truncated}`", "", "| # | resource | change | archive | fields |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.resource}` | `{item.change_type}` | `{item.archive_id}` | `{', '.join(item.changed_fields) or '—'}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "diff_address": {"type": "string"}, "resources": {"type": "array", "items": {"type": "string", "enum": list(RESOURCES)}}, "change_type": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"type": "string", "enum": list(RESOURCES)}, "item_id": {"type": "string"}, "change_type": {"type": "string", "enum": list(diff_model.CHANGE_TYPES)}, "entry_id": {"type": "string"}, "archive_id": {"type": "string"}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "changed_fields": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult.FIELDS), "properties": {"query": query_schema(), "diff_id": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer"}, "matched_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "next_offset": {"type": "integer"}, "truncated": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RESULT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "result_prefix": RESULT_PREFIX, "resources": RESOURCES, "change_types": diff_model.CHANGE_TYPES, "filters": ("change_type", "text", "offset", "limit"), "limits": {"max_limit": MAX_LIMIT}, "features": ("summary rows", "all change rows", "added removed and changed views", "bounded pagination", "evidence-linked rows", "JSON CSV and Markdown exports"), "schemas": ("query", "row", "result")}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RESOURCES", "MAX_LIMIT", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQuery", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryResult", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryDiffQueryRow", "VERSION", "address_query", "address_result", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_diff", "query_json", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_query_result"]
