"""Bounded queries over federation diff items."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
DEFAULT_LIMIT = 50
RESOURCES = ("summary", "items", "added", "removed", "changed", "resolved", "regressed", "unchanged")


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
    return diff_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery:
    FIELDS = ("query_id", "diff_address", "resources", "action", "entry_id", "text", "offset", "limit", "content_address")

    def __init__(self, query_id: str, diff_address: str, resources: Sequence[str], action: str, entry_id: str, text: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "federation diff query ID")
        self.diff_address = _address(diff_address, "federation diff query address", diff_model.DIFF_PREFIX)
        self.resources = tuple(_label(item, "federation diff query resource") for item in _sequence(resources, "federation diff query resources", len(RESOURCES)))
        self.action = _label(action, "federation diff query action", required=False)
        self.entry_id = _label(entry_id, "federation diff query entry ID", required=False)
        self.text = _text(text, "federation diff query text", 512, required=False)
        self.offset = _count(offset, "federation diff query offset", diff_model.MAX_ITEMS)
        self.limit = _count(limit, "federation diff query limit", diff_model.MAX_ITEMS)
        self.content_address = _address(content_address, "federation diff query content address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation diff query content address")
        self._validate()

    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources) or self.limit < 1 or self.action not in ("", *diff_model.ACTIONS):
            raise ValidationError("federation diff query is invalid")
        if not _public(self.to_dict()):
            raise ValidationError("federation diff query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("federation diff query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery":
        value = _mapping(value, "federation diff query")
        _strict(value, set(cls.FIELDS), "federation diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow:
    FIELDS = ("ordinal", "resource", "row_id", "entry_id", "package_id", "action", "baseline_state", "candidate_state", "baseline_archive_addresses", "candidate_archive_addresses", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, entry_id: str, package_id: str, action: str, baseline_state: str, candidate_state: str, baseline_archive_addresses: Sequence[str], candidate_archive_addresses: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation diff query row ordinal", diff_model.MAX_ITEMS)
        self.resource = _label(resource, "federation diff query row resource")
        self.row_id = _label(row_id, "federation diff query row ID")
        self.entry_id = _label(entry_id, "federation diff query row entry ID")
        self.package_id = _label(package_id, "federation diff query row package ID", required=False)
        self.action = _label(action, "federation diff query row action")
        self.baseline_state = _label(baseline_state, "federation diff query row baseline state", required=False)
        self.candidate_state = _label(candidate_state, "federation diff query row candidate state", required=False)
        self.baseline_archive_addresses = tuple(_address(item, "federation diff query baseline archive address", diff_model.federation_model.registry_model.archive_model.ARCHIVE_PREFIX) for item in _sequence(baseline_archive_addresses, "federation diff query baseline addresses", diff_model.federation_model.MAX_PEERS))
        self.candidate_archive_addresses = tuple(_address(item, "federation diff query candidate archive address", diff_model.federation_model.registry_model.archive_model.ARCHIVE_PREFIX) for item in _sequence(candidate_archive_addresses, "federation diff query candidate addresses", diff_model.federation_model.MAX_PEERS))
        self.evidence_addresses = tuple(_text(item, "federation diff query evidence", 2048) for item in _sequence(evidence_addresses, "federation diff query evidence", diff_model.federation_model.MAX_PEERS + 2))
        self.content_address = _address(content_address, "federation diff query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation diff query row address")
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES or self.action not in diff_model.ACTIONS or self.baseline_state not in ("", *diff_model.federation_model.STATES) or self.candidate_state not in ("", *diff_model.federation_model.STATES) or not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("federation diff query row is invalid")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("federation diff query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow":
        value = _mapping(value, "federation diff query row")
        _strict(value, set(cls.FIELDS), "federation diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult:
    FIELDS = ("query", "diff_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery, diff_id: str, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        self.query = query if isinstance(query, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery.from_mapping(query)
        self.diff_id = _label(diff_id, "federation diff query result diff ID")
        self.rows = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow.from_mapping(item) for item in _sequence(rows, "federation diff query result rows", diff_model.MAX_ITEMS))
        self.total_count = _count(total_count, "federation diff query total count", diff_model.MAX_ITEMS)
        self.matched_count = _count(matched_count, "federation diff query matched count", diff_model.MAX_ITEMS)
        self.returned_count = _count(returned_count, "federation diff query returned count", diff_model.MAX_ITEMS)
        self.next_offset = _count(next_offset, "federation diff query next offset", diff_model.MAX_ITEMS)
        self.truncated = _bool(truncated, "federation diff query truncation")
        self.content_address = _address(content_address, "federation diff query result address", RESULT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation diff query result address")
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.matched_count or self.next_offset != self.query.offset + self.returned_count or self.truncated != (self.next_offset < self.query.offset + self.matched_count):
            raise ValidationError("federation diff query result counters are invalid")
        if self.rows and tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)):
            raise ValidationError("federation diff query result ordinals are invalid")
        if not _public(self.to_dict()):
            raise ValidationError("federation diff query result crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("federation diff query result address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "diff_id": self.diff_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("diff_id", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult":
        value = _mapping(value, "federation diff query result")
        _strict(value, set(cls.FIELDS), "federation diff query result")
        return cls(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery.from_mapping(value["query"]), value["diff_id"], tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow.from_mapping(item) for item in _sequence(value["rows"], "federation diff query result rows", diff_model.MAX_ITEMS)), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, item: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "row_id": item.entry_id, "entry_id": item.entry_id, "package_id": item.package_id, "action": item.action, "baseline_state": item.baseline_state, "candidate_state": item.candidate_state, "baseline_archive_addresses": item.baseline_archive_addresses, "candidate_archive_addresses": item.candidate_archive_addresses, "evidence_addresses": item.evidence_addresses}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow(**body, content_address=address_row(provisional))


def _all_rows(value: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow, ...]:
    selected = tuple(resources)
    rows: list[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow] = []
    ordinal = 1
    if "summary" in selected:
        body = diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem(ordinal, value.diff_id, "", "unchanged", "", "", (), (), (value.content_address,), diff_model.ITEM_PREFIX + ":pending")
        rows.append(_row(ordinal, "summary", body)); ordinal += 1
    for item in value.items:
        resource = "items" if "items" in selected else item.action
        if resource not in selected:
            continue
        rows.append(_row(ordinal, resource, item)); ordinal += 1
    return tuple(rows)


def _matches(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery) -> bool:
    if query.action and row.action != query.action or query.entry_id and row.entry_id != query.entry_id:
        return False
    if query.text and query.text.lower() not in " ".join((row.row_id, row.entry_id, row.package_id, row.action, row.baseline_state, row.candidate_state, *row.baseline_archive_addresses, *row.candidate_archive_addresses)).lower():
        return False
    return True


def _reordinal(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow, ordinal: int) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow.from_mapping(body)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow.from_mapping(provisional.to_dict() | {"content_address": address_row(provisional)})


def query_diff(value: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff, *, query_id: str = "consensus-certificate-observatory-archive-registry-federation-diff-query", resources: Sequence[str] = ("summary", "items"), action: str = "", entry_id: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult:
    value = diff_model.verify_diff(value)
    provisional_query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery(query_id, value.content_address, resources, action, entry_id, text, offset, limit, QUERY_PREFIX + ":pending")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery(provisional_query.query_id, provisional_query.diff_address, provisional_query.resources, provisional_query.action, provisional_query.entry_id, provisional_query.text, provisional_query.offset, provisional_query.limit, address_query(provisional_query))
    rows = _all_rows(value, query.resources); matched = tuple(row for row in rows if _matches(row, query))
    page = tuple(_reordinal(row, query.offset + index + 1) for index, row in enumerate(matched[query.offset:query.offset + query.limit]))
    next_offset = query.offset + len(page)
    provisional_result = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult(query, value.diff_id, page, len(rows), len(matched), len(page), next_offset, next_offset < query.offset + len(matched), RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult(query, provisional_result.diff_id, provisional_result.rows, provisional_result.total_count, provisional_result.matched_count, provisional_result.returned_count, provisional_result.next_offset, provisional_result.truncated, address_result(provisional_result))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult:
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult.from_mapping(value)


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("federation diff query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult) -> str:
    value = verify_query_result(value); fields = ("ordinal", "resource", "row_id", "entry_id", "package_id", "action", "baseline_state", "candidate_state", "baseline_archive_addresses", "candidate_archive_addresses", "evidence_addresses", "content_address"); stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n"); writer.writeheader()
    for item in value.rows:
        row = item.to_dict()
        for field in ("baseline_archive_addresses", "candidate_archive_addresses", "evidence_addresses"):
            row[field] = ",".join(row[field])
        writer.writerow(row)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult) -> str:
    value = verify_query_result(value); lines = ["# Archive Registry Federation Diff Query", "", f"- Returned: `{value.returned_count}/{value.matched_count}`", "", "| # | resource | entry | action |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.entry_id}` | `{item.action}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "diff_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "action": {"type": "string"}, "entry_id": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}, "content_address": {"type": "string"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer"}, "resource": {"type": "string"}, "row_id": {"type": "string"}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "action": {"type": "string"}, "baseline_state": {"type": "string"}, "candidate_state": {"type": "string"}, "baseline_archive_addresses": {"type": "array"}, "candidate_archive_addresses": {"type": "array"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult.FIELDS), "properties": {"query": query_schema(), "diff_id": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer"}, "matched_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "next_offset": {"type": "integer"}, "truncated": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "operations": ("query_diff", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "verify_query_result"), "resources": RESOURCES}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQuery", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryResult", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffQueryRow", "address_query", "address_result", "address_row", "capabilities", "query_csv", "query_diff", "query_from_mapping", "query_json", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_query_result"]
