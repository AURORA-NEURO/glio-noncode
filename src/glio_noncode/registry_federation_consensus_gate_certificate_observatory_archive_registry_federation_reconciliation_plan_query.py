"""Bounded inspection of non-mutating reconciliation-plan operations."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan as plan_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = plan_model.VERSION + "-query-v1"
BOUNDARY = plan_model.BOUNDARY + "_query"
QUERY_PREFIX = plan_model.PLAN_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
DEFAULT_LIMIT = 50
MAX_QUERY_ITEMS = plan_model.MAX_OPERATIONS + 1
RESOURCES = ("summary", "operations", "no-op", "request-missing", "replace-with-consensus", "manual-review", "planned", "review", "blocked")


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
    return plan_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery:
    FIELDS = ("query_id", "plan_address", "resources", "peer_id", "entry_id", "state", "action", "status", "priority", "registry_id", "package_id", "text", "offset", "limit", "content_address")

    def __init__(self, query_id: str, plan_address: str, resources: Sequence[str], peer_id: str, entry_id: str, state: str, action: str, status: str, priority: str, registry_id: str, package_id: str, text: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "plan query ID")
        self.plan_address = _address(plan_address, "plan query address", plan_model.PLAN_PREFIX)
        self.resources = tuple(_label(item, "plan query resource") for item in _sequence(resources, "plan query resources", len(RESOURCES)))
        self.peer_id = _label(peer_id, "plan query peer ID", required=False)
        self.entry_id = _label(entry_id, "plan query entry ID", required=False)
        self.state = _label(state, "plan query source state", required=False)
        self.action = _label(action, "plan query action", required=False)
        self.status = _label(status, "plan query status", required=False)
        self.priority = _label(priority, "plan query priority", required=False)
        self.registry_id = _label(registry_id, "plan query registry ID", required=False)
        self.package_id = _label(package_id, "plan query package ID", required=False)
        self.text = _text(text, "plan query text", 512, required=False)
        self.offset = _count(offset, "plan query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "plan query limit", MAX_QUERY_ITEMS)
        self.content_address = _address(content_address, "plan query address", QUERY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "plan query address")
        self._validate()

    def _validate(self) -> None:
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(item not in RESOURCES for item in self.resources) or self.limit < 1:
            raise ValidationError("plan query resources or limit are invalid")
        if self.state and self.state not in plan_model.resolution_model.STATES or self.action and self.action not in plan_model.ACTIONS or self.status and self.status not in plan_model.STATUSES or self.priority and self.priority not in plan_model.PRIORITIES:
            raise ValidationError("plan query filter vocabulary is unsupported")
        if not _public(self.to_dict()):
            raise ValidationError("plan query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("plan query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery":
        value = _mapping(value, "plan query")
        _strict(value, set(cls.FIELDS), "plan query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow:
    FIELDS = ("ordinal", "resource", "row_id", "peer_id", "registry_id", "entry_id", "package_id", "source_state", "action", "status", "priority", "observed_archive_address", "desired_archive_address", "requires_confirmation", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, peer_id: str, registry_id: str, entry_id: str, package_id: str, source_state: str, action: str, status: str, priority: str, observed_archive_address: str, desired_archive_address: str, requires_confirmation: bool, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "plan query row ordinal", MAX_QUERY_ITEMS)
        self.resource = _label(resource, "plan query row resource")
        self.row_id = _label(row_id, "plan query row ID")
        self.peer_id = _label(peer_id, "plan query row peer ID", required=False)
        self.registry_id = _label(registry_id, "plan query row registry ID", required=False)
        self.entry_id = _label(entry_id, "plan query row entry ID", required=False)
        self.package_id = _label(package_id, "plan query row package ID", required=False)
        self.source_state = _label(source_state, "plan query row source state")
        self.action = _label(action, "plan query row action", required=False)
        self.status = _label(status, "plan query row status", required=False)
        self.priority = _label(priority, "plan query row priority", required=False)
        self.observed_archive_address = _address(observed_archive_address, "plan query row observed address", plan_model.federation_model.registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.desired_archive_address = _address(desired_archive_address, "plan query row desired address", plan_model.federation_model.registry_model.archive_model.ARCHIVE_PREFIX, required=False)
        self.requires_confirmation = _bool(requires_confirmation, "plan query row confirmation")
        self.evidence_addresses = tuple(_text(item, "plan query row evidence", 2048) for item in _sequence(evidence_addresses, "plan query row evidence", plan_model.resolution_model.MAX_PEERS + 4))
        self.content_address = _address(content_address, "plan query row address", ROW_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "plan query row address")
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES or self.source_state not in plan_model.resolution_model.STATES + ("ready",) or self.action and self.action not in plan_model.ACTIONS or self.status and self.status not in plan_model.STATUSES or self.priority and self.priority not in plan_model.PRIORITIES or not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("plan query row vocabulary is invalid")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("plan query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow":
        value = _mapping(value, "plan query row")
        _strict(value, set(cls.FIELDS), "plan query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult:
    FIELDS = ("query", "plan_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery, plan_id: str, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        self.query = query if isinstance(query, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery.from_mapping(query)
        self.plan_id = _label(plan_id, "plan query result plan ID")
        self.rows = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow.from_mapping(item) for item in _sequence(rows, "plan query result rows", MAX_QUERY_ITEMS))
        self.total_count = _count(total_count, "plan query total count", MAX_QUERY_ITEMS)
        self.matched_count = _count(matched_count, "plan query matched count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "plan query returned count", MAX_QUERY_ITEMS)
        self.next_offset = _count(next_offset, "plan query next offset", MAX_QUERY_ITEMS)
        self.truncated = _bool(truncated, "plan query truncation")
        self.content_address = _address(content_address, "plan query result address", RESULT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "plan query result address")
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.matched_count or self.next_offset != self.query.offset + self.returned_count:
            raise ValidationError("plan query result counters are not conserved")
        if self.rows and tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)):
            raise ValidationError("plan query result ordinals do not replay")
        if self.truncated != (self.next_offset < self.query.offset + self.matched_count):
            raise ValidationError("plan query truncation does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("plan query result crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("plan query result address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "plan_id": self.plan_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("plan_id", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult":
        value = _mapping(value, "plan query result")
        _strict(value, set(cls.FIELDS), "plan query result")
        return cls(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery.from_mapping(value["query"]), value["plan_id"], tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow.from_mapping(item) for item in _sequence(value["rows"], "plan query result rows", MAX_QUERY_ITEMS)), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, row_id: str, operation: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationOperation | None, value: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow:
    if operation is None:
        body = {"ordinal": ordinal, "resource": resource, "row_id": row_id, "peer_id": "", "registry_id": "", "entry_id": "", "package_id": "", "source_state": "ready", "action": "", "status": "", "priority": "none", "observed_archive_address": "", "desired_archive_address": "", "requires_confirmation": False, "evidence_addresses": (value.content_address,)}
    else:
        body = {"ordinal": ordinal, "resource": resource, "row_id": row_id, "peer_id": operation.peer_id, "registry_id": operation.registry_id, "entry_id": operation.entry_id, "package_id": operation.package_id, "source_state": operation.source_state, "action": operation.action, "status": operation.status, "priority": operation.priority, "observed_archive_address": operation.observed_archive_address, "desired_archive_address": operation.desired_archive_address, "requires_confirmation": operation.requires_confirmation, "evidence_addresses": operation.evidence_addresses}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow(**body, content_address=ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow(**body, content_address=address_row(provisional))


def _all_rows(value: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow, ...]:
    rows: list[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow] = []
    ordinal = 1
    selected = tuple(resources)
    if "summary" in selected:
        rows.append(_row(ordinal, "summary", value.plan_id, None, value))
        ordinal += 1
    for operation in value.operations:
        categories = ("operations", operation.action, operation.status)
        if any(resource in selected for resource in categories):
            resource = "operations" if "operations" in selected else next(resource for resource in categories if resource in selected)
            rows.append(_row(ordinal, resource, f"{operation.peer_id}-{operation.entry_id}", operation, value))
            ordinal += 1
    return tuple(rows)


def _matches(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow, query: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery) -> bool:
    if query.peer_id and row.peer_id != query.peer_id or query.entry_id and row.entry_id != query.entry_id or query.state and row.source_state != query.state or query.action and row.action != query.action or query.status and row.status != query.status or query.priority and row.priority != query.priority or query.registry_id and row.registry_id != query.registry_id or query.package_id and row.package_id != query.package_id:
        return False
    if query.text:
        haystack = " ".join((row.row_id, row.peer_id, row.registry_id, row.entry_id, row.package_id, row.source_state, row.action, row.status, row.priority, row.observed_archive_address, row.desired_archive_address)).lower()
        if query.text.lower() not in haystack:
            return False
    return True


def _reordinal(row: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow, ordinal: int) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow:
    body = row.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow.from_mapping(body)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow.from_mapping(provisional.to_dict() | {"content_address": address_row(provisional)})


def query_plan(value: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan, *, query_id: str = "consensus-certificate-observatory-archive-registry-federation-reconciliation-plan-query", resources: Sequence[str] = ("summary", "operations"), peer_id: str = "", entry_id: str = "", state: str = "", action: str = "", status: str = "", priority: str = "", registry_id: str = "", package_id: str = "", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult:
    value = plan_model.verify_plan(value)
    provisional_query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery(query_id, value.content_address, resources, peer_id, entry_id, state, action, status, priority, registry_id, package_id, text, offset, limit, QUERY_PREFIX + ":pending")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery(provisional_query.query_id, provisional_query.plan_address, provisional_query.resources, provisional_query.peer_id, provisional_query.entry_id, provisional_query.state, provisional_query.action, provisional_query.status, provisional_query.priority, provisional_query.registry_id, provisional_query.package_id, provisional_query.text, provisional_query.offset, provisional_query.limit, address_query(provisional_query))
    rows = _all_rows(value, query.resources)
    matched = tuple(row for row in rows if _matches(row, query))
    page = tuple(_reordinal(row, query.offset + index + 1) for index, row in enumerate(matched[query.offset:query.offset + query.limit]))
    next_offset = query.offset + len(page)
    provisional_result = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult(query, value.plan_id, page, len(rows), len(matched), len(page), next_offset, next_offset < query.offset + len(matched), RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult(query, provisional_result.plan_id, provisional_result.rows, provisional_result.total_count, provisional_result.matched_count, provisional_result.returned_count, provisional_result.next_offset, provisional_result.truncated, address_result(provisional_result))


def query_plan_from_mapping(value: Mapping[str, Any], **kwargs: Any) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult:
    return query_plan(plan_model.plan_from_mapping(value), **kwargs)


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult:
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult.from_mapping(value)


def verify_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("plan query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("plan query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult) -> str:
    value = verify_query_result(value)
    fields = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow.FIELDS
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        row = item.to_dict()
        for field in fields:
            if isinstance(row[field], tuple):
                row[field] = ",".join(row[field])
        writer.writerow(row)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Archive Registry Federation Reconciliation Plan Query", "", f"- Plan: `{value.plan_id}`", f"- Returned: `{value.returned_count}/{value.matched_count}`", f"- Next offset: `{value.next_offset}`", "", "| # | resource | peer | entry | action | status |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.peer_id}` | `{item.entry_id}` | `{item.action}` | `{item.status}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "plan_address": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "peer_id": {"type": "string"}, "entry_id": {"type": "string"}, "state": {"enum": [""] + list(plan_model.resolution_model.STATES)}, "action": {"enum": [""] + list(plan_model.ACTIONS)}, "status": {"enum": [""] + list(plan_model.STATUSES)}, "priority": {"enum": [""] + list(plan_model.PRIORITIES)}, "registry_id": {"type": "string"}, "package_id": {"type": "string"}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "row_id": {"type": "string"}, "peer_id": {"type": "string"}, "registry_id": {"type": "string"}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "source_state": {"enum": list(plan_model.resolution_model.STATES) + ["ready"]}, "action": {"type": "string"}, "status": {"type": "string"}, "priority": {"type": "string"}, "observed_archive_address": {"type": "string"}, "desired_archive_address": {"type": "string"}, "requires_confirmation": {"type": "boolean"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult.FIELDS), "properties": {"query": query_schema(), "plan_id": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "operations": ("query_plan", "query_plan_from_mapping", "query_from_mapping", "query_json", "query_csv", "render_query_markdown", "verify_query_result"), "resources": RESOURCES, "max_items": MAX_QUERY_ITEMS}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQuery", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryResult", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanQueryRow", "address_query", "address_result", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_plan", "query_plan_from_mapping", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_query", "verify_query_result"]
