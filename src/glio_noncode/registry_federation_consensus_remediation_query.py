"""Bounded query projections for consensus remediation plans."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_remediation as remediation_model
from . import registry_federation_consensus as consensus_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = remediation_model.VERSION + "-query-v1"
BOUNDARY = remediation_model.BOUNDARY + "_query"
QUERY_PREFIX = registry_model.REGISTRY_PREFIX + "-consensus-remediation-query"
ROW_PREFIX = registry_model.REGISTRY_PREFIX + "-consensus-remediation-query-row"
RESULT_PREFIX = registry_model.REGISTRY_PREFIX + "-consensus-remediation-query-result"
RESOURCES = ("summary", "steps", "evidence", "required", "recommended", "all")
DEFAULT_RESOURCES = ("summary", "steps")
MAX_ROWS = 1 + remediation_model.MAX_STEPS * 2 + remediation_model.MAX_STEPS * consensus_model.MAX_PEERS * 4
CHECK_IDS = ("exact-fields", "public-boundary", "resource-conservation", "filter-conservation", "row-conservation", "ordinal-conservation", "pagination-conservation", "address-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _labels(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(values))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(values))


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusRemediationQuery:
    FIELDS = ("query_id", "remediation_address", "resources", "package_id", "status", "kind", "severity", "offset", "limit", "content_address")

    def __init__(self, query_id: str, remediation_address: str, resources: Sequence[str], package_id: str, status: str, kind: str, severity: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "remediation query ID")
        self.remediation_address = _address(remediation_address, "query remediation address", remediation_model.REMEDIATION_PREFIX)
        values = tuple(resources)
        if not values or any(item not in RESOURCES for item in values) or len(set(values)) != len(values) or "all" in values and len(values) != 1:
            raise ValidationError("remediation query resources are unsupported")
        self.resources = tuple(RESOURCES[:-1] if "all" in values else values)
        self.package_id = "" if package_id == "" else _label(package_id, "query package ID")
        self.status = "" if status == "" else _label(status, "query status")
        self.kind = "" if kind == "" else _label(kind, "query kind")
        self.severity = "" if severity == "" else _label(severity, "query severity")
        if self.status and self.status not in remediation_model.STATUSES or self.severity and self.severity not in consensus_model.SEVERITIES:
            raise ValidationError("remediation query filter is unsupported")
        self.offset = _count(offset, "query offset", MAX_ROWS)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_ROWS:
            raise ValidationError("query limit is outside its bound")
        self.limit = limit
        self.content_address = _address(content_address, "query content address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("remediation query content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("remediation query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query_id": self.query_id, "remediation_address": self.remediation_address, "resources": self.resources, "package_id": self.package_id, "status": self.status, "kind": self.kind, "severity": self.severity, "offset": self.offset, "limit": self.limit, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusRemediationQuery:
        value = _mapping(value, "remediation query")
        _strict(value, set(cls.FIELDS), "remediation query")
        return cls(value["query_id"], value["remediation_address"], value["resources"], value["package_id"], value["status"], value["kind"], value["severity"], value["offset"], value["limit"], value["content_address"])


def address_query(value: RegistryFederationConsensusRemediationQuery) -> str:
    if not isinstance(value, RegistryFederationConsensusRemediationQuery):
        raise ValidationError("remediation query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusRemediationQueryRow:
    FIELDS = ("ordinal", "resource", "row_id", "package_id", "action_id", "kind", "severity", "status", "peer_ids", "evidence_addresses", "detail", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, package_id: str, action_id: str, kind: str, severity: str, status: str, peer_ids: Sequence[str], evidence_addresses: Sequence[str], detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "query row ordinal", MAX_ROWS)
        if self.ordinal < 1:
            raise ValidationError("query row ordinal must be positive")
        self.resource = _label(resource, "query row resource")
        if self.resource not in RESOURCES[:-1]:
            raise ValidationError("query row resource is unsupported")
        self.row_id = _label(row_id, "query row ID")
        self.package_id = "" if package_id == "" else _label(package_id, "query row package ID")
        self.action_id = "" if action_id == "" else _label(action_id, "query row action ID")
        self.kind = "" if kind == "" else _label(kind, "query row kind")
        self.severity = "" if severity == "" else _label(severity, "query row severity")
        self.status = "" if status == "" else _label(status, "query row status")
        self.peer_ids = _labels(peer_ids, "query row peer IDs", consensus_model.MAX_PEERS)
        self.evidence_addresses = _addresses(evidence_addresses, "query row evidence addresses", 32)
        self.detail = _text(detail, "query row detail", 4096, required=True)
        self.content_address = _address(content_address, "query row content address", ROW_PREFIX)
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("query row content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "resource": self.resource, "row_id": self.row_id, "package_id": self.package_id, "action_id": self.action_id, "kind": self.kind, "severity": self.severity, "status": self.status, "peer_ids": self.peer_ids, "evidence_addresses": self.evidence_addresses, "detail": self.detail, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusRemediationQueryRow:
        value = _mapping(value, "remediation query row")
        _strict(value, set(cls.FIELDS), "remediation query row")
        return cls(value["ordinal"], value["resource"], value["row_id"], value["package_id"], value["action_id"], value["kind"], value["severity"], value["status"], value["peer_ids"], value["evidence_addresses"], value["detail"], value["content_address"])


def address_row(value: RegistryFederationConsensusRemediationQueryRow) -> str:
    if not isinstance(value, RegistryFederationConsensusRemediationQueryRow):
        raise ValidationError("remediation query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusRemediationQueryResult:
    FIELDS = ("query", "remediation_id", "consensus_address", "ready", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusRemediationQuery, remediation_id: str, consensus_address: str, ready: bool, rows: Sequence[RegistryFederationConsensusRemediationQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        if not isinstance(query, RegistryFederationConsensusRemediationQuery):
            raise ValidationError("remediation query result query must be typed")
        self.query = query
        self.remediation_id = _label(remediation_id, "query result remediation ID")
        self.consensus_address = _address(consensus_address, "query result consensus address", consensus_model.CONSENSUS_PREFIX)
        self.ready = _bool(ready, "query result readiness")
        self.rows = tuple(rows)
        self.total_count = _count(total_count, "query result total count", MAX_ROWS)
        self.matched_count = _count(matched_count, "query result matched count", self.total_count)
        self.returned_count = _count(returned_count, "query result returned count", self.matched_count)
        self.next_offset = _count(next_offset, "query result next offset", MAX_ROWS + 1)
        self.truncated = _bool(truncated, "query result truncation")
        self.content_address = _address(content_address, "query result content address", RESULT_PREFIX)
        if self.query.remediation_address.startswith(remediation_model.REMEDIATION_PREFIX + ":") is False or len(self.rows) != self.returned_count or tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)) or self.returned_count > self.matched_count or self.next_offset != (self.query.offset + self.returned_count if self.truncated else 0) or self.truncated != (self.next_offset > 0):
            raise ValidationError("query result counters are not conserved")
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("query result content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("query result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "remediation_id": self.remediation_id, "consensus_address": self.consensus_address, "ready": self.ready, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"query", "rows"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusRemediationQueryResult:
        value = _mapping(value, "remediation query result")
        _strict(value, set(cls.FIELDS), "remediation query result")
        return cls(RegistryFederationConsensusRemediationQuery.from_mapping(value["query"]), value["remediation_id"], value["consensus_address"], value["ready"], tuple(RegistryFederationConsensusRemediationQueryRow.from_mapping(item) for item in value["rows"]), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusRemediationQueryResult) -> str:
    if not isinstance(value, RegistryFederationConsensusRemediationQueryResult):
        raise ValidationError("remediation query result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def build_query(value: remediation_model.RegistryFederationConsensusRemediation, *, query_id: str = "remediation-query", resources: Sequence[str] = DEFAULT_RESOURCES, package_id: str = "", status: str = "", kind: str = "", severity: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationConsensusRemediationQuery:
    value = remediation_model.verify_remediation(value)
    provisional = RegistryFederationConsensusRemediationQuery(query_id, value.content_address, resources, package_id, status, kind, severity, offset, limit, QUERY_PREFIX + ":pending")
    return RegistryFederationConsensusRemediationQuery(provisional.query_id, provisional.remediation_address, provisional.resources, provisional.package_id, provisional.status, provisional.kind, provisional.severity, provisional.offset, provisional.limit, address_query(provisional))


def _matches(row: RegistryFederationConsensusRemediationQueryRow, query: RegistryFederationConsensusRemediationQuery) -> bool:
    return (not query.package_id or row.package_id == query.package_id) and (not query.status or row.status == query.status) and (not query.kind or row.kind == query.kind) and (not query.severity or row.severity == query.severity)


def _rows(value: remediation_model.RegistryFederationConsensusRemediation, query: RegistryFederationConsensusRemediationQuery) -> tuple[RegistryFederationConsensusRemediationQueryRow, ...]:
    rows: list[RegistryFederationConsensusRemediationQueryRow] = []
    resources = set(query.resources)
    if "summary" in resources:
        provisional = RegistryFederationConsensusRemediationQueryRow(1, "summary", "remediation-summary", "", "", "summary", "blocking" if value.blocking_count else "review", "required" if value.blocking_count else "recommended", (), (value.content_address,), f"{value.step_count} remediation steps; {value.blocking_count} required; ready={value.ready}", ROW_PREFIX + ":pending")
        rows.append(RegistryFederationConsensusRemediationQueryRow(1, provisional.resource, provisional.row_id, provisional.package_id, provisional.action_id, provisional.kind, provisional.severity, provisional.status, provisional.peer_ids, provisional.evidence_addresses, provisional.detail, address_row(provisional)))
    if "steps" in resources or "required" in resources or "recommended" in resources:
        status_resources = {status for status in ("required", "recommended") if status in resources}
        for step in value.steps:
            if status_resources and step.status not in status_resources:
                continue
            provisional = RegistryFederationConsensusRemediationQueryRow(len(rows) + 1, "steps", f"step-{step.ordinal}", step.package_id, step.action_id, step.kind, step.severity, step.status, step.peer_ids, step.evidence_addresses, step.instruction, ROW_PREFIX + ":pending")
            rows.append(RegistryFederationConsensusRemediationQueryRow(provisional.ordinal, provisional.resource, provisional.row_id, provisional.package_id, provisional.action_id, provisional.kind, provisional.severity, provisional.status, provisional.peer_ids, provisional.evidence_addresses, provisional.detail, address_row(provisional)))
    if "evidence" in resources:
        addresses = sorted({address for step in value.steps for address in step.evidence_addresses})
        for address in addresses:
            provisional = RegistryFederationConsensusRemediationQueryRow(len(rows) + 1, "evidence", f"evidence-{len(rows) + 1}", "", "", "evidence", "", "", (), (address,), address, ROW_PREFIX + ":pending")
            rows.append(RegistryFederationConsensusRemediationQueryRow(provisional.ordinal, provisional.resource, provisional.row_id, provisional.package_id, provisional.action_id, provisional.kind, provisional.severity, provisional.status, provisional.peer_ids, provisional.evidence_addresses, provisional.detail, address_row(provisional)))
    return tuple(row for row in rows if _matches(row, query))


def query_remediation(value: remediation_model.RegistryFederationConsensusRemediation, *, resources: Sequence[str] = DEFAULT_RESOURCES, package_id: str = "", status: str = "", kind: str = "", severity: str = "", offset: int = 0, limit: int = 100, query_id: str = "remediation-query") -> RegistryFederationConsensusRemediationQueryResult:
    value = remediation_model.verify_remediation(value)
    query = build_query(value, query_id=query_id, resources=resources, package_id=package_id, status=status, kind=kind, severity=severity, offset=offset, limit=limit)
    all_rows = _rows(value, query)
    start, stop = query.offset, query.offset + query.limit
    selected = all_rows[start:stop]
    normalized = tuple(RegistryFederationConsensusRemediationQueryRow(index + 1, row.resource, row.row_id, row.package_id, row.action_id, row.kind, row.severity, row.status, row.peer_ids, row.evidence_addresses, row.detail, ROW_PREFIX + ":pending") for index, row in enumerate(selected))
    rows = tuple(RegistryFederationConsensusRemediationQueryRow(row.ordinal, row.resource, row.row_id, row.package_id, row.action_id, row.kind, row.severity, row.status, row.peer_ids, row.evidence_addresses, row.detail, address_row(row)) for row in normalized)
    truncated = stop < len(all_rows)
    provisional = RegistryFederationConsensusRemediationQueryResult(query, value.remediation_id, value.consensus_address, value.ready, rows, len(_rows(value, build_query(value, resources=RESOURCES[:-1], package_id=package_id, status=status, kind=kind, severity=severity, offset=0, limit=MAX_ROWS))), len(all_rows), len(rows), query.offset + len(rows) if truncated else 0, truncated, RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusRemediationQueryResult(provisional.query, provisional.remediation_id, provisional.consensus_address, provisional.ready, provisional.rows, provisional.total_count, provisional.matched_count, provisional.returned_count, provisional.next_offset, provisional.truncated, address_result(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusRemediationQueryResult:
    return verify_query_result(RegistryFederationConsensusRemediationQueryResult.from_mapping(value))


def verify_query_result(value: RegistryFederationConsensusRemediationQueryResult) -> RegistryFederationConsensusRemediationQueryResult:
    if not isinstance(value, RegistryFederationConsensusRemediationQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("remediation query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusRemediationQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusRemediationQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusRemediationQueryRow.FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        record = row.to_dict()
        record["peer_ids"] = "|".join(row.peer_ids)
        record["evidence_addresses"] = "|".join(row.evidence_addresses)
        writer.writerow(record)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusRemediationQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Consensus Remediation Query", "", f"- Remediation: `{value.remediation_id}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", "", "| resource | row | package | action | status | detail |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{row.resource}` | `{row.row_id}` | `{row.package_id}` | `{row.action_id}` | `{row.status}` | {row.detail} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusRemediationQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "remediation_address": {"type": "string"}, "resources": {"type": "array"}, "package_id": {"type": "string"}, "status": {"type": "string"}, "kind": {"type": "string"}, "severity": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}, "content_address": {"type": "string"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusRemediationQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer"}, "resource": {"type": "string"}, "row_id": {"type": "string"}, "package_id": {"type": "string"}, "action_id": {"type": "string"}, "kind": {"type": "string"}, "severity": {"type": "string"}, "status": {"type": "string"}, "peer_ids": {"type": "array"}, "evidence_addresses": {"type": "array"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusRemediationQueryResult.FIELDS), "properties": {"query": query_schema(), "remediation_id": {"type": "string"}, "consensus_address": {"type": "string"}, "ready": {"type": "boolean"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer"}, "matched_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "next_offset": {"type": "integer"}, "truncated": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "result_prefix": RESULT_PREFIX, "resources": RESOURCES, "check_ids": CHECK_IDS, "limits": {"max_rows": MAX_ROWS}, "features": ("bounded remediation step projection", "required and recommended filters", "package and action filters", "evidence-address view", "deterministic pagination", "JSON CSV and Markdown exports"), "schemas": ("query", "row", "result")}


__all__ = ["BOUNDARY", "CHECK_IDS", "DEFAULT_RESOURCES", "MAX_ROWS", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "RegistryFederationConsensusRemediationQuery", "RegistryFederationConsensusRemediationQueryResult", "RegistryFederationConsensusRemediationQueryRow", "VERSION", "address_query", "address_result", "address_row", "build_query", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_remediation", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_query_result"]
