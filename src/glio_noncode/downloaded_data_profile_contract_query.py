"""Bounded value-free queries over inferred downloaded-data contracts."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile as profile_model
from . import downloaded_data_profile_contract as contract_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "types", "members", "fields", "issues")
MAX_TEXT = 512
MAX_LIMIT = 10_000
MAX_TOTAL_COUNT = 1 + len(profile_model.VALUE_TYPES) + profile_model.MAX_MEMBERS + profile_model.MAX_FIELDS * 2
QUERY_FIELDS = (
    "contract_address",
    "version",
    "boundary",
    "resources",
    "member_name",
    "data_kind",
    "field_name",
    "value_type",
    "state",
    "required",
    "type_consistent",
    "text",
    "offset",
    "limit",
    "total_count",
    "matched_count",
    "returned_count",
    "next_offset",
    "truncated",
    "rows",
    "content_address",
)
ROW_FIELDS = (
    "ordinal",
    "resource",
    "field_name",
    "member_name",
    "member_address",
    "data_kind",
    "value_type",
    "state",
    "issue",
    "required",
    "type_consistent",
    "observed_count",
    "missing_count",
    "member_count",
    "count",
    "field_count",
    "record_count",
    "required_field_count",
    "optional_field_count",
    "mixed_type_field_count",
    "sparse_field_count",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048, required=True)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
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
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractQueryRow:
    """One bounded contract query row with no source values."""

    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, field_name: str, member_name: str, member_address: str, data_kind: str, value_type: str, state: str, issue: str, required: bool, type_consistent: bool, observed_count: int, missing_count: int, member_count: int, count: int, field_count: int, record_count: int, required_field_count: int, optional_field_count: int, mixed_type_field_count: int, sparse_field_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "contract query row ordinal", MAX_LIMIT, positive=True)
        self.resource = _label(resource, "contract query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("contract query row resource is unsupported")
        self.field_name = ingestion_model._key(field_name, "contract query row field name") if field_name else ""
        self.member_name = ingestion_model._safe_member_name(member_name, "contract query row member name") if member_name else ""
        self.member_address = _address(member_address, "contract query row member address") if member_address else ""
        self.data_kind = _label(data_kind, "contract query row data kind") if data_kind else ""
        if self.data_kind and self.data_kind not in ingestion_model.DATA_KINDS:
            raise ValidationError("contract query row data kind is unsupported")
        self.value_type = _label(value_type, "contract query row value type") if value_type else ""
        if self.value_type and self.value_type not in profile_model.VALUE_TYPES:
            raise ValidationError("contract query row value type is unsupported")
        self.state = _label(state, "contract query row state") if state else ""
        if self.state and self.state not in contract_model.STATES:
            raise ValidationError("contract query row state is unsupported")
        self.issue = _label(issue, "contract query row issue") if issue else ""
        self.required = _bool(required, "contract query row required state")
        self.type_consistent = _bool(type_consistent, "contract query row type consistency")
        self.observed_count = _count(observed_count, "contract query row observed count", profile_model.MAX_RECORDS)
        self.missing_count = _count(missing_count, "contract query row missing count", profile_model.MAX_RECORDS)
        self.member_count = _count(member_count, "contract query row member count", profile_model.MAX_MEMBERS)
        self.count = _count(count, "contract query row count", profile_model.MAX_TOTAL_RECORDS)
        self.field_count = _count(field_count, "contract query row field count", profile_model.MAX_FIELDS)
        self.record_count = _count(record_count, "contract query row record count", profile_model.MAX_RECORDS)
        self.required_field_count = _count(required_field_count, "contract query row required field count", profile_model.MAX_FIELDS)
        self.optional_field_count = _count(optional_field_count, "contract query row optional field count", profile_model.MAX_FIELDS)
        self.mixed_type_field_count = _count(mixed_type_field_count, "contract query row mixed field count", profile_model.MAX_FIELDS)
        self.sparse_field_count = _count(sparse_field_count, "contract query row sparse field count", profile_model.MAX_FIELDS)
        self.content_address = _address(content_address, "contract query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract query row address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary":
            if any((self.field_name, self.member_name, self.member_address, self.data_kind, self.value_type, self.state, self.issue, self.required, self.type_consistent, self.observed_count, self.missing_count, self.count)):
                raise ValidationError("summary contract query row has detail-only fields")
        elif self.resource == "types":
            if not self.value_type or any((self.field_name, self.member_name, self.member_address, self.data_kind, self.state, self.issue, self.required, self.type_consistent, self.observed_count, self.missing_count, self.record_count, self.required_field_count, self.optional_field_count, self.mixed_type_field_count, self.sparse_field_count)):
                raise ValidationError("type contract query row is incomplete")
        elif self.resource == "members":
            if not self.member_name or not self.member_address or not self.data_kind or any((self.field_name, self.value_type, self.state, self.issue, self.observed_count, self.missing_count, self.member_count, self.count, self.sparse_field_count)):
                raise ValidationError("member contract query row is incomplete")
        elif self.resource == "fields":
            if not self.field_name or not self.state or not self.observed_count + self.missing_count or any((self.member_name, self.member_address, self.data_kind, self.issue, self.record_count, self.required_field_count, self.optional_field_count, self.mixed_type_field_count, self.sparse_field_count)):
                raise ValidationError("field contract query row is incomplete")
        elif self.resource == "issues":
            if not self.field_name or self.state not in {"sparse", "mixed"} or not self.issue or any((self.member_name, self.member_address, self.data_kind, self.record_count, self.required_field_count, self.optional_field_count, self.mixed_type_field_count, self.sparse_field_count)):
                raise ValidationError("issue contract query row is incomplete")
        if not _public(self.to_dict()):
            raise ValidationError("contract query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("contract query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractQueryRow:
        value = _mapping(value, "contract query row")
        _strict(value, set(cls.FIELDS), "contract query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractQuery:
    """Content-addressed bounded selection of contract resources."""

    FIELDS = QUERY_FIELDS

    def __init__(self, contract_address: str, version: str, boundary: str, resources: Sequence[str], member_name: str, data_kind: str, field_name: str, value_type: str, state: str, required: bool, type_consistent: bool, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.contract_address = _address(contract_address, "contract query contract address", contract_model.CONTRACT_PREFIX)
        self.version = _text(version, "contract query version", required=True)
        self.boundary = _text(boundary, "contract query boundary", 512, required=True)
        self.resources = tuple(_label(item, "contract query resource") for item in _sequence(resources, "contract query resources", len(RESOURCES)))
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.resources != tuple(sorted(self.resources, key=RESOURCES.index)):
            raise ValidationError("contract query resources are unsupported, duplicated, or unordered")
        self.member_name = ingestion_model._safe_member_name(member_name, "contract query member name") if member_name else ""
        self.data_kind = _label(data_kind, "contract query data kind") if data_kind else ""
        if self.data_kind and self.data_kind not in ingestion_model.DATA_KINDS:
            raise ValidationError("contract query data kind is unsupported")
        self.field_name = ingestion_model._key(field_name, "contract query field name") if field_name else ""
        self.value_type = _label(value_type, "contract query value type") if value_type else ""
        if self.value_type and self.value_type not in profile_model.VALUE_TYPES:
            raise ValidationError("contract query value type is unsupported")
        self.state = _label(state, "contract query state") if state else ""
        if self.state and self.state not in contract_model.STATES:
            raise ValidationError("contract query state is unsupported")
        self.required = _bool(required, "contract query required filter")
        self.type_consistent = _bool(type_consistent, "contract query consistency filter")
        self.text = _text(text, "contract query text", MAX_TEXT)
        self.offset = _count(offset, "contract query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "contract query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "contract query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "contract query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "contract query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "contract query next offset", MAX_TOTAL_COUNT)
        self.truncated = _bool(truncated, "contract query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractQueryRow) else DownloadedDataProfileContractQueryRow.from_mapping(item) for item in _sequence(rows, "contract query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "contract query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract query address", required=True)
        self._validate()

    def _validate(self) -> None:
        if self.total_count < self.matched_count or self.matched_count < self.returned_count or self.returned_count != len(self.rows) or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("contract query counts or truncation do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)):
            raise ValidationError("contract query row ordinals are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("contract query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("contract query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"contract_address": self.contract_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "member_name": self.member_name, "data_kind": self.data_kind, "field_name": self.field_name, "value_type": self.value_type, "state": self.state, "required": self.required, "type_consistent": self.type_consistent, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": tuple(item.to_dict() for item in self.rows), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractQuery:
        value = _mapping(value, "downloaded data profile contract query")
        _strict(value, set(cls.FIELDS), "downloaded data profile contract query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _base(ordinal: int, resource: str, *, field_name: str = "", member_name: str = "", member_address: str = "", data_kind: str = "", value_type: str = "", state: str = "", issue: str = "", required: bool = False, type_consistent: bool = False, observed_count: int = 0, missing_count: int = 0, member_count: int = 0, count: int = 0, field_count: int = 0, record_count: int = 0, required_field_count: int = 0, optional_field_count: int = 0, mixed_type_field_count: int = 0, sparse_field_count: int = 0) -> dict[str, Any]:
    return {"ordinal": ordinal, "resource": resource, "field_name": field_name, "member_name": member_name, "member_address": member_address, "data_kind": data_kind, "value_type": value_type, "state": state, "issue": issue, "required": required, "type_consistent": type_consistent, "observed_count": observed_count, "missing_count": missing_count, "member_count": member_count, "count": count, "field_count": field_count, "record_count": record_count, "required_field_count": required_field_count, "optional_field_count": optional_field_count, "mixed_type_field_count": mixed_type_field_count, "sparse_field_count": sparse_field_count, "content_address": ROW_PREFIX + ":pending"}


def _row(body: dict[str, Any]) -> DownloadedDataProfileContractQueryRow:
    provisional = DownloadedDataProfileContractQueryRow(**body)
    return DownloadedDataProfileContractQueryRow(**(body | {"content_address": address_row(provisional)}))


def _summary_row(ordinal: int, value: contract_model.DownloadedDataProfileContract) -> DownloadedDataProfileContractQueryRow:
    return _row(_base(ordinal, "summary", member_count=value.member_count, field_count=value.field_count, record_count=value.record_count, required_field_count=value.required_field_count, optional_field_count=value.optional_field_count, mixed_type_field_count=value.mixed_type_field_count, sparse_field_count=value.sparse_field_count))


def _type_row(ordinal: int, value: contract_model.DownloadedDataContractType) -> DownloadedDataProfileContractQueryRow:
    return _row(_base(ordinal, "types", value_type=value.value_type, count=value.observed_count, member_count=value.member_count, field_count=value.field_count))


def _member_row(ordinal: int, value: contract_model.DownloadedDataContractMember) -> DownloadedDataProfileContractQueryRow:
    return _row(_base(ordinal, "members", member_name=value.member_name, member_address=value.member_address, data_kind=value.data_kind, field_count=value.field_count, record_count=value.record_count, required_field_count=value.required_field_count, optional_field_count=value.optional_field_count, mixed_type_field_count=value.mixed_type_field_count))


def _field_row(ordinal: int, value: contract_model.DownloadedDataContractField, resource: str = "fields", issue: str = "") -> DownloadedDataProfileContractQueryRow:
    return _row(_base(ordinal, resource, field_name=value.field_name, value_type=value.dominant_value_type, state=value.state, issue=issue, required=value.required, type_consistent=value.type_consistent, observed_count=value.observed_count, missing_count=value.missing_count, member_count=value.member_count, count=value.observed_count,))


def _matches(row: DownloadedDataProfileContractQueryRow, query: DownloadedDataProfileContractQuery) -> bool:
    if query.member_name and row.member_name != query.member_name:
        return False
    if query.data_kind and row.data_kind != query.data_kind:
        return False
    if query.field_name and row.field_name != query.field_name:
        return False
    if query.value_type and row.value_type != query.value_type:
        return False
    if query.state and row.state != query.state:
        return False
    if query.required and not row.required:
        return False
    if query.type_consistent and not row.type_consistent:
        return False
    if query.text:
        haystack = " ".join((row.resource, row.field_name, row.member_name, row.member_address, row.data_kind, row.value_type, row.state, row.issue)).casefold()
        if query.text.casefold() not in haystack:
            return False
    return True


def _readdress_row(row: DownloadedDataProfileContractQueryRow, ordinal: int) -> DownloadedDataProfileContractQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    return _row(body)


def query_contract(value: contract_model.DownloadedDataProfileContract, *, resources: Sequence[str] = RESOURCES, member_name: str = "", data_kind: str = "", field_name: str = "", value_type: str = "", state: str = "", required: bool = False, type_consistent: bool = False, text: str = "", offset: int = 0, limit: int = 100) -> DownloadedDataProfileContractQuery:
    if not isinstance(value, contract_model.DownloadedDataProfileContract):
        raise ValidationError("contract query requires a typed downloaded data profile contract")
    normalized = tuple(sorted({_label(item, "contract query resource") for item in resources}, key=RESOURCES.index))
    if not normalized:
        raise ValidationError("contract query requires at least one resource")
    candidate = DownloadedDataProfileContractQuery(value.content_address, VERSION, BOUNDARY, normalized, member_name, data_kind, field_name, value_type, state, required, type_consistent, text, offset, limit, 0, 0, 0, offset, False, (), QUERY_PREFIX + ":pending")
    all_rows: list[DownloadedDataProfileContractQueryRow] = []
    ordinal = 1
    if "summary" in normalized:
        all_rows.append(_summary_row(ordinal, value))
        ordinal += 1
    if "types" in normalized:
        for item in value.types:
            all_rows.append(_type_row(ordinal, item))
            ordinal += 1
    if "members" in normalized:
        for item in value.members:
            all_rows.append(_member_row(ordinal, item))
            ordinal += 1
    if "fields" in normalized:
        for item in value.fields:
            all_rows.append(_field_row(ordinal, item))
            ordinal += 1
    if "issues" in normalized:
        for item in value.fields:
            if item.state in {"sparse", "mixed"}:
                all_rows.append(_field_row(ordinal, item, "issues", f"{item.state}-field"))
                ordinal += 1
    matched = tuple(row for row in all_rows if _matches(row, candidate))
    page = matched[offset : offset + limit]
    rows = tuple(_readdress_row(row, index + 1) for index, row in enumerate(page))
    body = {"contract_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": normalized, "member_name": member_name, "data_kind": data_kind, "field_name": field_name, "value_type": value_type, "state": state, "required": required, "type_consistent": type_consistent, "text": text, "offset": offset, "limit": limit, "total_count": len(all_rows), "matched_count": len(matched), "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < len(matched), "rows": rows}
    provisional = DownloadedDataProfileContractQuery(**body, content_address=QUERY_PREFIX + ":pending")
    return DownloadedDataProfileContractQuery(**body, content_address=address_query(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractQuery:
    return DownloadedDataProfileContractQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractQuery) -> str:
    return canonical_json(DownloadedDataProfileContractQuery.from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractQuery) -> str:
    value = DownloadedDataProfileContractQuery.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    writer.writerows(tuple(row.to_dict()[field] for field in ROW_FIELDS) for row in value.rows)
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractQuery) -> str:
    value = DownloadedDataProfileContractQuery.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Query", "", f"- Contract: `{value.contract_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Returned: `{value.returned_count}/{value.matched_count}`", f"- Address: `{value.content_address}`", "", "| # | resource | field | member | type | state | issue | count |", "| ---: | --- | --- | --- | --- | --- | --- | ---: |"]
    lines.extend(f"| {row.ordinal} | `{row.resource}` | `{row.field_name}` | `{row.member_name}` | `{row.value_type}` | `{row.state}` | `{row.issue}` | {row.count} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "field_name": {"type": "string"}, "member_name": {"type": "string"}, "member_address": {"type": "string"}, "data_kind": {"type": "string"}, "value_type": {"enum": list(profile_model.VALUE_TYPES) + [""]}, "state": {"enum": list(contract_model.STATES) + [""]}, "issue": {"type": "string"}, "required": {"type": "boolean"}, "type_consistent": {"type": "boolean"}, "observed_count": {"type": "integer", "minimum": 0}, "missing_count": {"type": "integer", "minimum": 0}, "member_count": {"type": "integer", "minimum": 0}, "count": {"type": "integer", "minimum": 0}, "field_count": {"type": "integer", "minimum": 0}, "record_count": {"type": "integer", "minimum": 0}, "required_field_count": {"type": "integer", "minimum": 0}, "optional_field_count": {"type": "integer", "minimum": 0}, "mixed_type_field_count": {"type": "integer", "minimum": 0}, "sparse_field_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"contract_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "member_name": {"type": "string"}, "data_kind": {"type": "string"}, "field_name": {"type": "string"}, "value_type": {"type": "string"}, "state": {"enum": list(contract_model.STATES) + [""]}, "required": {"type": "boolean"}, "type_consistent": {"type": "boolean"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "resources": RESOURCES, "states": contract_model.STATES, "value_types": profile_model.VALUE_TYPES, "operations": ("query_contract", "query_from_mapping", "query_json", "query_csv", "render_query_markdown"), "limits": {"default_limit": 100, "max_limit": MAX_LIMIT, "max_query_items": MAX_TOTAL_COUNT}}


__all__ = ["BOUNDARY", "MAX_LIMIT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "DownloadedDataProfileContractQuery", "DownloadedDataProfileContractQueryRow", "address_query", "address_row", "capabilities", "query_contract", "query_csv", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "row_schema"]
