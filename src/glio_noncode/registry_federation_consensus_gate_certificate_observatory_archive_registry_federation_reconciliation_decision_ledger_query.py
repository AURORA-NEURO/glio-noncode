"""Bounded, deterministic projections of reconciliation decision ledgers."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger as ledger_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = ledger_model.VERSION + "-query-v1"
BOUNDARY = ledger_model.BOUNDARY + "_query"
QUERY_PREFIX = ledger_model.LEDGER_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
DEFAULT_LIMIT = 50
MAX_QUERY_ITEMS = ledger_model.MAX_DECISIONS + 1
RESOURCES = (
    "summary",
    "decisions",
    "pending",
    "approved",
    "held",
    "rejected",
    "deferred",
    "not-required",
    "needs-action",
)
_STATUS_RESOURCES = frozenset(ledger_model.STATUSES)


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
    return ledger_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery:
    """A path-free query specification for one ledger."""

    FIELDS = (
        "query_id",
        "ledger_address",
        "resources",
        "operation_address",
        "peer_id",
        "entry_id",
        "plan_status",
        "action",
        "priority",
        "disposition",
        "status",
        "text",
        "offset",
        "limit",
        "content_address",
    )

    def __init__(self, query_id: str, ledger_address: str, resources: Sequence[str], operation_address: str, peer_id: str, entry_id: str, plan_status: str, action: str, priority: str, disposition: str, status: str, text: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "ledger query ID")
        self.ledger_address = _address(ledger_address, "ledger query ledger address", ledger_model.LEDGER_PREFIX)
        self.resources = tuple(_label(item, "ledger query resource") for item in _sequence(resources, "ledger query resources", len(RESOURCES)))
        self.operation_address = _address(operation_address, "ledger query operation address", ledger_model.plan_model.OPERATION_PREFIX, required=False)
        self.peer_id = _label(peer_id, "ledger query peer ID", required=False)
        self.entry_id = _label(entry_id, "ledger query entry ID", required=False)
        self.plan_status = _label(plan_status, "ledger query plan status", required=False)
        self.action = _label(action, "ledger query action", required=False)
        self.priority = _label(priority, "ledger query priority", required=False)
        self.disposition = _label(disposition, "ledger query disposition", required=False)
        self.status = _label(status, "ledger query status", required=False)
        self.text = _text(text, "ledger query text", 512, required=False)
        self.offset = _count(offset, "ledger query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "ledger query limit", MAX_QUERY_ITEMS)
        self.content_address = _address(content_address, "ledger query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "ledger query address")
        self._validate()

    def _validate(self) -> None:
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.limit < 1:
            raise ValidationError("ledger query resources or limit are invalid")
        if self.plan_status and self.plan_status not in ledger_model.plan_model.STATUSES or self.action and self.action not in ledger_model.plan_model.ACTIONS or self.priority and self.priority not in ledger_model.plan_model.PRIORITIES or self.disposition and self.disposition not in ledger_model.DISPOSITIONS or self.status and self.status not in ledger_model.STATUSES:
            raise ValidationError("ledger query filter vocabulary is unsupported")
        if not _public(self.to_dict()):
            raise ValidationError("ledger query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("ledger query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery:
        value = _mapping(value, "ledger query")
        _strict(value, set(cls.FIELDS), "ledger query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow:
    """One query row, re-ordinalled to the requested page."""

    FIELDS = (
        "ordinal",
        "resource",
        "row_id",
        "operation_address",
        "peer_id",
        "registry_id",
        "entry_id",
        "package_id",
        "source_state",
        "action",
        "plan_status",
        "priority",
        "disposition",
        "status",
        "requires_confirmation",
        "note",
        "evidence_addresses",
        "content_address",
    )

    def __init__(self, ordinal: int, resource: str, row_id: str, operation_address: str, peer_id: str, registry_id: str, entry_id: str, package_id: str, source_state: str, action: str, plan_status: str, priority: str, disposition: str, status: str, requires_confirmation: bool, note: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger query row ordinal", MAX_QUERY_ITEMS)
        self.resource = _label(resource, "ledger query row resource")
        self.row_id = _label(row_id, "ledger query row ID")
        self.operation_address = _address(operation_address, "ledger query row operation address", ledger_model.plan_model.OPERATION_PREFIX, required=False)
        self.peer_id = _label(peer_id, "ledger query row peer ID", required=False)
        self.registry_id = _label(registry_id, "ledger query row registry ID", required=False)
        self.entry_id = _label(entry_id, "ledger query row entry ID", required=False)
        self.package_id = _label(package_id, "ledger query row package ID", required=False)
        self.source_state = _label(source_state, "ledger query row source state")
        self.action = _label(action, "ledger query row action", required=False)
        self.plan_status = _label(plan_status, "ledger query row plan status", required=False)
        self.priority = _label(priority, "ledger query row priority", required=False)
        self.disposition = _label(disposition, "ledger query row disposition", required=False)
        self.status = _label(status, "ledger query row status", required=False)
        self.requires_confirmation = _bool(requires_confirmation, "ledger query row confirmation")
        self.note = _text(note, "ledger query row note", 2048, required=False)
        self.evidence_addresses = tuple(_text(item, "ledger query row evidence", 2048) for item in _sequence(evidence_addresses, "ledger query row evidence", ledger_model.MAX_DECISIONS + 8))
        self.content_address = _address(content_address, "ledger query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "ledger query row address")
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES or self.source_state not in ledger_model.plan_model.resolution_model.STATES + ("ready",) or self.action and self.action not in ledger_model.plan_model.ACTIONS or self.plan_status and self.plan_status not in ledger_model.plan_model.STATUSES or self.priority and self.priority not in ledger_model.plan_model.PRIORITIES or self.disposition and self.disposition not in ledger_model.DISPOSITIONS or self.status and self.status not in ledger_model.STATUSES or not self.evidence_addresses:
            raise ValidationError("ledger query row vocabulary is invalid")
        if self.operation_address and self.operation_address not in self.evidence_addresses:
            raise ValidationError("ledger query row evidence does not retain operation address")
        if not _public(self.to_dict()):
            raise ValidationError("ledger query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("ledger query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow:
        value = _mapping(value, "ledger query row")
        _strict(value, set(cls.FIELDS), "ledger query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult:
    FIELDS = ("query", "ledger_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery, ledger_id: str, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        self.query = query if isinstance(query, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery.from_mapping(query)
        self.ledger_id = _label(ledger_id, "ledger query result ledger ID")
        self.rows = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow.from_mapping(item) for item in _sequence(rows, "ledger query result rows", MAX_QUERY_ITEMS))
        self.total_count = _count(total_count, "ledger query total count", MAX_QUERY_ITEMS)
        self.matched_count = _count(matched_count, "ledger query matched count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "ledger query returned count", MAX_QUERY_ITEMS)
        self.next_offset = _count(next_offset, "ledger query next offset", MAX_QUERY_ITEMS)
        self.truncated = _bool(truncated, "ledger query truncation")
        self.content_address = _address(content_address, "ledger query result address", RESULT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "ledger query result address")
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.matched_count or self.next_offset != self.query.offset + self.returned_count:
            raise ValidationError("ledger query result counters are not conserved")
        if self.rows and tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)):
            raise ValidationError("ledger query result ordinals do not replay")
        if self.truncated != (self.next_offset < self.matched_count):
            raise ValidationError("ledger query truncation does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger query result crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("ledger query result address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "ledger_id": self.ledger_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("ledger_id", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult:
        value = _mapping(value, "ledger query result")
        _strict(value, set(cls.FIELDS), "ledger query result")
        query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery.from_mapping(value["query"])
        rows = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow.from_mapping(item) for item in _sequence(value["rows"], "ledger query result rows", MAX_QUERY_ITEMS))
        return cls(query, value["ledger_id"], rows, value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, row_id: str, decision: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision | None, value: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow:
    if decision is None:
        body = {"ordinal": ordinal, "resource": resource, "row_id": row_id, "operation_address": "", "peer_id": "", "registry_id": "", "entry_id": "", "package_id": "", "source_state": "ready", "action": "", "plan_status": "", "priority": "none", "disposition": "", "status": "", "requires_confirmation": False, "note": "", "evidence_addresses": (value.content_address,)}
    else:
        body = {"ordinal": ordinal, "resource": resource, "row_id": f"decision-{decision.ordinal}-{resource}", "operation_address": decision.operation_address, "peer_id": decision.peer_id, "registry_id": decision.registry_id, "entry_id": decision.entry_id, "package_id": decision.package_id, "source_state": decision.source_state, "action": decision.action, "plan_status": decision.plan_status, "priority": decision.priority, "disposition": decision.disposition, "status": decision.status, "requires_confirmation": decision.requires_confirmation, "note": decision.note, "evidence_addresses": decision.evidence_addresses}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow(**body, content_address=address_row(provisional))


def _all_rows(value: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow, ...]:
    rows: list[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow] = []
    ordinal = 1
    selected = tuple(resources)
    if "summary" in selected:
        rows.append(_row(ordinal, "summary", value.ledger_id, None, value))
        ordinal += 1
    for decision in value.decisions:
        categories = ("decisions", decision.status, "needs-action" if decision.status in {"pending", "held", "rejected", "deferred"} else "")
        resource = next((item for item in categories if item and item in selected), None)
        if resource is not None:
            rows.append(_row(ordinal, resource, f"decision-{decision.ordinal}", decision, value))
            ordinal += 1
    return tuple(rows)


def _matches(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery) -> bool:
    if query.operation_address and row.operation_address != query.operation_address or query.peer_id and row.peer_id != query.peer_id or query.entry_id and row.entry_id != query.entry_id or query.plan_status and row.plan_status != query.plan_status or query.action and row.action != query.action or query.priority and row.priority != query.priority or query.disposition and row.disposition != query.disposition or query.status and row.status != query.status:
        return False
    if query.text:
        haystack = " ".join((row.row_id, row.operation_address, row.peer_id, row.registry_id, row.entry_id, row.package_id, row.source_state, row.action, row.plan_status, row.priority, row.disposition, row.status, row.note, *row.evidence_addresses)).lower()
        if query.text.lower() not in haystack:
            return False
    return True


def _reordinal(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow, ordinal: int) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow.from_mapping(body)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow.from_mapping(provisional.to_dict() | {"content_address": address_row(provisional)})


def query_ledger(value: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger, *, query_id: str = "consensus-certificate-observatory-archive-registry-federation-reconciliation-decision-ledger-query", resources: Sequence[str] = ("summary", "decisions"), operation_address: str = "", peer_id: str = "", entry_id: str = "", plan_status: str = "", action: str = "", priority: str = "", disposition: str = "", status: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult:
    value = ledger_model.verify_ledger(value)
    provisional_query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery(query_id, value.content_address, resources, operation_address, peer_id, entry_id, plan_status, action, priority, disposition, status, text, offset, limit, QUERY_PREFIX + ":pending")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery(provisional_query.query_id, provisional_query.ledger_address, provisional_query.resources, provisional_query.operation_address, provisional_query.peer_id, provisional_query.entry_id, provisional_query.plan_status, provisional_query.action, provisional_query.priority, provisional_query.disposition, provisional_query.status, provisional_query.text, provisional_query.offset, provisional_query.limit, address_query(provisional_query))
    rows = _all_rows(value, query.resources)
    matched = tuple(row for row in rows if _matches(row, query))
    page = tuple(_reordinal(row, query.offset + index + 1) for index, row in enumerate(matched[query.offset:query.offset + query.limit]))
    next_offset = query.offset + len(page)
    provisional_result = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult(query, value.ledger_id, page, len(rows), len(matched), len(page), next_offset, next_offset < len(matched), RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult(query, provisional_result.ledger_id, provisional_result.rows, provisional_result.total_count, provisional_result.matched_count, provisional_result.returned_count, provisional_result.next_offset, provisional_result.truncated, address_result(provisional_result))


def query_ledger_from_mapping(value: Mapping[str, Any], **kwargs: Any) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult:
    return query_ledger(ledger_model.ledger_from_mapping(value), **kwargs)


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult:
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult.from_mapping(value)


def verify_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("ledger query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("ledger query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult) -> str:
    value = verify_query_result(value)
    fields = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow.FIELDS
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Archive Registry Federation Reconciliation Decision Ledger Query", "", f"- Ledger: `{value.ledger_id}`", f"- Returned: `{value.returned_count}/{value.matched_count}`", f"- Next offset: `{value.next_offset}`", "", "| # | resource | peer | entry | action | disposition | status |", "| ---: | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.peer_id}` | `{item.entry_id}` | `{item.action}` | `{item.disposition}` | `{item.status}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "ledger_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "operation_address": {"type": "string"}, "peer_id": {"type": "string"}, "entry_id": {"type": "string"}, "plan_status": {"enum": [""] + list(ledger_model.plan_model.STATUSES)}, "action": {"enum": [""] + list(ledger_model.plan_model.ACTIONS)}, "priority": {"enum": [""] + list(ledger_model.plan_model.PRIORITIES)}, "disposition": {"enum": [""] + list(ledger_model.DISPOSITIONS)}, "status": {"enum": [""] + list(ledger_model.STATUSES)}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 0}, "resource": {"enum": list(RESOURCES)}, "row_id": {"type": "string"}, "operation_address": {"type": "string"}, "peer_id": {"type": "string"}, "registry_id": {"type": "string"}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "source_state": {"enum": list(ledger_model.plan_model.resolution_model.STATES) + ["ready"]}, "action": {"type": "string"}, "plan_status": {"type": "string"}, "priority": {"type": "string"}, "disposition": {"type": "string"}, "status": {"type": "string"}, "requires_confirmation": {"type": "boolean"}, "note": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult.FIELDS), "properties": {"query": query_schema(), "ledger_id": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "operations": ("query_ledger", "query_ledger_from_mapping", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "verify_query", "verify_query_result"), "resources": RESOURCES, "max_items": MAX_QUERY_ITEMS}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "QUERY_PREFIX",
    "RESOURCES",
    "RESULT_PREFIX",
    "ROW_PREFIX",
    "VERSION",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQuery",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryRow",
    "address_query",
    "address_result",
    "address_row",
    "capabilities",
    "query_csv",
    "query_from_mapping",
    "query_json",
    "query_ledger",
    "query_ledger_from_mapping",
    "query_schema",
    "render_query_markdown",
    "result_schema",
    "row_schema",
    "verify_query",
    "verify_query_result",
]
