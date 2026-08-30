"""Bounded inspection of decision-ledger transition diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_diff as diff_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
DEFAULT_LIMIT = 50
MAX_QUERY_ITEMS = diff_model.MAX_ITEMS + 1
RESOURCES = ("summary", "items", "added", "removed", "changed", "unchanged")


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
    return diff_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery:
    FIELDS = ("query_id", "diff_address", "resources", "operation_address", "peer_id", "entry_id", "change", "text", "offset", "limit", "content_address")

    def __init__(self, query_id: str, diff_address: str, resources: Sequence[str], operation_address: str, peer_id: str, entry_id: str, change: str, text: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "diff query ID")
        self.diff_address = _address(diff_address, "diff query diff address", diff_model.DIFF_PREFIX)
        self.resources = tuple(_label(item, "diff query resource") for item in _sequence(resources, "diff query resources", len(RESOURCES)))
        self.operation_address = _address(operation_address, "diff query operation address", diff_model.ledger_model.plan_model.OPERATION_PREFIX, required=False)
        self.peer_id = _label(peer_id, "diff query peer ID", required=False)
        self.entry_id = _label(entry_id, "diff query entry ID", required=False)
        self.change = _label(change, "diff query change", required=False)
        self.text = _text(text, "diff query text", 512, required=False)
        self.offset = _count(offset, "diff query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "diff query limit", MAX_QUERY_ITEMS)
        self.content_address = _address(content_address, "diff query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff query address")
        self._validate()

    def _validate(self) -> None:
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.limit < 1 or self.change and self.change not in diff_model.CHANGES:
            raise ValidationError("diff query resources or filters are invalid")
        if not _public(self.to_dict()):
            raise ValidationError("diff query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("diff query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery:
        value = _mapping(value, "diff query")
        _strict(value, set(cls.FIELDS), "diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow:
    FIELDS = ("ordinal", "resource", "row_id", "operation_address", "peer_id", "entry_id", "package_id", "action", "priority", "left_disposition", "right_disposition", "left_status", "right_status", "left_note", "right_note", "change", "changed_fields", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, operation_address: str, peer_id: str, entry_id: str, package_id: str, action: str, priority: str, left_disposition: str, right_disposition: str, left_status: str, right_status: str, left_note: str, right_note: str, change: str, changed_fields: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff query row ordinal", MAX_QUERY_ITEMS)
        self.resource = _label(resource, "diff query row resource")
        self.row_id = _label(row_id, "diff query row ID")
        self.operation_address = _address(operation_address, "diff query row operation address", diff_model.ledger_model.plan_model.OPERATION_PREFIX, required=False)
        self.peer_id = _label(peer_id, "diff query row peer ID", required=False)
        self.entry_id = _label(entry_id, "diff query row entry ID", required=False)
        self.package_id = _label(package_id, "diff query row package ID", required=False)
        self.action = _label(action, "diff query row action", required=False)
        self.priority = _label(priority, "diff query row priority", required=False)
        self.left_disposition = _label(left_disposition, "diff query row left disposition", required=False)
        self.right_disposition = _label(right_disposition, "diff query row right disposition", required=False)
        self.left_status = _label(left_status, "diff query row left status", required=False)
        self.right_status = _label(right_status, "diff query row right status", required=False)
        self.left_note = _text(left_note, "diff query row left note", 2048, required=False)
        self.right_note = _text(right_note, "diff query row right note", 2048, required=False)
        self.change = _label(change, "diff query row change")
        self.changed_fields = tuple(_label(item, "diff query row changed field") for item in _sequence(changed_fields, "diff query row changed fields", len(diff_model.CHANGED_FIELDS)))
        self.evidence_addresses = tuple(_text(item, "diff query row evidence", 2048) for item in _sequence(evidence_addresses, "diff query row evidence", 8))
        self.content_address = _address(content_address, "diff query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff query row address")
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES or self.change not in diff_model.CHANGES or any(item not in diff_model.CHANGED_FIELDS for item in self.changed_fields) or len(set(self.changed_fields)) != len(self.changed_fields) or not self.evidence_addresses:
            raise ValidationError("diff query row vocabulary is invalid")
        if self.operation_address and self.operation_address not in self.evidence_addresses:
            raise ValidationError("diff query row evidence does not retain operation address")
        if not _public(self.to_dict()):
            raise ValidationError("diff query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("diff query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow:
        value = _mapping(value, "diff query row")
        _strict(value, set(cls.FIELDS), "diff query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult:
    FIELDS = ("query", "diff_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery, diff_id: str, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        self.query = query if isinstance(query, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery.from_mapping(query)
        self.diff_id = _label(diff_id, "diff query result diff ID")
        self.rows = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow.from_mapping(item) for item in _sequence(rows, "diff query result rows", MAX_QUERY_ITEMS))
        self.total_count = _count(total_count, "diff query total count", MAX_QUERY_ITEMS)
        self.matched_count = _count(matched_count, "diff query matched count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "diff query returned count", MAX_QUERY_ITEMS)
        self.next_offset = _count(next_offset, "diff query next offset", MAX_QUERY_ITEMS)
        self.truncated = _bool(truncated, "diff query truncation")
        self.content_address = _address(content_address, "diff query result address", RESULT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff query result address")
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.matched_count or self.next_offset != self.query.offset + self.returned_count:
            raise ValidationError("diff query result counters are not conserved")
        if self.rows and tuple(row.ordinal for row in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)):
            raise ValidationError("diff query result ordinals do not replay")
        if self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("diff query truncation does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff query result crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("diff query result address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "diff_id": self.diff_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("diff_id", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult:
        value = _mapping(value, "diff query result")
        _strict(value, set(cls.FIELDS), "diff query result")
        query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery.from_mapping(value["query"])
        rows = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow.from_mapping(item) for item in _sequence(value["rows"], "diff query result rows", MAX_QUERY_ITEMS))
        return cls(query, value["diff_id"], rows, value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, item: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem | None, value: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow:
    if item is None:
        body = {"ordinal": ordinal, "resource": resource, "row_id": value.diff_id, "operation_address": "", "peer_id": "", "entry_id": "", "package_id": "", "action": "", "priority": "", "left_disposition": "", "right_disposition": "", "left_status": "", "right_status": "", "left_note": "", "right_note": "", "change": "unchanged", "changed_fields": (), "evidence_addresses": (value.content_address,)}
    else:
        body = {"ordinal": ordinal, "resource": resource, "row_id": f"item-{item.ordinal}", "operation_address": item.operation_address, "peer_id": item.peer_id, "entry_id": item.entry_id, "package_id": item.package_id, "action": item.action, "priority": item.priority, "left_disposition": item.left_disposition, "right_disposition": item.right_disposition, "left_status": item.left_status, "right_status": item.right_status, "left_note": item.left_note, "right_note": item.right_note, "change": item.change, "changed_fields": item.changed_fields, "evidence_addresses": item.evidence_addresses}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow(**body, content_address=address_row(provisional))


def _all_rows(value: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow, ...]:
    rows: list[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow] = []
    ordinal = 1
    selected = tuple(resources)
    if "summary" in selected:
        rows.append(_row(ordinal, "summary", None, value))
        ordinal += 1
    for item in value.items:
        categories = ("items", item.change)
        resource = next((candidate for candidate in categories if candidate in selected), None)
        if resource is not None:
            rows.append(_row(ordinal, resource, item, value))
            ordinal += 1
    return tuple(rows)


def _matches(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery) -> bool:
    if query.operation_address and row.operation_address != query.operation_address or query.peer_id and row.peer_id != query.peer_id or query.entry_id and row.entry_id != query.entry_id or query.change and row.change != query.change:
        return False
    if query.text:
        haystack = " ".join((row.row_id, row.operation_address, row.peer_id, row.entry_id, row.package_id, row.action, row.priority, row.left_disposition, row.right_disposition, row.left_status, row.right_status, row.left_note, row.right_note, row.change, *row.changed_fields, *row.evidence_addresses)).lower()
        if query.text.lower() not in haystack:
            return False
    return True


def _reordinal(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow, ordinal: int) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow.from_mapping(body)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow.from_mapping(provisional.to_dict() | {"content_address": address_row(provisional)})


def query_diff(value: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff, *, query_id: str = "consensus-certificate-observatory-archive-registry-federation-reconciliation-decision-ledger-diff-query", resources: Sequence[str] = ("summary", "items"), operation_address: str = "", peer_id: str = "", entry_id: str = "", change: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult:
    value = diff_model.verify_diff(value)
    provisional_query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery(query_id, value.content_address, resources, operation_address, peer_id, entry_id, change, text, offset, limit, QUERY_PREFIX + ":pending")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery(provisional_query.query_id, provisional_query.diff_address, provisional_query.resources, provisional_query.operation_address, provisional_query.peer_id, provisional_query.entry_id, provisional_query.change, provisional_query.text, provisional_query.offset, provisional_query.limit, address_query(provisional_query))
    rows = _all_rows(value, query.resources)
    matched = tuple(row for row in rows if _matches(row, query))
    page = tuple(_reordinal(row, query.offset + index + 1) for index, row in enumerate(matched[query.offset:query.offset + query.limit]))
    next_offset = query.offset + len(page)
    provisional_result = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult(query, value.diff_id, page, len(rows), len(matched), len(page), next_offset, next_offset < len(matched), RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult(query, provisional_result.diff_id, provisional_result.rows, provisional_result.total_count, provisional_result.matched_count, provisional_result.returned_count, provisional_result.next_offset, provisional_result.truncated, address_result(provisional_result))


def query_diff_from_mapping(value: Mapping[str, Any], **kwargs: Any) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult:
    return query_diff(diff_model.diff_from_mapping(value), **kwargs)


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult:
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult.from_mapping(value)


def verify_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("diff query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("diff query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult) -> str:
    value = verify_query_result(value)
    fields = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow.FIELDS
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        row = item.to_dict()
        row["changed_fields"] = ",".join(row["changed_fields"])
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Archive Registry Federation Reconciliation Decision Ledger Diff Query", "", f"- Diff: `{value.diff_id}`", f"- Returned: `{value.returned_count}/{value.matched_count}`", f"- Next offset: `{value.next_offset}`", "", "| # | resource | peer | entry | change | left | right | fields |", "| ---: | --- | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.peer_id}` | `{item.entry_id}` | `{item.change}` | `{item.left_disposition}` | `{item.right_disposition}` | `{','.join(item.changed_fields)}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "diff_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "operation_address": {"type": "string"}, "peer_id": {"type": "string"}, "entry_id": {"type": "string"}, "change": {"enum": [""] + list(diff_model.CHANGES)}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 0}, "resource": {"enum": list(RESOURCES)}, "row_id": {"type": "string"}, "operation_address": {"type": "string"}, "peer_id": {"type": "string"}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "action": {"type": "string"}, "priority": {"type": "string"}, "left_disposition": {"type": "string"}, "right_disposition": {"type": "string"}, "left_status": {"type": "string"}, "right_status": {"type": "string"}, "left_note": {"type": "string"}, "right_note": {"type": "string"}, "change": {"enum": list(diff_model.CHANGES)}, "changed_fields": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult.FIELDS), "properties": {"query": query_schema(), "diff_id": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "operations": ("query_diff", "query_diff_from_mapping", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "verify_query", "verify_query_result"), "resources": RESOURCES, "max_items": MAX_QUERY_ITEMS}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "QUERY_PREFIX",
    "RESOURCES",
    "RESULT_PREFIX",
    "ROW_PREFIX",
    "VERSION",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQuery",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryResult",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffQueryRow",
    "address_query",
    "address_result",
    "address_row",
    "capabilities",
    "query_csv",
    "query_diff",
    "query_diff_from_mapping",
    "query_from_mapping",
    "query_json",
    "query_schema",
    "render_query_markdown",
    "result_schema",
    "row_schema",
    "verify_query",
    "verify_query_result",
]
